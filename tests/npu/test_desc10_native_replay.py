#!/usr/bin/env python3
"""Captured-prefix DESC10 diagnostic with protected-memory differences."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace

sys.dont_write_bytecode = True
from unicorn import riscv_const as r
from test_attach_tx_callbacks import done_oracle
from test_desc10_native_controls import ROOT, fixture
import test_npu_raw_pair as raw


def compare(h, expected, directory):
    rows = []
    for index, (base, want) in enumerate(expected.items()):
        actual = bytes(h.cpu.mem_read(base, len(want)))
        offsets = [offset for offset, (a, b) in enumerate(zip(actual, want)) if a != b]
        name = f'region-{index:02d}'
        for suffix, data in (('actual', actual), ('expected', want)):
            with (directory / (name + '-' + suffix + '.bin')).open('xb') as stream:
                stream.write(data)
        examples = []
        for offset in offsets[:32]:
            begin, end = max(0, offset - 4), min(len(want), offset + 5)
            examples.append(dict(address=hex(base + offset), offset=offset,
                actual=actual[begin:end].hex(), expected=want[begin:end].hex(),
                context_address=hex(base + begin)))
        rows.append(dict(base=hex(base), bytes=len(want), differing_bytes=len(offsets),
                         actual_sha256=hashlib.sha256(actual).hexdigest(),
                         expected_sha256=hashlib.sha256(want).hexdigest(), examples=examples))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    directory = args.output.resolve()
    assert directory.is_relative_to(ROOT / '.local')
    directory.mkdir()
    h, _, record, inputs, drift = fixture(args.pair.resolve(), args.snapshot.resolve())
    for path in (Path(__file__).resolve(), ROOT / 'tests/npu/test_attach_tx_callbacks.py',
                 ROOT / 'tests/npu/test_desc10_native_controls.py'):
        inputs[str(path.relative_to(ROOT))] = raw.composition.sha(path)
    expected, _, footprint = done_oracle(SimpleNamespace(h=h, fixed=h.fixed), 512)
    reply, error = None, None
    try:
        reply = h.message(record['request'])
    except Exception as exc:
        error = dict(type=type(exc).__name__, message=str(exc))
    differences = compare(h, expected, directory)
    owner = h.desc10.symbols['npu_emulation_desc10_state']
    cold = h.rv.symbols['npu_emulation_cold_setup_state']
    packet = h.packet.symbols['npu_emulation_packet_state']
    result = dict(diagnostic_replay=True, fresh_loader_allocator_caller_proof=False,
        snapshot_origin=record['origin'], snapshot_observer_input_drift=drift,
        native_returned=reply is not None and error is None, reply=reply, error=error,
        owner=list(struct.unpack('<16I', h.cpu.mem_read(owner, 64))),
        packet_claims=h.get32(packet + 16), rx_event_steps=h.get32(cold + 380),
        ready=h.cpu.mem_read(0x3e9046fa, 1)[0], pc=hex(h.cpu.reg_read(r.UC_RISCV_REG_PC)),
        oracle_memory_matches=all(not row['differing_bytes'] for row in differences),
        differences=differences, oracle_footprint=footprint, inputs=inputs,
        limits=['Actual guarded RV32 executes from a hash-bound captured prefix, not fresh loader/allocator/caller setup.',
                'Actual and expected protected-memory bytes are retained, including any unexplained changes.',
                'MMIO, DMA/backing and scheduling are modeled; no physical, hardware or client proof.'])
    assert all(raw.composition.sha(ROOT / name) == digest for name, digest in inputs.items())
    with (directory / 'result.json').open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('diagnostic_replay', 'native_returned',
        'error', 'owner', 'packet_claims', 'rx_event_steps', 'ready', 'oracle_memory_matches')}))
    print(json.dumps(dict(differences=[row for row in differences if row['differing_bytes']])))


if __name__ == '__main__':
    main()
