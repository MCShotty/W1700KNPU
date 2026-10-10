#!/usr/bin/env python3
"""Actual pre-copy Linux request plan with native ABI, guards and mutants."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys

sys.dont_write_bytecode = True
import test_npu_firmware_loader as loader

ROOT = loader.ROOT
HARNESS = ROOT / 'tests/npu/provider-request-plan-harness.c'


def once(source, old, new):
    assert source.count(old) == 1, (old, source.count(old))
    return source.replace(old, new)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    source = args.source.resolve()
    assert source.is_relative_to(ROOT)
    dest = ROOT / '.local/npu-provider-plan-20261010' / args.name
    assert not dest.exists()
    dest.mkdir(parents=True)
    paths = [source, HARNESS, loader.HARNESS, Path(loader.__file__), Path(loader.extract.__file__), Path(__file__)]
    inputs = {str(path.relative_to(ROOT)): loader.sha(path) for path in paths}
    text = source.read_text()
    flags = ['-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-Wno-sign-compare',
             '-Wno-unused-function', '-fno-pie', '-no-pie', '-fsanitize=address,undefined', '-fno-sanitize-recover=all']
    compiler = shutil.which('gcc')
    assert compiler
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1')

    def build(name, contents):
        directory = dest / name
        directory.mkdir()
        fragment = directory / 'firmware-loader.inc'
        fragment.write_text(loader.fragment(contents))
        binary = directory / 'test'
        loader.run([compiler, *flags, '-I' + str(directory), '-I' + str(ROOT / 'tests/npu'),
                    HARNESS, '-o', binary], directory / 'build.log')
        return directory, binary

    nominal_dir, nominal = build('nominal', text)
    plan_path = nominal_dir / 'plan.bin'
    result = json.loads(loader.run([nominal, plan_path], nominal_dir / 'run.log', env=env).stdout)
    assert result['passed'] and plan_path.stat().st_size == 48
    print(json.dumps(dict(request_plan=result)), flush=True)
    mutants = {
        'accept-unaligned-request': once(text, 'if (!IS_ALIGNED(core->addr, sizeof(u32)))', 'if (false)'),
        'accept-outside-request-window': once(text, 'if (core->addr < 0x80000000ULL ||\n\t    core->addr > 0xc0000000ULL - AIROHA_NPU_MBOX_SIZE)', 'if (false)'),
        'accept-binary-overlap': once(text, 'if (resource_overlaps(&request, &priv->firmware_region))', 'if (false)'),
        'accept-wlan-overlap': once(text, 'if (resource_overlaps(&request, &priv->wlan_memory[i]))', 'if (false)'),
        'accept-pending-mailbox': once(text, 'if (core->mbox_pending)\n\t\treturn -EBUSY;', 'if (false)\n\t\treturn -EBUSY;'),
        'pin-fixture-address': once(text, 'priv->native_plan[5][0] = request.start;', 'priv->native_plan[5][0] = 0x82000000;'),
        'accept-incomplete-ba-plan': once(text, 'if (priv->wlan_memory_count != 4 ||', 'if (false ||'),
        'accept-relocated-native-code': once(text, 'priv->firmware_region.start != 0x84000000ULL', 'false'),
        'retain-plan-after-load-failure': once(text,
            '\t\tpriv->wlan_request_valid = false;\n\t\tpriv->native_plan_ready = false;\n'
            '\t\tmemset(&priv->wlan_request, 0, sizeof(priv->wlan_request));\n'
            '\t\tmemset(priv->native_plan, 0, sizeof(priv->native_plan));\n', ''),
    }
    rejected = []
    for name, contents in mutants.items():
        directory, binary = build(name, contents)
        loader.run([binary, directory / 'plan.bin'], directory / 'run.log', env=env, accepted=11)
        assert 'FAIL[provider-request-plan]' in (directory / 'run.log').read_text()
        rejected.append(name)
        print(json.dumps(dict(rejected_mutant=name)), flush=True)
    assert all(loader.sha(ROOT / path) == digest for path, digest in inputs.items()), 'inputs-changed'
    receipt = dict(passed=True, actual_provider_c=True, matrix=result, rejected_mutants=rejected, inputs=inputs,
                   plan=dict(path=str(plan_path.relative_to(ROOT)), sha256=loader.sha(plan_path)),
                   binary_sha256=loader.sha(nominal), sanitizers=['address', 'undefined', 'leak'],
                   limits=['Private native-plan/request snapshot from actual provider C; allocations/OF/I/O remain modeled.',
                           'No SRAM publication,boot identity,reset containment,physical drains,hardware or clients.'])
    (dest / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=result['request_cases'], rejected_mutants=len(rejected))))


if __name__ == '__main__':
    main()
