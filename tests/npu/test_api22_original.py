#!/usr/bin/env python3
"""Original RX-event address callback effects, not candidate admission or DMA proof."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
from capstone import Cs, CS_ARCH_RISCV, CS_MODE_RISCV32, CS_MODE_RISCVC
from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / '.local/npu-quiescence/firmware/en7581_MT7996_npu_rv32.bin'
CODE, DATA, STACK, END = 0x84000000, 0x3e900000, 0x84038000, 0x841ffff0
SLOTS = {0: 0x3964, 5: 0x2a94, 6: 0x2aa4, 7: 0x4638}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(ROOT) and not output.exists()
    assert sha(SOURCE) == 'e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643'
    code = SOURCE.read_bytes()
    decoder = Cs(CS_ARCH_RISCV, CS_MODE_RISCV32 | CS_MODE_RISCVC)
    rows, sites = [], {}
    inputs = {str(path.relative_to(ROOT)): sha(path) for path in (Path(__file__).resolve(), SOURCE)}
    for selector in range(16):
        for value in (0, 1, 0x96000001, 0xffffffff):
            cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
            cpu.mem_map(CODE, 0x200000)
            cpu.mem_write(CODE, code)
            cpu.mem_map(DATA, 0x10000)
            data = bytearray((i * 31 + 41) % 251 + 1 for i in range(0x10000))
            struct.pack_into('<III', data, 0x7000, 0x10 | selector, 22, value)
            cpu.mem_write(DATA, bytes(data))
            calls, writes = [], []
            def instruction(uc, pc, size, unused):
                calls.append(pc)
                if pc == 0x840048f4:
                    uc.reg_write(r.UC_RISCV_REG_A0, 0)
                    uc.reg_write(r.UC_RISCV_REG_PC, uc.reg_read(r.UC_RISCV_REG_RA))
            def store(uc, access, address, size, stored, unused):
                if DATA <= address < DATA + len(data):
                    writes.append((uc.reg_read(r.UC_RISCV_REG_PC), address, size, stored & ((1 << (size * 8)) - 1)))
            cpu.hook_add(UC_HOOK_CODE, instruction)
            cpu.hook_add(UC_HOOK_MEM_WRITE, store)
            cpu.reg_write(r.UC_RISCV_REG_GP, DATA + 0x13a8)
            cpu.reg_write(r.UC_RISCV_REG_A0, DATA + 0x7000)
            cpu.reg_write(r.UC_RISCV_REG_SP, STACK)
            cpu.reg_write(r.UC_RISCV_REG_RA, END)
            cpu.emu_start(0x8400fbb4, END, count=10000, timeout=1000000)
            assert cpu.reg_read(r.UC_RISCV_REG_PC) == END and cpu.reg_read(r.UC_RISCV_REG_SP) == STACK
            assert cpu.reg_read(r.UC_RISCV_REG_A0) == 1
            assert [(address, width) for _, address, width, _ in writes] == (
                [(DATA + SLOTS[selector], 4)] if selector in SLOTS else [])
            for pc, address, width, stored in writes:
                data[address - DATA:address - DATA + width] = stored.to_bytes(width, 'little')
                if pc not in sites:
                    decoded = next(decoder.disasm(code[pc - CODE:pc - CODE + 4], pc))
                    sites[pc] = dict(pc=pc, instruction=decoded.mnemonic + ' ' + decoded.op_str)
            assert bytes(cpu.mem_read(DATA, len(data))) == data
            assert bytes(cpu.mem_read(CODE, len(code))) == code
            assert 0x840064b4 not in calls and 0x84004ff8 not in calls
            rows.append(dict(selector=selector, supplied=value, callback_result=1,
                             writes=writes, other_data_unchanged=True,
                             allocator_lock_called=False, instructions=len(calls)))
    transformed = [row for row in rows if row['writes']]
    candidates = {
        'raw-or-40000000': lambda value: value | 0x40000000,
        'masked-30bit-or-40000000': lambda value: (value & 0x3fffffff) | 0x40000000,
    }
    compatible = [name for name, transform in candidates.items()
                  if all(row['writes'][0][3] == transform(row['supplied']) for row in transformed)]
    assert all(sha(ROOT / name) == digest for name, digest in inputs.items())
    with output.open('x') as stream:
        json.dump(dict(passed=True, cases=rows, store_sites=list(sites.values()),
                       compatible_alias_formulas=compatible, inputs=inputs,
                       limits=['Original RV32 callback/helper with patterned synthetic DATA and stack; only printf skipped.',
                               'Formula compatibility covers these explicit vectors; source review and candidate lifetime/extent admission remain required.',
                               'No candidate API22 admission, host queue lifetime, descriptor ownership, physical DMA or client proof.']), stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(passed=True, cases=len(rows), accepted_selectors=sorted(SLOTS),
                         stores=len(transformed), compatible_alias_formulas=compatible)))


if __name__ == '__main__':
    main()
