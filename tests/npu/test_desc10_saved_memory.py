#!/usr/bin/env python3
"""Reconcile retained replay bytes against a request-derived transaction oracle."""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from desc10_transaction_oracle import expected
from test_desc10_native_controls import ROOT, fixture
import test_npu_raw_pair as raw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--replay', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists() and args.output.resolve().is_relative_to(ROOT / '.local')
    replay_path = args.replay.resolve() / 'result.json'
    replay = json.loads(replay_path.read_bytes())
    assert replay['diagnostic_replay'] and replay['fresh_loader_allocator_caller_proof'] is False
    assert replay['native_returned'] and replay['error'] is None
    assert replay['reply']['flags'] == 7 and replay['reply']['words'][14] == 0
    assert replay['owner'][:11] == [0x31445443, 1, 0, 0, 25606, 25606, 25606, 512, 512, 512, 1]
    assert replay['packet_claims'] == 3072 and replay['rx_event_steps'] == 2 and replay['ready'] == 1
    h, _, record, inputs, drift = fixture(args.pair.resolve(), args.snapshot.resolve())
    wanted, _, footprint = expected(h, record['request'])
    rows = []
    assert list(map(lambda row: int(row['base'], 16), replay['differences'])) == list(wanted)
    for i, (base, image) in enumerate(wanted.items()):
        path = args.replay.resolve() / f'region-{i:02d}-actual.bin'
        actual = path.read_bytes()
        assert len(actual) == len(image) and raw.composition.sha(path) == replay['differences'][i]['actual_sha256']
        differences = [offset for offset, (a, b) in enumerate(zip(actual, image)) if a != b]
        rows.append(dict(base=hex(base), bytes=len(image), differing_bytes=len(differences),
                         first_addresses=[hex(base + offset) for offset in differences[:32]]))
        inputs[str(path.relative_to(ROOT))] = raw.composition.sha(path)
    for path in (Path(__file__).resolve(), ROOT / 'tests/npu/desc10_transaction_oracle.py',
                 ROOT / 'tests/npu/test_attach_tx_callbacks.py', replay_path):
        inputs[str(path.relative_to(ROOT))] = raw.composition.sha(path)
    assert all(raw.composition.sha(ROOT / name) == digest for name, digest in inputs.items())
    result = dict(passed=all(not row['differing_bytes'] for row in rows), regions=rows,
        transaction_sequence=footprint['transaction_sequence'], inputs=inputs,
        snapshot_observer_input_drift=drift, diagnostic_replay=True,
        fresh_loader_allocator_caller_proof=False,
        limits=['Expected bytes are rebuilt from the original captured prefix and request, never from post-state.',
                'Actual bytes are retained from the named diagnostic native replay; no region is excluded.',
                'This is diagnostic protected-memory agreement, not fresh full setup, physical/hardware or client acceptance.'])
    with args.output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=result['passed'], regions=rows,
                          transaction_sequence=footprint['transaction_sequence'], diagnostic_replay=True)))


if __name__ == '__main__':
    main()
