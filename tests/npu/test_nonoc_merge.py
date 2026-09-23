#!/usr/bin/env python3
"""Exercise the rebased provider/client, including the changed retry boundary."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
import test_memory_preflight as preflight
import test_host_queue_publication as extract

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '.local/merge-nonoc-20260923'
SOURCE = WORK / 'kernel-merged/drivers/net/ethernet/airoha/airoha_npu.c'
HEADER = WORK / 'kernel-merged/include/linux/soc/airoha/airoha_offload.h'
CONTROL = WORK / 'mt76-merged/w1700k'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log, env=None):
    done = subprocess.run(list(map(str, command)), capture_output=True, text=True,
                          env=env, timeout=180)
    log.write_text(done.stdout + done.stderr)
    assert done.returncode == 0, log.read_text()[-4000:]
    return done.stdout


def main():
    global SOURCE, HEADER, CONTROL
    args = argparse.ArgumentParser()
    args.add_argument('--name', default='verified')
    args.add_argument('--prepared', action='store_true', help='Test the actual sources used by the image build')
    options = args.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]*', options.name)
    dest = WORK / ('tests-' + options.name)
    assert not dest.exists()
    dest.mkdir()
    bindings = []
    if options.prepared:
        lock = json.loads((ROOT / 'firmware/source-lock.json').read_text())
        build = ROOT / lock['build_directory']
        linux = build / 'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581'
        kernel = linux / ('linux-' + lock['kernel'])
        matches = [path for path in linux.glob('mt76-*') if (path / 'npu.c').is_file()]
        assert len(matches) == 1
        mt76 = matches[0]
        for label, tree in (('kernel', kernel), ('mt76', mt76)):
            names = {row['path'] for row in json.loads((WORK / (label + '-merge.json')).read_text())}
            if label == 'mt76':
                names.add('Makefile')
                names.update(str(path.relative_to(WORK / 'mt76-merged'))
                             for path in (WORK / 'mt76-merged/w1700k').rglob('*') if path.is_file())
            for name in sorted(names):
                staged, actual = WORK / (label + '-merged') / name, tree / name
                assert sha(staged) == sha(actual), ('prepared-source-drift', label, name)
                bindings.append(dict(staged=str(staged.relative_to(ROOT)),
                                     prepared=str(actual.relative_to(ROOT)), sha256=sha(actual)))
        SOURCE = kernel / 'drivers/net/ethernet/airoha/airoha_npu.c'
        HEADER = kernel / 'include/linux/soc/airoha/airoha_offload.h'
        CONTROL = mt76 / 'w1700k'
    source, header = SOURCE.read_text(), HEADER.read_text()
    retry = extract.function(source, 'airoha_npu_wlan_cmd_with_retry')
    preflight.HEADER = HEADER
    preflight.MIDDLE += '\nstatic void mdelay(unsigned int msec) { (void)msec; }\n' + retry
    lib = preflight.build(source, source, 'memory', dest)
    cases = preflight.suite(lib)
    print(json.dumps(dict(stage='memory-preflight', cases=len(cases))), flush=True)
    retry_source = r'''
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <assert.h>
#include <errno.h>
typedef uint32_t u32;
#define GFP_KERNEL 0
struct airoha_npu { int unused; };
enum airoha_npu_wlan_set_cmd { TEST_CMD = 32 };
static struct airoha_npu provider;
static int errors[3], calls, delays, want_index;
static enum airoha_npu_wlan_set_cmd want_command;
static u32 want_value;
static void mdelay(unsigned int value) { assert(value == 10); delays++; }
static int airoha_npu_wlan_msg_send(struct airoha_npu *n, int index,
                                  enum airoha_npu_wlan_set_cmd cmd,
                                  void *value, int bytes, int flags) {
    assert(n == &provider && index == want_index && cmd == want_command);
    assert(bytes == 4 && flags == GFP_KERNEL && *(u32 *)value == want_value);
    assert(calls < 3);
    return errors[calls++];
}
''' + retry + r'''
int main(void) {
    const int faults[] = { 0, -ENOMEM, -ETIMEDOUT, -EBUSY, -EIO, -EINVAL, -EAGAIN };
    const int commands[] = { 18, 32, 8, 23, 7, 12 };
    const u32 values[] = { 0, 0x90c00000, UINT32_MAX };
    unsigned int cases = 0;
    for (unsigned c = 0; c < 6; c++)
    for (unsigned v = 0; v < 3; v++)
    for (unsigned a = 0; a < 7; a++)
    for (unsigned b = 0; b < 7; b++)
    for (unsigned d = 0; d < 7; d++) {
        int expected_calls = 0, expected_delays = 0, expected = 0;
        errors[0] = faults[a]; errors[1] = faults[b]; errors[2] = faults[d];
        for (int i = 0; i < 3; i++) {
            expected_calls++;
            expected = errors[i];
            if (!expected) { expected_delays++; break; }
            if (expected != -ENOMEM || i == 2) break;
            expected_delays++;
        }
        calls = delays = 0;
        want_index = c ? 0 : 1; want_command = commands[c]; want_value = values[v];
        assert(airoha_npu_wlan_cmd_with_retry(&provider, want_index,
                                             want_command, want_value) == expected);
        assert(calls == expected_calls && delays == expected_delays);
        cases++;
    }
    printf("{\"cases\":%u}\n", cases);
    return 0;
}
'''
    retry_path = dest / 'retry.c'
    retry_path.write_text(retry_source)
    compiler = shutil.which('clang')
    assert compiler
    flags = [compiler, '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
             '-fsanitize=address,undefined', '-fno-sanitize-recover=all']
    environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1')
    run(flags + [retry_path, '-o', dest / 'retry'], dest / 'retry-build.log')
    retry_result = json.loads(run([dest / 'retry'], dest / 'retry-run.log', environment))
    print(json.dumps(dict(stage='retry', **retry_result)), flush=True)
    mutants = {
        'replay-timeout': retry_source.replace('err != -ENOMEM || attempt == 2',
                                              '(err != -ENOMEM && err != -ETIMEDOUT) || attempt == 2'),
        'lose-return': retry_source.replace('return err;', 'return 0;'),
        'extra-attempt': retry_source.replace('attempt < 3', 'attempt < 4').replace('attempt == 2', 'attempt == 3'),
    }
    for name, text in mutants.items():
        path = dest / (name + '.c')
        path.write_text(text)
        run(flags + [path, '-o', dest / name], dest / (name + '-build.log'))
        result = subprocess.run([str(dest / name)], env=environment, capture_output=True, text=True, timeout=30)
        (dest / (name + '-run.log')).write_text(result.stdout + result.stderr)
        assert result.returncode and 'Assertion' in result.stderr
    parts = [preflight.block(source, r'^enum \{(?=\n\t' + name + r'(?:\b|,))') + ';'
             for name in ('NPU_OP_SET', 'NPU_FUNC_WIFI')]
    parts += [extract.declaration(header, 'enum', 'airoha_npu_wlan_get_cmd'),
              extract.declaration(source, 'struct', 'wlan_mbox_data')]
    parts += [extract.function(source, name) for name in
              ('__airoha_npu_send_msg', 'airoha_npu_wlan_msg_get', 'airoha_npu_wlan_control')]
    (dest / 'control-v2-provider.inc').write_text('\n\n'.join(parts) + '\n')
    shims = ROOT / '.local/npu-linux-control/verified/shims'
    assert shims.is_dir()
    command = flags + ['-pthread', '-I' + str(shims), '-I' + str(dest), '-I' + str(CONTROL),
                       '-I' + str(ROOT / 'firmware/npu'), '-I' + str(ROOT / 'tests/npu'),
                       ROOT / 'tests/npu/linux-control-harness.c']
    command += [CONTROL / name for name in ('control-client.c', 'control-v2-client.c', 'linux-control.c')]
    command += [ROOT / 'firmware/npu' / name for name in ('control-v2.c', 'admission.c', 'barrier.c')]
    run(command + ['-o', dest / 'linux-control'], dest / 'linux-control-build.log')
    linux_result = json.loads(run([dest / 'linux-control'], dest / 'linux-control-run.log', environment))
    print(json.dumps(dict(stage='linux-control', **linux_result)), flush=True)
    inputs = [Path(__file__), Path(preflight.__file__), Path(extract.__file__), SOURCE, HEADER,
              ROOT / 'tests/npu/linux-control-harness.c', ROOT / 'tests/npu/control-v2-provider-harness.c']
    inputs += [p for p in CONTROL.rglob('*') if p.is_file()]
    inputs += [p for p in shims.rglob('*') if p.is_file()]
    inputs += [ROOT / 'firmware/npu' / name for name in ('control-v2.c', 'admission.c', 'barrier.c')]
    inputs += [ROOT / 'firmware/source-lock.json', ROOT / 'firmware/build.config']
    receipt = dict(memory_preflight_cases=cases, allocation_retry=retry_result,
                   prepared_source_bindings=bindings,
                   mutants=list(mutants), linux_executor=linux_result,
                   inputs={str(p.relative_to(ROOT)): sha(p) for p in inputs},
                   artifacts={str(p.relative_to(ROOT)): sha(p) for p in dest.iterdir() if p.is_file()},
                   limits=['Actual merged provider/client C with modeled OF, load, regmap, firmware delivery and mutexes.',
                           'No physical boot, containment, DMA drains, module loading or runtime recovery proof.'])
    path = dest / 'result.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(receipt=str(path), sha256=sha(path))), flush=True)


if __name__ == '__main__':
    main()
