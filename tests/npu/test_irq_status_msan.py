#!/usr/bin/env python3
"""Defined status error output and a real preserved legacy body under host MSan."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
import native_prefix_snapshot
import test_npu_firmware_loader as loader
from test_final_irq_contract import PROVIDER

ROOT = loader.ROOT


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--legacy-source', type=Path)
    args = parser.parse_args()
    assert args.name.replace('-', '').isalnum()
    destination = ROOT / '.local/npu-irq-status-msan' / args.name
    assert not destination.exists()
    destination.mkdir(parents=True)
    inputs = native_prefix_snapshot.source_inputs({str(PROVIDER.relative_to(ROOT)): sha(PROVIDER)})
    body = loader.extract.function(PROVIDER.read_text(), 'airoha_npu_wlan_irq_status_get')
    prefix = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
typedef uint32_t u32;
#define REG_IRQ_STATUS 0x30d030u
#define BIT(n) (1u << (n))
#define NPU_IRQ_RX_MASK(q) ((q)==1 ? BIT(17) : BIT(16))
struct airoha_npu { void *regmap; };
static volatile int fail_read;
static int cookie;
static __attribute__((noinline)) int regmap_read(void *map,u32 reg,u32 *value) {
    assert(map==&cookie && reg==0x30d030u && value);
    if(fail_read) return -5;
    *value=0x10000u; return 0;
}
'''
    suffix = r'''
int main(int argc,char **argv) {
    struct airoha_npu npu={&cookie};
    fail_read=argc>1;
    u32 result=airoha_npu_wlan_irq_status_get(&npu,0);
    printf("%u\n",result);
    if(!fail_read) assert(result==0x10000u);
    return 0;
}
'''
    environment = dict(os.environ, MSAN_OPTIONS='halt_on_error=1:symbolize=1')
    def execute_body(body, name, legacy):
        source, binary = destination / (name + '.c'), destination / name
        source.write_text(prefix + body + suffix)
        command = [shutil.which('clang'), '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
            '-Wno-unused-parameter', '-fno-inline', '-fno-omit-frame-pointer', '-fno-optimize-sibling-calls',
            '-fsanitize=memory', '-fsanitize-memory-track-origins=2', '-fPIE', '-pie', source, '-o', binary]
        loader.run(command, destination / (name + '.build.log'))
        runs = []
        for case, arguments in (('nominal', []), ('no-output-error', ['read-error'])):
            result = subprocess.run([str(binary), *arguments], capture_output=True, text=True,
                env=environment, timeout=30)
            log = destination / (name + '-' + case + '.log')
            with log.open('x') as stream: stream.write(result.stdout + result.stderr)
            runs.append(dict(name=case, returncode=result.returncode, log_sha256=sha(log)))
            if legacy and arguments:
                assert result.returncode != 0 and 'MemorySanitizer: use-of-uninitialized-value' in result.stderr, result.stderr[-4000:]
                assert 'airoha_npu_wlan_irq_status_get' in result.stderr and "'val'" in result.stderr, result.stderr[-4000:]
            else:
                expected = '0' if arguments else '65536'
                assert result.returncode == 0 and result.stdout.strip() == expected, ('MSan-clean-case-failed', result.stderr[-4000:])
                assert 'MemorySanitizer:' not in result.stderr
        return dict(name=name, legacy=legacy, command=list(map(str, command)), runs=runs,
            source_sha256=sha(source), binary_sha256=sha(binary))
    executions = [execute_body(body, 'actual', False)]
    if args.legacy_source:
        legacy = args.legacy_source.resolve()
        assert legacy.is_relative_to(ROOT / '.local/npu-validation-capsules') and legacy.is_file()
        inputs[str(legacy.relative_to(ROOT))] = sha(legacy)
        old_body = loader.extract.function(legacy.read_text(), 'airoha_npu_wlan_irq_status_get')
        assert old_body != body
        executions.append(execute_body(old_body, 'preserved-legacy', True))
    inputs = native_prefix_snapshot.source_inputs(inputs)
    assert all(sha(ROOT / name) == expected for name, expected in inputs.items())
    record = dict(passed=True, inputs=inputs, executions=executions,
        actual_provider_getter=True, no_output_error_fixture=True, defined_zero_error_output=True,
        preserved_legacy_uninitialized_reproduced=args.legacy_source is not None,
        host_memory_sanitizer=True, physical_bus_fault_observed=False,
        source_fix='status-getter-output-only', checked_IRQ_contract=False, hardware=False,
        limits=['Exact extracted getter,with explicit synthetic regmap success and error-without-output fixtures.',
                'MSan instruments this host C program;this is not the real kernel,regmap bus or a physical router fault.',
                'Defined zero output fixes the getter value path only;checked-IRQ/error-channel/drain/lifecycle work remains.'])
    target = destination / 'result.json'
    with target.open('x') as stream: stream.write(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(passed=True, defined_zero_error_output=True,
        legacy_uninitialized_reproduced=args.legacy_source is not None, checked_IRQ_contract=False, sha256=sha(target))), flush=True)


if __name__ == '__main__': main()
