#!/usr/bin/env python3
"""Raw/count denials on a captured peer; fixture leases are not authority."""
import argparse
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
from test_bootstrap_native import ADM
from test_desc10_native_controls import ROOT, fixture
import test_npu_raw_pair as raw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists() and args.output.resolve().is_relative_to(ROOT / '.local')
    h, restore, record, inputs, drift = fixture(args.pair.resolve(), args.snapshot.resolve())
    inputs[str(Path(__file__).relative_to(ROOT))] = raw.composition.sha(Path(__file__))
    inputs['tests/npu/test_desc10_native_controls.py'] = raw.composition.sha(
        ROOT / 'tests/npu/test_desc10_native_controls.py')
    owner = h.desc10.symbols['npu_emulation_desc10_state']
    packet = h.packet.symbols['npu_emulation_packet_state']
    guarded = h.allocator_rv.symbols['npu_emulation_callback_guarded']
    rows = []
    cases = [('bad-count', value, False) for value in (0, 1, 511, 513, 65535, 0xffffffff)]
    cases += [('unmarked', 512, False), ('unmarked-modeled-lease', 512, True)]
    for name, value, modeled_lease in cases:
        restore()
        before = bytes(h.cpu.mem_read(packet, 2076))
        count_before = bytes(h.cpu.mem_read(0x3e902a7c, 2))
        pointer_before = h.get32(0x3e902cf4)
        request = record['request'].copy()
        if name == 'bad-count':
            request[13] = value
        else:
            request = [0x1a, 1, value]
        if modeled_lease:
            h.put32(ADM + 4, 1)
            h.put32(guarded, 1)
        reply = h.message(request)
        if name == 'bad-count':
            assert reply['flags'] == 7 and reply['words'][14] != 0, (name, value, reply)
        else:
            assert not (reply['flags'] == 7 and reply['words'][2] == 1), (name, reply)
        words = list(struct.unpack('<16I', h.cpu.mem_read(owner, 64)))
        assert words[4:11] == [0] * 7, (name, words)
        assert bytes(h.cpu.mem_read(packet, 2076)) == before
        assert bytes(h.cpu.mem_read(0x3e902a7c, 2)) == count_before
        assert h.get32(0x3e902cf4) == pointer_before
        assert h.cpu.mem_read(0x3e9046fa, 1)[0] == 0 and h.unmodeled is None
        rows.append(dict(name=name, value=value, modeled_lease=modeled_lease,
                         constructor_effects=0, retained_packet_claims=2560, reply=reply))
        print(json.dumps(dict(desc10_denial=name, value=value, passed=True)), flush=True)
    assert all(raw.composition.sha(ROOT / name) == digest for name, digest in inputs.items())
    result = dict(passed=True, cases=len(rows), controls=rows, inputs=inputs,
        diagnostic_prefix=True, snapshot_observer_input_drift=drift,
        fresh_loader_allocator_caller_proof=False,
        limits=['Actual raw guarded peer starts from an artifact-bound captured producing-run prefix.',
                'Restoration and the deliberately seeded lease are negative fixtures, not setup authority.',
                'Only malformed-count/unmarked admission and retained prefix are covered; no hardware/physical/client proof.'])
    with args.output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=len(rows), fresh_loader_allocator_caller_proof=False)))


if __name__ == '__main__':
    main()
