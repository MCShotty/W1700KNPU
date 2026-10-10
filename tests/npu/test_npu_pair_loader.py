#!/usr/bin/env python3
"""Exact raw pair through actual provider C; resource, firmware and I/O stubs."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import npu_image as image
import test_npu_firmware_loader as loader


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-raw-pair-20261010' / args.name
    assert not dest.exists()
    dest.mkdir(parents=True)
    pair = args.pair.resolve()
    manifest = json.loads((pair / 'manifest.json').read_bytes())
    code, data = [(pair / name).read_bytes() for name in ('CODE.bin', 'DATA.bin')]
    image.validate(code, data, manifest)
    lock = ROOT / 'firmware/source-lock.json'
    build = ROOT / json.loads(lock.read_text())['build_directory']
    source = build / 'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/linux-6.18.52' / loader.DRIVER
    fixtures = ROOT / 'tests/npu/fixtures/airoha-npu-6.18.52'
    reference = fixtures / 'provenance.json'
    upstream = fixtures / 'provider-upstream.c'
    assert loader.sha(upstream) == json.loads(reference.read_text())['files']['provider-upstream.c']
    replay = dest / 'replayed'
    replay_source = replay / loader.DRIVER
    replay_source.parent.mkdir(parents=True)
    shutil.copy2(upstream, replay_source)
    loader.run(['git', 'apply', '--include=' + loader.DRIVER, ROOT / loader.BASE_PATCH],
               dest / 'replay.log', cwd=replay,
               env=dict(os.environ, GIT_CEILING_DIRECTORIES=str(replay.parent)))
    assert source.read_bytes() == replay_source.read_bytes(), 'prepared-provider-differs-from-canonical-patch'
    harness = ROOT / 'tests/npu/raw-pair-loader-harness.c'
    paths = [source, reference, upstream, lock, ROOT / loader.BASE_PATCH, harness, loader.HARNESS, Path(loader.__file__),
             Path(loader.extract.__file__), ROOT / 'tools/npu_image.py', Path(__file__),
             *[pair / name for name in ('CODE.bin', 'DATA.bin', 'manifest.json')]]
    inputs = {str(path.relative_to(ROOT)): loader.sha(path) for path in paths}
    fragment = dest / 'firmware-loader.inc'
    fragment.write_text(loader.fragment(source.read_text()))
    compiler = shutil.which('gcc')
    assert compiler
    flags = ['-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-Wno-sign-compare',
             '-Wno-unused-function', '-fno-pie', '-no-pie', '-fsanitize=address,undefined', '-fno-sanitize-recover=all']
    binary = dest / 'loader'
    loader.run([compiler, *flags, '-I' + str(dest), '-I' + str(ROOT / 'tests/npu'), harness, '-o', binary], dest / 'build.log')
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1')
    matrix = json.loads(loader.run([binary], dest / 'matrix.log', env=env).stdout)
    rows = []
    for mode in ('nominal', 'missing-data', 'empty-code', 'empty-data', 'oversize-code', 'oversize-data', 'invalid-plan'):
        directory = dest / mode
        directory.mkdir()
        row = json.loads(loader.run([binary, pair / 'CODE.bin', pair / 'DATA.bin', directory, mode],
                                    directory / 'run.log', env=env).stdout)
        for name, payload, capacity in (('code', code, image.CODE_LIMIT), ('data', data, image.DATA_LIMIT)):
            readback = (directory / (name + '-memory.bin')).read_bytes()
            expected = bytes([0xa5]) * 16 + payload + bytes([0xa5]) * (capacity - len(payload) + 16)
            assert readback == (expected if mode == 'nominal' else bytes([0xa5]) * (capacity + 32))
            row[name + '_readback_sha256'] = image.sha(readback)
        row['mode'] = mode
        rows.append(row)
        print(json.dumps(dict(actual_c_pair=mode, copies=row['copies'], passed=True)), flush=True)
    assert all(loader.sha(ROOT / path) == digest for path, digest in inputs.items()), 'loader-inputs-changed'
    result = dict(passed=True, actual_provider_c=True, matrix=matrix, pair_cases=rows, inputs=inputs,
                  binary_sha256=loader.sha(binary), fragment_sha256=loader.sha(fragment),
                  sanitizers=['address', 'undefined', 'leak'],
                  limits=['Actual current provider C copies the exact raw pair; requests/resources/mapping/memcpy_toio remain modeled.',
                          'No probe boot trigger,per-boot loader publication,live replacement containment or physical cache/DMA proof.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, matrix_cases=matrix['cases'], exact_pair_cases=len(rows))))


if __name__ == '__main__':
    main()
