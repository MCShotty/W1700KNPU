#!/usr/bin/env python3
"""Replay the locked provider and check pre-copy memory admission offline.

Only host C runs. Kernel OF, firmware requests, I/O and mailbox behavior are
modeled. This runner neither contacts a router nor executes native NPU code.
"""
import argparse
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
import test_npu_firmware_loader as loader
import test_nonoc_merge as merged

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests/npu/fixtures/airoha-npu-6.18.52'
DRIVER = 'drivers/net/ethernet/airoha/airoha_npu.c'
PATCH = ROOT / 'firmware/overlay/openwrt/target/linux/airoha/patches-6.18/999-w1700k-integrated-npu.patch'
PRIOR_SHA = '8dc8545d3b5ea776820f2d75ed0795fee0ca8f93a12bb9e0708169320425f052'
LEAK_CHECK = True


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(path):
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size, sha256=sha(path))


def run(command, log, *, cwd=None, expected=0):
    def no_core():
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    done = subprocess.run([str(x) for x in command], cwd=cwd, capture_output=True,
                          text=True, timeout=120, preexec_fn=no_core,
                          env=dict(os.environ, GIT_CEILING_DIRECTORIES=str(cwd.parent if cwd else ROOT),
                                   ASAN_OPTIONS=f'detect_leaks={int(LEAK_CHECK)}:detect_stack_use_after_return=1'))
    log.write_text(done.stdout + done.stderr)
    assert done.returncode == expected, (command, done.returncode, log.read_text()[-4000:])
    return done


def once(source, old, new):
    assert source.count(old) == 1, old
    return source.replace(old, new)


def main():
    global LEAK_CHECK
    args = argparse.ArgumentParser()
    args.add_argument('--name', required=True)
    args.add_argument('--disable-leak-check', action='store_true',
                      help='Explicitly disable LeakSanitizer when the host cannot run it')
    args.add_argument('--candidate-source', type=Path,
                      help='Test an explicitly staged source before integrating the canonical patch')
    options = args.parse_args()
    LEAK_CHECK = not options.disable_leak_check
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', options.name)
    dest = ROOT / '.local/npu-cold-memory-plan' / options.name
    assert not dest.exists(), 'Choose a fresh result name'
    dest.mkdir(parents=True)
    provenance = json.loads((FIXTURES / 'provenance.json').read_text())
    for name, digest in provenance['files'].items():
        assert sha(FIXTURES / name) == digest
    lock = json.loads((ROOT / 'firmware/source-lock.json').read_text())
    assert lock['kernel'] == provenance['kernel']
    assert lock['openwrt']['base'] == provenance['openwrt_base']
    relative_patch = str(PATCH.relative_to(ROOT / 'firmware/overlay/openwrt'))
    assert sha(PATCH) == next(x['sha256'] for x in lock['openwrt']['changed_files']
                             if x['path'] == relative_patch)
    current_path = dest / 'replayed' / DRIVER
    current_path.parent.mkdir(parents=True)
    shutil.copy2(FIXTURES / 'provider-upstream.c', current_path)
    run(['git', 'apply', '--include=' + DRIVER, PATCH], dest / 'source-apply.log',
        cwd=dest / 'replayed')
    prior_patch = dest / 'prior.patch'
    prior_patch.write_bytes(subprocess.check_output([
        'git', '-C', str(ROOT), 'show', 'ac4c639:' + str(PATCH.relative_to(ROOT))]))
    prior_path = dest / 'prior' / DRIVER
    prior_path.parent.mkdir(parents=True)
    shutil.copy2(FIXTURES / 'provider-upstream.c', prior_path)
    run(['git', 'apply', '--include=' + DRIVER, prior_patch], dest / 'prior-apply.log',
        cwd=dest / 'prior')
    assert sha(prior_path) == PRIOR_SHA
    tested = options.candidate_source.resolve() if options.candidate_source else current_path
    assert tested.is_relative_to(ROOT)
    before, after = prior_path.read_text(), tested.read_text()
    compiler = shutil.which('gcc')
    assert compiler
    flags = [compiler, '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
             '-Wno-sign-compare', '-Wno-unused-function', '-fno-pie', '-no-pie',
             '-fsanitize=address,undefined', '-fno-sanitize-recover=all']
    header = (FIXTURES / 'airoha_offload.h').read_text()

    def host(name, source):
        directory = dest / name
        directory.mkdir()
        (directory / 'firmware-loader.inc').write_text(loader.fragment(source))
        (directory / 'wlan-enum.inc').write_text(extract.declaration(header, 'enum', 'airoha_npu_wlan_set_cmd'))
        (directory / 'wlan-memory.inc').write_text('\n\n'.join(extract.function(source, n) for n in
            ('airoha_npu_wlan_cmd_with_retry', 'airoha_npu_wlan_init_memory')))
        binary = directory / 'test'
        run(flags + ['-I' + str(directory), ROOT / 'tests/npu/cold-memory-plan-harness.c', '-o', binary],
            directory / 'build.log')
        return directory, binary

    old_dir, old_binary = host('before', before)
    new_dir, new_binary = host('after', after)
    controls = []
    for name in ('invalid-before-load', 'snapshot-reuse', 'failed-load-unbound'):
        run([old_binary, name], old_dir / (name + '.log'), expected=11)
        assert 'FAIL[' + name + ']' in (old_dir / (name + '.log')).read_text()
        run([new_binary, name], new_dir / (name + '.log'))
        controls.append(name)
    done = run([new_binary], new_dir / 'matrix.log')
    matrix = [json.loads(line) for line in done.stdout.splitlines()]
    mutants = {
        'omit-precopy-preflight': once(after, 'if (priv->txbuf_min_size) {', 'if (false) {'),
        'reread-after-load': once(after, 'if (!priv->txbuf_min_size) {', 'if (true) {'),
        'admit-failed-load': once(after, '\tif (!priv->firmware_loaded)\n\t\treturn -EINVAL;\n', ''),
        'keep-plan-on-early-run-failure': once(after,
            '\tpriv->firmware_loaded = false;\n\tpriv->wlan_memory_count = 0;\n\tsoc =', '\tsoc ='),
        'accept-undersized-tx': once(after, 'resource_size(&memory[0]) < priv->txbuf_min_size', 'false'),
        'omit-snapshot-copy': once(after, '\tmemcpy(regions, memory, sizeof(memory));', '\t(void)regions;'),
        'omit-region-overlap': after.replace('if (resource_overlaps(res,', 'if (false && resource_overlaps(res,'),
        'force-wlan-on-generic-probe': once(after, 'if (priv->txbuf_min_size) {', 'if (true) {'),
        'share-generic-plan-between-callers': after.replace(
            'airoha_npu_wlan_prepare_memory(priv, local, &count)',
            'airoha_npu_wlan_prepare_memory(priv, priv->wlan_memory, &priv->wlan_memory_count)').replace(
            'memory = local;', 'memory = priv->wlan_memory; count = priv->wlan_memory_count; (void)local;').replace(
            'i < count; i++) {\n\t\tval = memory[i].start;',
            'i < priv->wlan_memory_count; i++) {\n\t\tval = memory[i].start;'),
    }
    rejected = []
    for name, source in mutants.items():
        directory, binary = host('mutant-' + name, source)
        run([binary], directory / 'matrix.log', expected=11)
        assert 'FAIL[' in (directory / 'matrix.log').read_text()
        rejected.append(name)
    retry_path = dest / 'retry.c'
    retry_path.write_text(merged.retry_harness(extract.function(after, 'airoha_npu_wlan_cmd_with_retry')))
    run(flags + [retry_path, '-o', dest / 'retry'], dest / 'retry-build.log')
    retry_result = json.loads(run([dest / 'retry'], dest / 'retry-run.log').stdout)
    shims = {
        'linux/types.h': '#ifndef NPU_TEST_TYPES_H\n#define NPU_TEST_TYPES_H\n#include <stdint.h>\n#include <stdbool.h>\n#include <stddef.h>\ntypedef uint8_t u8;\ntypedef uint16_t u16;\ntypedef uint32_t u32;\n#endif\n',
        'linux/mutex.h': '#ifndef NPU_TEST_MUTEX_H\n#define NPU_TEST_MUTEX_H\n#include <pthread.h>\nstruct mutex { pthread_mutex_t native; };\nvoid npu_test_mutex_init(struct mutex *m);\nvoid npu_test_mutex_lock(struct mutex *m);\nvoid npu_test_mutex_unlock(struct mutex *m);\nstatic inline void mutex_init(struct mutex *m) { npu_test_mutex_init(m); }\nstatic inline void mutex_lock(struct mutex *m) { npu_test_mutex_lock(m); }\nstatic inline void mutex_unlock(struct mutex *m) { npu_test_mutex_unlock(m); }\n#endif\n',
        'linux/soc/airoha/airoha_offload.h': 'struct airoha_npu;\nint airoha_npu_wlan_control(struct airoha_npu *npu, void *data, int len);\n',
    }
    for name, contents in shims.items():
        path = dest / 'shims' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
    parts = [re.search(r'^enum \{\n\t' + name + r'\b.*?^};', after, re.M | re.S)[0]
             for name in ('NPU_OP_SET', 'NPU_FUNC_WIFI')]
    parts += [extract.declaration(header, 'enum', 'airoha_npu_wlan_get_cmd'),
              extract.declaration(after, 'struct', 'wlan_mbox_data')]
    parts += [extract.function(after, name) for name in
              ('__airoha_npu_send_msg', 'airoha_npu_wlan_msg_get', 'airoha_npu_wlan_control')]
    (dest / 'control-v2-provider.inc').write_text('\n\n'.join(parts) + '\n')
    core = ROOT / 'firmware/npu'
    component_names = ('control-client.c', 'control-v2-client.c', 'linux-control.c',
                       'control-v2.c', 'admission.c', 'barrier.c')
    command = flags + ['-pthread', '-I' + str(dest / 'shims'), '-I' + str(dest),
                       '-I' + str(core), '-I' + str(ROOT / 'tests/npu'),
                       ROOT / 'tests/npu/linux-control-harness.c']
    command += [core / name for name in component_names]
    run(command + ['-o', dest / 'linux-control'], dest / 'linux-control-build.log')
    control_result = json.loads(run([dest / 'linux-control'], dest / 'linux-control-run.log').stdout)
    inputs = [Path(__file__), ROOT / 'tests/npu/cold-memory-plan-harness.c',
              ROOT / 'tests/npu/firmware-loader-harness.c', Path(loader.__file__),
              Path(extract.__file__), PATCH, ROOT / 'firmware/source-lock.json']
    inputs += [Path(merged.__file__), ROOT / 'tests/npu/linux-control-harness.c',
               ROOT / 'tests/npu/control-v2-provider-harness.c']
    inputs += sorted(p for p in core.iterdir() if p.suffix in ('.c', '.h'))
    inputs += sorted(FIXTURES.iterdir())
    receipt = dict(passed=True, staged_candidate=bool(options.candidate_source),
                   tested_provider=record(tested), canonical_replay=record(current_path),
                   prior_provider=record(prior_path), matrix=matrix,
                   original_failure_controls=controls, rejected_mutants=rejected,
                   retry_regression=retry_result, linux_control_regression=control_result,
                   compiler=subprocess.check_output([compiler, '--version'], text=True).splitlines()[0],
                   sanitizers=dict(address=True, undefined=True, leak=LEAK_CHECK),
                   inputs=[record(p) for p in inputs],
                   artifacts=[record(p) for p in sorted(dest.rglob('*')) if p.is_file()],
                   limits=['Actual selected provider C on x86-64 with GCC ASan/UBSan; OF, I/O, firmware and mailbox dependencies modeled.',
                           ('LeakSanitizer is enabled for this host run; fixture storage remains modeled.'
                            if LEAK_CHECK else 'LeakSanitizer was explicitly disabled; no leak-check coverage is claimed.'),
                           'No complete kernel/target object build, NPU execution, module load, hardware access or flash.',
                           'Geometry/snapshot admission is not physical containment, exclusive reservation, DMA drain or safe live reset.',
                           'The source replay covers this provider file, not the full 60-file OpenWrt/LuCI source tree.'])
    out = dest / 'result.json'
    out.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(receipt=record(out), matrix=matrix, rejected_mutants=len(rejected),
                         retry=retry_result, linux_control=control_result)))


if __name__ == '__main__':
    main()
