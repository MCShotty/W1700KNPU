#!/usr/bin/env python3
"""Exercise the actual queue-filtered getter; not a checked IRQ lifecycle."""
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


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--legacy-source', type=Path)
    args = parser.parse_args()
    assert args.name.replace('-', '').isalnum()
    destination = ROOT / '.local/npu-irq-queue-status' / args.name
    assert not destination.exists()
    destination.mkdir(parents=True)
    files = (PROVIDER, Path(__file__), Path(loader.__file__), Path(loader.extract.__file__))
    inputs = native_prefix_snapshot.source_inputs({str(p.relative_to(ROOT)): sha(p) for p in files})
    provider = PROVIDER.read_text()
    body = loader.extract.function(provider, 'airoha_npu_wlan_irq_status_get')
    constants = [line for line in provider.splitlines() if line.startswith('#define ') and
        line.split()[1].split('(')[0] in ('NPU_WLAN_BASE_ADDR', 'REG_IRQ_STATUS', 'NPU_IRQ_RX_MASK')]
    assert len(constants) == 3
    prefix = r'''
#include <assert.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
typedef uint32_t u32;
#define BIT(n) (1u << (n))
''' + '\n'.join(constants) + r'''
struct airoha_npu { void *regmap; };
static int cookie, error, supply_output;
static unsigned reads;
static u32 pending;
static int regmap_read(void *map, u32 reg, u32 *value) {
    assert(map==&cookie && reg==0x30d030u && value);
    reads++;
    if(supply_output) *value=pending;
    return error;
}
'''
    suffix = r'''
int main(void) {
    struct airoha_npu npu={&cookie};
    const u32 values[]={0,1,4,0x80000000u,0x10000u,0x20000u,0x30000u,
                        0x80030005u,0xffffffffu,0x5a010008u,0xa5020020u};
    const int errors[]={0,-5,-110};
    unsigned valid=0, invalid=0;
    for(int q=0;q<2;q++)for(unsigned v=0;v<sizeof(values)/sizeof(values[0]);v++)
        for(unsigned e=0;e<3;e++)for(int output=0;output<2;output++) {
            if(!e && !output) continue;
            pending=values[v]; error=errors[e]; supply_output=output; reads=0;
            u32 result=airoha_npu_wlan_irq_status_get(&npu,q);
            u32 mask=q ? 0x20000u : 0x10000u;
            assert(result==(error ? 0 : (pending&mask)));
            assert(reads==1 && pending==values[v] && npu.regmap==&cookie);
            valid++;
        }
    const int invalid_queues[]={INT_MIN,-1,2,31,INT_MAX};
    for(unsigned q=0;q<sizeof(invalid_queues)/sizeof(invalid_queues[0]);q++)
        for(unsigned null=0;null<2;null++) {
            reads=0; error=0; supply_output=1; pending=0xffffffffu;
            assert(airoha_npu_wlan_irq_status_get(null ? 0 : &npu,invalid_queues[q])==0);
            assert(!reads && pending==0xffffffffu && npu.regmap==&cookie);
            invalid++;
        }
    assert(valid==110 && invalid==10);
    printf("{\"passed\":true,\"valid_queue_cases\":%u,\"invalid_queue_cases\":%u}\n",valid,invalid);
    return 0;
}
'''
    environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',
                       UBSAN_OPTIONS='halt_on_error=1')

    def execute(candidate, name, expect_pass):
        source, binary = destination / (name + '.c'), destination / name
        with source.open('x') as stream:
            stream.write(prefix + candidate + suffix)
        command = [shutil.which('clang'), '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                   '-Wno-unused-parameter', '-fno-omit-frame-pointer', '-fsanitize=address,undefined',
                   str(source), '-o', str(binary)]
        loader.run(command, destination / (name + '.build.log'))
        result = subprocess.run([str(binary)], capture_output=True, text=True, env=environment, timeout=30)
        log = destination / (name + '.run.log')
        with log.open('x') as stream:
            stream.write(result.stdout + result.stderr)
        if expect_pass:
            assert result.returncode == 0, result.stderr[-4000:]
            assert json.loads(result.stdout) == dict(passed=True, valid_queue_cases=110, invalid_queue_cases=10)
        else:
            assert result.returncode != 0 and ('Assertion' in result.stderr or
                'AddressSanitizer' in result.stderr or 'runtime error:' in result.stderr), result.stderr[-4000:]
        return dict(name=name, expected_pass=expect_pass, returncode=result.returncode,
                    source_sha256=sha(source), binary_sha256=sha(binary), log_sha256=sha(log))

    actual = execute(body, 'actual', True)
    replacements = {
        'unfiltered': ('return val & NPU_IRQ_RX_MASK(q);', 'return val;'),
        'other-queue': ('NPU_IRQ_RX_MASK(q);', 'NPU_IRQ_RX_MASK(1-q);'),
        'both-queues': ('return val & NPU_IRQ_RX_MASK(q);', 'return val & (BIT(16)|BIT(17));'),
        'invalid-queue-read': ('\tif (q < 0 || q > 1)\n\t\treturn 0;\n', ''),
        'partial-error-value': ('if (regmap_read(npu->regmap, REG_IRQ_STATUS, &val))\n\t\treturn 0;',
                                'if (regmap_read(npu->regmap, REG_IRQ_STATUS, &val))\n\t\treturn val;'),
    }
    mutants = []
    for name, (old, new) in replacements.items():
        assert body.count(old) == 1, ('mutation-not-unique', name)
        mutants.append(execute(body.replace(old, new), name, False))
    legacy_result = None
    if args.legacy_source:
        legacy = args.legacy_source.resolve()
        assert legacy.is_relative_to(ROOT / '.local/npu-validation-capsules') and legacy.is_file()
        inputs[str(legacy.relative_to(ROOT))] = sha(legacy)
        old_body = loader.extract.function(legacy.read_text(), 'airoha_npu_wlan_irq_status_get')
        assert old_body != body
        legacy_result = execute(old_body, 'preserved-unfiltered', False)
    inputs = native_prefix_snapshot.source_inputs(inputs)
    assert all(sha(ROOT / name) == expected for name, expected in inputs.items())
    result = dict(passed=True, inputs=inputs, actual=actual, mutants=mutants, preserved_legacy=legacy_result,
                  valid_queue_cases=110, invalid_queue_cases=10, actual_provider_getter=True,
                  queue_mapping_from_current_provider=True, invalid_queue_no_register_access=True,
                  read_errors_zero_with_or_without_output=True, sanitizer='address,undefined,leak',
                  checked_IRQ_contract=False, physical_lost_interrupt_proof=False, hardware=False,
                  limits=['Exact getter and current provider constants; register reads and errors are synthetic.',
                          'No checked acknowledgement/mask/enable channel, concurrency, readiness, quarantine or drain.',
                          'Current queue bit mapping is not independently qualified on physical hardware.'])
    target = destination / 'result.json'
    with target.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, valid_queue_cases=110, invalid_queue_cases=10,
                         rejected_mutants=len(mutants), legacy_rejected=legacy_result is not None,
                         sha256=sha(target))), flush=True)


if __name__ == '__main__':
    main()
