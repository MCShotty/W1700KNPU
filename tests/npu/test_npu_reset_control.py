#!/usr/bin/env python3
"""Validate the shared reset primitive required by a future NPU cold loader."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import resource
import shutil
import struct
import subprocess
import sys
import tarfile

sys.dont_write_bytecode = True
from elftools.elf.elffile import ELFFile
import test_host_queue_publication as extract
import test_memory_preflight as preflight
import test_npu_linked_modules as modules

ROOT = modules.ROOT
BUILD = ROOT / '.local/npu-reset-control'
OUT = ROOT / 'research/checkpoints/2026-09-23-npu-reset-control'
KERNEL = ROOT / '.local/npu-provider-kernel-link/verified/linux-6.18.44'
OPENWRT = ROOT / '.build/openwrt'
DRIVER = 'drivers/clk/clk-en7523.c'
PATCH = OUT / '930-clk-en7523-preserve-reset-errors.patch'
HARNESS = ROOT / 'tests/npu/reset-control-harness.c'
FUNCTIONS = ('en7523_reset_update', 'en7523_reset_assert', 'en7523_reset_deassert',
             'en7523_reset_status', 'en7523_reset_xlate')
HEADERS = tuple('include/dt-bindings/reset/airoha,' + name + '-reset.h'
                for name in ('en7523', 'en7581', 'an7583'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def record(path):
    return dict(path=str(path.relative_to(ROOT)), sha256=sha(path), bytes=path.stat().st_size)


def no_core():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def run(command, log, *, env=None, cwd=None, accepted=0, timeout=180):
    result = subprocess.run([str(p) for p in command], capture_output=True, text=True,
                            env=env, cwd=cwd, timeout=timeout, preexec_fn=no_core)
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == accepted, log.read_text()[-5000:]
    return result


def once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def fragment(text):
    names = ('RST_NR_PER_BANK', 'REG_RST_CTRL2', 'REG_RST_CTRL1', 'REG_NP_SCU_PCIC')
    parts = [re.search(r'^#define\s+' + n + r'\s+[^\n]+', text, re.M).group() for n in names]
    parts += ['#include "' + Path(n).name + '"' for n in HEADERS]
    parts += [extract.declaration(text, 'struct', 'en_rst_data')]
    for name in ('en7581_rst_ofs', 'en7523_rst_map', 'en7581_rst_map', 'an7583_rst_map'):
        parts.append(preflight.block(text, r'^static const u16 ' + name + r'\[\]') + ';')
    parts += [extract.function(text, name) for name in FUNCTIONS]
    return '\n\n'.join(parts) + '\n'


def reconstruct(dest, out):
    lock = json.loads((ROOT / 'firmware/source-lock.json').read_text())
    head = subprocess.check_output(['git', '-C', str(OPENWRT), 'rev-parse', 'HEAD'], text=True).strip()
    assert head == lock['openwrt']['local_head']
    seed = OPENWRT / 'target/linux/generic/kernel-6.18'
    archived = subprocess.check_output(['git', '-C', str(OPENWRT), 'show', head + ':target/linux/generic/kernel-6.18'])
    assert seed.read_bytes() == archived
    expected = re.search(r'^LINUX_KERNEL_HASH-6\.18\.44\s*=\s*([a-f0-9]{64})$', seed.read_text(), re.M).group(1)
    archive = OPENWRT / 'dl/linux-6.18.44.tar.xz'
    assert sha(archive) == expected
    path = dest / DRIVER
    path.parent.mkdir(parents=True)
    with tarfile.open(archive) as tar:
        path.write_bytes(tar.extractfile('linux-6.18.44/' + DRIVER).read())
    sources = [seed, archive]
    applied = []
    # Stop Git discovering the outer repository; only this extracted file is patched.
    env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(dest.parent))
    for name in ('generic/backport-6.18', 'generic/pending-6.18',
                 'generic/hack-6.18', 'airoha/patches-6.18'):
        for patch in sorted((OPENWRT / 'target/linux' / name).glob('*.patch')):
            if ('+++ b/' + DRIVER + '\n') not in patch.read_text():
                continue
            relative = str(patch.relative_to(OPENWRT))
            assert patch.read_bytes() == subprocess.check_output(
                ['git', '-C', str(OPENWRT), 'show', head + ':' + relative])
            log = out / ('reconstruct-' + patch.stem + '.log')
            run(['git', 'apply', '--verbose', '--include=' + DRIVER, patch], log, cwd=dest, env=env)
            sources.append(patch)
            applied.append(dict(source=record(patch), log=record(log)))
    assert sha(path) == sha(KERNEL / DRIVER) == sha(modules.KERNEL / DRIVER)
    return sources, dict(openwrt_head=head, kernel_archive=record(archive),
                         baseline=record(path), patches=applied)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-name', default='verified')
    parser.add_argument('--output-dir', type=Path, default=OUT)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,31}', args.build_name)
    dest, out = BUILD / args.build_name, args.output_dir.resolve()
    assert out == OUT or out.is_relative_to((ROOT / '.local').resolve())
    assert not dest.exists() and not (out / 'reset-control.json').exists()
    dest.mkdir(parents=True)
    out.mkdir(parents=True, exist_ok=True)
    protected = [Path(__file__), HARNESS, PATCH, Path(extract.__file__), Path(preflight.__file__),
                 Path(modules.__file__), ROOT / 'firmware/source-lock.json',
                 ROOT / 'firmware/patches/openwrt.patch', ROOT / 'firmware/build.config',
                 KERNEL / DRIVER, modules.KERNEL / DRIVER, KERNEL / '.config',
                 KERNEL / 'Module.symvers', KERNEL / 'include/generated/autoconf.h',
                 KERNEL / 'include/generated/utsrelease.h', KERNEL / 'include/linux/regmap.h']
    protected += [KERNEL / n for n in HEADERS]
    initial = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    sources, provenance = reconstruct(dest / 'baseline', out)
    protected += sources
    initial.update({str(p.relative_to(ROOT)): sha(p) for p in sources})
    baseline = (dest / 'baseline' / DRIVER).read_text()
    staged = dest / 'candidate' / DRIVER
    staged.parent.mkdir(parents=True)
    staged.write_text(baseline)
    log = out / 'candidate-apply.log'
    run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', PATCH], log, cwd=dest / 'candidate')
    assert 'offset' not in log.read_text() and 'fuzz' not in log.read_text(), log.read_text()
    corrected = staged.read_text()
    checkpatch = KERNEL / 'scripts/checkpatch.pl'
    run(['perl', checkpatch, '--no-signoff', '--strict', PATCH], out / 'checkpatch.log')
    before_functions = {n: hashlib.sha256(extract.function(baseline, n).encode()).hexdigest() for n in FUNCTIONS}
    after_functions = {n: hashlib.sha256(extract.function(corrected, n).encode()).hexdigest() for n in FUNCTIONS}
    assert {n for n in FUNCTIONS if before_functions[n] != after_functions[n]} == {
        'en7523_reset_update', 'en7523_reset_status'}
    compiler = shutil.which('clang')
    assert compiler
    command = [compiler, '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
               '-Wno-error=uninitialized', '-ftrivial-auto-var-init=pattern',
               '-fsanitize=address,undefined', '-fno-sanitize-recover=all']
    environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1')

    def host(name, text):
        directory = dest / name
        directory.mkdir()
        (directory / 'reset-control.inc').write_text(fragment(text))
        for header in HEADERS:
            shutil.copy2(KERNEL / header, directory / Path(header).name)
        binary = directory / 'test'
        build = directory / 'build.log'
        run(command + ['-I' + str(directory), HARNESS, '-o', binary], build)
        return directory, binary

    before_dir, before_bin = host('host-before', baseline)
    after_dir, after_bin = host('host-after', corrected)
    assert not (after_dir / 'build.log').read_text()
    controls = []
    for case in ('write-error', 'read-error', 'value-init', 'value-pcic'):
        log = before_dir / (case + '.log')
        run([before_bin, case], log, env=environment, accepted=11)
        assert 'FAIL[' + case + ']' in log.read_text()
        controls.append(dict(case=case, log=record(log)))
        run([after_bin, case], after_dir / (case + '.log'), env=environment)
    result = json.loads(run([after_bin], after_dir / 'run.log', env=environment).stdout)
    print(json.dumps(dict(stage='host', **result)), flush=True)
    write_return = '\treturn regmap_update_bits(rst_data->map, addr, BIT(id % RST_NR_PER_BANK),\n\t\t\t\t  val);'
    mutations = {
        'indeterminate-value': ('value-init', corrected.replace('\t\tval = assert ?', '\t\tval |= assert ?')),
        'hide-write-error': ('write-error', once(corrected, write_return,
            '\tregmap_update_bits(rst_data->map, addr, BIT(id % RST_NR_PER_BANK), val);\n\treturn 0;')),
        'hide-read-error': ('read-error', once(corrected, '\tif (ret)\n\t\treturn ret;\n', '\t(void)ret;\n')),
        'invert-pcic-polarity': ('value-pcic', once(corrected,
            '\t\tval = assert ? 0 : BIT(id % RST_NR_PER_BANK);',
            '\t\tval = assert ? BIT(id % RST_NR_PER_BANK) : 0;')),
        'wrong-mask': (None, once(corrected, write_return, write_return.replace('addr, BIT(', 'addr, ~BIT('))),
        'wrong-bank': (None, once(corrected, 'u32 addr = rst_data->bank_ofs[id / RST_NR_PER_BANK];\n\tu32 val;',
            'u32 addr = rst_data->bank_ofs[0];\n\tu32 val;')),
        'repeat-failed-write': ('write-error', once(corrected, write_return,
            '\tregmap_update_bits(rst_data->map, addr, BIT(id % RST_NR_PER_BANK), val);\n' + write_return)),
    }
    mutants = []
    for name, (case, text) in mutations.items():
        directory, binary = host('mutant-' + name, text)
        log = directory / 'run.log'
        run([binary] + ([case] if case else []), log, env=environment, accepted=11)
        assert 'FAIL[' + (case or 'nominal') + ']' in log.read_text()
        mutants.append(dict(name=name, case=case or 'nominal', binary=record(binary), log=record(log)))
    print(json.dumps(dict(stage='mutants', rejected=len(mutants))), flush=True)
    prefix = modules.STAGING.parent / 'toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin/aarch64-openwrt-linux-musl-'
    kernel_env = dict(os.environ, STAGING_DIR=str(modules.STAGING),
                      PATH=str(prefix.parent) + ':' + str(modules.STAGING.parent / 'host/bin') + ':/usr/bin:/bin')
    objects = []
    for name, source in (('before', baseline), ('after', corrected)):
        directory = dest / ('kernel-' + name)
        directory.mkdir()
        (directory / 'clk-en7523.c').write_text(source)
        (directory / 'layout.c').write_text('#include "clk-en7523.c"\n'
            'const u32 reset_layout[] __used __section(".reset_layout") = {\n'
            'sizeof(struct en_rst_data), offsetof(struct en_rst_data, bank_ofs),\n'
            'offsetof(struct en_rst_data, idx_map), offsetof(struct en_rst_data, map),\n'
            'offsetof(struct en_rst_data, rcdev), offsetof(struct reset_controller_dev, nr_resets),\n'
            'offsetof(struct of_phandle_args, args), ARRAY_SIZE(en7523_rst_map),\n'
            'ARRAY_SIZE(en7581_rst_map), ARRAY_SIZE(an7583_rst_map),\n'
            'EN7581_NPU_RST, REG_RST_CTRL2, RST_NR_PER_BANK };\n')
        (directory / 'Makefile').write_text('obj-m += clk-en7523.o layout.o\n')
        make = ['make', '-C', KERNEL, '-j2', 'ARCH=arm64', 'CROSS_COMPILE=' + str(prefix),
                'CC=' + str(prefix) + 'gcc', 'KERNELRELEASE=6.18.44', 'V=0', 'M=' + str(directory),
                'clk-en7523.o', 'layout.o']
        log = out / ('kernel-' + name + '.log')
        run(make, log, env=kernel_env, timeout=180)
        diagnostics = [l for l in log.read_text().splitlines() if re.search(r'\b(?:warning|error):', l, re.I)]
        assert not diagnostics, diagnostics
        elf = ELFFile(io.BytesIO((directory / 'layout.o').read_bytes()))
        layout = list(struct.unpack('<13I', elf.get_section_by_name('.reset_layout').data()))
        assert sum(layout[7:10]) == result['mapped_resets'] and layout[10:] == [8, 0x830, 32]
        elf = ELFFile(io.BytesIO((directory / 'clk-en7523.o').read_bytes()))
        assert elf['e_machine'] == 'EM_AARCH64'
        symbols = {s.name for s in elf.get_section_by_name('.symtab').iter_symbols() if s['st_shndx'] != 'SHN_UNDEF'}
        assert {'en7523_reset_assert', 'en7523_reset_deassert', 'en7523_reset_status'} <= symbols
        run([str(prefix) + 'objdump', '-dr', directory / 'clk-en7523.o'], directory / 'disassembly.txt')
        objects.append(dict(profile=name, command=list(map(str, make)), layout=layout,
                            object=record(directory / 'clk-en7523.o'), probe=record(directory / 'layout.o'),
                            log=record(log), disassembly=record(directory / 'disassembly.txt')))
    assert objects[0]['layout'] == objects[1]['layout']
    assert initial == {str(p.relative_to(ROOT)): sha(p) for p in protected}
    artifacts = [record(p) for p in sorted(dest.rglob('*')) if p.is_file() and
                 (p.suffix in ('.c', '.h', '.inc', '.o', '.log', '.txt') or p.name in ('test', 'Makefile'))]
    receipt = dict(schema=1, scope='Shared reset-controller software prerequisite; not physical NPU containment.',
                   inputs_before_after=initial, provenance=provenance, patch=record(PATCH),
                   function_hashes=dict(before=before_functions, after=after_functions),
                   host=result, baseline_controls=controls, mutants=mutants, kernel_objects=objects,
                   artifacts=artifacts, host_compiler=subprocess.check_output([compiler, '--version'], text=True),
                   host_flags=command[1:],
                   limits=['Regmap and device effects are explicitly modeled, including failed writes with and without side effects.',
                           'Pattern initialization is a test compiler option used to expose source indeterminacy; it is not the production kernel configuration.',
                           'Reset maps and polarity are preserved; translated IDs are assumed valid as supplied by the reset framework.',
                           'No NPU provider reset wiring, boot identity, firmware publication, physical drain or reset-domain coverage is established.',
                           'No packaged source, image, router, restricted INODE/DESC operation or resource-release authority changes.'])
    path = out / 'reset-control.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(stage='complete', receipt_sha256=sha(path), cases=result['cases'],
                         baseline_controls=len(controls), mutants=len(mutants), kernel_objects=4)), flush=True)


if __name__ == '__main__':
    main()
