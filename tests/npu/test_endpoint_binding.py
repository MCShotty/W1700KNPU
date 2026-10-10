#!/usr/bin/env python3
"""Mutate the actual provider BAR binding and reuse its geometry/fault oracles."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
import test_provider_session as parent

ROOT, SOURCE, loader = parent.ROOT, parent.SOURCE, parent.loader


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    source = args.source.resolve()
    header = ROOT / '.local/merge-nonoc-20260923/kernel-merged/include/linux/soc/airoha/airoha_offload.h'
    dest = ROOT / '.local/npu-cold-pages-wire-20261010' / args.name
    assert source.is_relative_to(ROOT) and not dest.exists()
    dest.mkdir(parents=True)
    text, htext = source.read_text(), header.read_text()
    binding = loader.extract.function(text, 'airoha_npu_wlan_bind_endpoint_session')
    inputs = {str(p.relative_to(ROOT)): loader.sha(p) for p in
              (source, header, parent.HARNESS, Path(__file__), Path(parent.__file__),
               Path(loader.__file__), Path(loader.extract.__file__))}
    inputs |= {str(p.relative_to(ROOT)): loader.sha(p) for p in SOURCE.rglob('*') if p.is_file()}
    mutations = {
        'accept-wrong-type': loader.once(binding, 'type != 2', 'type == 99'),
        'accept-truncated-base': loader.once(binding, 'upper_32_bits(base)', '(upper_32_bits(base) == 99)'),
        'accept-truncated-size': loader.once(binding, 'upper_32_bits(bytes)', '(upper_32_bits(bytes) == 99)'),
        'skip-window-geometry': loader.once(binding, '!npu_cold_endpoint_valid(base, bytes)', 'false'),
        'skip-retained-overlap': loader.once(binding, 'if (base < (u64)', 'if (false && base < (u64)'),
        'omit-length-binding': loader.once(binding, 'command.api = NPU_COLD_BIND_BYTES_API;',
                                           'command.api = NPU_COLD_BIND_BASE_API;'),
    }
    rejected = []
    for name, function in mutations.items():
        directory = dest / name
        command = parent.prepare(directory, loader.once(text, binding, function), htext)
        binary = directory / 'test'
        loader.run(command + ['-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-o', binary],
                   directory / 'build.log')
        done = loader.run([binary], directory / 'run.log', accepted=11,
                          env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1'))
        assert 'FAIL[session]' in done.stderr and 'AddressSanitizer' not in done.stderr
        rejected.append(dict(name=name, binary_sha256=loader.sha(binary), oracle=done.stderr.strip()))
    assert all(loader.sha(ROOT / p) == digest for p, digest in inputs.items())
    result = dict(passed=True, mutants=rejected, inputs=inputs,
                  sanitizers=['address', 'undefined', 'leak'],
                  limits=['Actual binding/client/server C; kernel/PCI/backing and callback effects modeled.',
                          'Mutation rejection supports geometry/ordering coverage, not physical containment or complete setup.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, endpoint_mutants=len(rejected))))


if __name__ == '__main__':
    main()
