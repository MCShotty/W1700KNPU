#!/usr/bin/env python3
"""Actual raw guard rejects synthetic unleased DESC10; no fresh setup proof."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import sys

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UcError, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r
from unicorn import __version__ as UNICORN_VERSION

import npu_image as image
from emulation_layout import CODE, SRAM, STATE
from test_attach_tx_callbacks import IMAGES, HOST, HOST_BYTES, SKB_STATE, SKB_BYTES
from test_bootstrap_native import ADM
from test_firmware_mailbox_dispatch import PAYLOAD
from test_firmware_memory_layout import STACK_TOPS
from test_firmware_stop_counterexample import END

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(pair):
    assert pair.is_relative_to(ROOT)
    manifest = json.loads((pair / 'manifest.json').read_text())
    code, data = (pair / 'CODE.bin').read_bytes(), (pair / 'DATA.bin').read_bytes()
    image.validate(code, data, manifest)
    inputs = dict(manifest['inputs'])
    symbols, writable = {}, []
    for name, relative in manifest['symbol_files'].items():
        path = ROOT / relative
        assert sha(path) == manifest['components'][name]['sha256']
        inputs[relative] = sha(path)
        binary = ELFFile(io.BytesIO(path.read_bytes()))
        for symbol in binary.get_section_by_name('.symtab').iter_symbols():
            if symbol['st_shndx'] == 'SHN_UNDEF' or not symbol.name.startswith('npu_'):
                continue
            previous = symbols.get(symbol.name)
            if previous is None or symbol['st_size'] > previous[1]:
                symbols[symbol.name] = (symbol['st_value'], symbol['st_size'])
        if name == 'cold-txdone':
            writable = [(s['sh_addr'], s['sh_addr'] + s['sh_size']) for s in binary.iter_sections()
                        if s['sh_flags'] & 3 == 3 and s['sh_size']]
    assert symbols['npu_emulation_admission_state'][0] == ADM
    assert symbols['npu_emulation_barrier_state'][0] == STATE
    setup, setup_bytes = symbols['npu_emulation_cold_setup_state']
    owner, owner_bytes = symbols['npu_emulation_desc10_state']
    packet, packet_bytes = symbols['npu_emulation_packet_state']
    assert setup_bytes in (0, 404) and owner_bytes == 13512 and packet_bytes == 2076
    stack = (STACK_TOPS[0] - 0x4000, STACK_TOPS[0])
    spaces = (*IMAGES, (HOST, HOST_BYTES), (SKB_STATE, SKB_BYTES))
    rows = []
    for mode in ('unmarked', 'legacy-modeled-lease', 'command-without-prior-owners'):
        for irq in (0, 8):
            cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
            cpu.mem_map(CODE, image.CODE_LIMIT + 0x1000)
            cpu.mem_write(CODE, code)
            for base, size in spaces:
                cpu.mem_map(base, size)
            cpu.mem_write(SRAM, data)
            cpu.mem_map(PAYLOAD & ~0xfff, 0x1000)
            cpu.mem_write(PAYLOAD, struct.pack('<3I', 0x1a, 1, 512) + bytes(12))

            def put(address, value):
                cpu.mem_write(address, struct.pack('<I', value))

            for name in ('npu_emulation_admission_state', 'npu_emulation_barrier_state',
                         'npu_emulation_cold_setup_state', 'npu_emulation_packet_state',
                         'npu_emulation_rx_event_state', 'npu_emulation_desc10_state'):
                address, size = symbols[name]
                if not size:
                    size = {'npu_emulation_admission_state': 44, 'npu_emulation_barrier_state': 104,
                            'npu_emulation_cold_setup_state': 404}[name]
                cpu.mem_write(address, bytes(size))
            put(packet + 16, 2560)
            cpu.mem_write(SRAM + 0x46fa, b'\0')
            if mode != 'unmarked':
                put(ADM + 4, 1)
                put(SRAM + 0x3964, HOST)
                put(SRAM + 0x3974, 0x87654321)
            if mode == 'command-without-prior-owners':
                put(setup + 4, 1)
                for offset, value in ((36, 0x1a), (40, 1), (44, 512), (380, 1), (384, 1)):
                    put(setup + offset, value)
                for address, value in ((SRAM + 0x17c, 0x8400fe34), (SRAM + 0xbc0, 8192),
                    (SRAM + 0x1b9c, 28), (SRAM + 0x1bb8, 19), (SRAM + 0x1bc4, 20),
                    (SRAM + 0x1b88, 0x3e810000), (SRAM + 0x1b84, 0x3e820000),
                    (SRAM + 0x1bc0, 0x3e830000), (SRAM + 0x1bd4, 0)):
                    put(address, value)
            cpu.reg_write(r.UC_RISCV_REG_SP, STACK_TOPS[0])
            cpu.reg_write(r.UC_RISCV_REG_RA, END)
            cpu.reg_write(r.UC_RISCV_REG_A0, PAYLOAD)
            cpu.reg_write(r.UC_RISCV_REG_GP, SRAM + 0x13a8)
            cpu.reg_write(r.UC_RISCV_REG_MSTATUS, irq)
            saved = {getattr(r, 'UC_RISCV_REG_S' + str(i)): 0xa1000000 + i * 0x101 for i in range(12)}
            saved[r.UC_RISCV_REG_GP] = SRAM + 0x13a8
            saved[r.UC_RISCV_REG_TP] = 0x98765430
            for register, value in saved.items():
                cpu.reg_write(register, value)
            before = {base: bytes(cpu.mem_read(base, size)) for base, size in spaces}
            code_before = bytes(cpu.mem_read(CODE, image.CODE_LIMIT))
            packet_before = bytes(cpu.mem_read(packet, packet_bytes))
            owner_before = bytes(cpu.mem_read(owner, owner_bytes))
            hits, code_writes = [], []

            def instruction(uc, pc, size, unused):
                hits.append(pc)

            def write(uc, access, address, size, value, unused):
                code_writes.append((address, size))
                assert any(begin <= address and address + size <= end for begin, end in (*writable, stack)), (
                    mode, 'unexpected-code-write', hex(address), size)

            for pc in (symbols['npu_emulation_desc10_callback'][0], 0x8400dd82, 0x8400b432):
                cpu.hook_add(UC_HOOK_CODE, instruction, begin=pc, end=pc)
            cpu.hook_add(UC_HOOK_MEM_WRITE, write, begin=CODE, end=CODE + image.CODE_LIMIT - 1)
            try:
                cpu.emu_start(0x8400fe34, END, count=3000000, timeout=10000000)
            except UcError as error:
                raise AssertionError(dict(mode=mode, pc=hex(cpu.reg_read(r.UC_RISCV_REG_PC)),
                    ra=hex(cpu.reg_read(r.UC_RISCV_REG_RA)), sp=hex(cpu.reg_read(r.UC_RISCV_REG_SP)),
                    end=hex(END), hits=[hex(pc) for pc in hits])) from error
            assert cpu.reg_read(r.UC_RISCV_REG_PC) == END and cpu.reg_read(r.UC_RISCV_REG_A0) == 0
            assert cpu.reg_read(r.UC_RISCV_REG_SP) == STACK_TOPS[0]
            assert cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8 == irq
            assert all(cpu.reg_read(register) == value for register, value in saved.items())
            assert hits == [symbols['npu_emulation_desc10_callback'][0]], (mode, hits)
            expected = {base: bytearray(contents) for base, contents in before.items()}
            for address in (ADM, ADM + 8, STATE + 16):
                struct.pack_into('<I', expected[SRAM], address - SRAM, 1)
            assert all(bytes(cpu.mem_read(base, len(contents))) == contents for base, contents in expected.items())
            assert bytes(cpu.mem_read(packet, packet_bytes)) == packet_before
            wanted_owner = bytearray(owner_before)
            struct.pack_into('<I', wanted_owner, 8, 1)
            assert bytes(cpu.mem_read(owner, owner_bytes)) == wanted_owner
            after_code = bytearray(cpu.mem_read(CODE, image.CODE_LIMIT))
            for begin, end in (*writable, stack):
                after_code[begin - CODE:end - CODE] = code_before[begin - CODE:end - CODE]
            assert after_code == code_before
            rows.append(dict(mode=mode, initial_irq=irq, returned=0, constructor_entries=0,
                             retained_packet_bytes=packet_bytes, retained_claim_count=2560,
                             protected_bytes=sum(len(contents) for contents in expected.values()),
                             exact_fault_only_protected_memory=True, saved_registers=True,
                             frame_restored=True, code_writes=len(code_writes)))
            print(json.dumps(dict(unleased_desc10=mode, initial_irq=irq, passed=True)), flush=True)
    for path in (pair / 'CODE.bin', pair / 'DATA.bin', pair / 'manifest.json', Path(__file__),
                 ROOT / 'tools/npu_image.py'):
        inputs[path.relative_to(ROOT).as_posix()] = sha(path)
    for module in list(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename:
            path = Path(filename).resolve()
            if path.is_relative_to(ROOT / 'tests/npu') or path.is_relative_to(ROOT / 'tools'):
                inputs[path.relative_to(ROOT).as_posix()] = sha(path)
    assert all(sha(ROOT / name) == expected for name, expected in inputs.items())
    return dict(passed=True, cases=rows, inputs=inputs, actual_raw_guard_executed=True,
        unicorn_version=UNICORN_VERSION, instruction_budget=3000000, wall_microseconds=10000000,
        terminal_sentinel_bytes=0x1000,
        synthetic_forbidden_contexts=True, post_load_elf_injection=False,
        fresh_loader_allocator_caller_proof=False, full_raw_regression_passed=False, hardware=False,
        limits=['Raw CODE/DATA execute the actual guarded callback; all seeded state is explicit negative test data.',
                'Neither activity/ring metadata nor a copied command/history counter establishes retained native owners.',
                'Zero constructor entries, exact retained PKT/owner state, protected RAM and ABI are checked.',
                'These six denials do not replace full512-store success or the late-fault control suite.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert args.name.replace('-', '').isalnum()
    destination = ROOT / '.local/npu-desc10-unleased-raw' / args.name
    assert not destination.exists()
    destination.mkdir(parents=True)
    result = run(args.pair.resolve())
    (destination / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=len(result['cases']), result=str(destination / 'result.json'))))


if __name__ == '__main__':
    main()
