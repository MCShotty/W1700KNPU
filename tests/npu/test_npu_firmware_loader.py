#!/usr/bin/env python3
"""Exercise actual paired firmware loading and compile the complete provider."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
import test_host_queue_publication as extract

ROOT = Path(__file__).resolve().parents[2]
DRIVER = 'drivers/net/ethernet/airoha/airoha_npu.c'
BASE_COMMIT = 'ec39858ac7abef1f462cef561777a03fa0d76ab5'
BASE_SHA = '6511daf3d74d3c0ea5b9369b4ee9dcb4b8911db4d5eec8d79e02f80f8605eca9'
BASE_PATCH = 'firmware/overlay/openwrt/target/linux/airoha/patches-6.18/999-w1700k-integrated-npu.patch'
WORK = ROOT / '.local/npu-loader-20260930'
OUT = ROOT / 'research/checkpoints/2026-09-30-npu-loader'
HARNESS = ROOT / 'tests/npu/firmware-loader-harness.c'
FUNCTIONS = ('airoha_npu_memory_valid', 'airoha_npu_load_firmware',
             'airoha_npu_load_firmware_from_dts', 'airoha_npu_run_firmware')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(path):
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size, sha256=sha(path))


def no_core():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def run(command, log, *, cwd=None, env=None, accepted=0, timeout=180):
    done = subprocess.run(list(map(str, command)), capture_output=True, text=True,
                          cwd=cwd, env=env, timeout=timeout, preexec_fn=no_core)
    log.write_text(done.stdout + done.stderr)
    assert done.returncode == accepted, log.read_text()[-4000:]
    return done


def once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def fragment(source):
    constants = re.findall(r'^#define (?:NPU_(?:EN7581|AN7583)\S*|NPU_SRAM_BACKUP_SIZE|REG_NPU_LOCAL_SRAM)\s+[^\n]+',
                           source, re.M)
    parts = constants + [extract.declaration(source, 'struct', name) for name in
                          ('airoha_npu_fw', 'airoha_npu_soc_data', 'airoha_npu_priv')]
    names = list(FUNCTIONS)
    if 'static int airoha_npu_request_firmware(' in source:
        names.insert(1, 'airoha_npu_request_firmware')
    if 'static int airoha_npu_wlan_prepare_memory(' in source:
        names.insert(1, 'airoha_npu_wlan_prepare_memory')
    parts += [extract.function(source, name) for name in names]
    return '\n\n'.join(parts) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', default='verified')
    parser.add_argument('--output-dir', type=Path, default=OUT)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,31}', args.name)
    dest, out = WORK / args.name, args.output_dir.resolve()
    assert out == OUT or out.is_relative_to((ROOT / '.local').resolve())
    assert not dest.exists() and not (out / 'firmware-loader.json').exists()
    dest.mkdir(parents=True)
    out.mkdir(parents=True, exist_ok=True)
    lock = json.loads((ROOT / 'firmware/source-lock.json').read_text())
    build = ROOT / lock['build_directory']
    kernel = build / 'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581' / ('linux-' + lock['kernel'])
    source = kernel / DRIVER
    staged = ROOT / '.local/merge-nonoc-20260923/kernel-merged' / DRIVER
    assert source.read_bytes() == staged.read_bytes()
    protected = [source, staged, ROOT / 'firmware/source-lock.json', ROOT / 'firmware/build.config',
                 ROOT / 'firmware/patches/openwrt.patch', ROOT / BASE_PATCH,
                 kernel / '.config', kernel / 'Module.symvers',
                 kernel / 'include/generated/autoconf.h', kernel / 'include/generated/utsrelease.h']
    initial = {str(path.relative_to(ROOT)): sha(path) for path in protected}
    baseline_root = dest / 'baseline'
    baseline_path = baseline_root / DRIVER
    baseline_path.parent.mkdir(parents=True)
    upstream = ROOT / '.local/merge-nonoc-20260923/kernel-upstream' / DRIVER
    shutil.copy2(upstream, baseline_path)
    patch = dest / 'baseline.patch'
    patch.write_bytes(subprocess.check_output(['git', '-C', str(ROOT), 'show', BASE_COMMIT + ':' + BASE_PATCH]))
    run(['git', 'apply', '--include=' + DRIVER, patch], out / 'baseline-apply.log', cwd=baseline_root,
        env=dict(os.environ, GIT_CEILING_DIRECTORIES=str(baseline_root.parent)))
    assert sha(baseline_path) == BASE_SHA, 'Baseline source differs from the committed checkpoint'
    before, after = baseline_path.read_text(), source.read_text()
    delta = out / 'provider-loader.patch'
    delta.write_text('Subject: [PATCH] net: airoha: preflight the NPU firmware pair\n\n'
                     'Obtain and validate both images before replacing code or SRAM.\n'
                     'Reject empty images and release acquired firmware on failure.\n\n---\n' +
                     ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                                fromfile='a/' + DRIVER, tofile='b/' + DRIVER)))
    run(['perl', kernel / 'scripts/checkpatch.pl', '--strict', '--no-signoff', delta], out / 'checkpatch.log')
    clang = shutil.which('clang')
    assert clang
    flags = [clang, '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-Wno-sign-compare',
             '-Wno-unused-function',
             '-fsanitize=address,undefined', '-fno-sanitize-recover=all']
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1')

    def host(name, contents):
        directory = dest / name
        directory.mkdir()
        (directory / 'firmware-loader.inc').write_text(fragment(contents))
        binary = directory / 'test'
        run(flags + ['-I' + str(directory), HARNESS, '-o', binary], directory / 'build.log')
        return directory, binary

    before_dir, before_binary = host('host-before', before)
    after_dir, after_binary = host('host-after', after)
    controls = []
    for case in ('data-missing', 'data-overlimit', 'code-empty', 'data-empty'):
        old_log = before_dir / (case + '.log')
        new_log = after_dir / (case + '.log')
        run([before_binary, case], old_log, env=env, accepted=11)
        assert 'FAIL[' + case + ']' in old_log.read_text()
        run([after_binary, case], new_log, env=env)
        controls.append(dict(case=case, before=record(old_log), after=record(new_log)))
    result = json.loads(run([after_binary], after_dir / 'matrix.log', env=env).stdout)
    print(json.dumps(dict(stage='paired-loader', **result)), flush=True)
    early = once(after, '\tmemcpy_toio(addr, rv32->data, rv32->size);\n', '')
    early = once(early, '\tret = airoha_npu_request_firmware(dev, &images->fw_data, &data);',
                 '\tmemcpy_toio(addr, rv32->data, rv32->size);\n' +
                 '\tret = airoha_npu_request_firmware(dev, &images->fw_data, &data);')
    mutants = {
        'code-write-before-data-request': early,
        'accept-empty-image': once(after, '!fw->size || fw->size > image->max_size', 'fw->size > image->max_size'),
        'forget-code-release': once(after, '\trelease_firmware(rv32);', '\t(void)rv32;'),
        'forget-data-release': once(after, '\trelease_firmware(data);', '\t(void)data;'),
        'wrong-data-image': once(after, '&images->fw_data, &data', '&images->fw_rv32, &data'),
        'hide-data-request-error': once(after, '\tif (ret)\n\t\tgoto release_rv32;',
                                      '\tif (ret) {\n\t\tret = 0;\n\t\tgoto release_rv32;\n\t}'),
    }
    mutation_records = []
    for name, contents in mutants.items():
        directory, binary = host('mutant-' + name, contents)
        log = directory / 'matrix.log'
        run([binary], log, env=env, accepted=11)
        assert 'FAIL[matrix]' in log.read_text()
        mutation_records.append(dict(name=name, log=record(log), binary=record(binary)))
    print(json.dumps(dict(stage='mutants', rejected=len(mutants))), flush=True)
    prefix = build / 'staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin/aarch64-openwrt-linux-musl-'
    kernel_env = dict(os.environ, STAGING_DIR=str(build / 'staging_dir/target-aarch64_cortex-a53_musl'),
                      PATH=str(prefix.parent) + ':' + str(build / 'staging_dir/host/bin') + ':/usr/bin:/bin')
    objects = []
    for name, path in (('before', baseline_path), ('after', source)):
        directory = dest / ('kernel-' + name)
        directory.mkdir()
        shutil.copy2(path, directory / 'airoha_npu.c')
        (directory / 'Makefile').write_text('obj-m += airoha_npu.o\n' +
            'ccflags-y += -I' + str(kernel / 'drivers/net/ethernet/airoha') + '\n')
        log = out / ('kernel-' + name + '.log')
        command = ['make', '-C', kernel, 'M=' + str(directory), 'ARCH=arm64', 'CROSS_COMPILE=' + str(prefix),
                   'KERNELRELEASE=' + lock['kernel'], 'KBUILD_BUILD_USER=', 'KBUILD_BUILD_HOST=', 'airoha_npu.o']
        run(command, log, env=kernel_env, timeout=180)
        assert not re.search(r'\b(?:warning|error):', log.read_text()), log.read_text()
        objects.append(dict(variant=name, object=record(directory / 'airoha_npu.o'), log=record(log)))
    final = {str(path.relative_to(ROOT)): sha(path) for path in protected}
    assert initial == final, 'The test modified an authoritative source or kernel configuration'
    inputs = protected + [Path(__file__), HARNESS, Path(extract.__file__), upstream,
                          kernel / 'include/linux/firmware.h']
    receipt = dict(passed=True, baseline_commit=BASE_COMMIT, baseline_source=record(baseline_path),
                   corrected_source=record(source), host_matrix=result, baseline_controls=controls,
                   mutants=mutation_records, kernel_objects=objects,
                   inputs=[record(path) for path in inputs],
                   artifacts=[record(path) for path in sorted(dest.rglob('*')) if path.is_file()],
                   protected_files_unchanged=final,
                   limits=['Actual provider C with modeled firmware requests, resource lookup, mapping and I/O copies.',
                           'AArch64 object builds; no module loading, firmware execution or hardware containment proof.',
                           'Preflight prevents request/size errors from partially copying the pair; it does not make live replacement atomic.',
                           'Cold reset, loader identity/placement, physical drains and V2 caller integration remain open.'])
    (out / 'firmware-loader.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(receipt=record(out / 'firmware-loader.json'), kernel_objects=len(objects))), flush=True)


if __name__ == '__main__':
    main()
