#!/usr/bin/env python3
"""All six original API21 callbacks, exact writes and patterned native backing."""
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
import test_cold_tx_buffer as oracle
import test_bootstrap_v2_composition as composition

ROOT = composition.ROOT
CODE, HEAP, DATA, STACK, END = 0x84000000, 0x3e800000, 0x3e900000, 0x84038000, 0x841ffff0


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(ROOT) and not output.exists()
    code = composition.CODE_INPUT.read_bytes()
    assert hashlib.sha256(code).hexdigest() == 'e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643'
    inputs = {str(path.relative_to(ROOT)): sha(path) for path in
              (Path(__file__).resolve(), Path(oracle.__file__), composition.CODE_INPUT)}
    decoder = Cs(CS_ARCH_RISCV, CS_MODE_RISCV32 | CS_MODE_RISCVC)
    cases, sites = [], {}
    for step, selector in enumerate(oracle.SELECTORS):
        cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        cpu.mem_map(CODE, 0x200000)
        cpu.mem_write(CODE, code)
        cpu.mem_map(HEAP, 0x100000)
        cpu.mem_map(DATA, 0x10000)
        heap = bytearray((index * 73 + 19) % 251 + 1 for index in range(0x100000))
        data = bytearray((index * 31 + 41) % 251 + 1 for index in range(0x10000))
        struct.pack_into('<I', data, 0x30fc, oracle.PROFILE[0])
        struct.pack_into('<I', data, 0x2ab8, oracle.PROFILE[23])
        struct.pack_into('<III', data, 0x7000, 0x10 | selector, 21, oracle.PROFILE[3 + step])
        cpu.mem_write(HEAP, bytes(heap))
        cpu.mem_write(DATA, bytes(data))
        writes, calls = [], []

        def instruction(uc, pc, size, unused):
            calls.append(pc)
            if pc == 0x840048f4:
                uc.reg_write(r.UC_RISCV_REG_A0, 0)
                uc.reg_write(r.UC_RISCV_REG_PC, uc.reg_read(r.UC_RISCV_REG_RA))

        def store(uc, access, address, size, value, unused):
            if HEAP <= address < HEAP + 0x100000 or DATA <= address < DATA + 0x10000:
                writes.append((uc.reg_read(r.UC_RISCV_REG_PC), address, size, value & ((1 << (size * 8)) - 1)))

        cpu.hook_add(UC_HOOK_CODE, instruction)
        cpu.hook_add(UC_HOOK_MEM_WRITE, store)
        cpu.reg_write(r.UC_RISCV_REG_GP, DATA + 0x13a8)
        cpu.reg_write(r.UC_RISCV_REG_A0, DATA + 0x7000)
        cpu.reg_write(r.UC_RISCV_REG_SP, STACK)
        cpu.reg_write(r.UC_RISCV_REG_RA, END)
        cpu.emu_start(0x8400fbca, END, count=500000, timeout=3000000)
        assert cpu.reg_read(r.UC_RISCV_REG_PC) == END and cpu.reg_read(r.UC_RISCV_REG_SP) == STACK
        assert cpu.reg_read(r.UC_RISCV_REG_A0) == 1
        expected = [oracle.original(step, index) for index in range(oracle.COUNTS[step])]
        assert [(address, width, value) for _, address, width, value in writes] == expected
        for pc, address, width, value in writes:
            target, base = (data, DATA) if address >= DATA else (heap, HEAP)
            target[address - base:address - base + width] = value.to_bytes(width, 'little')
            if pc not in sites:
                decoded = list(decoder.disasm(code[pc - CODE:pc - CODE + 10], pc))
                assert decoded
                sites[pc] = dict(pc=pc, instruction=decoded[0].mnemonic + ' ' + decoded[0].op_str,
                                 width=width, following=[dict(pc=i.address, size=i.size, bytes=i.bytes.hex(),
                                     instruction=i.mnemonic + ' ' + i.op_str) for i in decoded[:2]])
        assert bytes(cpu.mem_read(HEAP, len(heap))) == heap
        assert bytes(cpu.mem_read(DATA, len(data))) == data
        assert bytes(cpu.mem_read(CODE, len(code))) == code
        assert 0x8400a614 not in calls and 0x840064b4 not in calls and 0x84004ff8 not in calls
        cases.append(dict(selector=selector, stores=len(writes), host=oracle.PROFILE[3 + step],
                          exact_recipe=True, exact_all_other_heap_data_bytes=True,
                          internal_records=512 if selector == 5 else 1024 if selector == 7 else 0,
                          l2_records=512 if selector in (10, 12) else 0,
                          callback_result=1, allocator_lock_called=False,
                          instruction_count=len(calls), store_pcs=sorted({pc for pc, _, _, _ in writes})))
        print(json.dumps(dict(selector=selector, stores=len(writes), exact_original_callback=True)), flush=True)
    assert all(sha(ROOT / name) == digest for name, digest in inputs.items())
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(dict(passed=True, cases=cases, sites=[sites[pc] for pc in sorted(sites)], inputs=inputs,
                       limits=['Original callback/lookup/fill/L2 instructions with patterned synthetic CODE/heap/DATA/stack backing.',
                               'Only printf is skipped. No candidate store detours, physical ownership, hardware or clients.']), stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(passed=True, selectors=len(cases), stores=sum(row['stores'] for row in cases), store_sites=len(sites))))


if __name__ == '__main__':
    main()
