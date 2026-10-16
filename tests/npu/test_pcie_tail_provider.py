#!/usr/bin/env python3
"""Actual retained-lifetime/provider predicates with explicit synthetic records."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
import test_provider_session as parent

ROOT = parent.ROOT
HARNESS = ROOT / 'tests/npu/pcie-tail-provider-harness.c'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--header', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert args.name.replace('-', '').isalnum()
    destination = ROOT / '.local/npu-pcie-tail-provider' / args.name
    assert not destination.exists()
    source, header = args.source.resolve(), args.header.resolve()
    paths = [source, header, HARNESS, parent.HARNESS, Path(__file__), Path(parent.__file__),
             Path(parent.loader.__file__), Path(parent.loader.extract.__file__),
             *[path for path in parent.SOURCE.rglob('*') if path.is_file()]]
    inputs = {str(path.relative_to(ROOT)): parent.loader.sha(path) for path in paths}
    command = parent.prepare(destination, source.read_text(), header.read_text())
    generated = destination / 'fixture.c'
    generated.write_text('#define main original_provider_main\n' + parent.HARNESS.read_text() +
        '\n#undef main\n#include "' + str(HARNESS) + '"\n')
    command = [generated if item == parent.HARNESS else item for item in command]
    flags = ['-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-Wno-unused-function', '-Wno-unused-variable']
    binary = destination / 'test'
    parent.loader.run(command + flags + ['-o', binary], destination / 'build.log')
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1')
    matrix = json.loads(parent.loader.run([binary], destination / 'run.log', env=env).stdout)
    assert matrix['passed'] and matrix['cases'] == 84 and matrix['native_admission'] is False
    text = source.read_text()
    helper = parent.loader.extract.function(text, 'airoha_npu_wlan_tail_lifetime_valid')
    original = (destination / 'provider-session.inc').read_text()
    mutations = {
        'omit-nonce-low': ('life->nonce_lo != control->client.base.nonce_lo ||', 'false ||'),
        'omit-rx-validity': ('!airoha_npu_wlan_rx_event_valid(priv) ||', 'false ||'),
        'omit-tx-validity': ('!airoha_npu_wlan_tx_buffer_valid(priv, i)', 'false'),
        'omit-tx-extents': ('life->tx_buffers[i].bytes != bytes[i] ||', 'false ||'),
        'omit-selected-tx2': ('control->tx2_register != life->endpoint_base + NPU_COLD_TX_REG2 &&',
                              'false &&')}
    rejected = []
    for name, (before, after) in mutations.items():
        target = destination / name
        target.mkdir()
        modified = parent.loader.once(helper, before, after)
        (destination / 'provider-session.inc').write_text(parent.loader.once(original, helper, modified))
        mutant = target / 'test'
        parent.loader.run(command + flags + ['-o', mutant], target / 'build.log')
        result = parent.loader.run([mutant], target / 'run.log', env=env, accepted=11)
        assert 'FAIL[session]' in result.stderr and 'AddressSanitizer' not in result.stderr
        rejected.append(dict(name=name, binary_sha256=parent.loader.sha(mutant), oracle=result.stderr.strip()))
    (destination / 'provider-session.inc').write_text(original)
    assert all(parent.loader.sha(ROOT / name) == digest for name, digest in inputs.items())
    receipt = dict(passed=True, matrix=matrix, mutants=rejected, inputs=inputs,
        binary_sha256=parent.loader.sha(binary), sanitizers=['address', 'undefined', 'leak'],
        native_tail_admission=False, full_setup=False, hardware=False,
        limits=['Actual read-only lifetime helper, existing geometry helpers and checked routing execute with synthetic retained records.',
                'Actual session/endpoint C uses modeled transport; no completed native owners or earlier SETUP are fabricated.',
                'Missing protocol history is rejected before transport; these fixtures do not prove original tail stores or physical lifetime.'])
    (destination / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=matrix['cases'], mutants=len(rejected), native_tail_admission=False)))


if __name__ == '__main__':
    main()
