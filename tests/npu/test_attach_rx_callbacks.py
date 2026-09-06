#!/usr/bin/env python3
"""Original SET DESC0/2 callback closure, not strict-bootstrap API1 admission."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r

from test_native_wifi_boot import NativeWifi, to_wifi, host_publish, footprints, L2, L2_BYTES
from test_bootstrap_native import ROOT, plan, sha, DTB, BOOT, ADM
from test_boot_irq_installation import UnmodeledAccess
from test_firmware_memory_layout import table, STACK_TOPS
from test_firmware_mailbox_dispatch import MBOX, PAYLOAD
from test_firmware_stop_counterexample import INPUT, CODE_SHA, DATA_SHA, END
from test_mt7996_bootstrap_sequence import exports, GHIDRA, GHIDRA_SHA, expected
from emulation_layout import CODE, SRAM, SRAM_BYTES, HEAP, HEAP_BYTES

ELF = ROOT / '.local/npu-barrier/admission-platform-bootstrap-bootstrap-startup-gdma-gdma-65536.elf'
ELF_SHA = 'bdb64d12d738bdef85a747d0b638e6b148c1c534410fd893348fbaf5908e2931'
OUT = ROOT / 'research/checkpoints/2026-09-06-npu-attachrx/rx-callbacks.json'
PARENTS = {
    'test_native_wifi_boot.py': 'd86cf4fddda6804bd0391426cc5201b7e7214be7520ab688d9a8cb97cbec8340',
    'test_mt7996_bootstrap_sequence.py': '93a8faaab3de05599bd262fafd32564216cdb3ee438abf19ab006c8c057a94dd',
    'test_bootstrap_native.py': '8c78809cc82352c0b2b49de4cd7caee773228d77440bef479fc92bc0141cc843',
    'test_boot_irq_installation.py': '54fd846e16665d52cdcd79471bbac09e11b6e857ae0a717cb8c47f9698c93afd',
}
REGISTERS = {
    0x1ec031f0: ('write', 0x40, 'bufid lock28 acquire-request storage; no arbitration'),
    0x1ec03070: ('read', 0x10000, 'bufid lock28 owner readback storage seeded to hart0; no ownership proof'),
    0x1ec03270: ('write', 0, 'bufid lock28 release-request storage; no physical release'),
}
IMAGES = ((SRAM, SRAM_BYTES), (HEAP, HEAP_BYTES), (L2, L2_BYTES))
TARGETS = (0x8400fe34, 0x8400dd82, 0x8400d2d4, 0x8400a364, 0x84005200,
           0x84004ff8, 0x8400fab2, 0x8400b6ba, 0x8400b7e8, 0x84004d80,
           0x840064b4, 0x8400651c)
RETURNS = (0x84005200, 0x84004ff8, 0x8400fab2, 0x84004d80, 0x840064b4, 0x8400651c)
BANDS = {
    0: dict(count=1536, helper=0x8400b6ba, slow=0x102, aux=0x104, subcase=1,
            slow_slot=0x2aa8, aux_slot=0x45a0, rx_slot=0x2ab0, stats_slot=0x1f04,
            stats_type=10, ids=0x397c, flag=0x2a84,
            reset16=(0x1f4e, 0x2cec, 0x1f4c, 0x21f2), reset32=0x460c, reset8=0x2a8e),
    2: dict(count=1024, helper=0x8400b7e8, slow=0x103, aux=0x105, subcase=2,
            slow_slot=0x1f48, aux_slot=0x4594, rx_slot=0x2ce0, stats_slot=0x1f18,
            stats_type=9, ids=0x3100, flag=0x4588,
            reset16=(0x390a, 0x2aac, 0x2ac4, 0x2a7a), reset32=0x2a98, reset8=0x4614),
}
REMAINING_PENDING = [f'api1_if{i}_native_entry_only' for i in (5, 6, 7, 8, 10)] + [
    f'api19_if{i}_native_entry_only' for i in (0, 2)] + [
    f'txbuf_if{i}_txpkt_{value:x}_wait_boundary' for i in (10, 12) for value in (0, 0x8a000000)]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def images(h):
    return {start: bytearray(h.cpu.mem_read(start, length)) for start, length in IMAGES}


def ranges(addresses):
    """Lossless arithmetic runs of unique addresses, including repetitions."""
    items = sorted(addresses.items())
    result, i = [], 0
    while i < len(items):
        first, repeats = items[i]
        stride = items[i+1][0] - first if i+1 < len(items) and items[i+1][1] == repeats else 0
        j = i+1
        while stride and j < len(items) and items[j] == (first+(j-i)*stride, repeats):
            j += 1
        result.append([hex(first), j-i, stride if j-i > 1 else 0, repeats])
        i = j
    return result


class Trace:
    def __init__(self):
        self.groups, self.entries, self.first_args = {}, Counter(), {}
        self.pending, self.return_values, self.inner = [], {}, []
        self.memory_written = set()
        self.all_entries, self.ordinal = Counter(), 0
        self.ordered_hash = hashlib.sha256()

    def access(self, h, address, size, value, write):
        pc = h.cpu.reg_read(r.UC_RISCV_REG_PC)
        if any(base <= address < base+length for base, length in IMAGES):
            space = 'memory'
            if write:
                self.memory_written.update(range(address, address+size))
        elif STACK_TOPS[0]-0x100 <= address and address+size <= STACK_TOPS[0]:
            space = 'stack'
        elif PAYLOAD <= address and address+size <= PAYLOAD+12:
            space = 'payload'
        elif CODE <= address and address+size <= CODE+len(h.code) and not write:
            space = 'original-code-table'
        else:
            assert h.register_model(address, write) is not None, (hex(pc), hex(address), write)
            space = 'register'
        key = (pc, 'write' if write else 'read', size, space)
        self.ordinal += 1
        self.ordered_hash.update(struct.pack('<BIIII', int(write), pc, address, size, value))
        row = self.groups.setdefault(key, dict(addresses=Counter(), values=[], hash=hashlib.sha256(),
                                              count=0, first_ordinal=self.ordinal, last_ordinal=self.ordinal))
        row['last_ordinal'] = self.ordinal
        row['addresses'][address] += 1
        if not row['values']:
            row['values'] = [value, value, value, value]
        row['values'][1] = value
        row['values'][2] = min(row['values'][2], value)
        row['values'][3] = max(row['values'][3], value)
        row['hash'].update(struct.pack('<IIII', pc, address, size, value))
        row['count'] += 1

    def code(self, h, pc):
        value = h.cpu.reg_read(r.UC_RISCV_REG_A0)
        for start, return_pc in self.pending[:]:
            if pc == return_pc:
                self.return_values.setdefault(start, []).append(value)
                self.pending.remove((start, return_pc))
        if pc in TARGETS:
            self.entries[pc] += 1
            self.first_args.setdefault(pc, [h.cpu.reg_read(getattr(r, f'UC_RISCV_REG_A{i}')) for i in range(3)])
        if pc in RETURNS:
            self.pending.append((pc, h.cpu.reg_read(r.UC_RISCV_REG_RA)))
        if pc == 0x8400fe42:
            self.inner.append(value)

    def result(self, detailed):
        rows = [dict(pc=hex(pc), access=kind, size=size, space=space, count=row['count'],
                     address_runs=ranges(row['addresses']), values_first_last_min_max=[hex(v) for v in row['values']],
                     first_ordinal=row['first_ordinal'], last_ordinal=row['last_ordinal'],
                     ordered_access_sha256=row['hash'].hexdigest())
                for (pc, kind, size, space), row in sorted(self.groups.items())]
        returns = {hex(pc): dict(count=len(values), first=hex(values[0]), last=hex(values[-1]),
                                min=hex(min(values)), max=hex(max(values)),
                                values_sha256=digest(struct.pack('<'+'I'*len(values), *values)))
                   for pc, values in sorted(self.return_values.items())}
        result = dict(entries={hex(k): v for k, v in sorted(self.entries.items())},
                      all_function_entries={hex(k): v for k, v in sorted(self.all_entries.items())},
                      first_arguments={hex(k): [hex(v) for v in values] for k, values in sorted(self.first_args.items())},
                      returns=returns, inner_returns=self.inner,
                      all_ordered_access_sha256=self.ordered_hash.hexdigest(),
                      aggregate_sha256=digest(json.dumps(rows, sort_keys=True).encode()),
                      read_count=sum(row['count'] for row in rows if row['access'] == 'read'),
                      write_count=sum(row['count'] for row in rows if row['access'] == 'write'),
                      unique_memory_bytes_written=len(self.memory_written))
        if detailed:
            result['accesses'] = rows
        return result


class Closure:
    def __init__(self, path, exported):
        assert sha(path) == ELF_SHA
        self.h = h = to_wifi(path)
        assert isinstance(h, NativeWifi)
        self.boot_footprint = footprints(h)
        host_publish(h, False)
        assert h.message([0x30, 10, 0])['words'][2] == 0x457
        # This is the original port callback, not an expansion of strict admission.
        h.cpu.mem_write(PAYLOAD, struct.pack('<3I', 0x10, 14, 2))
        assert h.call(0x8400ff34, PAYLOAD) == 1
        assert bytes(h.cpu.mem_read(SRAM+0x390e, 1)) == b'\x02'
        self.boot_stubs = h.stub_counts.copy()
        assert set(self.boot_stubs) <= {'0x840048f4', '0x84004212', '0x84004130', '0x8400452a', 'mhartid-csr'}
        self.fixed = {row['type']: row['value'] for row in table(h.code, 0x8401cf70)}
        self.offsets = {row['type']: row['value'] for row in table(h.code, 0x8401cf18)}
        self.dynamic = {row['type']: row for row in table(h.code, 0x8401cfc8)}
        assert h.get32(SRAM+0x1b88) == HEAP
        assert bytes(h.cpu.mem_read(HEAP, 0x8000)) == struct.pack('<16384H', *range(16384))
        assert h.get32(SRAM+0x1b9c) == 28
        assert h.get32(SRAM+0x30fc) == HEAP+0x17000
        assert self.dynamic[1]['value'] == 303168
        assert any(row['type'] == 1 and row['value'] == HEAP+0x17000 for row in h.allocations)
        self.trace, self.missing = None, None
        self.functions = set(exported)
        self.original_model = h.register_model
        h.register_model = self.register_model
        h.put32(0x1ec03070, 0x10000)
        h.cpu.hook_add(UC_HOOK_CODE, self.code)
        h.cpu.hook_add(UC_HOOK_MEM_READ, self.read)
        h.cpu.hook_add(UC_HOOK_MEM_WRITE, self.write)

    def register_model(self, address, write):
        if address == self.missing:
            return None
        if address in REGISTERS:
            kind, _, description = REGISTERS[address]
            return description if write == (kind == 'write') else None
        return self.original_model(address, write)

    def code(self, cpu, pc, size, _):
        if self.trace is not None:
            if pc in self.functions:
                self.trace.all_entries[pc] += 1
            self.trace.code(self.h, pc)

    def read(self, cpu, access, address, size, value, _):
        if self.trace is not None:
            self.trace.access(self.h, address, size, int.from_bytes(cpu.mem_read(address, size), 'little'), False)

    def write(self, cpu, access, address, size, value, _):
        if self.trace is not None:
            self.trace.access(self.h, address, size, value, True)

    def snapshot(self):
        h = self.h
        return h.cpu.context_save(), [(base, bytes(h.cpu.mem_read(base, end-base+1)))
                                       for base, end, _ in h.cpu.mem_regions()]

    def restore(self, snapshot):
        h = self.h
        self.trace, self.missing = None, None
        for base, data in snapshot[1]:
            h.cpu.mem_write(base, data)
        h.cpu.context_restore(snapshot[0])
        h.pending_call, h.unmodeled = None, None
        h.allocations.clear()
        h.logs.clear()
        h.events.clear()
        h.mmio.clear()
        h.stub_counts.clear()
        h.stub_returns.clear()

    def invoke(self, selector, count, detailed=False):
        h = self.h
        h.cpu.mem_write(PAYLOAD, struct.pack('<3I', 0x10|selector, 1, count))
        h.put32(MBOX+0x3c, 1)
        h.cpu.reg_write(r.UC_RISCV_REG_SP, STACK_TOPS[0])
        h.cpu.reg_write(r.UC_RISCV_REG_RA, END)
        h.cpu.reg_write(r.UC_RISCV_REG_A0, PAYLOAD)
        h.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 0)
        h.unmodeled = None
        before_allocations, before_logs = len(h.allocations), len(h.logs)
        self.trace = trace = Trace()
        error, result = None, None
        try:
            assert h.run(0x8400fe34, []) == END
            result = h.cpu.reg_read(r.UC_RISCV_REG_A0)
        except UnmodeledAccess as exc:
            error = str(exc)
        finally:
            self.trace = None
        assert set(h.stub_counts) <= {'0x840048f4', '0x84004212'}, h.stub_counts
        assert set(trace.all_entries) <= set(TARGETS) | {0x840048f4, 0x84004212}
        assert h.get32(MBOX+0x3c) == 1  # Direct callback never fabricates mailbox completion.
        assert h.get32(BOOT+8) == 6 and h.get32(ADM) == 1
        row = dict(selector=selector, requested_count=count, callback_return=result,
                   mailbox_flags_untouched=1, ready_flag=h.get32(SRAM+BANDS[selector]['flag']),
                   stopped_access=error, trace=trace.result(detailed),
                   native_lookup_returns=h.allocations[before_allocations:],
                   logs=[dict(format=fmt, count=n) for fmt, n in Counter(
                       item['format'] for item in h.logs[before_logs:]).items()])
        return row, trace


def oracle(c, before, selector, count):
    """Independent source-table/descriptor oracle, never learned from observed writes."""
    b = BANDS[selector]
    result = {base: bytearray(data) for base, data in before.items()}
    allowed = set()

    def read(address, fmt='I'):
        for base, data in before.items():
            if base <= address < base+len(data):
                return struct.unpack_from('<'+fmt, data, address-base)[0]
        raise AssertionError(hex(address))

    def put(address, data):
        for base, image in result.items():
            if base <= address and address+len(data) <= base+len(image):
                image[address-base:address-base+len(data)] = data
                allowed.update(range(address, address+len(data)))
                return
        raise AssertionError(('oracle extent outside mapped RAM', hex(address), len(data)))

    def number(address, value, fmt='I'):
        put(address, struct.pack('<'+fmt, value))

    slow, aux = c.fixed[b['slow']], c.fixed[b['aux']]
    arena = read(SRAM+0x30fc)
    rx = arena+c.offsets[b['subcase']]
    for offset in b['reset16']:
        number(SRAM+offset, 0, 'H')
    for offset, value in ((b['slow_slot'], slow), (b['aux_slot'], aux), (b['rx_slot'], rx)):
        number(SRAM+offset, value)
    for index in range(512):
        put(slow+index*12, struct.pack('<IIHBB', 0xffffffff, 0, 0, 0, 0))
    for index in range(128):
        put(aux+index*12, struct.pack('<IIB', 0xffffffff, 0, 0))
    index, heap_offset = read(SRAM+0x1bd4), read(SRAM+0x1be0)
    assert b['stats_type'] not in [read(SRAM+0x1be4+i*8, 'H') for i in range(index)]
    stats = HEAP+(heap_offset+31)//32*32
    assert c.dynamic[b['stats_type']]['value'] == 1000
    assert c.dynamic[b['stats_type']]['alignment_tag'] == 0
    number(SRAM+0x1bdc, read(SRAM+0x1bdc)+1)
    number(SRAM+0x1be4+index*8, b['stats_type'], 'H')
    number(SRAM+0x1be8+index*8, stats)
    number(SRAM+0x1be0, stats-HEAP+1000)
    number(SRAM+0x1bd4, index+1)
    number(SRAM+b['stats_slot'], stats)
    put(stats, bytes(1000))
    head, tail = read(SRAM+0x1ba4, 'H'), read(SRAM+0x1b80, 'H')
    allocated = min(count, (tail-head-1) % 0x4000)
    failed = allocated != count
    ids = [read(read(SRAM+0x1b88)+((head+i) % 0x4000)*2, 'H') for i in range(allocated)]
    packet = read(SRAM+0x396c)
    pool_stats = read(SRAM+0x1f08)
    for index, bufid in enumerate(ids):
        pointer = ((packet+bufid*2048) & 0x3fffffff | 0x80000000)+128
        number(SRAM+b['ids']+index*2, bufid, 'H')
        put(rx+index*16, struct.pack('<4I', pointer, 0x07000100, bufid << 16, 0))
    if allocated:
        number(SRAM+0x1ba4, (head+allocated) % 0x4000, 'H')
        number(SRAM+0x1b90, read(SRAM+0x1b90)+allocated)
        number(pool_stats+0x1c, read(pool_stats+0x1c)+allocated)
    if failed:
        number(pool_stats+0x20, read(pool_stats+0x20)+1)
    else:
        number(SRAM+b['reset32'], 0)
        number(SRAM+b['reset8'], 0, 'B')
        number(SRAM+b['flag'], 1)
    next_offset = min(offset for offset in c.offsets.values() if offset > c.offsets[b['subcase']])
    return result, allowed, dict(allocated=allocated, failed=failed,
        slow_table=dict(base=hex(slow), entries=512, stride=12, bytes=6144),
        auxiliary_table=dict(base=hex(aux), entries=128, stride=12, bytes_written_per_entry=9,
                             extent_bytes=1536, preserved_tail_bytes_per_entry=3),
        rx_descriptors=dict(base=hex(rx), entries=allocated, stride=16, end=hex(rx+allocated*16),
                            nominal_end=hex(rx+b['count']*16), next_subregion=hex(arena+next_offset)),
        software_ids=dict(base=hex(SRAM+b['ids']), end=hex(SRAM+b['ids']+allocated*2),
                          first=ids[0] if ids else None, last=ids[-1] if ids else None),
        stats=dict(base=hex(stats), bytes=1000),
        packet_slots=dict(base=hex(packet), stride=2048, data_offset=128,
                          first=hex(packet+ids[0]*2048) if ids else None,
                          last_end=hex(packet+(ids[-1]+1)*2048) if ids else None,
                          reservation_end=hex(sum(plan()[2])), packet_memory_accessed=False))


def completed(c, selector, count, name, detailed=False):
    before = images(c.h)
    want, allowed, footprint = oracle(c, before, selector, count)
    row, trace = c.invoke(selector, count, detailed)
    assert row['stopped_access'] is None and row['callback_return'] == 1, row
    assert trace.inner == [int(footprint['failed'])]
    assert row['ready_flag'] == int(not footprint['failed'])
    assert images(c.h) == want, (name, 'whole RAM images differ from independent oracle')
    assert trace.memory_written == allowed, (name, 'unexpected or missing consumer writes',
                                            sorted(trace.memory_written-allowed)[:8], sorted(allowed-trace.memory_written)[:8])
    assert trace.entries[0x8400d2d4] == trace.entries[BANDS[selector]['helper']] == 1
    assert trace.entries[0x84004d80] == footprint['allocated']+int(footprint['failed'])
    assert trace.entries[0x84005200] == 3 and trace.entries[0x84004ff8] == trace.entries[0x8400fab2] == 1
    assert trace.first_args[0x8400d2d4][0] == selector
    assert trace.first_args[BANDS[selector]['helper']][:2] == [count, selector//2]
    b = BANDS[selector]
    stats = int(footprint['stats']['base'], 16)
    rx = int(footprint['rx_descriptors']['base'], 16)
    lookups = [(b['slow'], c.fixed[b['slow']]), (b['aux'], c.fixed[b['aux']]), (b['stats_type'], stats)]
    assert [(item['type'], item['value']) for item in row['native_lookup_returns']] == lookups
    assert trace.return_values[0x84005200] == [value for _, value in lookups]
    assert trace.return_values[0x84004ff8] == [stats]
    assert trace.return_values[0x8400fab2] == [rx]
    for pc in (0x840064b4, 0x8400651c):
        assert set(trace.return_values[pc]) == {0}
    head = struct.unpack_from('<H', before[SRAM], 0x1ba4)[0]
    pool = struct.unpack_from('<I', before[SRAM], 0x1b88)[0]
    ids = [struct.unpack_from('<H', before[HEAP], pool-HEAP+((head+i) % 0x4000)*2)[0]
           for i in range(footprint['allocated'])]
    assert trace.return_values.get(0x84004d80, []) == ids+([0xffffffff] if footprint['failed'] else [])
    diagnostic = sum(item['count'] for item in row['logs'] if 'ERROR! rx_ring_size' in item['format'])
    assert diagnostic == int(count == 0 or count > 1536)
    if not footprint['failed']:
        flag = SRAM+b['flag']
        memory_writes = [group for (_, kind, _, space), group in trace.groups.items()
                         if kind == 'write' and space == 'memory']
        publication = [group for group in memory_writes if flag in group['addresses']]
        assert len(publication) == 1 and publication[0]['count'] == 1
        assert publication[0]['first_ordinal'] > max(group['last_ordinal'] for group in memory_writes
                                                     if group is not publication[0])
    row.update(name=name, footprint=footprint, whole_ram_compared_bytes=sum(length for _, length in IMAGES),
               whole_ram_sha256={hex(base): digest(data) for base, data in want.items()},
               exact_memory_write_footprint=True, size_diagnostics=diagnostic,
               ready_publication_after_other_memory_writes=not footprint['failed'])
    return row


def rejected_access(c, selector, name, expected_pc, expected_address):
    row, _ = c.invoke(selector, BANDS[selector]['count'])
    assert row['callback_return'] is None and row['ready_flag'] == 0, row
    assert hex(expected_pc) in row['stopped_access'] and hex(expected_address) in row['stopped_access'], row
    row['name'] = name
    row['partial_state'] = {hex(offset): hex(c.h.get32(SRAM+offset))
                            for offset in (0x1ba4, 0x1b90, 0x1be0, BANDS[selector]['stats_slot'])}
    return row


def run(path):
    exported = exports()
    dependencies = {Path(module.__file__).resolve() for module in list(sys.modules.values())
                    if getattr(module, '__file__', None)
                    and Path(module.__file__).resolve().is_relative_to(ROOT/'tests/npu')}
    dependency_hashes = {file: sha(file) for file in dependencies}
    for name, expected_sha in PARENTS.items():
        assert sha(ROOT/'tests/npu'/name) == expected_sha, name
    assert sha(path) == ELF_SHA
    c = Closure(path, exported)
    h = c.h
    assert h.get32(SRAM+0x17c) == 0x8400fe34
    for pc in TARGETS:
        lines = exported[pc]['assembly'].strip().splitlines()
        last = lines[-1].split()[0].split(':')[1]
        last_pc = int(last, 16)
        halfword = int.from_bytes(h.code[last_pc-CODE:last_pc-CODE+2], 'little')
        end = last_pc+(4 if halfword & 3 == 3 else 2)
        assert bytes(h.cpu.mem_read(pc, end-pc)) == h.code[pc-CODE:end-CODE]
    first = c.snapshot()
    c.restore(first)
    valid0 = completed(c, 0, 1536, 'host_sequence_desc0', True)
    second = c.snapshot()
    c.restore(second)
    valid2 = completed(c, 2, 1024, 'host_sequence_desc2_after_desc0', True)
    assert valid0['footprint']['software_ids']['first'] == 0
    assert valid0['footprint']['software_ids']['last'] == 1535
    assert valid2['footprint']['software_ids']['first'] == 1536
    assert valid2['footprint']['software_ids']['last'] == 2559
    assert h.get32(SRAM+0x1b90) == 2560 and h.get32(SRAM+0x1ba4) == 2560
    for row in (valid0, valid2):
        assert int(row['footprint']['packet_slots']['last_end'], 16) <= sum(plan()[2])
    # A real native completed prefix is restored for each bounded control.
    controls = []
    for selector, snapshot in ((0, first), (2, second)):
        for allocated in (0, 17):
            c.restore(snapshot)
            head = int.from_bytes(h.cpu.mem_read(SRAM+0x1ba4, 2), 'little')
            h.cpu.mem_write(SRAM+0x1b80, struct.pack('<H', (head+allocated+1) % 0x4000))
            row = completed(c, selector, BANDS[selector]['count'], f'bufid_exhaustion_if{selector}_after{allocated}')
            assert row['footprint']['failed'] and row['footprint']['allocated'] == allocated
            controls.append(row)
        c.restore(snapshot)
        h.put32(SRAM+0x396c, 0)
        row = completed(c, selector, BANDS[selector]['count'], f'missing_packet_base_if{selector}_accepted')
        assert row['ready_flag'] == 1
        controls.append(row)
        c.restore(snapshot)
        controls.append(completed(c, selector, 0, f'zero_capacity_if{selector}_accepted'))
        c.restore(snapshot)
        oversized = 1539 if selector == 0 else 1027
        row = completed(c, selector, oversized, f'next_subregion_crossed_if{selector}')
        assert int(row['footprint']['rx_descriptors']['end'], 16) == int(row['footprint']['rx_descriptors']['next_subregion'], 16)+16
        controls.append(row)
        c.restore(snapshot)
        h.put32(SRAM+0x30fc, 0)
        controls.append(rejected_access(c, selector, f'missing_wifi_arena_if{selector}',
                                       0x8400b748 if selector == 0 else 0x8400b876,
                                       c.offsets[BANDS[selector]['subcase']]+4))
        c.restore(snapshot)
        h.put32(SRAM+0x1b88, 0)
        head = int.from_bytes(h.cpu.mem_read(SRAM+0x1ba4, 2), 'little')
        controls.append(rejected_access(c, selector, f'missing_bufid_table_if{selector}', 0x84004dea, head*2))
        c.restore(snapshot)
        h.put32(SRAM+0x1be0, HEAP_BYTES)
        row = rejected_access(c, selector, f'native_stats_allocation_failure_if{selector}', 0x8400a384, 0)
        assert row['native_lookup_returns'][-1]['value'] == 0
        controls.append(row)
        c.restore(snapshot)
        h.put32(SRAM+0x1be0, HEAP_BYTES-32)
        row = rejected_access(c, selector, f'native_stats_allocation_extent_if{selector}', 0x8400a384, HEAP+HEAP_BYTES)
        assert row['native_lookup_returns'][-1]['value'] == HEAP+HEAP_BYTES-32
        controls.append(row)
    for address in REGISTERS:
        c.restore(first)
        c.missing = address
        pc = 0x840064f4 if address == 0x1ec03070 else 0x84006554 if address == 0x1ec03270 else 0x840064f2
        controls.append(rejected_access(c, 0, f'missing_register_model_{address:x}', pc, address))
    c.restore(first)
    strict = [h.message([0x10|selector, 1, count]) for selector, count in ((0, 1536), (2, 1024))]
    assert [row['flags'] for row in strict] == [3, 3]
    assert all(not row['callbacks'] for row in strict)
    assert not h.allocations
    assert h.get32(SRAM+0x2a84) == h.get32(SRAM+0x4588) == 0
    assert sha(path) == ELF_SHA
    assert all(sha(file) == value for file, value in dependency_hashes.items())
    profiles = [[(m['word0'] & 15, m['value']) for m in expected(hif2, port)
                 if m['kind'] == 'message' and m['api'] == 1][:2]
                for hif2 in (0, 1) for port in (2, 3)]
    assert profiles == [[(0, 1536), (2, 1024)]]*4
    sources = {str(file.relative_to(ROOT)): value for file, value in dependency_hashes.items()}
    sources.update({str(Path(__file__).relative_to(ROOT)): sha(Path(__file__)),
                    str(path.relative_to(ROOT)): ELF_SHA, str(GHIDRA.relative_to(ROOT)): GHIDRA_SHA,
                    str(DTB.relative_to(ROOT)): sha(DTB),
                    str((INPUT/'en7581_MT7996_npu_rv32.bin').relative_to(ROOT)): CODE_SHA,
                    str((INPUT/'en7581_MT7996_npu_data.bin').relative_to(ROOT)): DATA_SHA})
    return dict(schema=1, scope='Original callback closure on native initialized core0; storage-only MMIO; no strict API1 admission or hardware proof.',
        base_commit='bc82345173efec5049e4cfc6e399966ab82b08f5', sources=sources,
        counts=dict(new_callback_closures=2, original_pending_paths=13, remaining_original_pending_paths=11,
                    remaining_separately_allocator_modeled_cases=2,
                    valid_callbacks=2, negative_controls=len(controls), strict_rejections=2,
                    nominal_rx_descriptors=2560, nominal_software_ids=2560, slow_table_records=1024,
                    auxiliary_table_records=256, stats_bytes=2000),
        prerequisite_state=dict(origin='to_wifi -> footprints -> host_publish -> GET10 -> original SET14(port2)',
            native_initialized_snapshot_reuse=True, boot_footprint=c.boot_footprint, boot_stub_counts=c.boot_stubs,
            callback_stubs_only=['printf(840048f4)', 'hart-id(84004212)'],
            callback_lookup_binding='original DATA +0x17c -> 0x8400fe34',
            wifi_arena=dict(base=hex(HEAP+0x17000), bytes=c.dynamic[1]['value'], subregion_offsets=c.offsets),
            bufid_table=dict(base=hex(HEAP), entries=16384, all_initial_contents_verified=True),
            new_register_models={hex(address): dict(direction=kind, seed_or_written_value=hex(value), model=model)
                                 for address, (kind, value, model) in REGISTERS.items()}),
        ghidra_functions={hex(pc): dict(line=exported[pc]['line'], name=exported[pc]['name'],
            export_sha256=digest((exported[pc]['text']+exported[pc]['assembly']).encode())) for pc in TARGETS},
        trace_encoding='address_runs = [first, unique_address_count, stride_bytes, repeats_per_address]; values = first,last,min,max; group SHA covers ordered (pc,address,size,value) uint32 tuples; global SHA prefixes uint8 write=1/read=0. Ordinals order all accesses. Full aggregates for valid callbacks; compact counts/digests for controls. Failed accesses are separate stop records.',
        valid_sequence=[valid0, valid2], negative_controls=controls,
        remaining_original_pending_cases=REMAINING_PENDING,
        remaining_separately_allocator_modeled_cases=['txbuf_if5_native_128byte_records_model_allocator',
                                                      'txbuf_if7_native_128byte_records_model_allocator'],
        strict_bootstrap=dict(api1_admitted=False, replies=strict),
        boundaries=['Eleven other originally pending paths remain unclosed by this sidecar.',
                    'Direct callbacks leave mailbox flags at 1; wrapper return and ready flags are not strict transport completion.',
                    'No packet memory, physical MMIO, DMA/cache effects, contention, all-hart boot, recovery, or parity proof.',
                    'Capacity/missing-prerequisite controls mutate emulator RAM only; they are conditional counterexamples, not observed device failures.',
                    'No firmware source/config/shared-build/ledger edits or shared ELF rebuild; parent owns integration.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--elf', type=Path, default=ELF)
    parser.add_argument('--check', action='store_true', help='verify without rewriting evidence')
    args = parser.parse_args()
    result = run(args.elf.resolve())
    encoded = json.dumps(result, indent=2, sort_keys=True)+'\n'
    assert len(encoded.encode()) < 400000, 'bounded evidence budget exceeded'
    if args.check:
        assert OUT.read_text() == encoded, 'committed evidence differs from fresh replay'
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(encoded)
    print(json.dumps(dict(status='PASS', **result['counts'], bytes=len(encoded.encode()),
                          json_sha256=digest(encoded.encode()), test_sha256=sha(Path(__file__)))))


if __name__ == '__main__':
    main()
