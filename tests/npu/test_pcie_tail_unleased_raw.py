#!/usr/bin/env python3
"""Actual raw tail guards reject explicit unleased/missing-owner negative states."""
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
            if symbol['st_shndx'] == 'SHN_UNDEF' or not symbol.name.startswith('npu_'):
                continue
            old = symbols.get(symbol.name)
            if old is None or symbol['st_size'] > old[1]:
                symbols[symbol.name] = (symbol['st_value'], symbol['st_size'])
        if name == 'cold-pcie-tail':
            writable = [(s['sh_addr'], s['sh_addr'] + s['sh_size']) for s in binary.iter_sections()
                        if s['sh_flags'] & 3 == 3 and s['sh_size']]
    owner, owner_bytes = symbols['npu_emulation_pcie_tail_state']
    setup, setup_bytes = symbols['npu_emulation_cold_setup_state']
    assert owner_bytes == 256 and setup_bytes == 404 and writable
    spaces = (*prior.IMAGES, (prior.HOST, prior.HOST_BYTES), (prior.SKB_STATE, prior.SKB_BYTES))
    stack = (prior.STACK_TOPS[0] - 0x4000, prior.STACK_TOPS[0])
    results = []
    for stage, (header, value) in enumerate(((0x10, 0x200d4580), (0x12, 0x200d4560), (0x1f, 0))):
        for mode in ('unmarked', 'legacy-modeled-lease', 'command-without-prior-owners'):
            for irq in (0, 8):
                cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
                cpu.mem_map(prior.CODE, image.CODE_LIMIT + 0x1000)
                cpu.mem_write(prior.CODE, code)
                for base, size in spaces:
                    cpu.mem_map(base, size)
                cpu.mem_write(prior.SRAM, data)
                cpu.mem_map(prior.PAYLOAD & ~0xfff, 0x1000)
                cpu.mem_write(prior.PAYLOAD, struct.pack('<3I', header, 0, value))

                def put(address, word):
                    cpu.mem_write(address, struct.pack('<I', word))

                if mode != 'unmarked':
                    put(prior.ADM + 4, 1)
                    put(prior.SRAM + 0x3964, prior.HOST)
                if mode == 'command-without-prior-owners':
                    for offset, word in ((4, 1), (8, 131071), (12, 80), (32, 131071),
                        (36, header), (44, value), (48, 0x20000000), (52, 0x100000),
                        (56, 0x20000000), (60, 0x100000), (104, 8), (108, 0x3e810000),
                        (112, 8), (116, 0x3e810000), (120, 14), (124, 14), (360, 6), (364, 6),
                        (368, 0x97000000), (372, 0x97000000), (376, 0x97000000), (380, 3), (384, 3),
                        (388, 0x200d4450), (392, 0x200d4450), (396, stage), (400, stage)):
                        put(setup + offset, word)
                before = {base: bytes(cpu.mem_read(base, size)) for base, size in spaces}
                code_before = bytes(cpu.mem_read(prior.CODE, image.CODE_LIMIT))
                owner_before = bytes(cpu.mem_read(owner, owner_bytes))
                cpu.reg_write(r.UC_RISCV_REG_SP, prior.STACK_TOPS[0])
                cpu.reg_write(r.UC_RISCV_REG_RA, prior.END)
                cpu.reg_write(r.UC_RISCV_REG_A0, prior.PAYLOAD)
                cpu.reg_write(r.UC_RISCV_REG_MSTATUS, irq)
                saved = {getattr(r, 'UC_RISCV_REG_S' + str(i)): 0xa1000000 + i * 0x101 for i in range(12)}
                saved[r.UC_RISCV_REG_GP] = prior.SRAM + 0x13a8
                saved[r.UC_RISCV_REG_TP] = 0x98765430
                for register, word in saved.items():
                    cpu.reg_write(register, word)
                hits, writes = [], []

                def instruction(uc, pc, size, opaque):
                    hits.append(pc)

                def write(uc, access, address, size, value, opaque):
                    writes.append((address, size))
                    assert any(begin <= address and address + size <= end for begin, end in (*writable, stack)), (
                        mode, 'unexpected-private-write', hex(address), size)

                import pcie_tail_wire_native as tail
                for pc in (symbols['npu_emulation_pcie_tail_callback'][0], 0x8400fdc8, *tail.SITES):
                    if pc != 0x8400fdc4:
                        cpu.hook_add(UC_HOOK_CODE, instruction, begin=pc, end=pc)
                cpu.hook_add(UC_HOOK_MEM_WRITE, write, begin=prior.CODE, end=prior.CODE + image.CODE_LIMIT - 1)
                cpu.emu_start(0x8400fdc4, prior.END, count=3000000, timeout=10000000)
                assert cpu.reg_read(r.UC_RISCV_REG_PC) == prior.END and cpu.reg_read(r.UC_RISCV_REG_A0) == 0
                assert cpu.reg_read(r.UC_RISCV_REG_SP) == prior.STACK_TOPS[0]
                assert cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8 == irq
                assert all(cpu.reg_read(register) == word for register, word in saved.items())
                assert hits == [symbols['npu_emulation_pcie_tail_callback'][0]], hits
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
                results.append(dict(stage=stage, mode=mode, initial_irq=irq, returned=0,
                    original_tail_entries=0, exact_fault_only_protected_memory=True,
                    protected_bytes=sum(len(contents) for contents in expected.values()),
                    saved_registers=True, frame_restored=True, private_writes=len(writes)))
    for path in (pair / 'CODE.bin', pair / 'DATA.bin', pair / 'manifest.json', Path(__file__)):
        inputs[str(path.relative_to(ROOT))] = prior.sha(path)
    inputs = native_prefix_snapshot.source_inputs(inputs)
    assert all(prior.sha(ROOT / name) == digest for name, digest in inputs.items())
    return dict(passed=True, cases=results, inputs=inputs, actual_raw_guard_executed=True,
        synthetic_forbidden_contexts=True, post_load_elf_injection=False,
        fresh_native_tail_admission=False, full_setup=False, hardware=False,
        limits=['Actual assembled raw tail callback is executed; seeded states are explicit forbidden negative fixtures.',
                'No completed real prior owners are seeded or accepted; no original tail store is reached.',
                'This does not replace a fresh allocator/caller or native post-reservation fault matrix.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert args.name.replace('-', '').isalnum()
    destination = ROOT / '.local/npu-pcie-tail-unleased' / args.name
    assert not destination.exists()
    destination.mkdir(parents=True)
    result = run(args.pair.resolve())
    (destination / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=len(result['cases']), fresh_native_tail_admission=False)))


if __name__ == '__main__':
    main()
