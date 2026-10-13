"""Observe original API21 fixed-record writes in bounded RV32 instruction replay."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn import Uc, UcError, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.riscv_const import UC_RISCV_REG_A0, UC_RISCV_REG_PC, UC_RISCV_REG_RA, UC_RISCV_REG_SP

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / 'research/checkpoints/2026-09-05-npu-admission/ghidra-mailbox/en7581_MT7996_npu_rv32.bin.txt'
AUTHORITY_SHA = '1536a9972838ca7c02da77629e784b392af919c5d25368478aff4d0c2422e2ca'
CODE_BASE, L2_BASE, DATA_BASE = 0x84000000, 0x3e800000, 0x3e900000
END, STACK = 0x840ffff0, DATA_BASE
SPECS = (
    dict(pointer=0x3e8a2000, host_slot=0x3e903960, pointer_slot=0x3e902acc, counters=(0x3e90462c, 0x3e90395a), table=0x1cf74),
    dict(pointer=0x3e8a4020, host_slot=0x3e902a88, pointer_slot=0x3e9021e8, counters=(0x3e902a8c, 0x3e90390c), table=0x1cf7c),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    pair = args.pair.resolve()
    assert pair.is_relative_to(ROOT) and sha(AUTHORITY) == AUTHORITY_SHA
    manifest = json.loads((pair / 'manifest.json').read_bytes())
    inputs = dict(manifest['inputs'])
    for path in (Path(__file__).resolve(), AUTHORITY, pair / 'CODE.bin', pair / 'manifest.json'):
        inputs[str(path.relative_to(ROOT))] = sha(path)
    assert all(sha(ROOT / name) == digest for name, digest in inputs.items())
    code = (pair / 'CODE.bin').read_bytes()
    assert struct.unpack_from('<IIII', code, 0x1cf70) == (0x100, 0x3e8a2000, 0x101, 0x3e8a4020)
    rows = []

    def execute(name, band, prerequisite=0x8cc00000, wrong_pointer=None, missing_table=False):
        selected = int(band != 0)
        spec = SPECS[selected]
        cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        cpu.mem_map(CODE_BASE, 0x100000)
        cpu.mem_write(CODE_BASE, code)
        cpu.mem_map(L2_BASE, 0x100000)
        cpu.mem_map(DATA_BASE, 0x10000)
        l2_before = bytes((index * 73 + 19) % 251 + 1 for index in range(0x100000))
        data_before = bytearray((index * 31 + 41) % 251 + 1 for index in range(0x10000))
        host = 0x96200000 if selected == 0 else 0x96500000
        struct.pack_into('<I', data_before, spec['host_slot'] - DATA_BASE, (host & 0x3fffffff) | 0x40000000)
        struct.pack_into('<I', data_before, 0x2ab8, prerequisite)
        cpu.mem_write(L2_BASE, l2_before)
        cpu.mem_write(DATA_BASE, bytes(data_before))
        if wrong_pointer is not None:
            cpu.mem_write(CODE_BASE + spec['table'], struct.pack('<I', wrong_pointer))
        if missing_table:
            cpu.mem_write(CODE_BASE + 0x1cf70, struct.pack('<I', 0xffff))
        code_before = bytes(cpu.mem_read(CODE_BASE, len(code)))
        cpu.reg_write(UC_RISCV_REG_A0, band)
        cpu.reg_write(UC_RISCV_REG_SP, STACK)
        cpu.reg_write(UC_RISCV_REG_RA, END)
        calls, writes = [], []
        wait_observed = False

        def hook(uc, pc, size, data):
            nonlocal wait_observed
            calls.append(pc)
            if pc == 0x8400a614:
                wait_observed = True
                uc.emu_stop()

        cpu.hook_add(UC_HOOK_CODE, hook)
        cpu.hook_add(UC_HOOK_MEM_WRITE, lambda uc, access, address, size, value, data: writes.append((address, size, value)))
        error = None
        try:
            cpu.emu_start(0x8400a5fa, END, count=20000)
        except UcError as exception:
            error = str(exception)
        assert 0x84004ff8 not in calls
        assert bytes(cpu.mem_read(CODE_BASE, len(code))) == code_before
        expected_data = bytearray(data_before)
        expected_l2 = bytearray(l2_before)
        pointer = 0 if missing_table else wrong_pointer if wrong_pointer is not None else spec['pointer']
        metadata = []
        if prerequisite:
            for address in spec['counters']:
                struct.pack_into('<H', expected_data, address - DATA_BASE, 0)
                metadata.append((address, 2, 0))
            struct.pack_into('<I', expected_data, spec['pointer_slot'] - DATA_BASE, pointer)
            metadata.append((spec['pointer_slot'], 4, pointer))
        if prerequisite and not missing_table:
            assert error is None and cpu.reg_read(UC_RISCV_REG_PC) == END
            assert cpu.reg_read(UC_RISCV_REG_SP) == STACK
            for index in range(512):
                offset = pointer - L2_BASE + 16 * index
                struct.pack_into('<III', expected_l2, offset, ((host + index * 256) & 0x3fffffff) | 0x80000000, 0, 0)
                expected_l2[offset + 12] = 0
            record_writes = [(address, size) for address, size, value in writes if pointer <= address < pointer + 8192]
            assert record_writes == [(pointer + index * 16 + offset, size)
                                     for index in range(512) for offset, size in ((0, 4), (4, 4), (8, 4), (12, 1))]
        elif missing_table:
            assert error is not None and not wait_observed
            record_writes = []
        else:
            assert error is None and wait_observed and cpu.reg_read(UC_RISCV_REG_PC) == 0x8400a614
            assert not [address for address, size, value in writes if DATA_BASE <= address < DATA_BASE + 0x10000]
            record_writes = []
        assert [(address, size, value) for address, size, value in writes if DATA_BASE <= address < DATA_BASE + 0x10000] == metadata
        expected_l2[-16:] = cpu.mem_read(STACK - 16, 16)
        assert bytes(cpu.mem_read(DATA_BASE, 0x10000)) == bytes(expected_data)
        assert bytes(cpu.mem_read(L2_BASE, 0x100000)) == bytes(expected_l2)
        rows.append(dict(name=name, band_argument=band, selected_band=selected, prerequisite=prerequisite,
                         pointer=pointer, host=host, completed=cpu.reg_read(UC_RISCV_REG_PC) == END,
                         wait_call_observed=wait_observed, memory_fault=error,
                         record_count=512 if record_writes else 0, record_stores=len(record_writes),
                         metadata_stores=[dict(address=address, bytes=size, value=value) for address, size, value in metadata],
                         untouched_tail_bytes=True, exact_other_bytes=True, dynamic_allocator_called=False,
                         instructions=len(calls), ring_sha256=hashlib.sha256(cpu.mem_read(pointer, 8192)).hexdigest() if record_writes else None))

    execute('band0-original', 0)
    execute('band1-original', 1)
    execute('wrong-nonzero-prerequisite-accepted', 0, prerequisite=1)
    execute('unsupported-nonzero-band-accepted', 2)
    execute('wrong-static-destination-written', 0, wrong_pointer=0x3e801000)
    execute('missing-type100-partial-metadata', 0, missing_table=True)
    execute('missing-type101-partial-metadata', 1, missing_table=True)
    execute('zero-prerequisite-enters-wait', 0, prerequisite=0)
    assert all(sha(ROOT / name) == digest for name, digest in inputs.items())
    receipt = dict(passed=True, cases=rows, inputs=inputs,
                   limits=['Original RV32 helper/lookup instructions with patterned synthetic CODE/L2/DATA/stack backing.',
                           'Zero prerequisite stops at the original delay-call site; this is a bounded branch observation, not physical wait/drain proof.',
                           'Corrupted table/prerequisite cases are original-code counterexamples, not production permission.',
                           'No candidate API21 admission, host buffer consumption, physical ownership or router/client acceptance.'])
    output = args.output.resolve()
    assert output.is_relative_to(ROOT)
    with output.open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(passed=True, cases=len(rows), records_per_completed_band=512, stores_per_completed_band=2048)))


if __name__ == '__main__':
    main()
