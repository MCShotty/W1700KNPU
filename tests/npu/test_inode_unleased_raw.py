#!/usr/bin/env python3
"""Actual raw constructor guards reject explicitly forbidden synthetic leases."""
import argparse
import io
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r
import native_prefix_snapshot
import test_desc10_unleased_raw as prior
import inode_wire_native as inode

ROOT, image = prior.ROOT, prior.image


def run(pair):
    manifest = json.loads((pair / 'manifest.json').read_bytes())
    code, data = (pair / 'CODE.bin').read_bytes(), (pair / 'DATA.bin').read_bytes()
    image.validate(code, data, manifest)
    inputs, symbols, writable = dict(manifest['inputs']), {}, []
    for name, relative in manifest['symbol_files'].items():
        path = ROOT / relative
        assert prior.sha(path) == manifest['components'][name]['sha256']
        inputs[relative] = prior.sha(path)
        binary = ELFFile(io.BytesIO(path.read_bytes()))
        for symbol in binary.get_section_by_name('.symtab').iter_symbols():
            if symbol['st_shndx'] == 'SHN_UNDEF' or not symbol.name.startswith('npu_'): continue
            old = symbols.get(symbol.name)
            if old is None or symbol['st_size'] > old[1]:
                symbols[symbol.name] = (symbol['st_value'], symbol['st_size'])
        if name == 'cold-inode':
            writable = [(s['sh_addr'], s['sh_addr'] + s['sh_size']) for s in binary.iter_sections()
                        if s['sh_flags'] & 3 == 3 and s['sh_size']]
    owner, owner_bytes = symbols['npu_emulation_inode_state']
    setup, setup_bytes = symbols['npu_emulation_cold_setup_state']
    assert owner_bytes == 4372 and setup_bytes == 412 and writable
    spaces = (*prior.IMAGES, (prior.HOST, prior.HOST_BYTES), (prior.SKB_STATE, prior.SKB_BYTES))
    stack = (prior.STACK_TOPS[0] - 0x4000, prior.STACK_TOPS[0])
    cases = [(selector, mode, irq) for selector in (2, 7)
             for mode in ('unmarked', 'legacy-modeled-lease', 'command-without-prior-owners') for irq in (0, 8)]
    cases += [(selector, 'unsupported-RRO', irq) for selector in (0, 1, 3) for irq in (0, 8)]
    results = []
    for selector, mode, irq in cases:
        cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        cpu.mem_map(prior.CODE, image.CODE_LIMIT + 0x1000)
        cpu.mem_write(prior.CODE, code)
        for base, size in spaces: cpu.mem_map(base, size)
        cpu.mem_write(prior.SRAM, data)
        cpu.mem_map(prior.PAYLOAD & ~0xfff, 0x1000)
        frame = struct.pack('<6I', 0x10 | selector, 24, 0, 0, 0, 0)
        cpu.mem_write(prior.PAYLOAD, frame)
        def put(address, value): cpu.mem_write(address, struct.pack('<I', value))
        if mode == 'legacy-modeled-lease':
            put(prior.ADM + 4, 1)
            put(prior.SRAM + 0x3964, prior.HOST)
        if mode == 'command-without-prior-owners':
            for offset, value in ((4, 1), (8, 131071), (12, 80), (32, 131071),
                (36, 0x10 | selector), (40, 24), (44, 0), (48, 0x20000000), (52, 0x100000),
                (56, 0x20000000), (60, 0x100000), (104, 8), (108, 0x3e810000),
                (112, 8), (116, 0x3e810000), (120, 14), (124, 14), (360, 6), (364, 6),
                (368, 0x97000000), (372, 0x97000000), (376, 0x97000000), (380, 3), (384, 3),
                (388, 0x200d4450), (392, 0x200d4450), (396, 3), (400, 3),
                (404, int(selector == 7)), (408, int(selector == 7))):
                put(setup + offset, value)
            put(prior.SRAM + 0x1d8, 0x8400fc2c)
            put(prior.SRAM + 0x2ac0, 0x3e8bc470)
            put(prior.ADM + 4, 1)
        before = {base: bytes(cpu.mem_read(base, size)) for base, size in spaces}
        code_before = bytes(cpu.mem_read(prior.CODE, image.CODE_LIMIT))
        owner_before = bytes(cpu.mem_read(owner, owner_bytes))
        cpu.reg_write(r.UC_RISCV_REG_SP, prior.STACK_TOPS[0])
        cpu.reg_write(r.UC_RISCV_REG_RA, prior.END)
        cpu.reg_write(r.UC_RISCV_REG_A0, prior.PAYLOAD)
        cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 0x1880 | irq)
        status = cpu.reg_read(r.UC_RISCV_REG_MSTATUS)
        saved = {getattr(r, 'UC_RISCV_REG_S' + str(i)): 0xa1000000 + i * 0x101 for i in range(12)}
        saved[r.UC_RISCV_REG_GP] = prior.SRAM + 0x13a8
        saved[r.UC_RISCV_REG_TP] = 0x98765430
        for register, value in saved.items(): cpu.reg_write(register, value)
        hits, writes = [], []
        def instruction(uc, pc, size, opaque): hits.append(pc)
        def write(uc, access, address, size, value, opaque):
            writes.append((address, size))
            assert any(begin <= address and address + size <= end for begin, end in (*writable, stack)), (
                mode, 'unexpected-private-write', hex(address), size)
        entry = symbols['npu_emulation_inode_callback'][0]
        for pc in (entry, symbols['npu_original_inode_callback'][0], 0x8400fc30, 0x8400e084,
                   *(site for site in inode.SITES if site != 0x8400fc2c)):
            cpu.hook_add(UC_HOOK_CODE, instruction, begin=pc, end=pc)
        cpu.hook_add(UC_HOOK_MEM_WRITE, write, begin=prior.CODE, end=prior.CODE + image.CODE_LIMIT - 1)
        cpu.emu_start(0x8400fc2c, prior.END, count=3000000, timeout=10000000)
        assert cpu.reg_read(r.UC_RISCV_REG_PC) == prior.END and cpu.reg_read(r.UC_RISCV_REG_A0) == 0
        assert cpu.reg_read(r.UC_RISCV_REG_SP) == prior.STACK_TOPS[0]
        assert cpu.reg_read(r.UC_RISCV_REG_MSTATUS) == status
        assert all(cpu.reg_read(register) == value for register, value in saved.items())
        assert hits == [entry], hits
        assert bytes(cpu.mem_read(prior.PAYLOAD, len(frame))) == frame
        expected = {base: bytearray(contents) for base, contents in before.items()}
        for address in (prior.ADM, prior.ADM + 8, prior.STATE + 16):
            struct.pack_into('<I', expected[prior.SRAM], address - prior.SRAM, 1)
        assert all(bytes(cpu.mem_read(base, len(contents))) == contents for base, contents in expected.items())
        wanted_owner = bytearray(owner_before)
        struct.pack_into('<I', wanted_owner, 8, 1)
        assert bytes(cpu.mem_read(owner, owner_bytes)) == wanted_owner
        after_code = bytearray(cpu.mem_read(prior.CODE, image.CODE_LIMIT))
        for begin, end in (*writable, stack):
            after_code[begin - prior.CODE:end - prior.CODE] = code_before[begin - prior.CODE:end - prior.CODE]
        assert after_code == code_before
        results.append(dict(selector=selector, mode=mode, initial_mstatus=status, returned=0,
            original_constructor_entries=0, exact_fault_only_protected_memory=True,
            protected_bytes=sum(len(contents) for contents in expected.values()),
            saved_registers=True, full_mstatus_restored=True, frame_restored=True, private_writes=len(writes)))
    return results, inputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert args.name.replace('-', '').isalnum()
    directory = ROOT / '.local/npu-inode-unleased' / args.name
    assert not directory.exists()
    directory.mkdir(parents=True)
    rows, inputs = run(args.pair.resolve())
    inputs = native_prefix_snapshot.source_inputs(inputs)
    assert all(prior.sha(ROOT / name) == expected for name, expected in inputs.items())
    record = dict(passed=True, cases=rows, inputs=inputs, actual_raw_guard_executed=True,
        synthetic_forbidden_contexts=True, post_load_elf_injection=False,
        fresh_native_inode_admission=False, full_setup=False, hardware=False,
        limits=['Direct raw callback denials with explicitly forbidden synthetic leases,not a fresh authenticated constructor.',
                'Original constructor/helper/store bodies are never reached; full protected memory/private owner/ABI/MSTATUS match.'])
    (directory / 'result.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=len(rows), fresh_native_inode_admission=False)))


if __name__ == '__main__': main()
