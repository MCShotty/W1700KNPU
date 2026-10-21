#!/usr/bin/env python3
"""Execute the actual TX queue entry with explicit ownership/API fixtures."""
import argparse
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
import test_npu_host_lifetime as lifetime
from test_current_provider_module import ROOT, WORK, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    assert args.name.replace('-', '').isalnum()
    directory = ROOT / '.local/npu-checked-irq-tx' / args.name
    assert not directory.exists()
    directory.mkdir(parents=True)
    source = WORK / 'mt76-merged/dma.c'
    harness = Path(__file__).with_name('checked-irq-tx-harness.c')
    paths = (source, harness, Path(__file__).resolve(), Path(lifetime.__file__))
    inputs = {str(path.relative_to(ROOT)): digest(path) for path in paths}
    actual = lifetime.function(source.read_text(), 'mt76_dma_tx_queue_skb')
    assert harness.read_text().count('/* ACTUAL_TX */') == 1
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')
    def execute(body, name, passed):
        c, binary = directory / (name + '.c'), directory / name
        c.write_text(harness.read_text().replace('/* ACTUAL_TX */', body))
        command = [shutil.which('clang'), '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
            '-Wno-unused-parameter', '-Wno-sign-compare', '-fsanitize=address,undefined',
            '-fno-omit-frame-pointer', str(c), '-o', str(binary)]
        build = subprocess.run(command, capture_output=True, text=True, timeout=60)
        (directory / (name + '.build.log')).write_text(build.stdout + build.stderr)
        assert build.returncode == 0, build.stderr
        result = subprocess.run([str(binary)], env=env, capture_output=True, text=True, timeout=60)
        (directory / (name + '.run.log')).write_text(result.stdout + result.stderr)
        assert (result.returncode == 0) == passed
        if not passed:
            assert 'Assertion' in result.stderr
        return dict(passed=passed, returncode=result.returncode,
            observations=json.loads(result.stdout) if passed else None,
            source_sha256=digest(c), binary_sha256=digest(binary))
    result = execute(actual, 'actual', True)
    correct = '\t\tint err = mt76_npu_io_admit(dev);\n\n\t\tif (err) {\n\t\t\tret = err;\n\t\t\tgoto free_skb;\n\t\t}'
    assert actual.count(correct) == 1
    mutant = execute(actual.replace(correct,
        '\t\tret = mt76_npu_io_admit(dev);\n\t\tif (ret)\n\t\t\tgoto free_skb;'), 'clobber-default-error', False)
    assert all(digest(ROOT / name) == expected for name, expected in inputs.items())
    record = dict(passed=True, actual=result, rejected_mutant=mutant, inputs=inputs,
        entire_actual_tx_queue_body=True, IRQ_controller='explicit admission-return fixture',
        sanitizers=['address', 'undefined', 'leak'], hardware=False,
        limits=['Actual complete queue-entry C;skb,token-preparation,DMA/cache and callbacks are explicit host fixtures.',
            'Rejects new post-fault admission before mapping/preparation;does not establish in-flight drain or physical TX ownership.'])
    (directory / 'result.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=result['observations']['cases'], rejected_mutants=1,
        receipt_sha256=digest(directory / 'result.json'))), flush=True)


if __name__ == '__main__':
    main()
