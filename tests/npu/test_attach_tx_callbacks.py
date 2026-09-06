#!/usr/bin/env python3
"""Native TX setup/completion consumers; no expansion of strict admission."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
from unicorn import UcError, riscv_const as r

from test_attach_rx_callbacks import (Closure, Trace, ELF, ELF_SHA, IMAGES, digest,
                                      images, completed as rx_completed, PARENTS as RX_PARENTS)
from test_bootstrap_native import ROOT, sha, DTB, BOOT, ADM
from test_boot_irq_installation import UnmodeledAccess
from test_boot_irq_installation import TX as SKB_STATE
import test_native_wifi_boot as native_wifi
from test_firmware_mailbox_dispatch import MBOX, PAYLOAD
from test_firmware_memory_layout import STACK_TOPS
from test_firmware_stop_counterexample import INPUT, CODE_SHA, DATA_SHA, END
from test_mt7996_bootstrap_sequence import (exports, GHIDRA, GHIDRA_SHA, expected,
                                           SET_CALLBACKS, TXFREE)
from emulation_layout import CODE, SRAM

OUT = ROOT/'research/checkpoints/2026-09-06-npu-attachtx/tx-callbacks.json'
REGS = tuple(base+offset for base in (0x1fc08000, 0x1fc28000, 0x1fc48000)
             for offset in (0x30, 0x34))
TARGETS = (0x8400fc16, 0x8400e28e, 0x8400d5da, 0x8400d490, 0x8400fab2)
RETURNS = (0x8400fab2,)
DONE_TARGETS = (0x8400fe34, 0x8400dd82, 0x8400b432, 0x84005200,
                0x84004d80, 0x840049f0, 0x84009aa6, 0x840064b4, 0x8400651c)
HOST, HOST_BYTES = TXFREE | 0x40000000, 0x3000
SKB_BYTES = 0xe000
RESET_REGS = {0x1ec031d0: ('write', 0x40), 0x1ec03050: ('read', 0x10000),
              0x1ec03250: ('write', 0)}
CALLBACK_PARENTS = {**RX_PARENTS, 'test_attach_rx_callbacks.py':
                   'c7b04924b71e9a09fef3eeba3c1143381a5a1e67157f51b1e341a1910e37f100'}


class TxTrace(Trace):
    def __init__(self, done=False):
        super().__init__()
        self.targets = DONE_TARGETS if done else TARGETS
        self.returns = (0x84005200, 0x84004d80, 0x84009aa6, 0x840064b4, 0x8400651c) if done else RETURNS

    def access(self, h, address, size, value, write):
        span = next(((base, length, space) for base, length, space in (
            (HOST, HOST_BYTES, 'host-memory'), (SKB_STATE, SKB_BYTES, 'skb-state-memory'))
                     if base <= address < base+length), None)
        if span is None:
            return super().access(h, address, size, value, write)
        base, length, space = span
        assert address+size <= base+length
        pc = h.cpu.reg_read(r.UC_RISCV_REG_PC)
        if write:
            self.memory_written.update(range(address, address+size))
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
        if pc in self.targets:
            self.entries[pc] += 1
            self.first_args.setdefault(pc, [h.cpu.reg_read(getattr(r, f'UC_RISCV_REG_A{i}'))
                                           for i in range(3)])
        if pc in self.returns:
            self.pending.append((pc, h.cpu.reg_read(r.UC_RISCV_REG_RA)))
        if pc == 0x8400fe42:
            self.inner.append(value)


class CallbackWifi(native_wifi.NativeWifi):
    def write_hook(self, cpu, access, address, size, value, data):
        # The inherited observer asserts sequential zero-only writes during boot.
        # Later native SKB reset legitimately stores state 3 in the same region.
        if getattr(self, 'done_tracking', False) and SKB_STATE <= address < SKB_STATE+SKB_BYTES:
            self.access(address, size, value, True)
            return
        super().write_hook(cpu, access, address, size, value, data)


class TxClosure(Closure):
    def __init__(self, path, exported):
        # Select an observer subclass for this process only; native code is unchanged.
        with patch.object(native_wifi, 'NativeWifi', CallbackWifi):
            super().__init__(path, exported)
        self.code_image = bytes(self.h.cpu.mem_read(CODE, len(self.h.code)))
        for base in sorted({address & ~0xfff for address in REGS}):
            self.h.cpu.mem_map(base, 0x1000)
        for address in REGS:
            self.h.put32(address, 0xa5a5a5a5)
        self.h.cpu.mem_map(HOST, HOST_BYTES)
        self.h.cpu.mem_write(HOST, b'\xa5'*HOST_BYTES)
        self.host_limit = HOST_BYTES
        self.original_memory = self.h.is_memory
        self.h.is_memory = lambda address, size: (
            HOST <= address and address+size <= HOST+self.host_limit or self.original_memory(address, size))
        self.h.put32(0x1ec03050, 0x10000)

    def done(self, count, detailed=False):
        h = self.h
        h.cpu.mem_write(PAYLOAD, struct.pack('<3I', 0x1a, 1, count))
        h.put32(MBOX+0x3c, 1)
        h.cpu.reg_write(r.UC_RISCV_REG_SP, STACK_TOPS[0])
        h.cpu.reg_write(r.UC_RISCV_REG_RA, END)
        h.cpu.reg_write(r.UC_RISCV_REG_A0, PAYLOAD)
        h.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 0)
        h.unmodeled = None
        self.trace = trace = TxTrace(done=True)
        h.done_tracking = True
        h.stops, h.skip_once = set(), None
        error, result = None, None
        try:
            h.cpu.emu_start(SET_CALLBACKS[1], END, count=3000000, timeout=60000000)
            assert h.cpu.reg_read(r.UC_RISCV_REG_PC) == END
            result = h.cpu.reg_read(r.UC_RISCV_REG_A0)
        except UnmodeledAccess as exc:
            error = str(exc)
        except UcError:
            if not h.unmodeled:
                raise
            error = h.unmodeled
        finally:
            self.trace = None
            h.done_tracking = False
        assert set(h.stub_counts) <= {'0x840048f4', '0x84004212', 'mhartid-csr'}, h.stub_counts
        assert set(trace.all_entries) <= set(DONE_TARGETS)|{0x840048f4, 0x84004212}, trace.all_entries
        assert h.get32(MBOX+0x3c) == 1
        assert h.get32(BOOT+8) == 6 and h.get32(ADM) == 1
        assert bytes(h.cpu.mem_read(CODE, len(h.code))) == self.code_image
        return dict(selector=10, requested_count=count, callback_return=result,
                    ready_flag=int.from_bytes(h.cpu.mem_read(SRAM+0x46fa, 1), 'little'),
                    mailbox_flags_untouched=1, stopped_access=error,
                    trace=trace.result(detailed),
                    logs=[dict(format=fmt, count=n) for fmt, n in Counter(
                        item['format'] for item in h.logs).items()]), trace

    def register_model(self, address, write):
        if address == self.missing:
            return None
        if address in REGS:
            return ('TX setup register write storage; no DMA, IRQ or hardware range semantics'
                    if write else None)
        if address in RESET_REGS:
            kind, _ = RESET_REGS[address]
            return ('SKB reset software mutex20 storage; hart0 readback, no hardware arbitration'
                    if write == (kind == 'write') else None)
        return super().register_model(address, write)

    def tx(self, selector, value, detailed=False):
        h = self.h
        h.cpu.mem_write(PAYLOAD, struct.pack('<3I', 0x10|selector, 19, value))
        h.put32(MBOX+0x3c, 1)
        h.cpu.reg_write(r.UC_RISCV_REG_SP, STACK_TOPS[0])
        h.cpu.reg_write(r.UC_RISCV_REG_RA, END)
        h.cpu.reg_write(r.UC_RISCV_REG_A0, PAYLOAD)
        h.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 0)
        h.unmodeled = None
        self.trace = trace = TxTrace()
        error, result = None, None
        try:
            assert h.run(SET_CALLBACKS[19], []) == END
            result = h.cpu.reg_read(r.UC_RISCV_REG_A0)
        except UnmodeledAccess as exc:
            error = str(exc)
        finally:
            self.trace = None
        assert set(h.stub_counts) <= {'0x840048f4'}, h.stub_counts
        assert set(trace.all_entries) <= set(TARGETS)|{0x840048f4}, trace.all_entries
        assert h.get32(MBOX+0x3c) == 1
        assert h.get32(BOOT+8) == 6 and h.get32(ADM) == 1
        assert bytes(h.cpu.mem_read(CODE, len(h.code))) == self.code_image
        return dict(selector=selector, supplied_value=hex(value), callback_return=result,
                    mailbox_flags_untouched=1, stopped_access=error,
                    trace=trace.result(detailed),
                    logs=[dict(format=fmt, count=n) for fmt, n in Counter(
                        item['format'] for item in h.logs).items()]), trace


def tx_oracle(c, selector, value):
    before = images(c.h)
    result = {base: bytearray(data) for base, data in before.items()}
    writes = set()

    def put(offset, number, fmt):
        data = struct.pack('<'+fmt, number)
        result[SRAM][offset:offset+len(data)] = data
        writes.update(range(SRAM+offset, SRAM+offset+len(data)))

    if selector in (0, 2, 3):
        put({0: 0x4700, 2: 0x46fc, 3: 0x4610}[selector], value, 'I')
    registers = {address: c.h.get32(address) for address in REGS}
    expected_register_writes = []
    if selector in (0, 2):
        put(0x3978, 0, 'H')
        put(0x21f4, 0, 'H')
        arena = struct.unpack_from('<I', before[SRAM], 0x30fc)[0]
        rx0, rx2 = ((arena+c.offsets[index]) & 0xffffffff for index in (1, 2))
        port = before[SRAM][0x390e]
        if port in (0, 1):
            target, values = (0x1fc08000 if port == 0 else 0x1fc28000), (rx0, rx2+0x28020)
        elif port in (2, 3):
            target = {(2, 0): 0x1fc08000, (2, 2): 0x1fc48000,
                      (3, 0): 0x1fc28000, (3, 2): 0x1fc08000}[port, selector]
            values = (rx0, rx0+0x22020) if selector == 0 else (rx2, rx2+0x28020)
        else:
            target, values = None, ()
        expected_register_writes = [(target+offset, number & 0x1fffffff)
                                    for offset, number in zip((0x30, 0x34), values)]
        registers.update(expected_register_writes)
    return result, writes, registers, expected_register_writes


def tx_completed(c, selector, value, name, detailed=False):
    want, allowed, registers, wanted_register_writes = tx_oracle(c, selector, value)
    row, trace = c.tx(selector, value, detailed)
    assert row['stopped_access'] is None and row['callback_return'] == 1, row
    assert images(c.h) == want, (name, 'whole RAM mismatch')
    assert trace.memory_written == allowed, (name, 'memory write extent mismatch')
    assert all(space not in ('host-memory', 'skb-state-memory') for _, _, _, space in trace.groups)
    actual_register_writes = [(int(event['address'], 16), event['value'])
                             for event in c.h.mmio if event['kind'] == 'mmio-write']
    assert actual_register_writes == wanted_register_writes, (name, actual_register_writes)
    assert {address: c.h.get32(address) for address in REGS} == registers
    assert trace.entries[0x8400d490] == int(selector in (0, 2))
    assert trace.entries[0x8400fab2] == 2*int(selector in (0, 2))
    if selector in (0, 2):
        arena = c.h.get32(SRAM+0x30fc)
        assert trace.return_values[0x8400fab2] == [(arena+c.offsets[i]) & 0xffffffff for i in (2, 1)]
    assert not c.h.allocations
    row.update(name=name, whole_ram_compared_bytes=sum(length for _, length in IMAGES),
               whole_ram_sha256={hex(base): digest(data) for base, data in want.items()},
               exact_memory_and_register_write_footprints=True,
               register_writes=[[hex(address), hex(value)] for address, value in wanted_register_writes],
               supplied_host_pointer_dereferenced=False)
    return row


def done_images(h):
    return {**images(h), **{base: bytearray(h.cpu.mem_read(base, length))
                            for base, length in ((HOST, HOST_BYTES), (SKB_STATE, SKB_BYTES))}}


def done_oracle(c, count):
    """Descriptor allocation and SKB reset from pre-call tables, not traced writes."""
    before = done_images(c.h)
    result = {base: bytearray(data) for base, data in before.items()}
    allowed = set()

    def read(address, fmt='I'):
        for base, data in before.items():
            if base <= address and address+struct.calcsize('<'+fmt) <= base+len(data):
                return struct.unpack_from('<'+fmt, data, address-base)[0]
        raise AssertionError(('oracle read outside RAM', hex(address)))

    def put(address, data):
        for base, image in result.items():
            if base <= address and address+len(data) <= base+len(image):
                image[address-base:address-base+len(data)] = data
                allowed.update(range(address, address+len(data)))
                return
        raise AssertionError(('oracle write outside RAM', hex(address), len(data)))

    def number(address, value, fmt='I'):
        put(address, struct.pack('<'+fmt, value))

    ids_base = c.fixed[0x107]
    number(SRAM+0x2a7c, count & 0xffff, 'H')
    number(SRAM+0x2cf4, ids_base)
    head, tail = (read(SRAM+offset, 'H') for offset in (0x1ba4, 0x1b80))
    allocated = min(count, (tail-head-1) % 16384)
    failed = allocated != count
    ids = [read(read(SRAM+0x1b88)+((head+i) % 16384)*2, 'H') for i in range(allocated)]
    packet, descriptors, stats = (read(SRAM+offset) for offset in (0x396c, 0x3964, 0x1f08))
    for index, bufid in enumerate(ids):
        pointer = ((packet+bufid*2048) & 0x3fffffff | 0x80000000)+128
        put(descriptors+16*index, struct.pack('<4I', pointer, 0x07000100, 0, 0))
        number(ids_base+2*index, bufid, 'H')
    if allocated:
        number(SRAM+0x1ba4, (head+allocated) % 16384, 'H')
        number(SRAM+0x1b90, read(SRAM+0x1b90)+allocated)
        number(stats+0x1c, read(stats+0x1c)+allocated)
    if failed:
        number(stats+0x20, read(stats+0x20)+1)
    footprint = dict(allocated=allocated, failed=failed, ids=ids,
                     descriptors=dict(base=hex(descriptors), bytes=allocated*16, nominal_bytes=8192),
                     software_ids=dict(base=hex(ids_base), bytes=allocated*2), skb_reset_executed=not failed)
    if not failed:
        gp = c.h.cpu.reg_read(r.UC_RISCV_REG_GP)
        capacity = read(gp-0x7e8)
        temporary, state, queue = (read(address) for address in (SRAM+0x1bc0, SRAM+0x469c, gp+0x7dc))
        tx_packet = read(SRAM+0x2ab8)
        occupied = [((read(read(SRAM+0x1f28+band*4)+index*32+8)-tx_packet) & 0xffffffff) >> 11 & 0xffff
                    for band in (0, 1) for index in range(1024)]
        assert len(set(occupied)) == 2048 and all(bufid < capacity for bufid in occupied)
        put(temporary, struct.pack('<2048H', *occupied))
        put(state, bytes(capacity*2))
        for bufid in occupied:
            number(state+bufid*2, 3, 'H')
        occupied_set = set(occupied)
        ordered = occupied+[bufid for bufid in range(capacity) if bufid not in occupied_set]
        put(queue, struct.pack('<'+'H'*capacity, *ordered))
        number(SRAM+0x1bb4, 2048, 'H')
        number(gp+0x7ec, 0, 'H')
        number(SRAM+0x3974, 0)
        number(SRAM+0x46fa, 1, 'B')
        footprint['skb_reset'] = dict(capacity=capacity, occupied_ids=2048,
            occupied_sha256=digest(struct.pack('<2048H', *occupied)),
            temporary_base=hex(temporary), temporary_written_bytes=4096,
            unconditional_temporary_read_bytes=capacity*2,
            state_base=hex(state), state_bytes=capacity*2,
            queue_base=hex(queue), queue_bytes=capacity*2,
            queue_sha256=digest(struct.pack('<'+'H'*capacity, *ordered)))
    return result, allowed, footprint


def done_completed(c, count, name, detailed=False):
    want, allowed, footprint = done_oracle(c, count)
    row, trace = c.done(count, detailed)
    assert row['callback_return'] == 1 and row['stopped_access'] is None, row
    assert row['ready_flag'] == int(not footprint['failed'])
    assert done_images(c.h) == want, (name, 'whole RAM including TXFREE/SKB state mismatch')
    assert trace.memory_written == allowed, (name, 'write extent mismatch',
        [hex(x) for x in sorted(trace.memory_written-allowed)[:8]],
        [hex(x) for x in sorted(allowed-trace.memory_written)[:8]])
    assert trace.return_values.get(0x84004d80, []) == footprint['ids']+([0xffffffff] if footprint['failed'] else [])
    assert trace.return_values[0x84005200] == [c.fixed[0x107]]
    assert [(entry['type'], entry['value']) for entry in c.h.allocations] == [(0x107, c.fixed[0x107])]
    assert trace.entries[0x840049f0] == trace.entries[0x84009aa6] == int(not footprint['failed'])
    register_writes = [(int(event['address'], 16), event['value']) for event in c.h.mmio
                       if event['kind'] == 'mmio-write']
    expected_writes = [(0x1ec031f0, 0x40), (0x1ec03270, 0)]*(footprint['allocated']+int(footprint['failed']))
    if not footprint['failed']:
        expected_writes += [(0x1ec031cc, 0x40), (0x1ec031d0, 0x40), (0x1ec03250, 0), (0x1ec0324c, 0)]
        assert trace.return_values[0x84009aa6] == [2048]
        base = int(footprint['skb_reset']['temporary_base'], 16)
        reads = trace.groups[0x84004b08, 'read', 2, 'memory']['addresses']
        assert reads == Counter({base+2*i: 1 for i in range(footprint['skb_reset']['capacity'])})
        publication = trace.groups[0x8400b558, 'write', 1, 'memory']
        assert publication['addresses'] == {SRAM+0x46fa: 1}
        assert publication['first_ordinal'] > max(group['last_ordinal'] for key, group in trace.groups.items()
            if key[1] == 'write' and key[3] != 'stack' and group is not publication)
    assert register_writes == expected_writes
    footprint['ids_first_last'] = footprint['ids'][:1]+footprint['ids'][-1:]
    del footprint['ids']
    row.update(name=name, footprint=footprint, whole_ram_compared_bytes=sum(len(data) for data in want.values()),
               whole_ram_sha256={hex(base): digest(data) for base, data in want.items()},
               exact_memory_and_register_write_footprints=True)
    return row


def run(path):
    exported = exports()
    for name, value in CALLBACK_PARENTS.items():
        assert sha(ROOT/'tests/npu'/name) == value
    c = TxClosure(path, exported)
    h = c.h
    assert h.get32(SRAM+0x1c4) == SET_CALLBACKS[19] and h.get32(SRAM+0x17c) == SET_CALLBACKS[1]
    for pc in set(TARGETS+DONE_TARGETS):
        last_pc = int(exported[pc]['assembly'].strip().splitlines()[-1].split()[0].split(':')[1], 16)
        halfword = int.from_bytes(h.code[last_pc-CODE:last_pc-CODE+2], 'little')
        end = last_pc+(4 if halfword & 3 == 3 else 2)
        assert bytes(h.cpu.mem_read(pc, end-pc)) == h.code[pc-CODE:end-CODE]
    dependencies = {Path(module.__file__).resolve() for module in list(sys.modules.values())
                    if getattr(module, '__file__', None)
                    and Path(module.__file__).resolve().is_relative_to(ROOT/'tests/npu')}
    source_hashes = {file: sha(file) for file in dependencies}
    # Full native RX callbacks are an established prefix, not substituted helpers.
    c.restore(c.snapshot())
    rx_completed(c, 0, 1536, 'prefix_rx0')
    c.restore(c.snapshot())
    rx_completed(c, 2, 1024, 'prefix_rx2')
    h.cpu.mem_write(SRAM+0x3978, b'\x34\x12')
    h.cpu.mem_write(SRAM+0x21f4, b'\x78\x56')
    snapshot = c.snapshot()
    valid, controls = [], []
    for hif2 in (0, 1):
        for port in (2, 3):
            c.restore(snapshot)
            h.cpu.mem_write(PAYLOAD, struct.pack('<3I', 0x10, 14, port))
            assert h.call(SET_CALLBACKS[14], PAYLOAD) == 1
            for message in expected(hif2, port):
                if message['kind'] != 'message' or message['api'] != 19:
                    continue
                h.logs.clear()
                h.mmio.clear()
                h.stub_counts.clear()
                selector = message['word0'] & 15
                valid.append(tx_completed(c, selector, message['value'],
                             f'host_hif{hif2}_port{port}_set19_if{selector}', hif2 == 0))
    for port in (0, 1, 4, 255):
        for selector in (0, 2):
            c.restore(snapshot)
            h.cpu.mem_write(SRAM+0x390e, bytes([port]))
            controls.append(tx_completed(c, selector, 0x200d4420, f'port{port}_if{selector}'))
    for selector in (0, 2):
        for value in (0, 0xc0000000, 0xffffffff):
            c.restore(snapshot)
            controls.append(tx_completed(c, selector, value, f'unchecked_pointer_if{selector}_{value:x}'))
        c.restore(snapshot)
        h.put32(SRAM+0x30fc, 0)
        controls.append(tx_completed(c, selector, 0x200d4420, f'missing_arena_if{selector}_accepted'))
    for address in REGS:
        c.restore(snapshot)
        port, selector = ((3, 0) if address & 0x20000 else
                          (2, 2) if address & 0x40000 else (2, 0))
        h.cpu.mem_write(SRAM+0x390e, bytes([port]))
        c.missing = address
        row, _ = c.tx(selector, 0x200d4420)
        assert row['callback_return'] is None and hex(address) in row['stopped_access'], row
        row['name'] = f'missing_register_{address:x}'
        controls.append(row)
    c.restore(snapshot)
    before_strict = done_images(h)
    strict = [h.message([0x10|selector, 19, 0x200d4420]) for selector in (0, 2)]
    assert all(row['flags'] == 3 and not row['callbacks'] for row in strict)
    assert done_images(h) == before_strict
    c.restore(snapshot)
    for message in expected(0, 2):
        if message['kind'] == 'message' and message['api'] == 19:
            h.logs.clear()
            h.mmio.clear()
            h.stub_counts.clear()
            tx_completed(c, message['word0'] & 15, message['value'], 'done_tx_prerequisite')
    for api, value in ((33, 8192), (22, TXFREE)):
        h.cpu.mem_write(PAYLOAD, struct.pack('<3I', 0x10, api, value))
        assert h.call(SET_CALLBACKS[api], PAYLOAD) == 1
    assert h.get32(SRAM+0xbc0) == 8192 and h.get32(SRAM+0x3964) == HOST
    done_snapshot = c.snapshot()
    c.restore(done_snapshot)
    valid_done = [done_completed(c, 512, 'host_txdone512_after_rx_and_set19', True)]
    done_controls = []
    for count in (0, 513):
        c.restore(done_snapshot)
        done_controls.append(done_completed(c, count, f'txdone_size{count}_accepted'))
    for available in (0, 17):
        c.restore(done_snapshot)
        head = int.from_bytes(h.cpu.mem_read(SRAM+0x1ba4, 2), 'little')
        h.cpu.mem_write(SRAM+0x1b80, struct.pack('<H', (head+available+1) % 16384))
        done_controls.append(done_completed(c, 512, f'txdone_bufid_exhaustion_after{available}'))
    c.restore(done_snapshot)
    h.put32(SRAM+0x396c, 0)
    done_controls.append(done_completed(c, 512, 'txdone_missing_packet_base_accepted'))
    c.restore(done_snapshot)
    h.cpu.mem_write(PAYLOAD, struct.pack('<3I', 0x10, 33, 0x7000))
    assert h.call(SET_CALLBACKS[33], PAYLOAD) == 1
    c.restore(c.snapshot())
    done_controls.append(done_completed(c, 512, 'txdone_native_max_token_bound'))
    c.restore(done_snapshot)
    tx_ring = h.get32(SRAM+0x1f28)
    h.put32(tx_ring+8, h.get32(SRAM+0x2ab8)+8191*2048)
    done_controls.append(done_completed(c, 512, 'txdone_synthetic_occupied_id8191'))
    missing_reset = {0x1ec031cc: 0x84004a28, 0x1ec0304c: 0x84004a2c,
                     0x1ec0324c: 0x84004b7e, 0x1ec031d0: 0x840064f2,
                     0x1ec03050: 0x840064f4, 0x1ec03250: 0x84006554}
    for address, pc in missing_reset.items():
        c.restore(done_snapshot)
        c.missing = address
        row, _ = c.done(512)
        assert row['callback_return'] is None and row['ready_flag'] == 0
        assert hex(address) in row['stopped_access'] and hex(pc) in row['stopped_access'], row
        row['name'] = f'txdone_missing_register_{address:x}'
        done_controls.append(row)
    for offset, pc in ((0x3964, 0x8400b4b6), (0x469c, 0x84004aac)):
        c.restore(done_snapshot)
        h.put32(SRAM+offset, 0)
        row, _ = c.done(512)
        assert row['callback_return'] is None and row['ready_flag'] == 0
        assert hex(pc) in row['stopped_access'], row
        row['name'] = f'txdone_missing_pointer_{offset:x}'
        done_controls.append(row)
    c.restore(done_snapshot)
    c.host_limit = 511*16
    row, _ = c.done(512)
    c.host_limit = HOST_BYTES
    assert row['callback_return'] is None and row['ready_flag'] == 0
    assert hex(HOST+511*16+4) in row['stopped_access'] and '0x8400b4b6' in row['stopped_access'], row
    row['name'] = 'txdone_host_capacity_one_descriptor_short'
    done_controls.append(row)
    c.restore(done_snapshot)
    before_strict = done_images(h)
    strict_done = h.message([0x1a, 1, 512])
    assert strict_done['flags'] == 3 and not strict_done['callbacks']
    assert done_images(h) == before_strict
    assert sha(path) == ELF_SHA
    assert all(sha(file) == value for file, value in source_hashes.items())
    sources = {str(file.relative_to(ROOT)): value for file, value in source_hashes.items()}
    sources.update({str(Path(__file__).relative_to(ROOT)): sha(Path(__file__)),
                    str(path.relative_to(ROOT)): ELF_SHA,
                    str(GHIDRA.relative_to(ROOT)): GHIDRA_SHA, str(DTB.relative_to(ROOT)): sha(DTB),
                    str((INPUT/'en7581_MT7996_npu_rv32.bin').relative_to(ROOT)): CODE_SHA,
                    str((INPUT/'en7581_MT7996_npu_data.bin').relative_to(ROOT)): DATA_SHA})
    return dict(schema=1, base_commit='d41ac7ba1987f2d47a5e95146f8127cd7f7d49e4', sources=sources,
        scope='Original SET19/TXDONE consumers after native core0/RX prefix; explicit storage MMIO only.',
        counts=dict(new_original_pending_closures=3, valid_callbacks=len(valid)+len(valid_done),
                    negative_controls=len(controls)+len(done_controls), strict_denials=len(strict)+1),
        prerequisite=dict(boot_footprint=c.boot_footprint, boot_stubs=c.boot_stubs,
            rx_prefix=[1536, 1024], page_callbacks_executed=False,
            counter_seeds={'0x3e903978': '0x1234', '0x3e9021f4': '0x5678'},
            new_registers={hex(address): 'write-only storage, seeded 0xa5a5a5a5; no physical semantics'
                           for address in REGS},
            reset_registers={hex(address): dict(direction=kind, seed_or_written_value=hex(value))
                             for address, (kind, value) in RESET_REGS.items()},
            txdone_origin='Same native RX prefix -> SET19(3,0,2) -> native SET33(8192) -> SET22(TXFREE)',
            txfree=dict(physical=hex(TXFREE), cpu_view=hex(HOST), nominal_bytes=8192,
                        guard_bytes=4096, cache_coherency_proven=False),
            skb_state=dict(cpu_view=hex(SKB_STATE), reservation_bytes=SKB_BYTES,
                           boot_observer_replaced_for_later_state_writes=True)),
        ghidra_functions={hex(pc): dict(line=exported[pc]['line'], name=exported[pc]['name'],
            export_sha256=digest((exported[pc]['text']+exported[pc]['assembly']).encode())) for pc in sorted(set(TARGETS+DONE_TARGETS))},
        valid_callbacks=valid, negative_controls=controls, strict_replies=strict,
        valid_txdone=valid_done, txdone_controls=done_controls, strict_txdone=strict_done,
        boundaries=['Not a complete host 38-message integration or strict API1/API19 admission.',
                    'Register values span native arena subregions; physical register meanings remain unproved.',
                    'A value equals the arena end; this alone does not establish an out-of-bounds consumer.',
                    'Malformed inputs are emulator counterexamples, not demonstrated client failures.',
                    'No packet memory, physical DMA/cache/drain/containment, worker release, restart or parity proof.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--elf', type=Path, default=ELF)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = run(args.elf.resolve())
    encoded = json.dumps(result, indent=2, sort_keys=True)+'\n'
    assert len(encoded.encode()) < 400000
    if args.check:
        assert OUT.read_text() == encoded, 'receipt differs from fresh native replay'
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(encoded)
    print(json.dumps(dict(status='PASS', **result['counts'], bytes=len(encoded.encode()),
                          json_sha256=digest(encoded.encode()), test_sha256=sha(Path(__file__)))))


if __name__ == '__main__':
    main()
