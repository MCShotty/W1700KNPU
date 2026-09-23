#!/usr/bin/env python3
"""Relink an isolated prepared kernel with provider candidates 928 and 929."""
import argparse
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
import test_npu_linked_modules as modules

ROOT, KERNEL = modules.ROOT, modules.KERNEL
BUILD = ROOT / '.local/npu-provider-kernel-link'
OUT = ROOT / 'research/checkpoints/2026-09-23-npu-provider-kernel-link'
LIFETIME = ROOT / 'research/checkpoints/2026-09-16-npu-host-lifetime/host-lifetime.json'
LINKED = modules.OUT / 'linked-modules.json'
PROVIDER = 'drivers/net/ethernet/airoha/airoha_npu.c'
HEADER = 'include/linux/soc/airoha/airoha_offload.h'
sha, relative = modules.sha, modules.relative


def record(path):
    return dict(path=relative(path), sha256=sha(path), bytes=path.stat().st_size)


def symbols(path, elf_type):
    elf = ELFFile(io.BytesIO(path.read_bytes()))
    assert elf['e_machine'] == 'EM_AARCH64' and elf['e_type'] == elf_type
    table = elf.get_section_by_name('.symtab')
    return {s.name: dict(address=s['st_value'], size=s['st_size'])
            for s in table.iter_symbols() if s['st_shndx'] != 'SHN_UNDEF'}


def run(command, log, env, timeout=1800):
    with log.open('w') as stream:
        done = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                              env=env, stdin=subprocess.DEVNULL, timeout=timeout)
    assert done.returncode == 0, log.read_text()[-6000:]
    return dict(command=command, **record(log))


def main():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-name', default='verified')
    parser.add_argument('--jobs', type=int, default=8)
    parser.add_argument('--resume-build', action='store_true',
                        help='Recheck and rebuild an existing isolated copy after an interrupted attempt')
    parser.add_argument('--output-dir', type=Path, default=OUT,
                        help='Fresh receipt directory; use an ignored .local path for replay')
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,31}', args.build_name)
    assert 1 <= args.jobs <= 16
    dest = BUILD / args.build_name
    assert dest.resolve().is_relative_to(BUILD.resolve()) and not dest.is_symlink()
    assert dest.is_dir() if args.resume_build else not dest.exists()
    default_out = OUT.resolve()
    OUT = args.output_dir.resolve()
    assert OUT == default_out or OUT.is_relative_to((ROOT / '.local').resolve())
    assert not (OUT / 'provider-kernel-link.json').exists()
    assert sha(LIFETIME) == '685a40fffe2f6e690784ae503b9a5b68717912dd5fc8730aa6b65d86d390e45f'
    assert sha(LINKED) == '196e783e84c098068f504e49dd816bf1709f2145f02593dc5a216d28506dfe03'
    lifetime, linked = json.loads(LIFETIME.read_text()), json.loads(LINKED.read_text())
    for name in (PROVIDER, HEADER):
        assert sha(KERNEL / name) == lifetime['inputs_before_after'][relative(KERNEL / name)]
    protected = [Path(__file__), Path(modules.__file__), LIFETIME, LINKED,
                 ROOT / 'firmware/source-lock.json', ROOT / 'firmware/patches/openwrt.patch',
                 ROOT / 'firmware/build.config', modules.STAGING.parent.parent / '.config']
    protected += [KERNEL / name for name in (PROVIDER, HEADER, '.config', 'Module.symvers',
                 'vmlinux', 'include/generated/autoconf.h', 'include/generated/utsrelease.h',
                 'include/linux/devm-helpers.h', 'drivers/net/ethernet/airoha/airoha_npu.o')]
    before = {relative(p): sha(p) for p in protected}
    config = (KERNEL / '.config').read_text()
    assert 'CONFIG_NET_AIROHA_NPU=y\n' in config and '# CONFIG_MODVERSIONS is not set\n' in config
    assert 'CONFIG_INITRAMFS_SOURCE=""\n' in config
    assert 'CONFIG_RELOCATABLE=y\n' in config
    assert 'CONFIG_MODULE_STRIPPED=y\n' in config
    symlinks = {}
    for base, dirs, files in os.walk(KERNEL, followlinks=False):
        for name in dirs + files:
            path = Path(base) / name
            if path.is_symlink():
                target = os.readlink(path)
                assert not os.path.isabs(target) and path.resolve().is_relative_to(KERNEL.resolve()), path
                symlinks[str(path.relative_to(KERNEL))] = target
    dest.mkdir(parents=True, exist_ok=args.resume_build)
    OUT.mkdir(parents=True, exist_ok=True)
    target = dest / KERNEL.name
    if not args.resume_build:
        print('Copying prepared kernel with independent files and preserved symlinks.', flush=True)
        shutil.copytree(KERNEL, target, symlinks=True)
    else:
        assert target.is_dir() and not target.is_symlink()
        assert sha(target / '.config') == sha(KERNEL / '.config')
        for name, expected in symlinks.items():
            assert (target / name).is_symlink() and os.readlink(target / name) == expected
    assert (target / PROVIDER).stat().st_ino != (KERNEL / PROVIDER).stat().st_ino
    patches = [ROOT / 'research/checkpoints/2026-09-14-npu-control-v2/928-net-airoha-npu-bidirectional-control.patch',
               ROOT / 'research/checkpoints/2026-09-16-npu-host-lifetime/929-net-airoha-npu-irq-work-lifetime.patch']
    patch_rows = []
    for patch in patches:
        assert sha(patch) == lifetime['inputs_before_after'].get(relative(patch),
            next((p['sha256'] for p in lifetime['patches'] if p['path'] == relative(patch)), None))
        application = 'Existing copy; patched provider and header verified against the lifetime receipt.'
        if not args.resume_build:
            done = subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)],
                                  cwd=target, capture_output=True, text=True, timeout=30)
            assert done.returncode == 0 and 'offset' not in done.stdout and 'fuzz' not in done.stdout, done.stdout + done.stderr
            application = done.stdout
        patch_rows.append(dict(**record(patch), application=application))
    for name, staged in ((PROVIDER, 'airoha_npu.c'), (HEADER, 'public.h')):
        expected = lifetime['derived']['.local/npu-host-lifetime/kernel-provider-after/' + staged]
        assert sha(target / name) == expected
    toolchain = modules.STAGING.parent / 'toolchain-aarch64_cortex-a53_gcc-14.4.0_musl'
    prefix = toolchain / 'bin/aarch64-openwrt-linux-musl-'
    env = dict(os.environ, STAGING_DIR=str(modules.STAGING),
               PATH=str(prefix.parent) + ':' + str(modules.STAGING.parent / 'host/bin') + ':/usr/bin:/bin')
    compiler = subprocess.check_output([str(prefix) + 'gcc', '--version'], text=True, env=env).splitlines()[0]
    assert 'CONFIG_CC_VERSION_TEXT="' + compiler + '"' in config
    remap = '-fmacro-prefix-map=' + str(KERNEL.parent.parent) + '=' + KERNEL.parent.parent.name
    common = ['make', '-C', str(target), '-j' + str(args.jobs), 'ARCH=arm64',
              'CROSS_COMPILE=aarch64-openwrt-linux-musl-', 'KERNELRELEASE=6.18.44',
              'KBUILD_BUILD_USER=', 'KBUILD_BUILD_HOST=', 'KBUILD_BUILD_VERSION=0',
              'KBUILD_BUILD_TIMESTAMP=Fri Sep 4 16:17:19 2026', 'KBUILD_HAVE_NLS=no',
              'KCFLAGS=' + remap + ' -fno-caller-saves', 'KAFLAGS=' + remap,
              'KBUILD_HOSTLDFLAGS=-L' + str(modules.STAGING.parent / 'host/lib'), 'V=0']
    print('Building vmlinux and kernel modules with provider candidates 928/929.', flush=True)
    kernel_build = run(common + ['vmlinux', 'modules'], OUT / 'kernel-build.log', env)
    assert sha(target / '.config') == sha(KERNEL / '.config')
    assert sha(target / 'include/generated/autoconf.h') == sha(KERNEL / 'include/generated/autoconf.h')
    assert sha(target / 'include/generated/utsrelease.h') == sha(KERNEL / 'include/generated/utsrelease.h')
    required = {'airoha_npu_get', 'airoha_npu_put', 'airoha_npu_wlan_control'}
    symvers = {p[1]: p for line in (target / 'Module.symvers').read_text().splitlines()
               if len(p := line.split('\t')) >= 4}
    assert required <= symvers.keys()
    assert all(symvers[name][2:4] == ['vmlinux', 'EXPORT_SYMBOL_GPL'] for name in required)
    kernel_symbols = symbols(target / 'vmlinux', 'ET_DYN')
    provider_object = target / 'drivers/net/ethernet/airoha/airoha_npu.o'
    object_symbols = symbols(provider_object, 'ET_REL')
    assert required <= kernel_symbols.keys() and required <= object_symbols.keys()
    assert 'devm_work_drop' in object_symbols and 'airoha_npu_remove' not in object_symbols
    assert sha(provider_object) != sha(KERNEL / 'drivers/net/ethernet/airoha/airoha_npu.o')
    assert sha(target / 'vmlinux') != sha(KERNEL / 'vmlinux')
    for name in required:
        assert '__ksymtab_' + name in kernel_symbols
    print('Kernel links all three provider exports; rebuilding mt76 consumers.', flush=True)
    mt76 = dest / modules.PREPARED.name
    for name, key in (('npu.c', 'npu_source'), ('mt7996/mac.c', 'mac_source')):
        assert sha(modules.PREPARED / name) == linked['inputs'][key]
    if not mt76.exists():
        shutil.copytree(modules.PREPARED, mt76, ignore=shutil.ignore_patterns(
            '*.o', '*.ko', '*.cmd', '*.d', '*.mod', '*.mod.c', 'Module.symvers', 'modules.order', '*.symversions'))
    else:
        assert args.resume_build and mt76.is_dir() and not mt76.is_symlink()
    for name, key in (('npu.c', 'npu_source'), ('mt7996/mac.c', 'mac_source')):
        assert sha(mt76 / name) == linked['inputs'][key]
    modules.KERNEL = target
    index = dest / 'dependency-exports.symvers'
    dependencies, export_count = modules.exports_from_installed_modules(index)
    old_mt76 = ROOT / Path(linked['modules'][0]['path']).parent
    command = [piece.replace(str(KERNEL), str(target)).replace(str(old_mt76), str(mt76))
               for piece in linked['command']]
    command = ['KBUILD_EXTRA_SYMBOLS=' + str(index) if s.startswith('KBUILD_EXTRA_SYMBOLS=') else s
               for s in command]
    module_build = run(command, OUT / 'mt76-build.log', env, 600)
    module_rows, graph = [], {}
    for name in ('mt76.ko', 'mt76-connac-lib.ko', 'mt7996/mt7996e.ko'):
        row, defined, undefined = modules.parse_module(mt76 / name)
        module_rows.append(row)
        graph[name] = (defined, undefined)
    assert {'airoha_npu_get', 'airoha_npu_put'} <= graph['mt76.ko'][1]
    assert 'airoha_npu_wlan_control' not in graph['mt76.ko'][1]
    npu_imports = {name for name in graph['mt7996/mt7996e.ko'][1] if name.startswith('mt76_npu_')}
    assert npu_imports == set(linked['link_graph']['mt7996e_to_mt76'])
    assert npu_imports <= graph['mt76.ko'][0]
    assert any(s.startswith('mt76_npu_rx_poll') for s in graph['mt76.ko'][0])
    assert any(s.startswith('mt7996_mac_fill_rx') for s in graph['mt7996/mt7996e.ko'][0])
    probe = dest / 'control-link-probe'
    probe.mkdir(exist_ok=args.resume_build)
    (probe / 'Makefile').write_text('obj-m += provider-control-link-probe.o\n')
    (probe / 'provider-control-link-probe.c').write_text(
        '#include <linux/module.h>\n#include <linux/soc/airoha/airoha_offload.h>\n'
        'int provider_control_link_probe(struct airoha_npu *npu, void *data, int len);\n'
        'int provider_control_link_probe(struct airoha_npu *npu, void *data, int len)\n'
        '{\n\treturn airoha_npu_wlan_control(npu, data, len);\n}\n'
        'MODULE_LICENSE("GPL");\nMODULE_DESCRIPTION("Unloaded NPU control export link probe");\n')
    probe_build = run(common + ['M=' + str(probe), 'modules'], OUT / 'control-probe-build.log', env, 120)
    probe_row, _, probe_undefined = modules.parse_module(probe / 'provider-control-link-probe.ko')
    assert 'airoha_npu_wlan_control' in probe_undefined
    diagnostics = {row['path']: [line for line in (ROOT / row['path']).read_text().splitlines()
                                 if re.search(r'\b(?:warning|error):', line, re.I)]
                   for row in (kernel_build, module_build, probe_build)}
    allowed = set(linked['metadata_warnings'])
    probe_allowed = {'WARNING: modpost: missing MODULE_DESCRIPTION() in provider-control-link-probe.o'}
    kernel_allowed = {'WARNING: modpost: missing MODULE_DESCRIPTION() in ' + name
                      for name in (target / 'modules.order').read_text().splitlines()}
    assert set(diagnostics[kernel_build['path']]) <= kernel_allowed, diagnostics
    assert set(diagnostics[probe_build['path']]) <= probe_allowed, diagnostics
    assert set(diagnostics[module_build['path']]) <= allowed, diagnostics
    assert before == {relative(p): sha(p) for p in protected}
    artifacts = [record(target / name) for name in (PROVIDER, HEADER, '.config', 'Module.symvers',
                 'vmlinux', 'System.map', 'modules.order', 'drivers/net/ethernet/airoha/airoha_npu.o')]
    artifacts += [record(index), record(probe / 'Makefile'), record(probe / 'provider-control-link-probe.c')]
    initial_log = OUT / 'initial-kernel-build.log'
    prior_attempt = []
    if initial_log.exists():
        warnings = [line for line in initial_log.read_text().splitlines()
                    if re.search(r'\b(?:warning|error):', line, re.I)]
        assert set(warnings) <= kernel_allowed, warnings
        diagnostics[relative(initial_log)] = warnings
        prior_attempt = [record(initial_log), record(dest / 'initial-runner.py')]
    for name, accepted in (('initial-mt76-build.log', allowed),
                           ('initial-control-probe-build.log', probe_allowed)):
        path = OUT / name
        if path.exists():
            warnings = {line for line in path.read_text().splitlines()
                        if re.search(r'\b(?:warning|error):', line, re.I)}
            assert warnings <= accepted, warnings
            diagnostics[relative(path)] = sorted(warnings)
            prior_attempt.append(record(path))
    if (dest / 'second-runner.py').exists():
        prior_attempt.append(record(dest / 'second-runner.py'))
    result = dict(schema=1, protected_inputs_before_after=before, compiler=compiler,
                  resumed_build=args.resume_build, preserved_initial_attempt=prior_attempt,
                  copy=dict(source=relative(KERNEL), destination=relative(target), symlinks=symlinks,
                            method='Independent copy2 files; symlinks preserved; prepared objects reused where Kbuild permits.'),
                  patches=patch_rows, builds=[kernel_build, module_build, probe_build],
                  artifacts=artifacts, dependencies=dependencies, export_count=export_count,
                  modules=module_rows, control_export_probe=probe_row,
                  provider_exports={name: symvers[name] for name in sorted(required)},
                  provider_kernel_symbols={name: kernel_symbols[name] for name in sorted(required)},
                  provider_lifetime_symbols=dict(devm_work_drop=True, airoha_npu_remove=False),
                  mt7996_to_mt76=sorted(npu_imports), diagnostics=diagnostics,
                  description_warnings='CONFIG_MODULE_STRIPPED=y makes MODULE_DESCRIPTION expand to disabled metadata.',
                  limits=['Incremental relink of a copied prepared target kernel, not a clean toolchain or full OpenWrt image build.',
                          'The mt76 candidate still uses provider get/put; only the unloaded probe imports the V2 control export.',
                          'External mac80211 symbol index is reconstructed from installed ELF exports with CONFIG_MODVERSIONS disabled.',
                          'No module load, firmware execution, board FIT/DTB validation, physical DMA/drains or lifecycle acceptance.'])
    receipt = OUT / 'provider-kernel-link.json'
    receipt.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(receipt_sha256=sha(receipt), kernel_sha256=sha(target / 'vmlinux'),
                          provider_exports=sorted(required), modules=len(module_rows), control_probe=True)), flush=True)


if __name__ == '__main__':
    main()
