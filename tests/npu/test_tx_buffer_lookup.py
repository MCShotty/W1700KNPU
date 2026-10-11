#!/usr/bin/env python3
"""Execute original API21 typed lookup paths, not the full TX initializer."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.riscv_const import UC_RISCV_REG_A0, UC_RISCV_REG_PC, UC_RISCV_REG_RA, UC_RISCV_REG_SP

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = ROOT / 'research/checkpoints/2026-09-05-npu-admission/ghidra-mailbox/en7581_MT7996_npu_rv32.bin.txt'
ORIGINAL_SHA = '1536a9972838ca7c02da77629e784b392af919c5d25368478aff4d0c2422e2ca'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    pair = args.pair.resolve()
    assert pair.is_relative_to(ROOT) and sha(ORIGINAL) == ORIGINAL_SHA
    manifest = json.loads((pair / 'manifest.json').read_bytes())
    inputs = dict(manifest['inputs'])
    for path in (Path(__file__).resolve(), ORIGINAL, pair / 'CODE.bin', pair / 'manifest.json'):
        inputs[str(path.relative_to(ROOT))] = sha(path)
    assert all(sha(ROOT / path) == digest for path, digest in inputs.items())
    code = (pair / 'CODE.bin').read_bytes()
    assert struct.unpack_from('<II', code, 0x1cf70) == (0x100, 0x3e8a2000)
    assert struct.unpack_from('<II', code, 0x1cf78) == (0x101, 0x3e8a4020)
    rows = []

    def execute(name, kind, expected, changes=()):
        cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        cpu.mem_map(0x84000000, 0x100000)
        cpu.mem_write(0x84000000, code)
        cpu.mem_map(0x3e8ff000, 4096)
        for offset, value in changes:
            cpu.mem_write(0x84000000 + offset, struct.pack('<I', value))
        cpu.reg_write(UC_RISCV_REG_A0, kind)
        cpu.reg_write(UC_RISCV_REG_SP, 0x3e900000)
        cpu.reg_write(UC_RISCV_REG_RA, 0x840ffff0)
        calls, writes = [], []
        cpu.hook_add(UC_HOOK_CODE, lambda uc, pc, size, data: calls.append(pc))
        cpu.hook_add(UC_HOOK_MEM_WRITE, lambda uc, access, address, size, value, data: writes.append(address))
        cpu.emu_start(0x84005200, 0x840ffff0, count=1000)
        actual = cpu.reg_read(UC_RISCV_REG_A0)
        assert cpu.reg_read(UC_RISCV_REG_PC) == 0x840ffff0 and actual == expected
        assert 0x84004ff8 not in calls and not writes
        assert cpu.reg_read(UC_RISCV_REG_SP) == 0x3e900000
        rows.append(dict(name=name, type=kind, output=actual, dynamic_allocator_called=False,
                         memory_writes=len(writes), instructions=len(calls)))

    execute('type100', 0x100, 0x3e8a2000)
    execute('type101', 0x101, 0x3e8a4020)
    execute('missing-table-type100', 0x100, 0, ((0x1cf70, 0xffff),))
    execute('missing-table-type101', 0x101, 0, ((0x1cf70, 0xffff),))
    execute('unaligned-pointer-returned', 0x100, 1, ((0x1cf74, 1),))
    execute('out-of-backing-pointer-returned', 0x101, 0xffffffff, ((0x1cf7c, 0xffffffff),))
    assert all(sha(ROOT / path) == digest for path, digest in inputs.items())
    destination = ROOT / '.local/npu-cold-descriptor-20261010' / args.name
    assert not destination.exists()
    destination.mkdir()
    result = dict(passed=True, cases=rows, inputs=inputs,
                  limits=['Original RV32 lookup instructions with synthetic CODE/stack backing.',
                          'No API21 helper initialization, physical memory ownership or host DMA lifetime acceptance.',
                          'Mutation returns are counterexamples to pointer validation, not acceptable production pointers.'])
    (destination / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, lookup_cases=len(rows), dynamic_allocator_called=False)))


if __name__ == '__main__':
    main()
