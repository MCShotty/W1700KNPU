#!/usr/bin/env python3
"""Link the unpromoted mt76/NPU candidates against the prepared target kernel."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]
PREPARED = ROOT / '.local/npu-rx-parser/kernel-after-1/mt76-2026.09.01~be5ce791'
BUILD = ROOT / '.local/npu-linked-modules'
OUT = ROOT / 'research/checkpoints/2026-09-23-npu-linked-modules'
KERNEL = ROOT / '.build/openwrt/build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/linux-6.18.44'
STAGING = ROOT / '.build/openwrt/staging_dir/target-aarch64_cortex-a53_musl'
MODULE_DIR = STAGING / 'root-airoha/lib/modules/6.18.44'
PARSER = ROOT / 'research/checkpoints/2026-09-23-npu-rx-parser/rx-parser.json'
RX = ROOT / 'research/checkpoints/2026-09-16-npu-rx-ownership/rx-ownership.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    return str(path.relative_to(ROOT))


def exports_from_installed_modules(index):
    built_in = {parts[1] for line in (KERNEL / 'Module.symvers').read_text().splitlines()
                if (parts := line.split('\t')) and len(parts) >= 2}
    assert {'airoha_npu_get', 'airoha_npu_put'} <= built_in
    entries, installed = {}, []
    for module in ('mac80211', 'cfg80211', 'compat'):
        path = MODULE_DIR / (module + '.ko')
        elf = ELFFile(io.BytesIO(path.read_bytes()))
        assert elf['e_machine'] == 'EM_AARCH64' and elf['e_type'] == 'ET_REL'
        assert b'vermagic=6.18.44 SMP mod_unload aarch64' in elf.get_section_by_name('.modinfo').data().split(b'\0')
        strings = elf.get_section_by_name('__ksymtab_strings').data()
        symbols = {symbol.name: symbol for symbol in elf.get_section_by_name('.symtab').iter_symbols()}
        count = 0
        for name, symbol in symbols.items():
            if not name.startswith('__ksymtab_') or name == '__ksymtab_strings':
                continue
            exported = name.removeprefix('__ksymtab_')
            section = elf.get_section(symbol['st_shndx']).name
            assert section in {'__ksymtab', '__ksymtab_gpl'}, (module, name, section)
            assert exported not in entries and exported not in built_in, exported
            ns = symbols.get('__kstrtabns_' + exported)
            assert ns is not None, exported
            pos = ns['st_value']
            namespace = strings[pos:strings.index(b'\0', pos)].decode()
            entries[exported] = (module, 'EXPORT_SYMBOL_GPL' if section.endswith('_gpl') else 'EXPORT_SYMBOL', namespace)
            count += 1
        installed.append(dict(path=relative(path), sha256=sha(path), exports=count,
                              vermagic='6.18.44 SMP mod_unload aarch64'))
    assert 'ieee80211_sta_register_airtime' in entries
    index.write_text(''.join(f'0x00000000\t{name}\t{module}\t{kind}\t{namespace}\n'
                             for name, (module, kind, namespace) in sorted(entries.items())))
    return installed, len(entries)


def parse_module(path):
    elf = ELFFile(io.BytesIO(path.read_bytes()))
    assert elf['e_machine'] == 'EM_AARCH64' and elf['e_type'] == 'ET_REL'
    info = elf.get_section_by_name('.modinfo').data().split(b'\0')
    assert b'vermagic=6.18.44 SMP mod_unload aarch64' in info
    symbols = elf.get_section_by_name('.symtab')
    defined = {s.name for s in symbols.iter_symbols() if s['st_shndx'] != 'SHN_UNDEF'}
    undefined = {s.name for s in symbols.iter_symbols() if s['st_shndx'] == 'SHN_UNDEF'}
    return (dict(path=relative(path), sha256=sha(path), bytes=path.stat().st_size,
                 vermagic='6.18.44 SMP mod_unload aarch64',
                 depends=next((s.decode().removeprefix('depends=') for s in info if s.startswith(b'depends=')), ''),
                 defined_symbols=len(defined), undefined_symbols=len(undefined)),
            defined, undefined)


def main():
    options = argparse.ArgumentParser()
    options.add_argument('--build-name', default='verified', help='New directory name beneath ignored .local/npu-linked-modules')
    args = options.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,31}', args.build_name)
    dest = BUILD / args.build_name / PREPARED.name
    assert dest.resolve().is_relative_to(BUILD.resolve()) and not dest.exists()
    parser = json.loads(PARSER.read_text())
    rx = json.loads(RX.read_text())
    npu_expected = rx['derived'][relative(ROOT / '.local/npu-rx-ownership/kernel-after-1' / PREPARED.name / 'npu.c')]
    mac_expected = parser['derived'][relative(ROOT / '.local/npu-rx-parser/kernel-after-1' / PREPARED.name / 'mt7996/mac.c')]
    assert sha(PREPARED / 'npu.c') == npu_expected and sha(PREPARED / 'mt7996/mac.c') == mac_expected
    dest.parent.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PREPARED, dest, ignore=shutil.ignore_patterns(
        '*.o', '*.ko', '*.cmd', '*.d', '*.mod', '*.mod.c', 'Module.symvers', 'modules.order', '*.symversions'))
    assert sha(dest / 'npu.c') == npu_expected and sha(dest / 'mt7996/mac.c') == mac_expected
    index = dest.parent / 'dependency-exports.symvers'
    installed, count = exports_from_installed_modules(index)
    row = next(item for item in parser['kernel_objects'] if item['phase'] == 'after' and item['npu_enabled'] == 1)
    command = [piece.replace(str(PREPARED), str(dest)) for piece in row['command'] if not piece.endswith('.o')]
    command += ['KBUILD_EXTRA_SYMBOLS=' + str(index), 'modules']
    prefix = next(piece.split('=', 1)[1] for piece in command if piece.startswith('CROSS_COMPILE='))
    env = dict(os.environ, STAGING_DIR=str(STAGING),
               PATH=str(Path(prefix).parent) + ':' + str(STAGING.parent / 'host/bin') + ':/usr/bin:/bin')
    done = subprocess.run(command, capture_output=True, text=True, env=env, timeout=600)
    log = OUT / 'linked-module-build.log'
    log.write_text(done.stdout + done.stderr)
    assert done.returncode == 0, (done.stderr or done.stdout)[-6000:]
    warnings_allowed = {
        'WARNING: modpost: missing MODULE_DESCRIPTION() in mt76.o',
        'WARNING: modpost: missing MODULE_DESCRIPTION() in mt76-connac-lib.o',
        'WARNING: modpost: missing MODULE_DESCRIPTION() in mt7996/mt7996e.o',
    }
    warnings = {line for line in log.read_text().splitlines() if re.search(r'\b(?:warning|error):', line, re.I)}
    assert warnings <= warnings_allowed, warnings
    modules, graph = [], {}
    for name in ('mt76.ko', 'mt76-connac-lib.ko', 'mt7996/mt7996e.ko'):
        data, defined, undefined = parse_module(dest / name)
        modules.append(data)
        graph[name] = (defined, undefined)
    assert any(name.startswith('mt76_npu_rx_poll') for name in graph['mt76.ko'][0])
    assert any(name.startswith('mt7996_mac_fill_rx') for name in graph['mt7996/mt7996e.ko'][0])
    assert {'airoha_npu_get', 'airoha_npu_put'} <= graph['mt76.ko'][1]
    npu_imports = {s for s in graph['mt7996/mt7996e.ko'][1] if s.startswith('mt76_npu_')}
    assert npu_imports and npu_imports <= graph['mt76.ko'][0]
    result = dict(schema=1, inputs=dict(runner=sha(Path(__file__)), parser_receipt=sha(PARSER), rx_receipt=sha(RX),
                                        npu_source=npu_expected, mac_source=mac_expected,
                                        kernel_config=sha(KERNEL / '.config'), kernel_symvers=sha(KERNEL / 'Module.symvers'),
                                        generated_exports=sha(index)),
                  dependencies=installed, export_count=count, command=command,
                  build_log=relative(log), build_log_sha256=sha(log),
                  metadata_warnings=sorted(warnings), modules=modules,
                  link_graph=dict(mt7996e_to_mt76=sorted(npu_imports),
                                  mt76_to_builtin_provider=['airoha_npu_get', 'airoha_npu_put']),
                  limits=['Original mac80211 Module.symvers is absent; this name/license/namespace index is reconstructed from installed ELF exports with CONFIG_MODVERSIONS disabled.',
                          'Target kernel provider is built in and does not contain unpromoted provider candidates 928/929.',
                          'Link success does not prove loading, physical DMA behavior, safe whole-device teardown/recovery or stock parity.'])
    receipt = OUT / 'linked-modules.json'
    receipt.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(receipt_sha256=sha(receipt), modules=[row['path'] for row in modules],
                          export_count=count, warnings=len(warnings), npu_link_imports=len(npu_imports))))


if __name__ == '__main__':
    main()
