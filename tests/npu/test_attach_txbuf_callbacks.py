#!/usr/bin/env python3
"""Native API21 consumer closure; no expansion of strict bootstrap admission."""
import argparse
from collections import Counter
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
from unicorn import UC_PROT_READ, UC_PROT_ALL
from unicorn import riscv_const as r

import test_attach_rx_callbacks as rx
from test_attach_rx_callbacks import ELF, ELF_SHA, ROOT, SRAM, HEAP, HEAP_BYTES, CODE
from test_attach_rx_callbacks import BOOT, ADM, MBOX, PAYLOAD, END, STACK_TOPS, sha, digest
from test_attach_rx_callbacks import INPUT, CODE_SHA, DATA_SHA, DTB, GHIDRA, GHIDRA_SHA
from test_mt7996_bootstrap_sequence import exports, expected, SNAPSHOT, HOST_SHA

OUT = ROOT/'research/checkpoints/2026-09-06-npu-attachtxbuf/txbuf-callbacks.json'
HOST = ROOT/'research/checkpoints/2026-09-06-npu-nativewifi/host-sequence.json'
HOST_MD = HOST.with_name('HOST_SEQUENCE.md')
HOST_JSON_SHA = '7135e05b76218e8f0cd815e9bd3cc13434129ddedb1afe15279f250c038e3739'
HOST_MD_SHA = 'ba48ff8d69160b873a015fa4083dd7112d30b3b8ffef0b697a79c8f772429973'
PARENTS = {**rx.PARENTS, 'test_attach_rx_callbacks.py':
           'c7b04924b71e9a09fef3eeba3c1143381a5a1e67157f51b1e341a1910e37f100'}
CALLBACK, WRAPPER_RETURN = 0x8400fbca, 0x8400fbd8
TARGETS = (CALLBACK, 0x8400f0c2, 0x8400ef36, 0x8400ee94, 0x8400fab2,
           0x8400a5fa, 0x84005200, 0x8400420a, 0x84004130)
RAM = rx.IMAGES
POOL_BYTES = 512*256
POOLS = (0x90200000, 0x90500000)
BANDS = {
    5: dict(count=512, stride=128, kind=10, slot=0x1f38, slot_pc=0x8400f014, host=0x10100000),
    7: dict(count=1024, stride=128, kind=11, slot=0x2abc, slot_pc=0x8400f062, host=0x10400000),
    10: dict(count=512, stride=16, kind=0x100, slot=0x2acc, slot_pc=0x8400a644,
             host=0x10200000, host_slot=0x3960, host_pc=0x8400f092,
             resets=((0x462c, 0x8400a630), (0x395a, 0x8400a638))),
    12: dict(count=512, stride=16, kind=0x101, slot=0x21e8, slot_pc=0x8400a6c6,
             host=0x10500000, host_slot=0x2a88, host_pc=0x8400ef98,
             resets=((0x2a8c, 0x8400a6a6), (0x390c, 0x8400a6ae))),
}


class Trace(rx.Trace):
    def __init__(self):
        super().__init__()
        self.ram_writes, self.order, self.cycle_inputs = [], [], []
        self.steps, self.last_ram_write_step = 0, 0
        self.nonstack_reads = Counter()

    def code(self, h, pc):
        self.steps += 1
        for start, return_pc in self.pending[:]:
            if pc == return_pc:
                value = h.cpu.reg_read(r.UC_RISCV_REG_A0)
                self.return_values.setdefault(start, []).append(value)
                self.pending.remove((start, return_pc))
                self.order.append(dict(event='return', function=hex(start), pc=hex(pc), step=self.steps,
                                       value=hex(value), after_access=self.ordinal))
        if pc in TARGETS:
            self.entries[pc] += 1
            args = [h.cpu.reg_read(getattr(r, f'UC_RISCV_REG_A{i}')) for i in range(3)]
            self.first_args.setdefault(pc, args)
            self.pending.append((pc, h.cpu.reg_read(r.UC_RISCV_REG_RA)))
            self.order.append(dict(event='entry', function=hex(pc), after_access=self.ordinal, step=self.steps))
        if pc == WRAPPER_RETURN:
            self.inner.append(h.cpu.reg_read(r.UC_RISCV_REG_A0))
            self.order.append(dict(event='wrapper-resumes', after_access=self.ordinal, step=self.steps))

    def access(self, h, address, size, value, write):
        super().access(h, address, size, value, write)
        if write and any(base <= address and address+size <= base+length for base, length in RAM):
            self.ram_writes.append((h.cpu.reg_read(r.UC_RISCV_REG_PC), address, size, value))
            self.last_ram_write_step = self.steps
        if not write and not STACK_TOPS[0]-0x100 <= address < STACK_TOPS[0]:
            self.nonstack_reads[h.cpu.reg_read(r.UC_RISCV_REG_PC), address, size, value] += 1

    def result(self, detailed):
        result = super().result(detailed)
        result.update(order=self.order, cycle_inputs=self.cycle_inputs, last_ram_write_step=self.last_ram_write_step,
                      ordered_ram_writes_sha256=digest(b''.join(struct.pack('<4I', *w) for w in self.ram_writes)))
        return result


class Closure(rx.Closure):
    def __init__(self, path, exported):
        super().__init__(path, exported)
        h = self.h
        self.code_image = bytes(h.cpu.mem_read(CODE, len(h.code)))
        self.denied, self.missing, self.trace = None, None, None
        self.cycle = 0
        self.cycle_model = 'advancing'
        self.capacity = {base: POOL_BYTES for base in POOLS}
        for base in POOLS:
            h.cpu.mem_map(base, POOL_BYTES)
            h.cpu.mem_write(base, bytes(range(256))*512)
        native_memory, native_model, native_skip = h.is_memory, self.original_model, h.skip

        def memory(address, size):
            return native_memory(address, size) or any(
                base <= address and address+size <= base+length for base, length in self.capacity.items())

        def model(address, write):
            return None if address == self.missing else native_model(address, write)

        def skip(cpu, pc, size, data):
            # Keep the actual delay and its arithmetic/loop/return, not the boot stub.
            if pc != 0x84004130:
                native_skip(cpu, pc, size, data)

        h.is_memory, h.register_model, h.skip = memory, model, skip
        self.functions.add(0x8400ee94)  # Native block merged into ef36's Ghidra C.

    def code(self, cpu, pc, size, data):
        if self.trace is None:
            return
        # Unicorn's MCYCLE is wall-clock-derived and ignores reg_write. Execute
        # each CSR instruction, then supply its explicit deterministic input
        # before the next native instruction consumes it. Never synthesize RA/A0.
        if pc in (0x84004198, 0x840041b8) and self.cycle_model == 'missing':
            raise rx.UnmodeledAccess(f'missing MCYCLE model at {pc:#x}')
        if pc in (0x8400419c, 0x840041bc):
            if self.cycle_model == 'advancing':
                self.cycle += 10000000
            cpu.reg_write(r.UC_RISCV_REG_A5, self.cycle)
            self.trace.cycle_inputs.append(dict(csr_pc=hex(pc-4), value=self.cycle))
        if pc in self.functions:
            self.trace.all_entries[pc] += 1
        self.trace.code(self.h, pc)

    def restore(self, snapshot):
        self.h.cpu.mem_protect(rx.L2, rx.L2_BYTES, UC_PROT_ALL)
        super().restore(snapshot)
        self.denied, self.cycle, self.cycle_model = None, 0, 'advancing'
        self.capacity = {base: POOL_BYTES for base in POOLS}

    def write(self, cpu, access, address, size, value, data):
        # Unicorn reports a write attempt before WRITE_PROT. It is not a store.
        if self.denied and address < self.denied[1] and address+size > self.denied[0]:
            return
        super().write(cpu, access, address, size, value, data)

    def images(self):
        return {base: bytearray(self.h.cpu.mem_read(base, length))
                for base, length in RAM+tuple((p, POOL_BYTES) for p in POOLS)}

    def invoke(self, selector, value, mode='complete', release=None, detailed=False):
        h, b = self.h, BANDS[selector]
        h.cpu.mem_write(PAYLOAD, struct.pack('<3I', 0x10|selector, 21, value))
        h.put32(MBOX+0x3c, 1)
        for register, v in ((r.UC_RISCV_REG_SP, STACK_TOPS[0]), (r.UC_RISCV_REG_RA, END),
                            (r.UC_RISCV_REG_A0, PAYLOAD), (r.UC_RISCV_REG_MSTATUS, 0)):
            h.cpu.reg_write(register, v)
        h.unmodeled = None
        before_allocations, before_logs = len(h.allocations), len(h.logs)
        self.trace = trace = Trace()
        error, result, wait = None, None, None
        try:
            if mode in ('wait', 'release', 'frozen'):
                stop = 0x840041b8 if mode == 'frozen' else 0x8400a618
                assert h.run(CALLBACK, [stop]) == stop
                if mode == 'frozen':
                    for _ in range(2):
                        assert h.run(stop, [stop]) == stop
                else:
                    assert h.run(stop, [0x8400a610]) == 0x8400a610
                    assert h.run(0x8400a610, [stop]) == stop
                assert trace.entries[0x84005200] == 0 and not trace.inner
                assert h.get32(SRAM+b['slot']) == 0
                wait = dict(stop_pc=hex(stop), callback_returned=False, lookup_entered=False,
                            host_pointer_already_published=hex(h.get32(SRAM+b['host_slot'])),
                            successful_ram_writes=len(trace.ram_writes),
                            native_delay_entries=trace.entries[0x84004130], cycle_model=self.cycle_model)
                if mode == 'release':
                    assert release and h.get32(SRAM+0x2ab8) == 0
                    h.put32(SRAM+0x2ab8, release)
                    wait['external_packet_base_release'] = hex(release)
                    assert h.run(stop, []) == END
                    result = h.cpu.reg_read(r.UC_RISCV_REG_A0)
            else:
                assert h.run(CALLBACK, []) == END
                result = h.cpu.reg_read(r.UC_RISCV_REG_A0)
            if result is not None:
                trace.code(h, END)
        except rx.UnmodeledAccess as exc:
            error = str(exc)
        finally:
            self.trace = None
        assert set(h.stub_counts) <= {'0x840048f4'}, h.stub_counts
        assert set(trace.all_entries) <= set(TARGETS)|{0x840048f4}, trace.all_entries
        assert h.get32(MBOX+0x3c) == 1
        assert h.get32(BOOT+8) == 6 and h.get32(ADM) == 1
        assert bytes(h.cpu.mem_read(CODE, len(h.code))) == self.code_image
        return dict(selector=selector, words=[hex(0x10|selector), 21, hex(value)],
                    callback_return=result, stopped_access=error, wait=wait,
                    mailbox_flags_untouched=1, strict_bootstrap_state=6, admission_state=1,
                    trace=trace.result(detailed), native_lookup_returns=h.allocations[before_allocations:],
                    logs=[dict(format=k, count=v) for k, v in Counter(
                        log['format'] for log in h.logs[before_logs:]).items()]), trace


def oracle(c, before, selector, value, complete=True, release=None):
    """Literal record ABI and pinned source tables, independent of observed stores."""
    b = BANDS[selector]
    want = {base: bytearray(image) for base, image in before.items()}
    writes = []
    if selector in (5, 7):
        arena = struct.unpack_from('<I', before[SRAM], 0x30fc)[0]
        base = arena+c.offsets[b['kind']]
        writes.append((b['slot_pc'], SRAM+b['slot'], 4, base))
        words = [0x100000]+[0]*30+[0x10000]
        store_pcs = [0x8400eeb2]+[0x8400eeb4+4*i for i in range(30)]+[0x8400ef2c]
        for index in range(b['count']):
            writes.extend((pc, base+index*128+offset*4, 4, word)
                          for offset, (pc, word) in enumerate(zip(store_pcs, words)))
    else:
        base = c.fixed[b['kind']]
        writes.append((b['host_pc'], SRAM+b['host_slot'], 4, value & 0x3fffffff | 0x40000000))
        if complete:
            writes.extend((pc, SRAM+offset, 2, 0) for offset, pc in b['resets'])
            writes.append((b['slot_pc'], SRAM+b['slot'], 4, base))
            for index in range(512):
                pointer = ((value+index*256) & 0x3fffffff) | 0x80000000
                writes.extend((pc, base+index*16+offset, size, word) for pc, offset, size, word in (
                    (0x8400a672, 0, 4, pointer), (0x8400a674, 4, 4, 0),
                    (0x8400a678, 8, 4, 0), (0x8400a67c, 12, 1, 0)))
    accepted, allowed, failure = [], set(), None
    for pc, address, size, word in writes:
        if not c.h.is_memory(address, size) or (c.denied and address < c.denied[1] and address+size > c.denied[0]):
            failure = dict(pc=hex(pc), address=hex(address), size=size)
            break
        for start, data in want.items():
            if start <= address and address+size <= start+len(data):
                data[address-start:address-start+size] = word.to_bytes(size, 'little')
                allowed.update(range(address, address+size))
                accepted.append((pc, address, size, word))
                break
        else:
            raise AssertionError(('oracle address outside compared RAM', hex(address)))
    if release:
        struct.pack_into('<I', want[SRAM], 0x2ab8, release)
    return want, accepted, allowed, failure, base


def read_oracle(c, before, selector, value, mode, release, base):
    """Independent non-stack loads, including table scan and startup reloads."""
    b, rows = BANDS[selector], []

    def load(pc, address, size=4, value=None):
        if value is None:
            if CODE <= address < CODE+len(c.h.code):
                value = int.from_bytes(c.h.code[address-CODE:address-CODE+size], 'little')
            else:
                value = int.from_bytes(before[SRAM][address-SRAM:address-SRAM+size], 'little')
        rows.append((pc, address, size, value))

    load(CALLBACK, PAYLOAD, value=0x10|selector)
    load(0x8400fbcc, PAYLOAD+8, value=value)
    load(0x8400ef5e, 0x8401bd84+selector*4)
    if selector in (5, 7):
        load(0x8400efee if selector == 5 else 0x8400f03c, SRAM+0x30fc)
        kinds = list(c.offsets)
        load(0x8400fae2, 0x8401cf1c+kinds.index(b['kind'])*8)
        for index in range(2, len(kinds)+1):
            load(0x8400faf0, 0x8401cf18+index*8, 2)
        load(0x8400f02a if selector == 5 else 0x8400f078, SRAM+b['slot'], value=base)
    else:
        load(0x8400a606, SRAM+0x2ab8)
        if mode in ('wait', 'release', 'frozen', 'cycle-missing'):
            for _ in range(2 if mode in ('wait', 'release') else 1):
                load(0x84004138, SRAM+0x4690)
            if mode in ('wait', 'release'):
                load(0x8400a618, SRAM+0x2ab8, value=0)
            if mode == 'release':
                load(0x8400a618, SRAM+0x2ab8, value=release)
        if mode not in ('wait', 'frozen', 'cycle-missing'):
            load(0x8400a62a if selector == 10 else 0x8400a6a0,
                 SRAM+b['host_slot'], value=value & 0x3fffffff | 0x40000000)
            load(0x8400523a, 0x8401cf70, 2)
            if selector == 12:
                load(0x8400525e, 0x8401cf78, 2)
            load(0x84005280, 0x8401cf74+(selector-10)//2*8)
            load(0x8400a650 if selector == 10 else 0x8400a6c0,
                 SRAM+(0x21e8 if selector == 10 else 0x2acc))
    return Counter(rows)


def completed(c, selector, name, value=None, mode='complete', release=None, detailed=False):
    value = BANDS[selector]['host'] if value is None else value
    before, b = c.images(), BANDS[selector]
    want, writes, allowed, failure, base = oracle(c, before, selector, value,
                                                 mode not in ('wait', 'frozen', 'cycle-missing'), release)
    row, trace = c.invoke(selector, value, mode, release, detailed)
    assert c.images() == want, (name, 'complete RAM mismatch', [
        (hex(start), hex(next(i for i, (a, z) in enumerate(zip(c.images()[start], want[start])) if a != z)))
        for start in want if c.images()[start] != want[start]])
    assert trace.ram_writes == writes, (name, len(trace.ram_writes), len(writes))
    assert trace.memory_written == allowed, (name, 'exact footprint mismatch')
    expected_reads = read_oracle(c, before, selector, value, mode, release, base)
    assert trace.nonstack_reads == expected_reads, (name, trace.nonstack_reads-expected_reads,
                                                    expected_reads-trace.nonstack_reads)
    assert trace.entries[CALLBACK] == trace.entries[0x8400f0c2] == trace.entries[0x8400ef36] == 1
    assert trace.first_args[0x8400ef36][:2] == [value, selector]
    if failure:
        assert row['callback_return'] is None and row['stopped_access'], row
        assert failure['pc'] in row['stopped_access'] and failure['address'] in row['stopped_access'], row
        assert not trace.inner
    elif mode == 'cycle-missing':
        assert row['stopped_access'] == 'missing MCYCLE model at 0x84004198' and not trace.inner
        assert row['callback_return'] is None
    elif mode in ('wait', 'frozen'):
        assert row['callback_return'] is None and row['stopped_access'] is None and not trace.inner
    else:
        assert row['callback_return'] == 1 and row['stopped_access'] is None and len(trace.inner) == 1
        assert trace.return_values[CALLBACK] == [1]
        assert not trace.pending
        if selector in (5, 7):
            assert trace.first_args[0x8400fab2] == [base-c.offsets[b['kind']], 1, b['kind']]
            assert trace.return_values[0x8400fab2] == [base]
            assert trace.first_args[0x8400ee94][:2] == [base, b['count']]
            assert trace.inner == [base+b['count']*128]
            assert not row['native_lookup_returns']
        else:
            assert trace.first_args[0x8400a5fa][0] == (selector-10)//2
            assert trace.first_args[0x84005200][0] == b['kind']
            assert trace.return_values[0x84005200] == [base]
            assert [(a['type'], a['value']) for a in row['native_lookup_returns']] == [(b['kind'], base)]
            # a5fa is void. Band1 retains band0's base in A0; the wrapper returns 1.
            expected_inner = base if selector == 10 else struct.unpack_from('<I', before[SRAM], 0x2acc)[0]
            assert trace.inner == [expected_inner]
    if selector in (5, 7):
        footprint = dict(base=hex(base), entries=b['count'], stride=128,
                         bytes=b['count']*128, supplied_address_used_for_memory=False,
                         first_word='0x100000', middle_zero_words=30, last_word='0x10000')
    else:
        host_base = value & 0x3fffffff | 0x80000000
        valid_slots = sum(any(p <= ((value+i*256)&0x3fffffff|0x80000000) and
                              ((value+i*256)&0x3fffffff|0x80000000)+256 <= p+n
                              for p, n in c.capacity.items()) for i in range(512))
        footprint = dict(base=hex(base), entries=512, stride=16, extent_bytes=8192,
                         bytes_written_per_entry=13, preserved_tail_bytes_per_entry=3,
                         linked_host_base=hex(host_base), linked_host_stride=256,
                         linked_host_extent_bytes=POOL_BYTES, host_pool_slots_within_capacity=valid_slots,
                         host_pool_accesses=0, host_pool_capacity={hex(k): v for k, v in c.capacity.items()})
    groups = [group for (_, kind, _, space), group in trace.groups.items() if kind == 'write' and space == 'memory']
    pointer_slot = SRAM+(b.get('host_slot', b['slot']))
    publication = [g for g in groups if pointer_slot in g['addresses']]
    assert len(publication) == 1 and publication[0]['count'] == 1
    if len(groups) > 1:
        assert publication[0]['last_ordinal'] < min(g['first_ordinal'] for g in groups if g is not publication[0])
    if row['callback_return'] is not None:
        assert next(e['step'] for e in trace.order if e['event'] == 'wrapper-resumes') > trace.last_ram_write_step
    row.update(name=name, footprint=footprint, predicted_failure=failure,
               whole_ram_compared_bytes=sum(len(image) for image in want.values()),
               whole_ram_sha256={hex(start): digest(data) for start, data in want.items()},
               exact_ordered_ram_writes=True, expected_ram_writes=len(writes),
               exact_nonstack_read_footprint_and_values=True, expected_nonstack_reads=sum(expected_reads.values()),
               exact_unique_memory_write_footprint=True,
               pointer_publication_precedes_record_initialization=True,
               dedicated_ready_flag_written=False,
               wrapper_return_follows_record_initialization=row['callback_return'] is not None,
               range_diagnostics=sum(log['count'] for log in row['logs'] if 'out of available range' in log['format']))
    return row


def run(path):
    assert sha(path) == ELF_SHA and path == ELF.resolve()
    for name, identity in PARENTS.items():
        assert sha(ROOT/'tests/npu'/name) == identity, name
    assert sha(HOST) == HOST_JSON_SHA and sha(HOST_MD) == HOST_MD_SHA
    assert sha(SNAPSHOT/'mt7996/npu.c') == HOST_SHA
    exported = exports()
    dependency_hashes = {Path(m.__file__).resolve(): sha(Path(m.__file__).resolve())
                         for m in list(sys.modules.values()) if getattr(m, '__file__', None)
                         and Path(m.__file__).resolve().is_relative_to(ROOT/'tests/npu')}
    c = Closure(path, exported)
    h = c.h
    assert h.get32(SRAM+0x1cc) == CALLBACK
    code_ranges = {pc: None for pc in TARGETS}
    for pc in code_ranges:
        if pc == 0x8400ee94:
            end = 0x8400ef36
        else:
            last = int(exported[pc]['assembly'].strip().splitlines()[-1].split()[0].split(':')[1], 16)
            half = int.from_bytes(h.code[last-CODE:last-CODE+2], 'little')
            end = last+(4 if half & 3 == 3 else 2)
        assert bytes(h.cpu.mem_read(pc, end-pc)) == h.code[pc-CODE:end-CODE]
        code_ranges[pc] = dict(end=hex(end), bytes=end-pc, native_bytes_sha256=digest(h.code[pc-CODE:end-CODE]))
    assert c.offsets[10]+512*128 == c.offsets[7]
    assert c.offsets[11]+1024*128 == c.dynamic[1]['value']
    assert c.fixed[0x101]-c.fixed[0x100] == 8192+32
    assert c.fixed[0x102]-c.fixed[0x101] == 8192+32
    packet_base = h.get32(SRAM+0x2ab8)
    assert packet_base == 0x8cc00000
    for selector, b in BANDS.items():
        assert h.get32(SRAM+b['slot']) == 0
    first = c.snapshot()
    valid, snapshots, controls = [], {}, []
    # Only this lane's four operations, in their actual host order. No intervening
    # parent/page callbacks are executed or claimed as a full host attachment.
    for selector in (5, 10, 7, 12):
        snapshots[selector] = c.snapshot()
        c.restore(snapshots[selector])
        valid.append(completed(c, selector, f'host_api21_if{selector}', detailed=True))
    for selector in (5, 7):
        b = BANDS[selector]
        baseline = next(row for row in valid if row['selector'] == selector)
        for value in (0, 0xdeadbeef):
            c.restore(snapshots[selector])
            row = completed(c, selector, f'if{selector}_diagnostic_only_{value:x}', value=value)
            assert row['whole_ram_sha256'] == baseline['whole_ram_sha256']
            assert row['range_diagnostics'] == int(value >= 0xc0000000)
            controls.append(row)
        c.restore(snapshots[selector])
        h.put32(SRAM+0x30fc, 0)
        controls.append(completed(c, selector, f'if{selector}_missing_arena'))
        c.restore(snapshots[selector])
        h.put32(SRAM+0x30fc, HEAP+HEAP_BYTES-c.offsets[b['kind']]-128)
        row = completed(c, selector, f'if{selector}_arena_extent_one_record')
        assert row['expected_ram_writes'] == 33 and row['predicted_failure']['address'] == hex(HEAP+HEAP_BYTES)
        controls.append(row)
    for selector in (10, 12):
        b = BANDS[selector]
        for value in (0x8a000000, 1):
            c.restore(snapshots[selector])
            h.put32(SRAM+0x2ab8, value)
            controls.append(completed(c, selector, f'if{selector}_nonzero_txpacket_{value:x}_accepted'))
        for mode in ('wait', 'release', 'frozen', 'cycle-missing'):
            c.restore(snapshots[selector])
            h.put32(SRAM+0x2ab8, 0)
            c.cycle_model = {'frozen': 'frozen', 'cycle-missing': 'missing'}.get(mode, 'advancing')
            row = completed(c, selector, f'if{selector}_zero_txpacket_{mode}', mode=mode,
                            release=packet_base if mode == 'release' else None)
            controls.append(row)
        for slots in ((0, 256) if selector == 10 else (0, 254, 510)):
            c.restore(snapshots[selector])
            base = c.fixed[b['kind']]
            boundary = (base & ~0xfff) if slots == 0 else base+slots*16
            assert boundary % 4096 == 0
            c.denied = (boundary, rx.L2+rx.L2_BYTES)
            h.cpu.mem_protect(boundary, c.denied[1]-boundary, UC_PROT_READ)
            row = completed(c, selector, f'if{selector}_descriptor_mapping_capacity_{slots}')
            assert row['expected_ram_writes'] == 4+slots*4
            assert row['predicted_failure']['pc'] == '0x8400a672'
            controls.append(row)
        for capacity in (0, POOL_BYTES-256):
            c.restore(snapshots[selector])
            c.capacity[b['host']|0x80000000] = capacity
            row = completed(c, selector, f'if{selector}_logical_host_capacity_{capacity}_accepted')
            assert row['footprint']['host_pool_slots_within_capacity'] == capacity//256
            assert row['callback_return'] == 1
            controls.append(row)
        for value in (0, 0xd0200000):
            c.restore(snapshots[selector])
            row = completed(c, selector, f'if{selector}_invalid_host_address_{value:x}_accepted', value=value)
            assert row['range_diagnostics'] == int(value >= 0xc0000000)
            controls.append(row)
    # Both fixed lookup tables exist in immutable CODE; missing dynamic heap
    # capacity cannot honestly force them to return NULL. Exercise that fact.
    for selector in (10, 12):
        c.restore(snapshots[selector])
        h.put32(SRAM+0x1be0, HEAP_BYTES)
        controls.append(completed(c, selector, f'if{selector}_dynamic_heap_exhausted_fixed_lookup_succeeds'))
    c.restore(first)
    strict = []
    strict_before = c.images()
    for selector, b in BANDS.items():
        row = h.message([0x10|selector, 21, b['host']])
        assert row['flags'] == 3 and not row['callbacks']
        strict.append(row)
    assert not h.allocations and c.images() == strict_before
    assert all(h.get32(SRAM+b['slot']) == 0 for b in BANDS.values())
    commands = [[m for m in expected(hif, port) if m['kind'] == 'message' and m['api'] == 21
                 and (m['word0'] & 15) in BANDS] for hif in (0, 1) for port in (2, 3)]
    assert commands == [commands[0]]*4
    assert [(m['word0'] & 15, m['value'], m['length']) for m in commands[0]] == [
        (s, BANDS[s]['host'], 12) for s in (5, 10, 7, 12)]
    prior = json.loads(HOST.read_text())
    assert prior['inputs']['tests/npu/test_mt7996_bootstrap_sequence.py'] == PARENTS['test_mt7996_bootstrap_sequence.py']
    for profile in prior['host']['success_profiles']:
        messages = [m for m in profile['trace'] if m['kind'] == 'message']
        assert [messages[i-1] for i in (25, 26, 29, 30)] == commands[0]
    assert sha(path) == ELF_SHA
    assert all(sha(file) == identity for file, identity in dependency_hashes.items())
    sources = {str(file.relative_to(ROOT)): identity for file, identity in dependency_hashes.items()}
    sources.update({str(Path(__file__).resolve().relative_to(ROOT)): sha(Path(__file__)),
                    str(path.relative_to(ROOT)): ELF_SHA, str(GHIDRA.relative_to(ROOT)): GHIDRA_SHA,
                    str(DTB.relative_to(ROOT)): sha(DTB), str(HOST.relative_to(ROOT)): HOST_JSON_SHA,
                    str(HOST_MD.relative_to(ROOT)): HOST_MD_SHA,
                    str((SNAPSHOT/'mt7996/npu.c').relative_to(ROOT)): HOST_SHA,
                    str((INPUT/'en7581_MT7996_npu_rv32.bin').relative_to(ROOT)): CODE_SHA,
                    str((INPUT/'en7581_MT7996_npu_data.bin').relative_to(ROOT)): DATA_SHA})
    return dict(schema=1, passed=True, base_commit='d41ac7ba1987f2d47a5e95146f8127cd7f7d49e4', sources=sources,
        scope='Four original API21 callbacks on actual native initialized C0. Direct invocation, not full host attachment or strict admission.',
        counts=dict(native_callback_selectors_closed=4, replaced_allocator_substitution_cases=2,
                    closed_original_wait_boundary_cases=4, valid_callbacks=4, negative_controls=len(controls),
                    strict_rejections=4, nominal_128byte_records=1536, nominal_16byte_descriptors=1024,
                    nominal_linked_host_slots=1024, original_pending_after_rx=11,
                    remaining_original_pending_case_labels=7, separately_allocator_modeled_cases_remaining=0),
        prerequisite_state=dict(origin='RX Closure: to_wifi -> footprints -> host_publish -> GET10 -> original SET14(port2)',
            boot_footprint=c.boot_footprint, boot_stub_counts=c.boot_stubs,
            callback_stubs_only=['printf(840048f4)'], helper_return_substitutions=0,
            native_txpacket_base=hex(packet_base), native_wifi_arena=hex(HEAP+0x17000),
            wifi_arena_bytes=c.dynamic[1]['value'], subregion_offsets=c.offsets,
            fixed_tables={hex(k): hex(v) for k, v in c.fixed.items()}, callback_binding='original DATA +0x1cc -> 8400fbca',
            synthetic_host_pools=[dict(base=hex(p), bytes=POOL_BYTES, seed='00..ff repeated 512 times') for p in POOLS],
            host_pool_model='Explicit descriptor-address view, not physical allocation or cached/uncached alias coherence. Logical capacity controls retain poisoned backing pages; accesses outside declared capacity would fail. Native callbacks never access these pages.',
            new_mmio_models=[], cycle_model='MCYCLE CSR instructions execute; A5 input overridden immediately afterward by 10,000,000 increments, or zero for frozen control. Native delay body and returns execute; no real timing claim.'),
        native_code_ranges={hex(pc): row for pc, row in code_ranges.items()},
        ghidra_functions={hex(pc): dict(line=exported[pc]['line'], name=exported[pc]['name'],
            export_sha256=digest((exported[pc]['text']+exported[pc]['assembly']).encode())) for pc in TARGETS if pc in exported},
        exact_host_commands=commands[0], host_message_positions=[25, 26, 29, 30],
        trace_encoding='Inherited rx address_runs=[first,count,stride,repeats], group SHA of ordered pc,address,size,value uint32; global SHA prefixes uint8 write. Valid cases include lossless aggregates; controls retain digests/counts/order. RAM write oracle independently generates every ordered pc,address,size,value tuple. No instruction trace.',
        valid_sequence=valid, negative_controls=controls, strict_bootstrap=dict(api21_admitted=False, replies=strict),
        remaining_original_pending_cases=[f'api1_if{i}_native_entry_only' for i in (5, 6, 7, 8, 10)]+
                                         [f'api19_if{i}_native_entry_only' for i in (0, 2)],
        boundaries=['Remaining case labels are parent/other-agent owned and not rerun or closed by this lane.',
                    'Pointers publish before records; no separate readiness flag. Original wrapper success does not validate capacity or readiness.',
                    'Fault controls stop on explicit emulator memory contracts, with partial native state and no wrapper return; not firmware error handling or rollback.',
                    'All helper/lookup bodies reached in these callbacks run. Fixed table lookup has no dynamic allocation failure path on immutable CODE.',
                    'Boot retains existing documented printf/hart/timer stubs; callback printf only. Delayed callback uses an explicit CSR input model, not a helper-return substitution.',
                    'No hardware, timing, concurrent workers, DMA/cache containment, full attachment, recovery, or parity proof.',
                    'No shared source/helper/build/ELF/policy/platform/ledger/docs/config/overlay/Git/router/network/flash modifications. Parent owns integration.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--elf', type=Path, default=ELF)
    parser.add_argument('--check', action='store_true', help='byte-identical replay without rewriting evidence')
    args = parser.parse_args()
    result = run(args.elf.resolve())
    encoded = json.dumps(result, indent=2, sort_keys=True)+'\n'
    assert len(encoded.encode()) < 400000
    if args.check:
        assert OUT.read_bytes() == encoded.encode(), 'fresh replay differs from saved evidence'
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_bytes(encoded.encode())
    print(json.dumps(dict(status='PASS', **result['counts'], bytes=len(encoded.encode()),
                          json_sha256=digest(encoded.encode()), test_sha256=sha(Path(__file__)))))


if __name__ == '__main__':
    main()
