#!/usr/bin/env python3
"""Rejected callbacks cannot release another invocation's lock; modeled RV32 I/O."""
import argparse
import json
from pathlib import Path
import re
import struct
import sys

sys.dont_write_bytecode = True
import test_npu_raw_pair as raw
from test_firmware_mailbox_dispatch import PAYLOAD


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--expect-old-release', action='store_true',
                        help='Record the old counterexample; never counts as a fixed-code pass')
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    destination = raw.ROOT / '.local/npu-cold-descriptor-20261010' / args.name
    assert not destination.exists()
    destination.mkdir()
    pair = args.pair.resolve()
    rows = []
    for component, callback, command in (
        ('cold-pages', 'npu_emulation_indication_callback', (0x18, 1, 1536)),
        ('cold-tx', 'npu_emulation_tx_callback', (0x10, 19, 0x200d4420)),
        ('cold-descriptor', 'npu_emulation_descriptor_callback', (0x30, 4, 0)),
    ):
        h, _, files, manifest = raw.load(pair)
        symbols = raw.image.symbols(files[component])
        lock = symbols['lock_owned']
        assert h.get32(lock) == 0
        h.put32(lock, 1)
        h.cpu.mem_write(PAYLOAD, struct.pack('<3I', *command))
        first = len(h.mmio)
        assert h.direct(symbols[callback], PAYLOAD) == 0
        unlocks = [row for row in h.mmio[first:] if row['kind'] == 'mmio-write'
                   and row['address'] == '0x1ec03248']
        if args.expect_old_release:
            assert len(unlocks) == 1 and h.get32(lock) == 0
        else:
            assert not unlocks and h.get32(lock) == 1
        rows.append(dict(component=component, lock_preserved=h.get32(lock) == 1,
                         unlock_writes=unlocks, callback_rejected=True))
    result = dict(passed=not args.expect_old_release, counterexample=args.expect_old_release,
                  cases=rows, inputs={str(path.relative_to(raw.ROOT)): raw.composition.sha(path)
                                     for path in (Path(__file__), pair / 'CODE.bin', pair / 'DATA.bin', pair / 'manifest.json')},
                  limits=['Direct rejected native callbacks with test-seeded preowned flags and modeled I/O.',
                          'No physical lock ownership, full setup, DMA drain or hardware acceptance proof.'])
    (destination / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=result['passed'], counterexample=result['counterexample'], cases=len(rows))))


if __name__ == '__main__':
    main()
