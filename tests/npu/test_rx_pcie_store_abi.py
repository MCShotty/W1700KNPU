#!/usr/bin/env python3
"""Actual store trampoline/original continuation ABI with explicitly stubbed guards."""
import argparse
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r
import test_bootstrap_v2_composition as composition
import npu_image as image

ROOT = composition.ROOT
CODE, SRAM, SP, END = 0x84000000, 0x3e900000, 0x841e0000, 0x841ffff0
ADDRESS, VALUE = 0x3e902a90, 0x200d4590


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    pair, output = args.pair.resolve(), args.output.resolve()
    assert pair.is_relative_to(ROOT) and output.is_relative_to(ROOT / '.local') and not output.exists()
    manifest = json.loads((pair / 'manifest.json').read_bytes())
    code, data = [(pair / name).read_bytes() for name in ('CODE.bin', 'DATA.bin')]
    image.validate(code, data, manifest)
    path = ROOT / manifest['symbol_files']['cold-rx-pcie']
    symbols = composition.symbols(path)
    original = composition.CODE_INPUT.read_bytes()
    assert image.sha(original) == image.CODE_SHA
    registers = [getattr(r, 'UC_RISCV_REG_' + name) for name in
        ('RA', 'GP', 'TP', *('S' + str(i) for i in range(12)),
         *('T' + str(i) for i in range(7)), *('A' + str(i) for i in range(8)))]
    rows = []
    for reserve_ok, publish_ok in ((1, 1), (0, 1), (1, 0)):
        for seed in (0x10203040, 0x90807060):
            cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
            cpu.mem_map(CODE, 0x200000)
            cpu.mem_write(CODE, code)
            cpu.mem_map(SRAM, 0x8000)
            before = b'\xa5' * 0x8000
            cpu.mem_write(SRAM, before)
            saved = {reg: (seed + i * 0x1111) & 0xffffffff for i, reg in enumerate(registers)}
            saved[r.UC_RISCV_REG_RA] = END
            saved[r.UC_RISCV_REG_A5] = ADDRESS - 12
            saved[r.UC_RISCV_REG_S1] = VALUE
            caller_s1 = seed ^ 0x12345678
            for reg, value in saved.items():
                cpu.reg_write(reg, value)
            cpu.reg_write(r.UC_RISCV_REG_SP, SP - 16)
            # ra/s0 are already restored. Only original saved s1 is consumed.
            cpu.mem_write(SP - 16, struct.pack('<4I', 0xfeedface, caller_s1, 0xdeadbeef, 0xbad00bad))
            stores, calls = [], []
            def instruction(uc, pc, size, unused):
                if pc not in (symbols['npu_emulation_rx_pcie_reserve'], symbols['npu_emulation_rx_pcie_publish']):
                    return
                arguments = [uc.reg_read(getattr(r, 'UC_RISCV_REG_A' + str(i))) for i in range(3)]
                is_reserve = pc == symbols['npu_emulation_rx_pcie_reserve']
                assert arguments[:3 if is_reserve else 2] == ([ADDRESS, VALUE, 4] if is_reserve else [ADDRESS, 4])
                calls.append('reserve' if is_reserve else 'publish')
                resume = uc.reg_read(r.UC_RISCV_REG_RA)
                for i, reg in enumerate(registers[-15:]):
                    uc.reg_write(reg, 0xcc000000 + i)
                uc.reg_write(r.UC_RISCV_REG_A0, reserve_ok if is_reserve else publish_ok)
                uc.reg_write(r.UC_RISCV_REG_PC, resume)
            def write(uc, access, address, width, value, unused):
                if SRAM <= address < SRAM + 0x8000:
                    stores.append((uc.reg_read(r.UC_RISCV_REG_PC), address, width, value))
            cpu.hook_add(UC_HOOK_CODE, instruction)
            cpu.hook_add(UC_HOOK_MEM_WRITE, write)
            cpu.emu_start(symbols['npu_emulation_rx_pcie_ba88'], END, count=10000)
            assert cpu.reg_read(r.UC_RISCV_REG_PC) == END and cpu.reg_read(r.UC_RISCV_REG_SP) == SP
            assert calls == (['reserve', 'publish'] if reserve_ok else ['reserve'])
            assert stores == ([(symbols['npu_emulation_rx_pcie_ba88_store'], ADDRESS, 4, VALUE)] if reserve_ok else [])
            expected = bytearray(before)
            if reserve_ok:
                struct.pack_into('<I', expected, ADDRESS - SRAM, VALUE)
            assert bytes(cpu.mem_read(SRAM, 0x8000)) == expected
            saved[r.UC_RISCV_REG_S1] = caller_s1
            if not (reserve_ok and publish_ok):
                saved[r.UC_RISCV_REG_A0] = 0
            assert all(cpu.reg_read(reg) == value for reg, value in saved.items())
            assert bytes(cpu.mem_read(0x8400ba8c, 6)) == original[0xba8c:0xba92]
            rows.append(dict(reserve_ok=reserve_ok, publish_ok=publish_ok, seed=seed,
                             stores=stores, all_saved_registers=True, original_frame_bytes=16))
    inputs = {str(path.relative_to(ROOT)): composition.sha(path) for path in
        (Path(__file__), composition.CODE_INPUT, path, pair / 'CODE.bin', pair / 'DATA.bin', pair / 'manifest.json')}
    output.write_text(json.dumps(dict(passed=True, cases=rows, inputs=inputs,
        limits=['Actual raw trampoline and original16-byte continuation; guards are explicitly stubbed.',
                'This proves operand/register/frame/store ABI only, not native ownership admission or physical execution.']), indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=len(rows), exact_store=True, original_frame_bytes=16)))


if __name__ == '__main__':
    main()
