#!/usr/bin/env python3
"""Trace original PCIe pointer/index effects; no candidate admission or hardware."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
from capstone import Cs, CS_ARCH_RISCV, CS_MODE_RISCV32, CS_MODE_RISCVC
from unicorn import Uc, UcError, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_HOOK_MEM_INVALID
from unicorn import riscv_const as r

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / '.local/npu-quiescence/firmware/en7581_MT7996_npu_rv32.bin'
CODE, DATA, STACK, END = 0x84000000, 0x3e900000, 0x841e0000, 0x841ffff0
HOSTS = (0x56000000, 0x96000000)
INDEX_POINTERS = {5: 0x395c, 6: 0x2a80, 7: 0x4630, 8: 0x2a9c, 10: 0x2a90}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def index_sequences(code):
    results = []
    for count, missing in [(n, None) for n in (0, 1, 512, 65535)] + [(512, i) for i in range(5)]:
        cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        cpu.mem_map(CODE, 0x200000)
        cpu.mem_write(CODE, code)
        cpu.mem_map(DATA, 0x10000)
        cpu.mem_write(DATA, bytes((i * 31 + 41) % 251 + 1 for i in range(0x10000)))
        host = HOSTS[-1]
        cpu.mem_map(host, 0x1000)
        original_host = bytes((i * 17 + 3) % 251 + 1 for i in range(0x1000))
        cpu.mem_write(host, original_host)
        stores, faults = [], []

        def instruction(uc, pc, size, unused):
            if pc == 0x840048f4:
                uc.reg_write(r.UC_RISCV_REG_A0, 0)
                uc.reg_write(r.UC_RISCV_REG_PC, uc.reg_read(r.UC_RISCV_REG_RA))

        def write(uc, access, address, size, value, unused):
            if host <= address < host + 0x1000 or DATA <= address < DATA + 0x10000:
                stores.append((uc.reg_read(r.UC_RISCV_REG_PC), address, size, value & ((1 << (size * 8)) - 1)))

        def invalid(uc, access, address, size, value, unused):
            faults.append(dict(pc=uc.reg_read(r.UC_RISCV_REG_PC), address=address, access=access, bytes=size))
            return False

        cpu.hook_add(UC_HOOK_CODE, instruction)
        cpu.hook_add(UC_HOOK_MEM_WRITE, write)
        cpu.hook_add(UC_HOOK_MEM_INVALID, invalid)

        def invoke(selector, value):
            cpu.mem_write(DATA + 0x7000, struct.pack('<III', 0x10 | selector, 0, value))
            cpu.reg_write(r.UC_RISCV_REG_GP, DATA + 0x13a8)
            cpu.reg_write(r.UC_RISCV_REG_A0, DATA + 0x7000)
            cpu.reg_write(r.UC_RISCV_REG_SP, STACK)
            cpu.reg_write(r.UC_RISCV_REG_RA, END)
            cpu.emu_start(0x8400fdc4, END, count=20000, timeout=1000000)

        pointers = [host + 0x100 + i * 0x100 for i in range(5)]
        for (selector, offset), pointer in zip(INDEX_POINTERS.items(), pointers):
            invoke(selector, pointer)
            assert cpu.reg_read(r.UC_RISCV_REG_PC) == END
            assert struct.unpack('<I', bytes(cpu.mem_read(DATA + offset, 4)))[0] == pointer
        # Only the already established DESC10 count is modeled here.
        cpu.mem_write(DATA + 0x2a7c, struct.pack('<H', count))
        if missing is not None:
            offset = list(INDEX_POINTERS.values())[missing]
            cpu.mem_write(DATA + offset, bytes(4))
        cpu.mem_write(DATA + 0x7000, struct.pack('<III', 0x1f, 0, 0))
        before = bytes(cpu.mem_read(DATA, 0x10000))
        stores.clear()
        error = None
        try:
            invoke(15, 0)
        except UcError as failure:
            error = str(failure)
        expected = [(pointers[i] + 8, 4, value) for i, value in enumerate(
                    (255, 511, 1023, 1535, (count - 1) & 0xffffffff))]
        expected = expected if missing is None else expected[:missing]
        assert [(address, width, value) for _, address, width, value in stores] == expected
        modeled = bytearray(original_host)
        for address, width, value in expected:
            modeled[address - host:address - host + width] = value.to_bytes(width, 'little')
        assert bytes(cpu.mem_read(host, 0x1000)) == modeled
        assert bytes(cpu.mem_read(DATA, 0x10000)) == before
        assert bytes(cpu.mem_read(CODE, len(code))) == code
        returned = cpu.reg_read(r.UC_RISCV_REG_PC) == END
        assert returned == (missing is None)
        assert bool(faults) == (missing is not None)
        if returned:
            assert cpu.reg_read(r.UC_RISCV_REG_SP) == STACK and cpu.reg_read(r.UC_RISCV_REG_A0) == 1
        results.append(dict(modeled_descriptor_count=count, missing_pointer=missing, returned=returned,
                            stores=stores, faults=faults, error=error, earlier_writes_retained=True,
                            data_and_other_host_bytes_unchanged=True))
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(ROOT) and not output.exists()
    code = SOURCE.read_bytes()
    assert sha(SOURCE) == 'e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643'
    inputs = {str(p.relative_to(ROOT)): sha(p) for p in (Path(__file__).resolve(), SOURCE)}
    decoder = Cs(CS_ARCH_RISCV, CS_MODE_RISCV32 | CS_MODE_RISCVC)
    rows, sites = [], {}
    for selector in range(16):
        for value in (0, 1, 0x96000200, 0xffffffff):
            cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
            cpu.mem_map(CODE, 0x200000)
            cpu.mem_write(CODE, code)
            cpu.mem_map(DATA, 0x10000)
            original = bytes((i * 31 + 41) % 251 + 1 for i in range(0x10000))
            data = bytearray(original)
            struct.pack_into('<III', data, 0x7000, 0x10 | selector, 0, value)
            cpu.mem_write(DATA, bytes(data))
            before_hosts = {}
            for host in HOSTS:
                cpu.mem_map(host, 0x1000)
                before_hosts[host] = bytes((i * 17 + 3) % 251 + 1 for i in range(0x1000))
                cpu.mem_write(host, before_hosts[host])
            calls, writes, faults = [], [], []

            def instruction(uc, pc, size, unused):
                calls.append(pc)
                if pc == 0x840048f4:
                    uc.reg_write(r.UC_RISCV_REG_A0, 0)
                    uc.reg_write(r.UC_RISCV_REG_PC, uc.reg_read(r.UC_RISCV_REG_RA))

            def store(uc, access, address, size, stored, unused):
                if DATA <= address < DATA + len(data) or any(host <= address < host + 0x1000 for host in HOSTS):
                    pc = uc.reg_read(r.UC_RISCV_REG_PC)
                    writes.append((pc, address, size, stored & ((1 << (size * 8)) - 1)))
                    if pc not in sites:
                        decoded = next(decoder.disasm(code[pc - CODE:pc - CODE + 4], pc))
                        sites[pc] = dict(pc=pc, instruction=decoded.mnemonic + ' ' + decoded.op_str)

            def invalid(uc, access, address, size, stored, unused):
                faults.append(dict(pc=uc.reg_read(r.UC_RISCV_REG_PC), access=access, address=address, bytes=size))
                return False

            cpu.hook_add(UC_HOOK_CODE, instruction)
            cpu.hook_add(UC_HOOK_MEM_WRITE, store)
            cpu.hook_add(UC_HOOK_MEM_INVALID, invalid)
            cpu.reg_write(r.UC_RISCV_REG_GP, DATA + 0x13a8)
            cpu.reg_write(r.UC_RISCV_REG_A0, DATA + 0x7000)
            cpu.reg_write(r.UC_RISCV_REG_SP, STACK)
            cpu.reg_write(r.UC_RISCV_REG_RA, END)
            error = None
            try:
                cpu.emu_start(0x8400fdc4, END, count=20000, timeout=1000000)
            except UcError as failure:
                error = str(failure)
            expected_hosts = {host: bytearray(content) for host, content in before_hosts.items()}
            for _, address, size, stored in writes:
                if DATA <= address < DATA + len(data):
                    data[address - DATA:address - DATA + size] = stored.to_bytes(size, 'little')
                else:
                    host = next(host for host in HOSTS if host <= address < host + 0x1000)
                    expected_hosts[host][address - host:address - host + size] = stored.to_bytes(size, 'little')
            assert bytes(cpu.mem_read(DATA, len(data))) == data
            assert all(bytes(cpu.mem_read(host, 0x1000)) == content for host, content in expected_hosts.items())
            assert bytes(cpu.mem_read(CODE, len(code))) == code
            returned = cpu.reg_read(r.UC_RISCV_REG_PC) == END
            if returned:
                assert cpu.reg_read(r.UC_RISCV_REG_SP) == STACK
            rows.append(dict(selector=selector, supplied=value, returned=returned,
                             callback_result=cpu.reg_read(r.UC_RISCV_REG_A0) if returned else None,
                             writes=writes, faults=faults, error=error, final_pc=cpu.reg_read(r.UC_RISCV_REG_PC),
                             instructions=len(calls), other_mapped_bytes_unchanged=True))
    assert all(sha(ROOT / p) == digest for p, digest in inputs.items())
    sequences = index_sequences(code)
    with output.open('x') as stream:
        json.dump(dict(passed=True, observations=rows, index_sequences=sequences,
                       store_sites=list(sites.values()), inputs=inputs,
                       limits=['Observation matrix only: non-returning and unmapped-access cases are retained, not successes.',
                               'Original RV32 callback, patterned synthetic DATA/host regions and stack; only printf skipped.',
                               'Mapped-byte comparisons cover the declared DATA/host regions, not arbitrary unmapped or MMIO effects.',
                               'Five prior pointers are installed by original callbacks; the DESC10 count field alone is explicitly modeled for index-reset sequences.',
                               'No candidate API0 admission, host-register ownership, physical DMA/drain or client proof.']), stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(observations=len(rows), returned=sum(row['returned'] for row in rows),
                         faults=sum(bool(row['faults']) for row in rows), store_sites=len(sites),
                         index_sequences=len(sequences))))


if __name__ == '__main__':
    main()
