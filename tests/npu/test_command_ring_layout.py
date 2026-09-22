#!/usr/bin/env python3
"""Unpromoted full-capacity ring placement and native instruction consumers."""
import argparse
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r

import test_allocator_protocol as p
import test_allocator_placement as placed
import test_allocator_startup as startup
import test_txdone_init as txdone
from test_allocator_reset import build as build_reset, COLD_TYPES
from test_bridge_memory_budget import BRIDGE_SIZE_WORD, LAYOUT_HYPOTHESIS, packet
from test_bridge_startup import input_bindings
from test_firmware_memory_layout import NativeMemory, STACK_TOPS, board_map
from test_firmware_mailbox_dispatch import PAYLOAD
from test_mt7996_bootstrap_sequence import exports, GHIDRA, GHIDRA_SHA, PROVIDER
from test_native_wifi_boot import L2, L2_BYTES
from emulation_layout import SRAM, SRAM_BYTES, HEAP, HEAP_BYTES, STATE

ROOT, OUT = p.ROOT, placed.OUT
RING, RING_BYTES = placed.RING, placed.RING_BYTES
LINKER = ROOT/'tests/npu/allocator-placement-emulation.ld'
FIXED = ((0x19, 0, RING),)
POINTER, WRITE_INDEX, READ_INDEX = SRAM+0x1f3c, SRAM+0x46e4, SRAM+0x46e2
PRODUCER, PRODUCED, BUSY = 0x8400c756, 0x8400c5f6, 0x8400c788
CONSUMER, CONSUMED, EMPTY = 0x8400cb7e, 0x8400cc72, 0x8400cbdc


def native_state(defs, order):
    expected = bytearray(placed.state_for(defs, order, FIXED))
    expected[4:8] = expected[12:16] = bytes(4)
    return bytes(expected)


class Profile(startup.StartupBridge):
    def __init__(self, path, reset_path, omit_start=True):
        self.ring_writes = []
        self.placement_lock_return = None
        super().__init__(path, reset_path, omit_start)
        self.bridge_type['value'] = LAYOUT_HYPOTHESIS

    def coordinator(self):
        assert self.get32(BRIDGE_SIZE_WORD) == 58879
        self.put32(BRIDGE_SIZE_WORD, LAYOUT_HYPOTHESIS)
        return super().coordinator()

    def write_hook(self, cpu, access, address, size, value, data):
        if RING <= address < RING+RING_BYTES:
            assert cpu.reg_read(r.UC_RISCV_REG_PC) == 0x8400bac8
            self.ring_writes.append((address, size, value))
        super().write_hook(cpu, access, address, size, value, data)

    def code_hook(self, cpu, pc, size, data):
        if self.bridge_active and pc == 0x840064b4:
            self.placement_lock_return = cpu.reg_read(r.UC_RISCV_REG_RA)
        if pc == self.placement_lock_return:
            self.lock_result = cpu.reg_read(r.UC_RISCV_REG_A0)
            self.placement_lock_return = None
        super().code_hook(cpu, pc, size, data)


def ring_template():
    return struct.pack('<4I', 0xfe, 0, 0, 0)*2048+bytes(16)


def build():
    path, command = startup.build(tag='command-ring-placement',
        extra_flags=('-DNPU_EMULATION_COMMAND_RING=0x84060000',), linker=LINKER)
    return path, command


def layout_proof(h, txdone_path):
    section = h.allocator_rv.elf.get_section_by_name('.command_ring')
    assert section['sh_type'] == 'SHT_PROGBITS'
    assert section['sh_addr'] == RING and section['sh_size'] == RING_BYTES
    assert section.data() == struct.pack('<I', 0xfe)+bytes(RING_BYTES-4)
    assert h.allocator_rv.symbols['npu_emulation_command_ring'] == RING
    occupied = [(STACK_TOPS[0]-0x4000, STACK_TOPS[-1], 'native-hart-stack-envelope'),
                (0x84200000, 0x84240000, 'provider-backup')]
    for label, rv in (('base', h.rv), ('bridge', h.guard_rv),
                      ('reset', h.reset_rv), ('allocator', h.allocator_rv)):
        for entry in rv.elf.iter_sections():
            if entry['sh_flags'] & 2 and entry['sh_size'] and entry.name != '.command_ring':
                occupied.append((entry['sh_addr'], entry['sh_addr']+entry['sh_size'], label+entry.name))
    for entry in txdone.sections(txdone_path):
        address = int(entry['address'], 16)
        occupied.append((address, address+entry['bytes'], 'txdone'+entry['name']))
    assert all(RING+RING_BYTES <= a or b <= RING for a, b, _ in occupied)
    provider = PROVIDER.read_text()
    assert '#define NPU_EN7581_FIRMWARE_RV32_MAX_SIZE\t0x200000' in provider
    assert '#define NPU_SRAM_BACKUP_SIZE\t\t0x40000' in provider
    board = board_map()
    region = board['reserved_memory']['npu-binary@84000000']
    assert region['start'] <= RING < RING+RING_BYTES <= region['start']+0x200000
    return dict(section_address=hex(RING), section_bytes=RING_BYTES,
                initialized_section_sha256=p.sha(section.data()),
                occupied=[dict(start=hex(a), end=hex(b), name=name) for a, b, name in occupied],
                provider_sha256=p.sha(PROVIDER.read_bytes()), board=board,
                loader_boundary='ELF fixture loads PROGBITS. No complete raw firmware image is emitted or uploaded.')


def headers(h):
    h.hart = 0
    h.bridge_active = False
    h.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 0)
    writes = []
    def write(cpu, access, address, size, value, data):
        if HEAP <= address < HEAP+HEAP_BYTES or SRAM <= address < SRAM+SRAM_BYTES:
            writes.append((address, size, value))
    handle = h.cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    result = []
    for kind, index, length in (('vxlan', 0, 50), ('vxlan', 19, 50),
                                ('srv6', 0, 128), ('srv6', 7, 128)):
        entry, destination, source = packet(h, kind, index, length)
        before = {base: bytearray(h.cpu.mem_read(base, size)) for base, size in
                  ((HEAP, HEAP_BYTES), (SRAM, SRAM_BYTES), (RING, RING_BYTES), (L2, L2_BYTES))}
        expected = {base: data.copy() for base, data in before.items()}
        expected[HEAP][destination-HEAP:destination-HEAP+length] = source
        wanted = set(range(destination, destination+length))
        if kind == 'srv6':
            expected[SRAM][0x4650+index] = length
            wanted.add(SRAM+0x4650+index)
        writes.clear()
        assert h.call(entry, PAYLOAD) == 1
        assert all(bytes(h.cpu.mem_read(base, len(data))) == data for base, data in expected.items())
        actual = {byte for address, size, _ in writes for byte in range(address, address+size)}
        assert actual == wanted
        bridge = h.get32(SRAM+0x184c)
        assert bridge <= destination and destination+length <= bridge+LAYOUT_HYPOTHESIS
        result.append(dict(kind=kind, index=index, length=length, destination=hex(destination),
                           inside_bridge=True, exact_write_bytes=len(actual)))
    h.cpu.hook_del(handle)
    return result


class RingSlice(NativeMemory):
    def __init__(self, h, address):
        super().__init__()
        self.address = address
        self.cpu.mem_write(HEAP, bytes(h.cpu.mem_read(HEAP, HEAP_BYTES)))
        self.cpu.mem_write(SRAM, bytes(h.cpu.mem_read(SRAM, SRAM_BYTES)))
        self.cpu.mem_write(address, bytes(h.cpu.mem_read(address, RING_BYTES)))
        assert self.get32(POINTER) == address
        assert bytes(self.cpu.mem_read(address, RING_BYTES)) == ring_template()
        self.put32(address-4, 0xa5a5a5a5)
        self.put32(address+RING_BYTES, 0xa5a5a5a5)
        assert bytes(self.cpu.mem_read(READ_INDEX, 4)) == bytes(4)
        defs = p.definitions()
        size = h.get32(BRIDGE_SIZE_WORD)
        defs[0] = [(*row[:3], size if row[0] == 0x81 else row[3]) for row in defs[0]]
        self.put32(BRIDGE_SIZE_WORD, size)
        before = bytes(self.cpu.mem_read(SRAM+0x1bcc, p.STATE_BYTES))
        result, expected, _ = placed.oracle(placed.Case('native-counter-init', defs, 10, 1,
                                              before, placements=FIXED if address == RING else ()))
        assert result[0] == p.OK and self.get32(SRAM+0x1f04) == 0
        self.call(0x8400a364, 0)
        assert bytes(self.cpu.mem_read(SRAM+0x1bcc, p.STATE_BYTES)) == expected
        self.stats = self.get32(SRAM+0x1f04)
        assert self.stats == result[1]
        assert bytes(self.cpu.mem_read(self.stats, 1000)) == bytes(1000)
        self.events = []
        self.ring_reads = []
        self.phase = None
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, self.write)
        self.cpu.hook_add(UC_HOOK_MEM_READ, self.read)

    def read(self, cpu, access, address, size, value, data):
        if self.phase and self.address-4 <= address < self.address+RING_BYTES+4:
            assert self.address <= address and address+size <= self.address+0x8000
            self.ring_reads.append((self.phase, address, size, cpu.reg_read(r.UC_RISCV_REG_PC)))

    def write(self, cpu, access, address, size, value, data):
        if self.phase and (HEAP <= address < HEAP+HEAP_BYTES or SRAM <= address < SRAM+SRAM_BYTES or
                           self.address-4 <= address < self.address+RING_BYTES+4):
            self.events.append((self.phase, address, size, value, cpu.reg_read(r.UC_RISCV_REG_PC)))

    def run(self, start, stop):
        self.cpu.emu_start(start, stop, count=100000, timeout=1000000)
        assert self.cpu.reg_read(r.UC_RISCV_REG_PC) == stop, hex(self.cpu.reg_read(r.UC_RISCV_REG_PC))

    def producer(self, token, message, stop=PRODUCED):
        self.phase = 'producer'
        self.cpu.reg_write(r.UC_RISCV_REG_SP, STACK_TOPS[6]-0xc0)
        self.cpu.reg_write(r.UC_RISCV_REG_S0, token)
        self.cpu.reg_write(r.UC_RISCV_REG_A5, message)
        self.run(PRODUCER, stop)

    def consumer(self, stop=CONSUMED):
        self.phase = 'consumer'
        self.cpu.reg_write(r.UC_RISCV_REG_SP, STACK_TOPS[5]-0x40)
        self.run(CONSUMER, stop)


def producer_writes(slot, stats, token, message, index, count):
    return [('producer', slot+4, 4, token, 0x8400c96c),
            ('producer', slot+8, 4, message, 0x8400c96e),
            ('producer', slot, 4, 4, 0x8400c976),
            ('producer', stats+0x134, 4, count & p.U32, 0x8400c98e),
            ('producer', WRITE_INDEX, 2, index, 0x8400c9a6)]


def consumer_writes(slot, index):
    return [('consumer', READ_INDEX, 2, index, 0x8400cc4e),
            ('consumer', slot, 4, 0xfe, 0x8400cc52)]


def ring_cycle(h, address, mutant=None, slice_factory=RingSlice):
    cpu = slice_factory(h, address)
    if mutant:
        pc, length = mutant
        cpu.cpu.mem_write(pc, b'\x01\x00' if length == 2 else b'\x13\x00\x00\x00')
        cpu.cpu.ctl_remove_cache(pc, pc+length)
    expected_ring = bytearray(ring_template())
    expected_sram = bytearray(cpu.cpu.mem_read(SRAM, SRAM_BYTES))
    expected_heap = bytearray(cpu.cpu.mem_read(HEAP, HEAP_BYTES))
    original_counter = cpu.get32(cpu.stats+0x134)
    expected_events = []
    for index in range(2048):
        token = (index*13+7) & 0x7fff
        message = ((index*11 & 0x3fff) << 3) | (2 if index & 1 else 0)
        slot, next_index = address+index*16, (index+1) % 2048
        cpu.producer(token, message)
        assert bytes(cpu.cpu.mem_read(slot, 12)) == struct.pack('<III', 4, token, message), 'producer-payload-or-ready'
        assert struct.unpack('<H', cpu.cpu.mem_read(WRITE_INDEX, 2))[0] == next_index, 'producer-index'
        expected_events += producer_writes(slot, cpu.stats, token, message, next_index, original_counter+index+1)
        cpu.consumer()
        assert cpu.cpu.reg_read(r.UC_RISCV_REG_S10) == token
        assert cpu.cpu.reg_read(r.UC_RISCV_REG_A3) == message
        assert cpu.cpu.reg_read(r.UC_RISCV_REG_A1) == 4
        assert struct.unpack('<H', cpu.cpu.mem_read(READ_INDEX, 2))[0] == next_index, 'consumer-index'
        assert cpu.get32(slot) == 0xfe, 'consumer-slot-return'
        expected_events += consumer_writes(slot, next_index)
        struct.pack_into('<III', expected_ring, index*16, 0xfe, token, message)
    assert cpu.events == expected_events
    struct.pack_into('<I', expected_heap, cpu.stats+0x134-HEAP, (original_counter+2048) & p.U32)
    if HEAP <= address < HEAP+HEAP_BYTES:
        expected_heap[address-HEAP:address-HEAP+RING_BYTES] = expected_ring
    assert bytes(cpu.cpu.mem_read(HEAP, HEAP_BYTES)) == expected_heap
    assert bytes(cpu.cpu.mem_read(SRAM, SRAM_BYTES)) == expected_sram
    assert bytes(cpu.cpu.mem_read(address, RING_BYTES)) == expected_ring
    assert cpu.get32(address-4) == cpu.get32(address+RING_BYTES) == 0xa5a5a5a5
    return dict(base=hex(address), slot_count=2048, producer_consumer_pairs=2048,
                native_stats_initializer='0x8400a364', native_stats_address=hex(cpu.stats),
                whole_heap_compared=HEAP_BYTES, whole_sram_compared=SRAM_BYTES,
                extra_unused_bytes=16, exact_ordered_writes=len(cpu.events),
                writes_sha256=p.sha(json.dumps(cpu.events).encode()),
                ring_sha256=p.sha(expected_ring), index_wrap=True)


def full_queue(h, address, slice_factory=RingSlice):
    cpu = slice_factory(h, address)
    expected_ring = bytearray(ring_template())
    expected_sram = bytearray(cpu.cpu.mem_read(SRAM, SRAM_BYTES))
    expected_heap = bytearray(cpu.cpu.mem_read(HEAP, HEAP_BYTES))
    count, waits = cpu.get32(cpu.stats+0x134), cpu.get32(cpu.stats+0x110)
    events = []
    for index in range(2048):
        message = index << 3
        cpu.producer(index, message)
        events += producer_writes(address+index*16, cpu.stats, index, message,
                                  (index+1) % 2048, count+index+1)
        struct.pack_into('<III', expected_ring, index*16, 0xfe, index, message)
    assert all(cpu.get32(address+index*16) == 4 for index in range(2048))
    before = [bytes(cpu.cpu.mem_read(base, size)) for base, size in
              ((HEAP, HEAP_BYTES), (SRAM, SRAM_BYTES), (address, RING_BYTES))]
    cpu.producer(0x7777, 0x1230, BUSY)
    assert cpu.ring_reads[-1] == ('producer', address, 4, 0x8400c782)
    pending = cpu.cpu.context_save()
    assert cpu.events == events
    assert [bytes(cpu.cpu.mem_read(base, len(data))) for base, data in
            zip((HEAP, SRAM, address), before)] == before
    cpu.consumer()
    assert cpu.cpu.reg_read(r.UC_RISCV_REG_S10) == cpu.cpu.reg_read(r.UC_RISCV_REG_A3) == 0
    events += consumer_writes(address, 1)
    cpu.cpu.context_restore(pending)
    cpu.phase = 'producer'
    cpu.run(BUSY, PRODUCED)
    events.append(('producer', cpu.stats+0x110, 4, (waits+1) & p.U32, 0x8400c794))
    events += producer_writes(address, cpu.stats, 0x7777, 0x1230, 1, count+2049)
    for index in [*range(1, 2048), 0]:
        cpu.consumer()
        token, message = (index, index << 3) if index else (0x7777, 0x1230)
        assert cpu.cpu.reg_read(r.UC_RISCV_REG_S10) == token
        assert cpu.cpu.reg_read(r.UC_RISCV_REG_A3) == message
        events += consumer_writes(address+index*16, (index+1) % 2048)
    reads = len(cpu.ring_reads)
    cpu.consumer(EMPTY)
    assert cpu.ring_reads[reads:] == [('consumer', address+16, 4, 0x8400cbd6)]
    assert cpu.events == events
    struct.pack_into('<III', expected_ring, 0, 0xfe, 0x7777, 0x1230)
    struct.pack_into('<HH', expected_sram, READ_INDEX-SRAM, 1, 1)
    struct.pack_into('<I', expected_heap, cpu.stats+0x110-HEAP, (waits+1) & p.U32)
    struct.pack_into('<I', expected_heap, cpu.stats+0x134-HEAP, (count+2049) & p.U32)
    if HEAP <= address < HEAP+HEAP_BYTES:
        expected_heap[address-HEAP:address-HEAP+RING_BYTES] = expected_ring
    assert bytes(cpu.cpu.mem_read(HEAP, HEAP_BYTES)) == expected_heap
    assert bytes(cpu.cpu.mem_read(SRAM, SRAM_BYTES)) == expected_sram
    assert bytes(cpu.cpu.mem_read(address, RING_BYTES)) == expected_ring
    assert cpu.get32(address-4) == cpu.get32(address+RING_BYTES) == 0xa5a5a5a5
    return dict(base=hex(address), simultaneously_owned_slots=2048, producer_consumer_pairs=2049,
                full_queue_did_not_overwrite=True, resumed_after_native_consumer=True,
                empty_queue_did_not_read_payload=True, exact_ordered_writes=len(events),
                whole_heap_compared=HEAP_BYTES, whole_sram_compared=SRAM_BYTES,
                ring_sha256=p.sha(expected_ring), writes_sha256=p.sha(json.dumps(events).encode()))


def mutations(h):
    rows = []
    for name, pc, length, expected in (
        ('omit-publication', 0x8400c976, 2, 'producer-payload-or-ready'),
        ('omit-slot-return', 0x8400cc52, 2, 'consumer-slot-return'),
        ('omit-producer-wrap', 0x8400c998, 4, 'producer-index'),
        ('omit-consumer-wrap', 0x8400cc42, 4, 'consumer-index'),
    ):
        try:
            ring_cycle(h, RING, (pc, length))
        except AssertionError as error:
            assert str(error) == expected, (name, str(error))
            rows.append(dict(name=name, pc=hex(pc), bytes=length, assertion=expected, detected=True))
        else:
            raise AssertionError('surviving native ring mutant: '+name)
    return rows


def static_references():
    assert p.sha(GHIDRA.read_bytes()) == GHIDRA_SHA
    functions = exports()
    users = {address: fn for address, fn in functions.items() if 'DAT_ram_3e901f3c' in fn['text']}
    assert set(users) == {0x8400baae, 0x8400c284, 0x8400cb0e}
    producer = functions[0x8400c284]['assembly']
    consumer = functions[0x8400cb0e]['assembly']
    assert 'ram:8400c976 c.sw a3,0x0(a4)' in producer
    assert 'ram:8400cc52 c.sw s1,0x0(a5)' in consumer
    assert 'fence' not in producer and 'fence' not in consumer
    return [dict(function=hex(a), name=fn['name'], line=fn['line'],
                 direct_global_references=fn['text'].count('DAT_ram_3e901f3c')) for a, fn in users.items()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output', type=Path, default=OUT/'command-ring-layout.json')
    args = parser.parse_args()
    inputs = input_bindings()
    paths = [Path(__file__), Path(placed.__file__), Path(startup.__file__),
             p.SOURCE, p.HEADER, p.BINDING, Path(p.__file__), startup.SOURCE,
             startup.ASM, startup.LINKER, LINKER, PROVIDER, txdone.LINKER]
    inputs.update({str(path.relative_to(ROOT)): p.sha(path.read_bytes()) for path in paths})
    profile, command = build()
    txdone_path, _ = txdone.build()
    normal, _ = startup.build()
    reset, _ = build_reset()
    legacy = startup.StartupBridge(normal, reset)
    h = Profile(profile, reset)
    assert len(h.startup_results) == 7 and all(row[0] == 0 for row in h.startup_results)
    defs = [[tuple(row) for row in group] for group in p.definitions()]
    defs[0] = [(*row[:3], LAYOUT_HYPOTHESIS if row[0] == 0x81 else row[3]) for row in defs[0]]
    before = startup.state(h)
    assert before == native_state(defs, COLD_TYPES)
    assert bytes(h.cpu.mem_read(RING, RING_BYTES)) == ring_template()
    assert h.ring_writes == [(RING+i*16, 4, 0xfe) for i in range(2048)]
    original_ring = legacy.get32(POINTER)
    wanted_heap = bytearray(legacy.cpu.mem_read(HEAP, HEAP_BYTES))
    wanted_heap[original_ring-HEAP:original_ring-HEAP+RING_BYTES] = bytes(RING_BYTES)
    assert bytes(h.cpu.mem_read(HEAP, HEAP_BYTES)) == wanted_heap
    wanted_sram = bytearray(legacy.cpu.mem_read(SRAM, SRAM_BYTES))
    wanted_sram[0x1bcc:0x1bcc+p.STATE_BYTES] = before
    struct.pack_into('<I', wanted_sram, POINTER-SRAM, RING)
    assert bytes(h.cpu.mem_read(SRAM, SRAM_BYTES)) == wanted_sram
    assert bytes(h.cpu.mem_read(L2, L2_BYTES)) == bytes(legacy.cpu.mem_read(L2, L2_BYTES))
    placement = layout_proof(h, txdone_path)
    print(json.dumps(dict(core0_allocations=7, relocated_initializer_writes=len(h.ring_writes))), flush=True)
    bridge = h.probe()
    ring_after = bytes(h.cpu.mem_read(RING, RING_BYTES))
    assert ring_after == ring_template()
    assert startup.state(h) == native_state(defs, [*COLD_TYPES, 0x81])
    header_cases = headers(h)
    assert bytes(h.cpu.mem_read(RING, RING_BYTES)) == ring_after
    cached = startup.state(h)
    cached_memory = {base: bytes(h.cpu.mem_read(base, size)) for base, size in
                     ((HEAP, HEAP_BYTES), (RING, RING_BYTES), (L2, L2_BYTES))}
    for kind in [*COLD_TYPES, 0x81]:
        address = next(struct.unpack_from('<HHI', cached, 24+i*8)[2] for i in range(8)
                       if struct.unpack_from('<H', cached, 24+i*8)[0] == kind)
        assert h.call(0x84005200, kind) == address
        # emu_start stops before executing END, so complete the trace entry
        # using the actual return value rather than expecting an END hook.
        assert h.pending_call == {'type': kind, 'return_pc': p.END}
        h.allocations.append({**h.pending_call, 'value': address})
        h.pending_call = None
        assert startup.state(h) == cached
        assert all(bytes(h.cpu.mem_read(base, len(data))) == data for base, data in cached_memory.items())
    print(json.dumps(dict(bridge_bytes=LAYOUT_HYPOTHESIS, header_cases=len(header_cases),
                          free_primary_bytes=HEAP_BYTES-h.get32(SRAM+0x1be0))), flush=True)
    pair = placed.Pair(p.build(tag='layout-postboot'))
    post = []
    current = startup.state(h)
    for kind in (2, 9, 10):
        case = placed.Case('postboot-'+str(kind), defs, kind, 1, current)
        post.append(pair.placed_case(case))
        result, current, _ = placed.oracle(case)
        assert result[0] == p.OK
    rings = [ring_cycle(h, RING), ring_cycle(legacy, original_ring)]
    assert rings[0]['ring_sha256'] == rings[1]['ring_sha256']
    queues = [full_queue(h, RING), full_queue(legacy, original_ring)]
    assert queues[0]['ring_sha256'] == queues[1]['ring_sha256']
    print(json.dumps(dict(ring_pairs=8194, full_queue_capacity=2048)), flush=True)
    mutants = mutations(h)
    all_gates = txdone.retained_gate(txdone_path, profile, reset, bridge_bytes=LAYOUT_HYPOTHESIS)
    assert all(p.sha((ROOT/name).read_bytes()) == value for name, value in inputs.items())
    result = dict(schema=1, inputs_before_after=inputs, command=command,
                  elf_sha256=p.sha(profile.read_bytes()), static_references=static_references(),
                  layout=placement, checked_cold_allocations=h.startup_results[:7],
                  native_initializer_writes=len(h.ring_writes), bridge=bridge, headers=header_cases,
                  unchanged_native_cached_lookups=8, postboot_allocator_cases=post,
                  remaining_after_postboot_types=HEAP_BYTES-struct.unpack_from('<I', current, 20)[0],
                  ring_cycles=rings, full_queues=queues, mutants=mutants,
                  all37_retained_gate=all_gates,
                  limits=['Profile is unpromoted; all 2048 ring slots and 28672 native SKB entries retain original capacity.',
                          'Core0 uses native startup, actual checked allocation and native ring initialization under existing MMIO models.',
                          'Consumer/producer tests enter explicit instruction slices with caller registers supplied; downstream helpers and full worker reachability are not executed.',
                          'Serialized emulator memory does not prove cross-hart cache/coherency or ordering. Native consumers have no publication fences.',
                          'Direct decompiler references are not a complete pointer-alias closure proof.',
                          'Postboot types 2/9/10 use the compiled allocator on captured metadata; this is not complete native attachment or every firmware allocation profile.',
                          'No raw firmware package, image, router or physical test; full NPU boot and recovery remain incomplete.'])
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(result, indent=2)+'\n').encode()
    if args.check:
        assert output.read_bytes() == encoded
    else:
        output.write_bytes(encoded)
    print(json.dumps(dict(native_ring_pairs=sum(row['producer_consumer_pairs'] for row in rings+queues),
                          evidence_sha256=p.sha(encoded))))


if __name__ == '__main__':
    main()
