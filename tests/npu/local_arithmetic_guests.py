"""Bounded synthetic RV32 probes, not original firmware or physical execution."""
import struct

from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_CODE, UC_QUERY_TIMEOUT
from unicorn import riscv_const as r


def exercise(fixtures):
    forms = ('mul', 'mulh', 'mulhsu', 'mulhu', 'div', 'divu', 'rem', 'remu', 'seqz')
    assert set(fixtures) == {'case_' + form + suffix for form in forms for suffix in ('', '_sp', '_zero')} | {'case_mul_framed'}
    registers = [getattr(r, 'UC_RISCV_REG_X' + str(index)) for index in range(32)]
    records = []
    for first, second in ((7, 3), (7, 0), (0x80000000, 0xffffffff)):
        for name, fixture in fixtures.items():
            negative, framed = name.endswith('_sp'), name == 'case_mul_framed'
            data, address = bytes.fromhex(fixture['bytes_hex']), fixture['address']
            assert address % 4 == 0 and 0x1000 <= address < address + len(data) <= 0x2000
            assert len(data) == (24 if framed else 8)
            cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
            cpu.mem_map(0x1000, 0x2000)
            cpu.mem_map(0x4000, 0x1000)
            cpu.mem_write(0x1000, b'\xcc' * 0x2000)
            cpu.mem_write(address, data)
            cpu.mem_write(0x4000, b'\xa5' * 0x1000)
            before = [(0x12340000 + index * 0x101) & 0xffffffff for index in range(32)]
            before[0], before[1], before[2] = 0, 0x2000, 0x4f00
            before[11:13] = [first, second]
            for register, value in zip(registers, before):
                cpu.reg_write(register, value)
            code_before = bytes(cpu.mem_read(0x1000, 0x2000))
            stack_before = bytes(cpu.mem_read(0x4000, 0x1000))
            pcs = []
            cpu.hook_add(UC_HOOK_CODE, lambda vm, pc, size, unused: pcs.append(pc))
            end = address + 4 if negative else 0x2000
            cpu.emu_start(address, end, count=20, timeout=1000000)
            assert not cpu.query(UC_QUERY_TIMEOUT), name
            after = [cpu.reg_read(register) & 0xffffffff for register in registers]
            changed = [index for index in range(32) if after[index] != before[index]]
            allowed = {2} if negative else set() if name.endswith('_zero') else {10}
            assert set(changed).issubset(allowed) and after[0] == 0, (name, changed)
            assert after[1] == before[1] and cpu.reg_read(r.UC_RISCV_REG_PC) == end
            if negative:
                assert after[2] != before[2] and len(pcs) == 1
            else:
                assert after[2] == before[2] and len(pcs) == (6 if framed else 2)
            assert bytes(cpu.mem_read(0x1000, 0x2000)) == code_before and 0x2000 not in pcs, name
            wanted = bytearray(stack_before)
            if framed:
                struct.pack_into('<I', wanted, before[2] - 4 - 0x4000, before[1])
            assert bytes(cpu.mem_read(0x4000, 0x1000)) == wanted, name
            records.append(dict(fixture=name, first=first, second=second, PC=end,
                instruction_PCs=pcs, changed_GPRs=changed, SP=after[2], zero=after[0],
                all_GPRs_compared_before_any_host_restore=True, exact_protected_code_and_stack=True))
    assert len(records) == 84
    return records
