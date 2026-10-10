#!/usr/bin/env python3
"""Actual DMA lease cleanup/exposure functions and their compiled-kernel form."""
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    source = args.source.resolve()
    dest = ROOT / '.local/npu-loader-publish-20261010' / args.name
    assert source.is_relative_to(ROOT) and not dest.exists()
    dest.mkdir(parents=True)
    text = source.read_text()
    q = loader.extract
    declarations = [q.declaration(text, 'struct', name) for name in ('airoha_npu_dma_lifetime', 'airoha_npu_priv')]
    globals_text = 'static LIST_HEAD(airoha_npu_retained_dma);\nstatic DEFINE_MUTEX(airoha_npu_retained_lock);\n'
    functions = [q.function(text, name) for name in ('airoha_npu_dma_retained', 'airoha_npu_dma_cleanup', 'airoha_npu_firmware_expose')]
    contents = '\n\n'.join(declarations) + '\n' + globals_text + '\n\n'.join(functions)
    harness = ROOT / 'tests/npu/dma-lifetime-harness.c'
    inputs = {str(p.relative_to(ROOT)): loader.sha(p) for p in (source, harness, Path(__file__), Path(q.__file__))}
    flags = ['-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-Wno-sign-compare', '-Wno-unused-function',
             '-fsanitize=address,undefined', '-fno-sanitize-recover=all']
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1')

    def run(name, fragment, expected=0):
        directory = dest / name
        directory.mkdir()
        (directory / 'lease.inc').write_text(fragment)
        binary = directory / 'test'
        loader.run([shutil.which('gcc'), *flags, '-I' + str(directory), harness, '-o', binary], directory / 'build.log')
        done = loader.run([binary], directory / 'run.log', env=env, accepted=expected)
        return done, binary

    done, binary = run('nominal', contents)
    matrix = json.loads(done.stdout)
    probe = q.function(text, 'airoha_npu_probe')
    assert probe.index('devm_add_action_or_reset') < probe.index('devm_work_autocancel') < probe.index('devm_request_irq') < probe.index('dma_alloc_coherent')
    assert probe.index('airoha_npu_dma_retained(dev)') < probe.index('priv->dma_lifetime = kzalloc')
    assert 'dmam_alloc_coherent' not in probe
    mutations = [('free-exposed-mailboxes', 'if (life->exposed) {', 'if (false) {'),
                 ('omit-exposure-latch', 'life->exposed = true;', '(void)life;'),
                 ('omit-module-pin', '__module_get(THIS_MODULE);', '(void)THIS_MODULE;'),
                 ('allow-retained-reprobe', 'retained = true;', 'retained = false;')]
    rejected = []
    for name, old, new in mutations:
        assert contents.count(old) == 1
        _, _ = run(name, contents.replace(old, new), expected=-6)
        rejected.append(name)
    assert all(loader.sha(ROOT / path) == digest for path, digest in inputs.items())
    result = dict(passed=True, matrix=matrix, rejected_mutants=rejected, inputs=inputs,
                  binary_sha256=loader.sha(binary), cleanup_before_cpu_producers=True,
                  limits=['Actual cleanup/exposure C; allocation/refs/list/devres and retirement are modeled.',
                          'Post-exposure retention is conservative and permanent until real retirement work exists; not containment/drain proof.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=matrix['cases'], mutants=len(rejected))))


if __name__ == '__main__':
    main()
