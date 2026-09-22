#!/usr/bin/env python3
"""Native bridge/header allocation extents; alternate size is a hypothesis."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import struct
import sys

sys.dont_write_bytecode = True
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_MEM_INVALID, UcError
from unicorn import riscv_const as r
import test_allocator_protocol as allocator
from test_allocator_startup import StartupBridge, build as build_startup
from test_allocator_reset import build as build_reset
from test_bridge_startup import BRIDGE, CHANNELS, START, OUTER, input_bindings
from test_firmware_memory_layout import NativeMemory, table, STACK_TOPS
from test_mt7996_bootstrap_sequence import exports, GHIDRA, GHIDRA_SHA
from test_firmware_mailbox_dispatch import PAYLOAD
from test_firmware_stop_counterexample import END
from test_boot_irq_installation import UnmodeledAccess
from emulation_layout import CODE, SRAM, SRAM_BYTES, HEAP, HEAP_BYTES, STATE

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'research/checkpoints/2026-09-09-npu-memory-budget'
BRIDGE_POINTER = SRAM+0x184c
BRIDGE_SIZE_WORD = 0x8401b224+8+4
HEADER_OFFSET, SLOT_BYTES = 0x10000, 0x80
LAYOUT_HYPOTHESIS = 0x11000


def sha(data):
    return allocator.sha(data)


def allocations(h, sizes):
    count = h.get32(SRAM+0x1bd4)
    rows = []
    for index in range(count):
        kind, reserved, address = struct.unpack('<HHI', h.cpu.mem_read(SRAM+0x1be4+index*8, 8))
        assert reserved == 0 and kind in sizes
        rows.append(dict(type=kind, address=address, bytes=sizes[kind], end=address+sizes[kind]))
    return rows


def packet(h, kind, index, length=50):
    if kind == 'vxlan':
        assert length == 50
        value = bytes(8)+bytes([index])+bytes((i*17+3) % 256 for i in range(length))
        offset = HEADER_OFFSET+index*SLOT_BYTES
        source = value[9:]
        entry = 0x84005c30
    else:
        assert kind == 'srv6'
        value = bytes(8)+bytes([index, length])+bytes((i*17+3) % 256 for i in range(length))
        offset = HEADER_OFFSET+(index+20)*SLOT_BYTES
        source = value[10:]
        entry = 0x84005c82
    h.cpu.mem_write(PAYLOAD, value)
    return entry, h.get32(BRIDGE_POINTER)+offset, source


class Primitive(NativeMemory):
    def __init__(self, bridge_size):
        super().__init__()
        self.tracking = False
        self.memory_writes = []
        self.entries = Counter()
        self.invalid = []
        self.timer = 0xfffffff0
        self.cpu.mem_map(BRIDGE, 0x1000)
        self.cpu.mem_map(0x1ec10000, 0x1000)
        self.cpu.mem_map(0x1fa20000, 0x1000)
        self.put32(0x1fa201fc, 0)
        self.cpu.mem_map(PAYLOAD, 0x1000)
        self.cpu.hook_add(UC_HOOK_MEM_READ, self.read)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, self.write)
        self.cpu.hook_add(UC_HOOK_CODE, self.code_hook)
        self.cpu.hook_add(UC_HOOK_MEM_INVALID, self.invalid_access)
        assert self.get32(BRIDGE_SIZE_WORD) == 58879
        self.put32(BRIDGE_SIZE_WORD, bridge_size)
        self.call(0x84005296)
        self.put32(0x1ec10100, 1)
        self.put32(0x1ec10104, 0xffffffff)
        for address in CHANNELS:
            self.put32(address, 1)
        self.call(0x84005200, 0x89)
        try:
            self.call(0x84001472)
        except UcError as error:
            raise AssertionError(self.invalid) from error
        self.call(0x8400b928)
        self.cpu.mem_write(HEAP, b'\xa5'*HEAP_BYTES)

    def read(self, cpu, access, address, size, value, data):
        if address == 0x1ec10108:
            self.timer = (self.timer-65536) & 0xffffffff
            self.put32(address, self.timer)

    def invalid_access(self, cpu, access, address, size, value, data):
        self.invalid.append(dict(address=hex(address), size=size, access=access,
                                 pc=hex(cpu.reg_read(r.UC_RISCV_REG_PC))))
        return False

    def write(self, cpu, access, address, size, value, data):
        if self.tracking and (HEAP <= address < HEAP+HEAP_BYTES or SRAM <= address < SRAM+SRAM_BYTES):
            self.memory_writes.append(dict(address=address, size=size, value=value,
                                           pc=cpu.reg_read(r.UC_RISCV_REG_PC)))

    def code_hook(self, cpu, pc, size, data):
        if self.tracking:
            self.entries[pc] += 1
        assert pc not in (0x8400dd82,), 'WLAN descriptor dispatch is outside this test'


def primitive_case(bridge_size, kind, index, length, sizes):
    h = Primitive(bridge_size)
    rows = allocations(h, {**sizes, 0x81: bridge_size})
    assert [row['type'] for row in rows] == [0x89, 0x81, 1]
    bridge = rows[1]
    assert h.get32(BRIDGE_POINTER) == bridge['address']
    assert h.call(0x84001466) == bridge['address']+HEADER_OFFSET
    entry, destination, source = packet(h, kind, index, length)
    before = {base: bytearray(h.cpu.mem_read(base, size)) for base, size in
              ((HEAP, HEAP_BYTES), (SRAM, SRAM_BYTES))}
    wanted = {base: data.copy() for base, data in before.items()}
    wanted[HEAP][destination-HEAP:destination-HEAP+length] = source
    expected_writes = set(range(destination, destination+length))
    if kind == 'srv6':
        wanted[SRAM][0x4650+index] = length
        expected_writes.add(SRAM+0x4650+index)
    h.tracking = True
    result = h.call(entry, PAYLOAD)
    h.tracking = False
    assert result == 1
    assert all(bytes(h.cpu.mem_read(base, len(data))) == bytes(data) for base, data in wanted.items())
    written = {address for event in h.memory_writes
               for address in range(event['address'], event['address']+event['size'])}
    assert written == expected_writes
    assert h.entries[0x84001466] == h.entries[0x840102da] == 1
    owner = next(row for row in rows if row['address'] <= destination and destination+length <= row['end'])
    assert owner['type'] == (1 if bridge_size == 58879 else 0x81)
    assert allocations(h, {**sizes, 0x81: bridge_size}) == rows
    return dict(kind=kind, index=index, length=length, bridge_allocation_bytes=bridge_size,
                allocations=rows, destination=hex(destination), end=hex(destination+length),
                header_write_owner_type=owner['type'], inside_bridge_allocation=owner['type'] == 0x81,
                descriptor_allocation_changed=owner['type'] == 1, callback_result=result,
                whole_memory_compared=HEAP_BYTES+SRAM_BYTES, exact_write_bytes=len(written),
                native_copy_entries=h.entries[0x840102da], writes=h.memory_writes,
                heap_sha256=sha(bytes(h.cpu.mem_read(HEAP, HEAP_BYTES))))


def boot_case(startup, reset, bridge_size, sizes):
    h = StartupBridge(startup, reset)
    assert len(h.startup_results) == 7 and all(row[0] == 0 for row in h.startup_results)
    h.prepare()
    before_state = bytes(h.cpu.mem_read(SRAM+0x1bcc, allocator.STATE_BYTES))
    before_heap = bytes(h.cpu.mem_read(HEAP, HEAP_BYTES))
    assert h.get32(BRIDGE_SIZE_WORD) == 58879
    h.put32(BRIDGE_SIZE_WORD, bridge_size)
    used = h.get32(SRAM+0x1be0)
    expected_base = (HEAP+used+31) & ~31
    hold = h.allocator_rv.symbols['npu_emulation_allocator_startup_hold']
    stop = h.run(START, [OUTER, hold])
    held = bridge_size == LAYOUT_HYPOTHESIS
    assert stop == (hold if held else OUTER)
    assert bytes(h.cpu.mem_read(HEAP, HEAP_BYTES)) == before_heap
    rows = allocations(h, {**sizes, 0x81: bridge_size})
    output = dict(bridge_allocation_bytes=bridge_size, core0_allocations=7, core0_used_bytes=used,
                  planned_bridge_base=hex(expected_base), declared_heap_end=hex(HEAP+HEAP_BYTES),
                  required_end=hex(expected_base+bridge_size),
                  full_extent_deficit=max(0, expected_base+bridge_size-HEAP-HEAP_BYTES),
                  held_before_publication=held, allocations=rows)
    if held:
        assert bytes(h.cpu.mem_read(SRAM+0x1bcc, allocator.STATE_BYTES)) == before_state
        assert h.get32(BRIDGE_POINTER) == 0x55aa55aa and h.get32(STATE+16) == 1
        assert not any(BRIDGE <= int(row['address'], 16) < BRIDGE+0x1000 for row in h.mmio)
        output['header_attempt'] = None
    else:
        assert h.get32(BRIDGE_POINTER) == expected_base
        h.hart = 0
        h.bridge_active = False
        h.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 0)
        entry, destination, _ = packet(h, 'vxlan', 0)
        h.unmodeled = None
        failure = None
        try:
            h.call(entry, PAYLOAD)
        except (UnmodeledAccess, UcError) as error:
            failure = str(error)
        assert failure and h.cpu.reg_read(r.UC_RISCV_REG_PC) == 0x84010318, failure
        assert destination == expected_base+0x10000 and destination >= HEAP+HEAP_BYTES
        assert bytes(h.cpu.mem_read(HEAP, HEAP_BYTES)) == before_heap
        output['header_attempt'] = dict(address=hex(destination), pc='0x84010318',
                                        outside_heap_by=destination-HEAP-HEAP_BYTES,
                                        stopped=failure, native_callback_guard=False)
    return output


def static_inventory():
    assert sha(GHIDRA.read_bytes()) == GHIDRA_SHA
    functions = exports()
    rows = []
    for target in (0x84005200, 0x84001466):
        callers = {}
        for address, function in functions.items():
            for pc in re.findall(r'ram:([0-9a-f]+) (?:c\.)?(?:jal|j) (?:ra,)?0x'+f'{target:x}'+r'\b',
                                 function['assembly']):
                callers.setdefault(pc, []).append(dict(function=hex(address), name=function['name']))
        rows.append(dict(target=hex(target), distinct_sites=len(callers),
                         callers=[dict(pc='0x'+pc, owners=owners) for pc, owners in sorted(callers.items())]))
    return rows


def bindings():
    values = input_bindings()
    paths = [Path(__file__), ROOT/'tools/ghidra/allocation-consumers.pattern',
             ROOT/'tools/ghidra/reexport_allocation_consumers.ps1']
    paths += sorted((ROOT/'tests/npu').glob('*-emulation.ld'))
    values.update({str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in paths})
    return values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    inputs = bindings()
    definitions = allocator.definitions()
    sizes = {row[0]: row[3] for group in definitions for row in group}
    assert sizes[0x81] == 58879 and sizes[0x84] == sizes[0x85] == LAYOUT_HYPOTHESIS
    rows = []
    for size in (sizes[0x81], LAYOUT_HYPOTHESIS):
        for kind, index, length in (('vxlan', 0, 50), ('vxlan', 19, 50),
                                    ('srv6', 0, 128), ('srv6', 7, 128)):
            rows.append(primitive_case(size, kind, index, length, sizes))
            print(json.dumps(dict(size=size, kind=kind, index=index, passed=True)), flush=True)
    startup, _ = build_startup()
    reset, _ = build_reset()
    boots = [boot_case(startup, reset, size, sizes) for size in (sizes[0x81], LAYOUT_HYPOTHESIS)]
    assert bindings() == inputs
    result = dict(schema=1, inputs_before_after=inputs, dynamic_definitions=definitions,
                  primitive_cases=rows, startup_cases=boots, static_calls=static_inventory(),
                  layout_hypothesis=dict(packet_bytes=0x10000, header_bytes=0x1000, total_bytes=LAYOUT_HYPOTHESIS),
                  limits=['Native selected bridge/tunnel callbacks only; strict admission is not expanded.',
                          'Primitive clock-divider register is fixed at zero with a decreasing synthetic timer counter.',
                          'Primitive bridge-before-descriptors is an ordered component scenario, not a proved stock scheduling order.',
                          'Core0-first case uses actual checked startup and native bridge initialization under existing MMIO/timer models.',
                          '69632-byte bridge size is an isolated ROM-table sizing hypothesis, not a promoted allocation or complete layout fix.',
                          'Existing header callback bounds, all consumers and complete memory/placement profiles are not yet closed.',
                          'No physical/router test, image, provider INODE correction or native DESC5/6/7/8 operation.'])
    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT/'bridge-memory.json'
    encoded = (json.dumps(result, indent=2)+'\n').encode()
    if args.check:
        assert output.read_bytes() == encoded
    else:
        output.write_bytes(encoded)
    print(json.dumps(dict(primitive_cases=len(rows), startup_cases=len(boots), evidence_sha256=sha(encoded))))


if __name__ == '__main__':
    main()
