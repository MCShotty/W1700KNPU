#!/usr/bin/env python3
"""Synthetic RV32 fixed-reader view only; no owner or SETUP is provisioned."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import struct

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_MEM_READ
from unicorn import riscv_const as r

ROOT = Path(__file__).resolve().parents[2]
CODE, END, STACK, OUTPUT = 0x84000000, 0x84200000, 0x841e0000, 0x841df000
ICV, ICV_BYTES, FLAGS, FLAG_BYTES = 0x3e8bc470, 4104, 0x3e9046dc, 36
METADATA = (0x8401cfb8, 0x8401cfbc, 0x3e902ac0)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    pair = args.pair.resolve()
    assert pair.is_relative_to(ROOT / '.local')
    manifest = json.loads((pair / 'manifest.json').read_bytes())
    code = (pair / 'CODE.bin').read_bytes()
    assert hashlib.sha256(code).hexdigest() == manifest['code']['sha256']
    elf_path = ROOT / manifest['symbol_files']['cold-inode']
    assert digest(elf_path) == manifest['components']['cold-inode']['sha256']
    elf = ELFFile(io.BytesIO(elf_path.read_bytes()))
    symbols = {s.name:int(s['st_value']) for s in elf.get_section_by_name('.symtab').iter_symbols()}
    plan, running, owner = [symbols[name] for name in ('plan', 'npu_emulation_inode_running', 'npu_emulation_inode_state')]
    cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
    cpu.mem_map(CODE, 0x201000)
    cpu.mem_write(CODE, code + bytes(0x201000 - len(code)))
    cpu.mem_map(0x3e900000, 0x10000)
    cpu.mem_write(0x3e900000, bytes((i * 29 + 11) & 255 for i in range(0x10000)))
    cpu.mem_map(0x3e8bc000, 0x2000)
    cpu.mem_write(0x3e8bc000, bytes((i * 17 + 7) & 255 for i in range(0x2000)))
    reads = []

    def observed(cpu_, access, address, size, value, unused):
        reads.append((address, size))

    for begin, size in ((0x8401cfb8, 8), (0x3e902ac0, 4), (ICV, ICV_BYTES), (FLAGS, FLAG_BYTES)):
        cpu.hook_add(UC_HOOK_MEM_READ, observed, begin=begin, end=begin + size - 1)
    positives = [(address, 4) for address in METADATA]
    positives += [(ICV + offset, 4) for offset in range(0, ICV_BYTES, 4)]
    positives += [(ICV, 1), (ICV + ICV_BYTES - 1, 1)]
    positives += [(FLAGS + offset, 1) for offset in range(FLAG_BYTES)]
    positives += [(FLAGS + offset, 4) for offset in range(0, FLAG_BYTES, 4)]
    cases = [dict(label='fixed-view', address=a, width=w, allowed=True) for a, w in positives]
    for address, width in ((ICV - 4, 4), (ICV + ICV_BYTES, 4), (ICV + ICV_BYTES - 1, 4),
        (FLAGS - 1, 1), (FLAGS + FLAG_BYTES, 1), (FLAGS + FLAG_BYTES, 4),
        (0, 4), (0xffffffff, 1), (0x3e902ac4, 4), (ICV + 1, 4)):
        cases.append(dict(label='extent-or-alignment', address=address, width=width, allowed=False))
    for width in (0, 2, 3, 8, 0xffffffff):
        cases.append(dict(label='unsupported-width', address=ICV, width=width, allowed=False))
    for field, values in (('opaque', (0, owner + 4)), ('result', (0,)), ('mstatus', (8,)),
                         ('running', (0, 2)), ('icv', (0, ICV + 4)), ('icv_bytes', (0, ICV_BYTES - 4))):
        for value in values:
            cases.append(dict(label='guard-' + field, address=ICV, width=4, allowed=False, **{field:value}))
    rows = []
    saved = {getattr(r, 'UC_RISCV_REG_' + name):0x51010000 + i * 0x101 for i, name in
        enumerate(('GP', 'TP', *('S' + str(i) for i in range(12))))}
    for case in cases:
        # Explicit synthetic globals select this private read view, not admission.
        cpu.mem_write(plan, bytes(180) + struct.pack('<2I', case.get('icv', ICV), case.get('icv_bytes', ICV_BYTES)))
        cpu.mem_write(running, struct.pack('<I', case.get('running', 1)))
        cpu.mem_write(OUTPUT, struct.pack('<I', 0xdeadbeef))
        for register, value in saved.items():
            cpu.reg_write(register, value)
        cpu.reg_write(r.UC_RISCV_REG_MSTATUS, case.get('mstatus', 0))
        cpu.reg_write(r.UC_RISCV_REG_SP, STACK)
        cpu.reg_write(r.UC_RISCV_REG_RA, END)
        for register, value in zip((r.UC_RISCV_REG_A0, r.UC_RISCV_REG_A1, r.UC_RISCV_REG_A2, r.UC_RISCV_REG_A3),
            (case.get('opaque', owner), case['address'], case['width'], case.get('result', OUTPUT))):
            cpu.reg_write(register, value)
        before = {base:bytes(cpu.mem_read(base, size)) for base, size in
            ((CODE, 0x200000), (0x3e900000, 0x10000), (0x3e8bc000, 0x2000))}
        expected = int.from_bytes(cpu.mem_read(case['address'], case['width']), 'little') if case['allowed'] else 0xdeadbeef
        reads.clear()
        cpu.emu_start(symbols['inode_read'], END, count=3000000, timeout=60000000)
        assert cpu.reg_read(r.UC_RISCV_REG_PC) == END
        assert cpu.reg_read(r.UC_RISCV_REG_A0) == int(case['allowed']), case
        assert cpu.reg_read(r.UC_RISCV_REG_SP) == STACK
        assert all(cpu.reg_read(register) == value for register, value in saved.items()), case
        assert cpu.reg_read(r.UC_RISCV_REG_MSTATUS) == case.get('mstatus', 0), case
        assert reads == ([(case['address'], case['width'])] if case['allowed'] else []), (case, reads)
        assert int.from_bytes(cpu.mem_read(OUTPUT, 4), 'little') == expected, case
        for base, data in before.items():
            after = bytearray(cpu.mem_read(base, len(data)))
            if base == CODE:
                after[STACK - 0x400 - CODE:STACK - CODE] = data[STACK - 0x400 - CODE:STACK - CODE]
                after[OUTPUT - CODE:OUTPUT - CODE + 4] = data[OUTPUT - CODE:OUTPUT - CODE + 4]
            assert after == data, ('unexpected-guest-write', case, hex(base))
        rows.append(case | dict(result=expected, observed_reads=reads.copy()))
    output = ROOT / '.local/npu-inode-reader-view' / args.name
    assert not output.exists()
    output.mkdir(parents=True)
    paths = (Path(__file__), pair / 'manifest.json', pair / 'CODE.bin', elf_path,
        ROOT / 'tests/npu/cold-inode-native-emulation.c')
    inputs = {str(path.relative_to(ROOT)):digest(path) for path in paths}
    for name, expected_hash in manifest['inputs'].items():
        assert digest(ROOT / name) == expected_hash
        inputs[name] = expected_hash
    record = dict(passed=True, rows=rows, cases=len(rows), allowed=len(positives),
        denied=len(rows) - len(positives), inputs=inputs, actual_compiled_reader=True,
        source_CODE_sha256=manifest['code']['sha256'], synthetic_globals=True,
        owner_or_SETUP_provisioned=False, original_constructor_executed=False,
        geometry_or_physical_acceptance=False, native_limits_changed=False, hardware=False,
        limits=['Private reader execution with explicitly synthetic running/plan globals;not native setup or ownership admission.',
            'Tests fixed allowed I/O spans,denied reads,return ABI and whole protected memory with no skipped guard or instruction.',
            'The separate core must establish full geometry and snapshot immutability around each read;this view does not do so alone.'])
    with (output / 'result.json').open('x') as stream:
        stream.write(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=len(rows), allowed=len(positives),
        denied=len(rows) - len(positives), receipt_sha256=digest(output / 'result.json'), hardware=False)), flush=True)


if __name__ == '__main__':
    main()
