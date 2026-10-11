#!/usr/bin/env python3
"""Additive pointer-shape and actual TX-caller publication controls; synthetic I/O."""
import argparse
import ctypes
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
import test_cold_descriptor as core


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--core-receipt', type=Path, required=True)
    parser.add_argument('--host-receipt', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    destination = core.ROOT / '.local/npu-cold-descriptor-20261010' / args.name
    assert not destination.exists()
    destination.mkdir()
    inputs = {}
    for receipt in (args.core_receipt.resolve(), args.host_receipt.resolve()):
        value = json.loads(receipt.read_text())
        assert receipt.is_relative_to(core.ROOT) and value['passed']
        for path, digest in value['inputs'].items():
            assert core.loader.sha(core.ROOT / path) == digest
            assert path not in inputs or inputs[path] == digest
            inputs[path] = digest
        inputs[str(receipt.relative_to(core.ROOT))] = core.loader.sha(receipt)
    pair = core.Pair(args.core_receipt.resolve().parent / 'host.so',
                     args.core_receipt.resolve().parent / 'rv32.elf')
    pointer_rows = []
    for step in range(8):
        pair.prefix(step)
        baseline = list(pair.state)
        bad = (core.WORDS, core.WORDS + 1) if step < 6 else (0, core.WORDS + 1, core.WORDS + 2, core.WORDS + 3)
        for pointer in bad:
            pair.reset(baseline)
            result = pair.call('begin', 0x3e810000, 1, core.SELECTORS[step], pointer)
            assert result != core.OK
            pointer_rows.append(dict(step=step, operation='begin', pointer=pointer, status=result))
        pair.reset(baseline)
        assert pair.call('begin', 0x3e810000, 1, core.SELECTORS[step], int(step >= 6)) == core.OK
        count = 0 if step < 6 else 512 if step == 6 else 1024
        for index in range(count):
            address = 0x3e810000 + core.OFFSETS[step] + index * 16 + 4
            assert pair.call('reserve', 0x3e810000, 1, address, core.STATUS, pair.words[index * 4 + 1]) == core.OK
            pair.words[index * 4 + 1] = core.STATUS
            assert pair.call('publish', 0x3e810000, 1, address, core.STATUS) == core.OK
        active, words = list(pair.state), list(pair.words)
        for pointer in bad:
            pair.reset(active); pair.words[:] = words
            result = pair.call('finish', 0x3e810000, 1,
                               (0x3e810000 + core.OFFSETS[step]) & 0x1fffffff, pointer)
            assert result == core.PUBLISH
            pointer_rows.append(dict(step=step, operation='finish', pointer=pointer, status=result))
    host_receipt = json.loads(args.host_receipt.read_text())
    library = core.ROOT / host_receipt['shared']
    assert core.loader.sha(library) == host_receipt['shared_sha256']
    lib = ctypes.CDLL(str(library))
    peer_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
                                ctypes.POINTER(ctypes.c_uint32))
    lib.npu_host_txdesc.argtypes = [peer_type]
    lib.npu_host_txdesc_value.argtypes = [ctypes.c_uint]
    lib.npu_host_txdesc_value.restype = ctypes.c_uint32
    sequence = [(0x35,4,0),(0x10,21,0x90001000),(0x15,21,0x90002000),(0x1a,21,0x90003000),
                (0x37,4,0),(0x12,21,0x90004000),(0x17,21,0x90005000),(0x1c,21,0x90006000)]
    tx_rows = []
    for failure in range(9):
        calls, errors = [], []
        @peer_type
        def peer(header, api, value, output):
            index = len(calls)
            calls.append((header, api, value))
            if index >= len(sequence) or calls[-1] != sequence[index]:
                errors.append(calls[-1]); return -5
            if index == failure:
                return -71
            if api == 4:
                output[0] = 0x1e810000 + (0x6020 if header == 0x35 else 0x26040)
            return 0
        result = lib.npu_host_txdesc(peer)
        assert not errors and result == (0 if failure == 8 else -71)
        writes = int(failure > 0) + int(failure > 4)
        assert lib.npu_host_register_writes() == writes
        assert lib.npu_host_txdesc_value(1) == (0x1e816020 if failure > 0 else 0xabcdef01)
        assert lib.npu_host_txdesc_value(0) == (0x1e836040 if failure > 4 else 0xabcdef01)
        assert calls == sequence[:min(failure + 1,8)]
        tx_rows.append(dict(failure_position=failure, result=result, register_writes=writes,
                            values=[lib.npu_host_txdesc_value(index) for index in range(2)]))
    for path in (Path(__file__), library, args.core_receipt.resolve().parent / 'host.so',
                 args.core_receipt.resolve().parent / 'rv32.elf'):
        inputs[str(path.relative_to(core.ROOT))] = core.loader.sha(path)
    assert all(core.loader.sha(core.ROOT / path) == digest for path,digest in inputs.items())
    result = dict(passed=True, host_rv32_calls=pair.calls, pointer_controls=pointer_rows,
                  tx_caller_controls=tx_rows, inputs=inputs,
                  limits=['Exact previously qualified portable object and independent oracle; synthetic descriptor backing.',
                          'Actual host TX initializer with a synthetic peer, including modeled successful API21 replies.',
                          'No native API21, full hardware setup, physical ownership, DMA retirement or clients are established.'])
    (destination / 'result.json').write_text(json.dumps(result,indent=2) + '\n')
    print(json.dumps(dict(passed=True,pointer_controls=len(pointer_rows),tx_caller_cases=len(tx_rows),calls=pair.calls)))


if __name__ == '__main__':
    main()
