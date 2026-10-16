#!/usr/bin/env python3
"""Original API24 RRO byte effects with synthetic RAM, not checked admission."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r

import native_prefix_snapshot
from test_firmware_memory_layout import NativeMemory, STACK_TOPS, SRAM, SRAM_BYTES
from test_firmware_stop_counterexample import INPUT, CODE_SHA, DATA_SHA, CODE
from test_npu_rx_ownership import q

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / '.local/merge-nonoc-20260923/mt76-merged'
GHIDRA = ROOT / 'research/checkpoints/2026-09-05-npu-quiescence/ghidra-current-rv32-decoded/en7581_MT7996_npu_rv32.bin.txt'
GHIDRA_SHA = '098da31821148eddb15d68d5d0c7b9cb889c03a5f2e1282f0b31e33aafbebcb9'
ALIAS, ALIAS_BYTES = 0x48000000, 0x804000
BLOCKS, BLOCK_BYTES, SESSION_BYTES = 128, 65536, 8192
SESSION = ALIAS + 0x801000
PAYLOAD = CODE + 0x1ff000
CALLBACK, INNER, CLEAR = 0x8400fc2c, 0x8400e084, 0x840103aa


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project(selector, argument, physical, sram, alias):
    assert selector in (0, 1, 3)
    expected_sram, expected_alias = bytearray(sram), bytearray(alias)
    allowed = set()
    if selector in (0, 1):
        assert selector != 0 or 0 <= argument < BLOCKS
        assert selector != 1 or argument == 0
        base = (physical & 0x3fffffff) | 0x40000000
        slot = SRAM + (0x1fdc + argument * 4 if selector == 0 else 0x458c)
        struct.pack_into('<I', expected_sram, slot - SRAM, base)
        allowed.update(range(slot, slot + 4))
        size = BLOCK_BYTES if selector == 0 else SESSION_BYTES
    else:
        assert 0 <= argument <= 1024
        slot = 0x458c if argument == 1024 else 0x1fdc + (argument // 8) * 4
        base = struct.unpack_from('<I', sram, slot)[0]
        if argument != 1024: base += (argument % 8) * SESSION_BYTES
        size = SESSION_BYTES
    offset = base - ALIAS
    assert 0 <= offset and offset + size <= len(alias), 'RRO-outside-synthetic-alias'
    if selector == 0:
        expected_alias[offset:offset + size] = bytes(size)
        allowed.update(range(base, base + size))
    for index in range(7, size, 8):
        expected_alias[offset + index] = 0xff
        allowed.add(base + index)
    return expected_sram, expected_alias, allowed, base, size


def geometry(destination):
    header = (SOURCE / 'mt7996/mt7996.h').read_text()
    names = ('MT7996_RRO_MAX_SESSION', 'MT7996_RRO_WINDOW_MAX_LEN', 'MT7996_RRO_ADDR_ELEM_LEN',
             'MT7996_RRO_BA_BITMAP_SESSION_SIZE', 'MT7996_RRO_WINDOW_MAX_SIZE')
    source = destination / 'geometry.c'
    source.write_text('#include <stdint.h>\n#include <stdio.h>\ntypedef uint32_t __le32;\n' +
        '\n'.join(q.macro(header, name) for name in names) + '\n' +
        q.declaration(header, 'struct', 'mt7996_wed_rro_addr') + '\n' +
        'int main(void) { printf("[%u,%u,%u,%u,%u,%zu]\\n",' +
        ','.join('(unsigned)' + name for name in names) + ',sizeof(struct mt7996_wed_rro_addr)); return 0; }\n')
    binary = destination / 'geometry'
    command = [shutil.which('clang'), '-std=c11', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(binary)]
    done = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (destination / 'geometry.log').write_text(done.stdout + done.stderr)
    assert done.returncode == 0, done.stderr
    actual = json.loads(subprocess.check_output([str(binary)], text=True, timeout=10))
    assert actual == [1024, 1024, 128, 8, 8192, 8], ('RRO-header-geometry-drift', actual)
    return dict(values=actual, command=command, compiled_header_constants=True)


class Trace:
    def __init__(self, h, allowed):
        self.h, self.allowed, self.written = h, allowed, set()
        self.hash, self.count, self.stack_writes = hashlib.sha256(), 0, 0

    def write(self, cpu, access, address, size, value, unused):
        if STACK_TOPS[0] - 256 <= address and address + size <= STACK_TOPS[0]:
            self.stack_writes += 1
            return
        span = set(range(address, address + size))
        assert span <= self.allowed, ('RRO-unexpected-original-write', hex(cpu.reg_read(r.UC_RISCV_REG_PC)), hex(address), size)
        self.written.update(span)
        self.count += 1
        self.hash.update(struct.pack('<IIIQ', cpu.reg_read(r.UC_RISCV_REG_PC), address, size, value))


def run(destination):
    paths = [Path(__file__), GHIDRA, SOURCE / 'mt7996/mt7996.h', SOURCE / 'mt7996/init.c', SOURCE / 'npu.c',
             INPUT / 'en7581_MT7996_npu_rv32.bin', INPUT / 'en7581_MT7996_npu_data.bin']
    inputs = native_prefix_snapshot.source_inputs({str(path.relative_to(ROOT)): sha(path) for path in paths})
    assert sha(GHIDRA) == GHIDRA_SHA
    assert sha(paths[-2]) == CODE_SHA and sha(paths[-1]) == DATA_SHA
    metadata = geometry(destination)
    h = NativeMemory()
    h.cpu.mem_map(ALIAS, ALIAS_BYTES)
    h.cpu.mem_write(ALIAS, b'\xa5' * ALIAS_BYTES)
    entries = {}

    def entry(cpu, pc, size, unused): entries[pc] = entries.get(pc, 0) + 1

    for pc in (CALLBACK, INNER, CLEAR, 0x840048f4, 0x84004212):
        h.cpu.hook_add(UC_HOOK_CODE, entry, begin=pc, end=pc)
    saved = [getattr(r, 'UC_RISCV_REG_S' + str(i)) for i in range(12)]
    saved += [r.UC_RISCV_REG_GP, r.UC_RISCV_REG_TP]
    rows = []

    def invoke(selector, argument, physical):
        before_sram = bytes(h.cpu.mem_read(SRAM, SRAM_BYTES))
        before_alias = bytes(h.cpu.mem_read(ALIAS, ALIAS_BYTES))
        expected_sram, expected_alias, allowed, base, size = project(selector, argument, physical, before_sram, before_alias)
        for index, register in enumerate(saved[:12]): h.cpu.reg_write(register, 0xa1000000 + index * 0x101)
        h.cpu.reg_write(r.UC_RISCV_REG_TP, 0xb1000101)
        registers = [h.cpu.reg_read(register) for register in saved]
        status = h.cpu.reg_read(r.UC_RISCV_REG_MSTATUS)
        h.cpu.mem_write(PAYLOAD, struct.pack('<6I', 0x10 | selector, 24, argument, physical, 0, 0))
        trace = Trace(h, allowed)
        previous = dict(entries)
        hook = h.cpu.hook_add(UC_HOOK_MEM_WRITE, trace.write)
        try: result = h.call(CALLBACK, PAYLOAD)
        finally: h.cpu.hook_del(hook)
        assert result == 1 and [h.cpu.reg_read(register) for register in saved] == registers, 'RRO-original-ABI'
        assert h.cpu.reg_read(r.UC_RISCV_REG_SP) == STACK_TOPS[0]
        assert h.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) == status, 'RRO-original-MSTATUS'
        assert bytes(h.cpu.mem_read(SRAM, SRAM_BYTES)) == expected_sram, 'RRO-other-SRAM-mutation'
        assert bytes(h.cpu.mem_read(ALIAS, ALIAS_BYTES)) == expected_alias, 'RRO-projected-bytes'
        assert trace.written == allowed, 'RRO-missing-original-store-footprint'
        assert bytes(h.cpu.mem_read(CODE, len(h.code))) == h.code, 'RRO-original-CODE-mutation'
        delta = {hex(pc): entries.get(pc, 0) - previous.get(pc, 0) for pc in entries}
        assert delta.get(hex(CALLBACK)) == delta.get(hex(INNER)) == 1
        assert delta.get(hex(CLEAR), 0) == int(selector == 0)
        assert not delta.get('0x840048f4', 0) and not delta.get('0x84004212', 0), 'RRO-helper-substitution'
        rows.append(dict(selector=selector, argument=argument, physical=hex(physical), aliased_base=hex(base),
            extent=size, result=result, exact_data_bytes_written=len(trace.written), original_data_stores=trace.count,
            ordered_data_writes_sha256=trace.hash.hexdigest(), stack_writes=trace.stack_writes, entries=delta,
            exact_SRAM_and_alias_projection=True, ABI_preserved=True, distinctive_callee_saved=True,
            MSTATUS_preserved=True))
        if selector != 0 or argument % 16 == 0:
            print(json.dumps(dict(original_RRO_selector=selector, argument=argument, stores=trace.count)), flush=True)

    for index in range(BLOCKS): invoke(0, index, 0x88000000 + index * BLOCK_BYTES)
    invoke(1, 0, (SESSION & 0x3fffffff) | 0x80000000)
    for session in (0, 7, 8, 1023, 1024): invoke(3, session, 0)
    for physical in (0x08000000, 0x48000000, 0xc8000000): invoke(0, 0, physical)
    inputs = native_prefix_snapshot.source_inputs(inputs)
    for path in destination.iterdir():
        if path.is_file(): inputs[str(path.relative_to(ROOT))] = sha(path)
    assert all(sha(ROOT / name) == expected for name, expected in inputs.items()), 'RRO-probe-input-drift'
    return dict(passed=True, original_callback_cases=len(rows), cases=rows, geometry=metadata, inputs=inputs,
        original_CODE_SHA256=CODE_SHA, original_DATA_SHA256=DATA_SHA, synthetic_RAM=True,
        checked_native_admission=False, fresh_loader_allocator_caller_proof=False, full_setup=False, hardware=False,
        limits=['Direct original API24 callback probes use explicit synthetic RAM, globals and a modeled SP/GP.',
                'All128 element blocks, the session table, five reset boundaries and three address-alias inputs execute original instructions.',
                'No allocator, clear or callback result is substituted; modeled print/hart stubs are not reached.',
                'Callback return1 is not transport/constructor success, lifetime, concurrent reset or a physical drain.',
                'This does not admit selectors0/1/3 in the checked current pair or validate actual DMA/PMA/cache/backing.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    destination = ROOT / '.local/npu-inode-rro-original' / args.name
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, destination / 'driver-at-run.py')
    result = run(destination)
    output = destination / 'result.json'
    with output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, original_callback_cases=result['original_callback_cases'],
        checked_native_admission=False, hardware=False, receipt=str(output.relative_to(ROOT)), sha256=sha(output))), flush=True)


if __name__ == '__main__': main()
