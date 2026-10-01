#!/usr/bin/env python3
"""Original DESC5/6/7/8 consumers with independently predicted native writes."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
from unicorn import riscv_const as r

import test_attach_rx_callbacks as rx
import test_bootstrap_postgate as postgate
from test_mt7996_bootstrap_sequence import exports, SET_CALLBACKS

ROOT = Path(__file__).resolve().parents[2]
CALLBACK, DISPATCH, LOOKUP = 0x8400fe34, 0x8400dd82, 0x8400fab2
PAGE, ALLOC, INDICATION = 0x8400bc02, 0x8400bb9c, 0x8400bae6
TARGETS = (CALLBACK, DISPATCH, LOOKUP, PAGE, ALLOC, INDICATION)
PROFILES = {
    5: dict(kind=7, count=256, slot=0x2a94, slot_pc=0x8400de10,
            ids=0x2ad0, ids_pc=0x8400bc68,
            done=((0x8400bd62, 0x1f44, 4, 1), (0x8400bd6a, 0x4580, 4, 0),
                  (0x8400bd72, 0x21dc, 1, 0))),
    6: dict(kind=8, count=512, slot=0x2aa4, slot_pc=0x8400de82,
            ids=0x2cfc, ids_pc=0x8400bce6,
            done=((0x8400bd7e, 0x2ac8, 4, 0), (0x8400bd86, 0x3954, 4, 1),
                  (0x8400bd8e, 0x3958, 1, 0))),
    7: dict(kind=9, count=1024, slot=0x4638, slot_pc=0x8400de94,
            ids=0x21f8, ids_pc=0x8400bcd4,
            done=((0x8400bd48, 0x2ce8, 4, 1), (0x8400bd50, 0x4598, 4, 0),
                  (0x8400bd58, 0x4584, 1, 0))),
    8: dict(kind=6, count=1536, slot=0x2aa0, slot_pc=0x8400de3a,
            done=((0x8400bb2a, 0x1fd4, 4, 0), (0x8400bb32, 0x4590, 1, 0))),
}
DESCRIPTOR_PCS = {0x8400bc88, 0x8400bc8c, 0x8400bc8e, 0x8400bc90, 0x8400bc9c}
ID_PCS = {p['ids_pc'] for p in PROFILES.values() if 'ids_pc' in p}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Trace(rx.Trace):
    def __init__(self):
        super().__init__()
        self.writes = []

    def code(self, h, pc):
        value = h.cpu.reg_read(r.UC_RISCV_REG_A0)
        for start, return_pc in self.pending[:]:
            if pc == return_pc:
                self.return_values.setdefault(start, []).append(value)
                self.pending.remove((start, return_pc))
        if pc in TARGETS:
            self.entries[pc] += 1
            self.first_args.setdefault(pc, [h.cpu.reg_read(getattr(r, 'UC_RISCV_REG_A' + str(i)))
                                           for i in range(3)])
            if pc != DISPATCH:
                self.pending.append((pc, h.cpu.reg_read(r.UC_RISCV_REG_RA)))
        if pc == 0x8400fe42:
            self.inner.append(value)

    def access(self, h, address, size, value, write):
        super().access(h, address, size, value, write)
        if write and any(base <= address and address + size <= base + length
                         for base, length in rx.IMAGES):
            self.writes.append((h.cpu.reg_read(r.UC_RISCV_REG_PC), address, size, value))


class Closure(rx.Closure):
    def __init__(self):
        super().__init__(rx.ELF, exports())
        self.capacity = None
        self.code_image = bytes(self.h.cpu.mem_read(rx.CODE, len(self.h.code)))
        memory = self.h.is_memory

        def bounded(address, size):
            if self.capacity:
                pc = self.h.cpu.reg_read(r.UC_RISCV_REG_PC)
                if pc in self.capacity['pcs']:
                    base, length = self.capacity['base'], self.capacity['bytes']
                    return base <= address and address + size <= base + length
            return memory(address, size)

        self.h.is_memory = bounded

    def restore(self, saved):
        self.capacity = None
        super().restore(saved)
        self.h.cpu.ctl_remove_cache(rx.CODE, rx.CODE + len(self.h.code))
        self.code_image = bytes(self.h.cpu.mem_read(rx.CODE, len(self.h.code)))

    def invoke(self, selector, count, detailed=False):
        h = self.h
        h.cpu.mem_write(rx.PAYLOAD, struct.pack('<3I', 0x10 | selector, 1, count))
        h.put32(rx.MBOX + 0x3c, 1)
        for reg, value in ((r.UC_RISCV_REG_SP, rx.STACK_TOPS[0]),
                           (r.UC_RISCV_REG_RA, rx.END), (r.UC_RISCV_REG_A0, rx.PAYLOAD),
                           (r.UC_RISCV_REG_MSTATUS, 0)):
            h.cpu.reg_write(reg, value)
        before_allocations = len(h.allocations)
        self.trace = trace = Trace()
        error, result = None, None
        try:
            assert h.run(CALLBACK, []) == rx.END
            result = h.cpu.reg_read(r.UC_RISCV_REG_A0)
            trace.code(h, rx.END)
        except rx.UnmodeledAccess as exc:
            error = str(exc)
        finally:
            self.trace = None
        assert set(h.stub_counts) <= {'0x840048f4'}, h.stub_counts
        assert set(trace.all_entries) <= set(TARGETS) | {0x840048f4}, trace.all_entries
        assert not h.allocations[before_allocations:], 'No dynamic allocation helper belongs to this path'
        assert h.get32(rx.MBOX + 0x3c) == 1
        assert h.get32(rx.BOOT + 8) == 6 and h.get32(rx.ADM) == 1
        assert bytes(h.cpu.mem_read(rx.CODE, len(h.code))) == self.code_image
        return dict(selector=selector, count=count, callback_return=result, stopped_access=error,
                    helper_return=trace.inner, trace=trace.result(detailed),
                    logs=[dict(format=k, count=v) for k, v in Counter(
                        log['format'] for log in h.logs).items()]), trace


def oracle(c, selector, count):
    before = rx.images(c.h)
    want = {base: bytearray(data) for base, data in before.items()}
    writes, failure, ids = [], None, []
    profile = PROFILES[selector]

    def read(address, size=4, signed=False):
        for base, data in want.items():
            if base <= address and address + size <= base + len(data):
                return int.from_bytes(data[address - base:address - base + size], 'little', signed=signed)
        raise AssertionError(('oracle-read', hex(address), size))

    def put(pc, address, size, value):
        nonlocal failure
        if c.capacity and pc in c.capacity['pcs']:
            base, length = c.capacity['base'], c.capacity['bytes']
            if not base <= address or address + size > base + length:
                failure = dict(pc=hex(pc), address=hex(address), size=size)
                return False
        for base, data in want.items():
            if base <= address and address + size <= base + len(data):
                data[address - base:address - base + size] = (value & ((1 << (size * 8)) - 1)).to_bytes(size, 'little')
                writes.append((pc, address, size, value & ((1 << (size * 8)) - 1)))
                return True
        failure = dict(pc=hex(pc), address=hex(address), size=size)
        return False

    arena = read(rx.SRAM + 0x30fc)
    ring = (arena + c.offsets[profile['kind']]) & 0xffffffff
    if not put(profile['slot_pc'], rx.SRAM + profile['slot'], 4, ring):
        return want, writes, failure, ids, False, ring
    exhausted = False
    if selector == 8:
        for i in range(count):
            address = ring + i * 8 + 4
            # Missing-backing controls must stop at the native load, before store.
            if not any(base <= address and address + 4 <= base + len(data) for base, data in want.items()):
                failure = dict(pc='0x8400bb10', address=hex(address), size=4)
                return want, writes, failure, ids, exhausted, ring
            if c.capacity and not (c.capacity['base'] <= address and
                                   address + 4 <= c.capacity['base'] + c.capacity['bytes']):
                failure = dict(pc='0x8400bb10', address=hex(address), size=4)
                return want, writes, failure, ids, exhausted, ring
            if not put(0x8400bb1a, address, 4, read(address) | 0xe0000000):
                return want, writes, failure, ids, exhausted, ring
    else:
        for i in range(count):
            head = read(rx.SRAM + 0x3950, 2)
            next_head = (head + 1) & 0xffff
            if next_head == 8192:
                next_head = 0
            tail, stats = read(rx.SRAM + 0x1f40, 2), read(rx.SRAM + 0x1f08)
            if tail == next_head:
                if stats:
                    assert put(0x8400bbfe, stats + 0x44, 4, read(stats + 0x44) + 1)
                exhausted = True
                break
            if stats:
                assert put(0x8400bbd8, stats + 0x48, 4, read(stats + 0x48) + 1)
            pool = read(rx.SRAM + 0x4634)
            bufid = read(pool + head * 2, 2, signed=True)
            assert put(0x8400bbf0, rx.SRAM + 0x3950, 2, next_head)
            if bufid == -1:
                exhausted = True
                break
            ids.append(bufid)
            if not put(profile['ids_pc'], rx.SRAM + profile['ids'] + i * 2, 2, bufid):
                return want, writes, failure, ids, exhausted, ring
            packet = read(rx.SRAM + 0x2ce4)
            pointer = ((bufid * 128 + packet) & 0x3fffffff) | 0x80000000
            for pc, offset, value in ((0x8400bc88, 4, 0), (0x8400bc8c, 0, pointer),
                                      (0x8400bc8e, 8, bufid << 16), (0x8400bc90, 12, 0),
                                      (0x8400bc9c, 4, 0x800100)):
                if not put(pc, ring + i * 16 + offset, 4, value):
                    return want, writes, failure, ids, exhausted, ring
    if not exhausted:
        for pc, offset, size, value in profile['done']:
            assert put(pc, rx.SRAM + offset, size, value)
    return want, writes, failure, ids, exhausted, ring


def completed(c, selector, count, name, detailed=False):
    arena = c.h.get32(rx.SRAM + 0x30fc)
    packet = c.h.get32(rx.SRAM + 0x2ce4)
    want, writes, failure, ids, exhausted, ring = oracle(c, selector, count)
    row, trace = c.invoke(selector, count, detailed)
    assert rx.images(c.h) == want, (name, 'whole-memory-oracle')
    assert trace.writes == writes, (name, 'ordered-writes', len(trace.writes), len(writes))
    allowed = {address + i for _, address, size, _ in writes for i in range(size)}
    assert trace.memory_written == allowed
    assert trace.entries[CALLBACK] == trace.entries[DISPATCH] == trace.entries[LOOKUP] == 1
    assert trace.return_values[LOOKUP] == [ring]
    assert trace.first_args[LOOKUP] == [arena, 1, PROFILES[selector]['kind']]
    if failure:
        assert row['callback_return'] is None and row['stopped_access']
        assert failure['pc'] in row['stopped_access'] and failure['address'] in row['stopped_access'], row
        assert not trace.inner
    else:
        assert row['callback_return'] == 1 and row['stopped_access'] is None
        assert trace.inner == [int(exhausted)]
        assert trace.return_values[CALLBACK] == [1] and not trace.pending
        if selector != 8:
            assert trace.return_values.get(ALLOC, []) == [x & 0xffffffff for x in ids] + ([0xffffffff] if exhausted else [])
            assert trace.entries[ALLOC] == len(ids) + int(exhausted)
        else:
            assert trace.entries[ALLOC] == 0
    row.update(name=name, oracle_failure=failure, exhausted=exhausted,
               exact_ordered_ram_writes=len(writes), exact_unique_memory_write_bytes=len(allowed),
               whole_ram_compared_bytes=sum(len(x) for x in want.values()),
               whole_ram_sha256={hex(base): hashlib.sha256(data).hexdigest() for base, data in want.items()},
               ring_base=hex(ring), descriptor_stride=8 if selector == 8 else 16,
               allocated_ids=len(ids), ids_first_last=ids[:1] + ids[-1:],
               ids_sha256=hashlib.sha256(struct.pack('<' + 'i' * len(ids), *ids)).hexdigest(),
               arena_before=hex(arena), arena_after=hex(c.h.get32(rx.SRAM + 0x30fc)),
               packet_before=hex(packet), packet_after=hex(c.h.get32(rx.SRAM + 0x2ce4)),
               pool_head_after=int.from_bytes(c.h.cpu.mem_read(rx.SRAM + 0x3950, 2), 'little'),
               pool_tail_after=int.from_bytes(c.h.cpu.mem_read(rx.SRAM + 0x1f40, 2), 'little'),
               ready_values={hex(rx.SRAM + offset): int.from_bytes(c.h.cpu.mem_read(rx.SRAM + offset, size), 'little')
                             for _, offset, size, value in PROFILES[selector]['done'] if value == 1},
               pointer_published_before_descriptors=True, physical_packet_memory_accessed=False)
    return row


def seed_indication(c):
    base = c.h.get32(rx.SRAM + 0x30fc) + c.offsets[6]
    c.h.cpu.mem_write(base, b''.join(struct.pack('<II', 0x11223344 ^ i,
                                                0x01234567 ^ (i << 3)) for i in range(1536)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-page-rings-20261001' / args.name
    assert not dest.exists(), 'Choose a fresh result name'
    dest.mkdir(parents=True)
    _, host = postgate.host_tx_calls(dest)
    commands = [[row for row in trace if row['api'] == 1 and row['selector'] in PROFILES]
                for trace in host['trace']]
    assert commands == [[dict(selector=s, api=1, value=PROFILES[s]['count'])
                         for s in PROFILES]] * 2, commands
    c = Closure()
    # Execute the established RX consumers, not an injected initialized state.
    prefix = []
    with patch.object(c, 'invoke', rx.Closure.invoke.__get__(c)):
        for selector, count in ((0, 1536), (2, 1024)):
            c.restore(c.snapshot())
            prefix.append(rx.completed(c, selector, count, 'page-prefix-rx' + str(selector)))
    assert c.offsets[8] - c.offsets[7] == 256 * 16
    assert c.offsets[9] - c.offsets[8] == 512 * 16
    assert c.offsets[6] - c.offsets[9] == 1024 * 16
    assert c.offsets[2] - c.offsets[6] == 1536 * 8
    first = c.snapshot()
    assert c.h.get32(rx.SRAM + 0x4634) == c.fixed[0x106]
    assert c.h.get32(rx.SRAM + 0x3950) & 0xffff == 0
    assert c.h.get32(rx.SRAM + 0x1f40) & 0xffff == 0
    assert bytes(c.h.cpu.mem_read(c.fixed[0x106], 16384)) == struct.pack('<8192H', *range(8192))
    valid, controls, saved = [], [], {}
    for command in commands[0]:
        selector = command['selector']
        saved[selector] = c.snapshot()
        c.restore(saved[selector])
        valid.append(completed(c, selector, command['value'], 'current-host-desc' + str(selector), True))
    for selector, p in PROFILES.items():
        for count in (0, p['count'] + 1, 1535 if selector == 8 else 1537):
            c.restore(saved[selector])
            controls.append(completed(c, selector, count, 'desc%d-count%d' % (selector, count)))
        c.restore(saved[selector])
        c.h.put32(rx.SRAM + 0x30fc, 0)
        controls.append(completed(c, selector, p['count'], 'desc%d-zero-arena' % selector))
        c.restore(saved[selector])
        ring = c.h.get32(rx.SRAM + 0x30fc) + c.offsets[p['kind']]
        stride = 8 if selector == 8 else 16
        c.capacity = dict(base=ring, bytes=(p['count'] - 1) * stride,
                          pcs=DESCRIPTOR_PCS if selector != 8 else {0x8400bb10, 0x8400bb1a})
        controls.append(completed(c, selector, p['count'], 'desc%d-ring-one-short' % selector))
        if selector == 8:
            c.restore(saved[selector])
            seed_indication(c)
            controls.append(completed(c, selector, p['count'], 'desc8-preserve-nonzero-indication'))
            continue
        for available in (0, 17):
            c.restore(saved[selector])
            head = int.from_bytes(c.h.cpu.mem_read(rx.SRAM + 0x3950, 2), 'little')
            c.h.cpu.mem_write(rx.SRAM + 0x1f40, struct.pack('<H', (head + available + 1) % 8192))
            controls.append(completed(c, selector, p['count'], 'desc%d-id-exhaustion%d' % (selector, available)))
        for packet in (0, 0xd0000001):
            c.restore(saved[selector])
            c.h.put32(rx.SRAM + 0x2ce4, packet)
            controls.append(completed(c, selector, p['count'], 'desc%d-packet%x' % (selector, packet)))
        c.restore(saved[selector])
        c.h.cpu.mem_write(rx.SRAM + 0x3950, struct.pack('<H', 8184))
        c.h.cpu.mem_write(rx.SRAM + 0x1f40, struct.pack('<H', (8184 + p['count'] + 1) % 8192))
        controls.append(completed(c, selector, p['count'], 'desc%d-pool-wrap' % selector))
        c.restore(saved[selector])
        c.h.put32(rx.SRAM + 0x1f08, 0)
        controls.append(completed(c, selector, p['count'], 'desc%d-no-stats' % selector))
        c.restore(saved[selector])
        head = int.from_bytes(c.h.cpu.mem_read(rx.SRAM + 0x3950, 2), 'little')
        c.h.cpu.mem_write(c.fixed[0x106] + 2 * head, b'\xff\xff')
        controls.append(completed(c, selector, p['count'], 'desc%d-poisoned-id' % selector))
        for bufid in (8192, 32768):
            c.restore(saved[selector])
            head = int.from_bytes(c.h.cpu.mem_read(rx.SRAM + 0x3950, 2), 'little')
            c.h.cpu.mem_write(c.fixed[0x106] + 2 * head, struct.pack('<H', bufid))
            controls.append(completed(c, selector, p['count'], 'desc%d-unchecked-id%d' % (selector, bufid)))
    mutants = []
    for name, selector, pc, replacement in (
            ('omit-id-head-advance', 5, 0x8400bbf0, b'\x13\x00\x00\x00'),
            ('omit-page-descriptor-status', 6, 0x8400bc9c, b'\x01\x00'),
            ('omit-page-ready', 5, 0x8400bd62, b'\x13\x00\x00\x00'),
            ('omit-indication-mark', 8, 0x8400bb1a, b'\x01\x00'),
            ('discard-indication-low-bits', 8, 0x8400bb16, b'\xb2\x86')):
        c.restore(saved[selector])
        if selector == 8:
            seed_indication(c)
        original = bytes(c.h.cpu.mem_read(pc, len(replacement)))
        assert original != replacement
        c.h.cpu.mem_write(pc, replacement)
        c.h.cpu.ctl_remove_cache(rx.CODE, rx.CODE + len(c.h.code))
        c.code_image = bytes(c.h.cpu.mem_read(rx.CODE, len(c.h.code)))
        try:
            completed(c, selector, PROFILES[selector]['count'], name)
        except AssertionError as error:
            assert len(error.args) == 1 and error.args[0][1] == 'whole-memory-oracle', error
            mutants.append(dict(name=name, pc=hex(pc), original=original.hex(),
                                replacement=replacement.hex(), rejected_by='whole-memory-oracle'))
        else:
            raise AssertionError(('surviving-native-mutant', name))
    c.restore(first)
    before = rx.images(c.h)
    strict = [c.h.message([0x10 | s, 1, p['count']]) for s, p in PROFILES.items()]
    assert all(row['flags'] == 3 and not row['callbacks'] for row in strict)
    assert rx.images(c.h) == before
    inputs = {str(Path(__file__).relative_to(ROOT)): sha(Path(__file__)),
              str(rx.ELF.relative_to(ROOT)): sha(rx.ELF),
              str(rx.GHIDRA.relative_to(ROOT)): sha(rx.GHIDRA),
              str(rx.DTB.relative_to(ROOT)): sha(rx.DTB)}
    inputs.update({str(Path(m.__file__).resolve().relative_to(ROOT)): sha(Path(m.__file__).resolve())
                   for m in list(sys.modules.values()) if getattr(m, '__file__', None)
                   and Path(m.__file__).resolve().is_relative_to(ROOT / 'tests/npu')})
    inputs.update(host['inputs'])
    result = dict(passed=True, selectors=4, valid=valid, controls=controls, strict_denials=strict,
                  rejected_mutants=mutants,
                  native_rx_prefix=[dict(selector=row['selector'], count=row['requested_count'],
                                         whole_ram_sha256=row['whole_ram_sha256']) for row in prefix],
                  subregion_offsets=c.offsets,
                  boot_stubs=c.boot_stubs, callback_stubs_only=['printf(0x840048f4)'],
                  host=host, inputs=inputs, code_sha256=rx.CODE_SHA, data_sha256=rx.DATA_SHA,
                  scope='Original native DESC5/6/7/8 after initialized core0; direct callbacks, no general strict admission.',
                  limits=['Earlier native core0 boot has documented platform/printf/hart/timer models.',
                          'Callback helper bodies and page-ID allocation execute; only printf is substituted.',
                          'Capacity faults are emulator access contracts, not native error propagation.',
                          'No physical page pool, alias coherence, concurrent worker, DMA, loader or recovery proof.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, selectors=4, valid=len(valid), controls=len(controls),
                          strict_denials=len(strict), mutants=len(mutants),
                          receipt=str((dest / 'result.json').relative_to(ROOT)))))


if __name__ == '__main__':
    main()
