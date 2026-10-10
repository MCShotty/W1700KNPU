#!/usr/bin/env python3
"""Reconstruct and replay the active clock/reset source without touching hardware."""
import argparse
import io
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tarfile

sys.dont_write_bytecode = True
from elftools.elf.elffile import ELFFile
import test_npu_reset_control as reset
import test_npu_reset_native as native

ROOT = reset.ROOT


def native_cases(target):
    faults = 0
    for variant, ids in ((name, target.arrays[name]) for name in ('en7523_rst_map', 'en7581_rst_map', 'an7583_rst_map')):
        for logical, hardware in enumerate(ids):
            row = target.call('en7523_reset_xlate', variant, logical)
            assert row['result'] == hardware and not row['events']
            address = target.arrays['en7581_rst_ofs'][hardware // 32]
            mask, inverted = 1 << (hardware % 32), address == 0x88
            for seed in (0, 0xffffffff, 0xaaaaaaaa, 0x55555555):
                for asserted in (False, True):
                    row = target.call('en7523_reset_assert' if asserted else 'en7523_reset_deassert', variant, logical, seed)
                    value = mask if asserted != inverted else 0
                    assert row['result'] == 0 and row['word'] == (seed & ~mask) | value
                    assert len(row['events']) == 1
                    assert (row['events'][0]['address'], row['events'][0]['mask'], row['events'][0]['value']) == (address, mask, value)
                row = target.call('en7523_reset_status', variant, logical, seed)
                assert row['result'] == (bool(seed & mask) != inverted) and row['word'] == seed
                assert len(row['events']) == 1 and row['events'][0]['address'] == address
            for error in (-5, -110, -11):
                for asserted in (False, True):
                    for effect in (False, True):
                        row = target.call('en7523_reset_assert' if asserted else 'en7523_reset_deassert',
                                          variant, logical, 0x55555555, error, effect)
                        value = mask if asserted != inverted else 0
                        assert row['result'] == error and len(row['events']) == 1
                        assert row['word'] == (((0x55555555 & ~mask) | value) if effect else 0x55555555)
                        faults += 1
                for output in (None, 0, 0xffffffff):
                    row = target.call('en7523_reset_status', variant, logical, 0, error, output=output)
                    assert row['result'] == error and row['word'] == 0 and len(row['events']) == 1
                    faults += 1
        for invalid in (len(ids), len(ids) + 1, 0xffffffff):
            row = target.call('en7523_reset_xlate', variant, invalid)
            assert row['result'] == -22 and not row['events']
    return dict(executions=target.total, faults=faults, observations_sha256=target.digest.hexdigest())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-boot-launch-20261010' / args.name
    assert not dest.exists()
    dest.mkdir(parents=True)
    lock_path = ROOT / 'firmware/source-lock.json'
    lock = json.loads(lock_path.read_bytes())
    build = ROOT / lock['build_directory']
    version = lock['kernel']
    kernel = build / 'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581' / ('linux-' + version)
    source = kernel / reset.DRIVER
    seed = build / 'target/linux/generic/kernel-6.18'
    archive = build / 'dl' / ('linux-' + version + '.tar.xz')
    expected = re.search(r'^LINUX_KERNEL_HASH-' + re.escape(version) + r'\s*=\s*([a-f0-9]{64})$', seed.read_text(), re.M)[1]
    assert reset.sha(archive) == expected
    inputs = [source, seed, archive, lock_path, Path(__file__), reset.HARNESS, Path(reset.__file__),
              Path(native.__file__), Path(reset.extract.__file__), Path(reset.preflight.__file__)]
    inputs += [kernel / name for name in reset.HEADERS]
    inputs += [kernel / name for name in ('.config', 'Module.symvers', 'include/generated/autoconf.h',
                                         'include/generated/utsrelease.h')]
    initial = {str(p.relative_to(ROOT)): reset.sha(p) for p in inputs}
    replay = dest / 'replayed'
    target = replay / reset.DRIVER
    target.parent.mkdir(parents=True)
    with tarfile.open(archive) as tar:
        target.write_bytes(tar.extractfile('linux-' + version + '/' + reset.DRIVER).read())
    patches = []
    for folder in ('generic/backport-6.18', 'generic/pending-6.18', 'generic/hack-6.18', 'airoha/patches-6.18'):
        for patch in sorted((build / 'target/linux' / folder).glob('*.patch')):
            if ('+++ b/' + reset.DRIVER + '\n') not in patch.read_text():
                continue
            relative = str(patch.relative_to(build))
            locked = next((row for row in lock['openwrt']['changed_files'] if row['path'] == relative), None)
            if locked:
                assert reset.sha(patch) == locked['sha256']
            else:
                assert patch.read_bytes() == subprocess.check_output(['git', '-C', build, 'show', lock['openwrt']['base'] + ':' + relative])
            reset.run(['git', 'apply', '--include=' + reset.DRIVER, patch], dest / ('apply-' + patch.stem + '.log'),
                      cwd=replay, env=dict(os.environ, GIT_CEILING_DIRECTORIES=str(replay.parent)))
            inputs.append(patch)
            initial[str(patch.relative_to(ROOT))] = reset.sha(patch)
            patches.append(reset.record(patch))
    assert target.read_bytes() == source.read_bytes(), 'active-reset-source-replay-mismatch'
    text = source.read_text()
    (dest / 'reset-control.inc').write_text(reset.fragment(text))
    for header in reset.HEADERS:
        shutil.copy2(kernel / header, dest / Path(header).name)
    host = dest / 'host'
    reset.run([shutil.which('clang'), '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
               '-ftrivial-auto-var-init=pattern', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
               '-I' + str(dest), reset.HARNESS, '-o', host], dest / 'host-build.log')
    matrix = json.loads(reset.run([host], dest / 'host-run.log',
                       env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1')).stdout)
    # Compile the full current driver and a real-kernel layout probe, not model types.
    module = dest / 'target'
    module.mkdir()
    shutil.copy2(source, module / 'clk-en7523.c')
    (module / 'layout.c').write_text('#include "clk-en7523.c"\nconst u32 reset_layout[] __used __section(".reset_layout") = {\n'
        'sizeof(struct en_rst_data), offsetof(struct en_rst_data, bank_ofs), offsetof(struct en_rst_data, idx_map),\n'
        'offsetof(struct en_rst_data, map), offsetof(struct en_rst_data, rcdev),\n'
        'offsetof(struct reset_controller_dev, nr_resets), offsetof(struct of_phandle_args, args),\n'
        'ARRAY_SIZE(en7523_rst_map), ARRAY_SIZE(en7581_rst_map), ARRAY_SIZE(an7583_rst_map),\n'
        'EN7581_NPU_RST, REG_RST_CTRL2, RST_NR_PER_BANK };\n')
    (module / 'Makefile').write_text('obj-m += clk-en7523.o layout.o\n')
    prefix = build / 'staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin/aarch64-openwrt-linux-musl-'
    env = dict(os.environ, STAGING_DIR=str(build / 'staging_dir/target-aarch64_cortex-a53_musl'),
               PATH=str(prefix.parent) + ':' + str(build / 'staging_dir/host/bin') + ':/usr/bin:/bin')
    command = ['make', '-C', kernel, '-j2', 'ARCH=arm64', 'CROSS_COMPILE=' + str(prefix),
               'KERNELRELEASE=' + version, 'M=' + str(module), 'clk-en7523.o', 'layout.o']
    reset.run(command, dest / 'target-build.log', env=env)
    assert not re.search(r'\b(?:warning|error):', (dest / 'target-build.log').read_text())
    layout = list(struct.unpack('<13I', ELFFile(io.BytesIO((module / 'layout.o').read_bytes())).get_section_by_name('.reset_layout').data()))
    compiled = dict(profile='current', object=reset.record(module / 'clk-en7523.o'), layout=layout)
    native_target = native.Target(compiled)
    executions = native_cases(native_target)
    assert sum(layout[7:10]) == matrix['mapped_resets'] and layout[10:] == [8, 0x830, 32]
    # Interpret names only after extracting actual IDs and compiled translation arrays.
    names = re.findall(r'^#define (EN7581_\w+)\s+(\d+)', (kernel / reset.HEADERS[1]).read_text(), re.M)
    translation = []
    for name, logical in names:
        hardware = native_target.arrays['en7581_rst_map'][int(logical)]
        translation.append(dict(name=name, logical=int(logical), bank_offset=native_target.arrays['en7581_rst_ofs'][hardware // 32], bit=hardware % 32))
    result = dict(passed=True, kernel=version, source_replay_equal=True, patches=patches, host_matrix=matrix,
                  compiled=compiled, native=executions, maps=native_target.arrays, translation=translation,
                  inputs={str(p.relative_to(ROOT)): reset.sha(p) for p in inputs},
                  limits=['Current full reset driver/layout compile and native callback instructions with modeled regmap.',
                          'No reset line is asserted on hardware; translated names/bits do not establish physical engine coverage or drains.'])
    assert result['inputs'] == initial, 'reset-replay-inputs-changed'
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, mapped_resets=matrix['mapped_resets'], host_cases=matrix['cases'], native=executions)))


if __name__ == '__main__':
    main()
