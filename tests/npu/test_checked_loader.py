#!/usr/bin/env python3
"""Actual checked-pair validation, runtime identity and publication fault cases."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import npu_image as image
import test_npu_firmware_loader as loader


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-loader-publish-20261010' / args.name
    assert not dest.exists()
    dest.mkdir(parents=True)
    source, pair = args.source.resolve(), args.pair.resolve()
    assert source.is_relative_to(ROOT) and pair.is_relative_to(ROOT)
    code, data = [(pair / name).read_bytes() for name in ('CODE.bin', 'DATA.bin')]
    image.validate(code, data, json.loads((pair / 'manifest.json').read_bytes()))
    harness = ROOT / 'tests/npu/checked-loader-harness.c'
    inputs = {str(path.relative_to(ROOT)): loader.sha(path) for path in
              (source, harness, loader.HARNESS, Path(__file__), Path(loader.__file__),
               Path(loader.extract.__file__), ROOT / 'tools/npu_image.py',
               *[pair / name for name in ('CODE.bin', 'DATA.bin', 'manifest.json')])}
    fragment = loader.fragment(source.read_text())
    (dest / 'firmware-loader.inc').write_text(fragment)
    binary = dest / 'test'
    flags = ['-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-Wno-sign-compare',
             '-Wno-unused-function', '-fno-pie', '-no-pie', '-fsanitize=address,undefined', '-fno-sanitize-recover=all']
    loader.run([shutil.which('gcc'), *flags, '-I' + str(dest), '-I' + str(ROOT / 'tests/npu'),
                harness, '-o', binary, '-lcrypto'], dest / 'build.log')
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1')
    cases = [('nominal', code, data, 0), ('rng-error', code, data, -4), ('rng-zero', code, data, -11),
             ('missing-ba', code, data, -22), ('missing-lease', code, data, -16),
             ('missing-buffer7', code, data, -22)]
    cases += [(f'readback-{i}', code, data, -5) for i in range(1, 20)]
    vendor = ROOT / '.local/npu-quiescence/firmware'
    cases += [('mixed-code', (vendor / 'en7581_MT7996_npu_rv32.bin').read_bytes(), data, -22),
              ('mixed-data', code, (vendor / 'en7581_MT7996_npu_data.bin').read_bytes(), -22)]
    for kind, offset in [('code-byte', 0x1000), ('data-byte', 0x1000),
                         ('code-magic', image.CODE_TAG_OFFSET), ('data-magic', image.DESCRIPTOR_OFFSET),
                         ('code-digest', image.DESCRIPTOR_OFFSET + 64), ('data-digest', image.DESCRIPTOR_OFFSET + 96)]:
        altered = bytearray(code if kind.startswith('code-') and kind not in ('code-digest',) else data)
        altered[offset] ^= 1
        cases.append((kind, bytes(altered) if len(altered) == len(code) else code,
                      bytes(altered) if len(altered) == len(data) else data, -22))
    for field in range(16):
        altered = bytearray(data)
        struct.pack_into('<I', altered, image.DESCRIPTOR_OFFSET + 4 * field,
                         struct.unpack_from('<I', altered, image.DESCRIPTOR_OFFSET + 4 * field)[0] ^ 1)
        cases.append((f'header-{field}', code, bytes(altered), -22))
    for field in range(8):
        altered_code = bytearray(code)
        struct.pack_into('<I', altered_code, image.CODE_TAG_OFFSET + 4 * field,
                         struct.unpack_from('<I', altered_code, image.CODE_TAG_OFFSET + 4 * field)[0] ^ 1)
        altered_data = bytearray(data)
        altered_data[image.DESCRIPTOR_OFFSET + 64:image.DESCRIPTOR_OFFSET + 96] = hashlib.sha256(altered_code).digest()
        cases.append((f'tag-{field}', bytes(altered_code), bytes(altered_data), -22))
    for name, offset in (('preseed-plan', 0x6300), ('preseed-session', 0x6380), ('preseed-identity', 0x63a0)):
        altered = bytearray(data)
        altered[offset] = 1
        altered[image.DESCRIPTOR_OFFSET + 96:] = hashlib.sha256(altered[:image.DESCRIPTOR_OFFSET]).digest()
        cases.append((name, code, bytes(altered), -22))
    rows = []
    for name, candidate_code, candidate_data, expected in cases:
        directory = dest / name
        directory.mkdir()
        (directory / 'CODE.bin').write_bytes(candidate_code)
        (directory / 'DATA.bin').write_bytes(candidate_data)
        done = loader.run([binary, directory / 'CODE.bin', directory / 'DATA.bin', directory, name, expected],
                          directory / 'run.log', env=env)
        row = json.loads(done.stdout)
        row['name'] = name
        rows.append(row)
        print(json.dumps(dict(case=name, passed=True, exposed=row['exposed'])), flush=True)
    mutations = [
        ('omit-code-digest', 'if (memcmp(digest, descriptor + 64, sizeof(digest)))', 'if (false)', 'code-byte'),
        ('omit-data-digest', 'if (memcmp(digest, descriptor + 96, sizeof(digest)))', 'if (false)', 'data-byte'),
        ('allow-seeded-session', 'memchr_inv(data->data + NPU_EN7581_NATIVE_SESSION, 0, 20)', 'false', 'preseed-session'),
        ('fixed-runtime-identity', 'get_random_bytes_wait(&identity, sizeof(identity))',
         '(identity = 0x9abcdef012345678ULL, 0)', 'nominal'),
        ('omit-plan-writes', 'writel(priv->native_plan[i / 2][i % 2],', 'writel(0,', 'nominal'),
        ('approve-plan-readback', 'priv->native_plan[i / 2][i % 2])\n\t\t\treturn -EIO;',
         'priv->native_plan[i / 2][i % 2] && false)\n\t\t\treturn -EIO;', 'readback-1'),
        ('omit-exposure-latch', 'life->exposed = true;', '(void)life;', 'nominal'),
        ('allow-second-load', 'if (priv->dma_lifetime && priv->dma_lifetime->exposed)',
         'if (false)', 'nominal'),
    ]
    rejected = []
    for name, old, new, case in mutations:
        assert fragment.count(old) == 1, name
        directory = dest / name
        directory.mkdir()
        (directory / 'firmware-loader.inc').write_text(fragment.replace(old, new))
        mutant = directory / 'test'
        loader.run([shutil.which('gcc'), *flags, '-I' + str(directory), '-I' + str(ROOT / 'tests/npu'),
                    harness, '-o', mutant, '-lcrypto'], directory / 'build.log')
        expected = next(row[3] for row in cases if row[0] == case)
        loader.run([mutant, dest / case / 'CODE.bin', dest / case / 'DATA.bin', directory, case, expected],
                   directory / 'run.log', env=env, accepted=11)
        rejected.append(dict(name=name, case=case, exit_code=11, binary_sha256=loader.sha(mutant)))
    assert all(loader.sha(ROOT / path) == digest for path, digest in inputs.items())
    result = dict(passed=True, cases=rows, rejected_mutants=rejected, inputs=inputs, binary_sha256=loader.sha(binary),
                  sanitizers=['address', 'undefined', 'leak'],
                  publication_output={name: loader.sha(dest / 'nominal' / name)
                                      for name in ('CODE-copied.bin', 'DATA-published.bin')},
                  limits=['Actual current Linux parser/RNG/publisher/one-shot C with OpenSSL SHA256 and modeled external dependencies.',
                          'Metadata readback/lifetime latch do not prove real containment,reset coverage,coherency/drains,hardware or clients.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=len(rows), mutants=len(rejected))))


if __name__ == '__main__':
    main()
