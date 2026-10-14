#!/usr/bin/env python3
"""Portable DESC10 owner: exact host-C/RV32 state and ordered logical effects."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import shutil
import struct
import sys

sys.dont_write_bytecode = True
import test_cold_tx_buffer as tx
from test_barrier_protocol import Rv32
from unicorn import riscv_const as r

ROOT, CORE = tx.ROOT, tx.ROOT / 'firmware/npu'
TESTS = ROOT / 'tests/npu'
PREFIX, IDS, OCCUPIED, CAPACITY = 2560, 512, 2048, 8192
DESCRIPTOR_STORES = 2 + IDS * 6
STORES = DESCRIPTOR_STORES + OCCUPIED * 3 + CAPACITY * 2 + 4
OWNER_IDS = 200 + 512 * 4
OWNER_BITMAP = OWNER_IDS + IDS * 4 + OCCUPIED * 4
END = tx.END
NAMES = ['state', 'plan', 'rx', 'packet', 'last', 'occupied', 'pool', 'head', 'tail',
         'ring', 'ids', 'temp', 'check', 'queue', 'count', 'pointer', 'skb_head',
         'skb_tail', 'counter', 'ready', 'events', 'event_count']


class Pair:
    def __init__(self, shared, elf):
        self.host, self.rv = ctypes.CDLL(str(shared)), Rv32(elf)
        self.calls = 0
        symbols = {s.name: s for s in self.rv.elf.get_section_by_name('.symtab').iter_symbols()}
        self.fields = {}
        for name in NAMES:
            symbol = symbols['npu_test_txdone_' + name]
            assert symbol['st_size'] and symbol['st_info']['type'] == 'STT_OBJECT'
            self.fields[name] = (symbol['st_value'], symbol['st_size'],
                (ctypes.c_uint8 * symbol['st_size']).in_dll(self.host, symbol.name))
        assert self.fields['state'][1] == 13512 and self.fields['plan'][1] == 136

    def compare(self, names=NAMES):
        for name in names:
            address, length, host = self.fields[name]
            assert bytes(host) == bytes(self.rv.cpu.mem_read(address, length)), ('host-rv-state', name)

    def values(self, name):
        return struct.unpack('<' + 'I' * (self.fields[name][1] // 4), bytes(self.fields[name][2]))

    def setword(self, name, offset, value):
        data = bytearray(bytes(self.fields[name][2]))
        struct.pack_into('<I', data, offset, value)
        self.setbytes(name, data)

    def setbytes(self, name, data):
        address, length, host = self.fields[name]
        assert len(data) == length
        ctypes.memmove(host, bytes(data), length)
        self.rv.cpu.mem_write(address, bytes(data))

    def snapshot(self):
        self.compare()
        return {name: bytes(value[2]) for name, value in self.fields.items()}

    def restore(self, saved):
        for name, data in saved.items():
            self.setbytes(name, data)

    def invoke(self, name, host, native, *, check=NAMES):
        function = getattr(self.host, name)
        function.restype = ctypes.c_uint32
        result = function(*host)
        for i, value in enumerate(native):
            self.rv.cpu.reg_write(getattr(r, 'UC_RISCV_REG_A' + str(i)), value)
        self.rv.cpu.reg_write(r.UC_RISCV_REG_SP, 0x84100000)
        self.rv.cpu.reg_write(r.UC_RISCV_REG_RA, END)
        self.rv.cpu.emu_start(self.rv.symbols[name], END, count=500000000, timeout=30000000)
        assert self.rv.cpu.reg_read(r.UC_RISCV_REG_PC) == END, ('native-budget', name)
        assert self.rv.cpu.reg_read(r.UC_RISCV_REG_SP) == 0x84100000, ('native-stack', name)
        assert result == self.rv.cpu.reg_read(r.UC_RISCV_REG_A0), ('host-rv-return', name)
        self.compare(check)
        self.calls += 1
        return result

    def call(self, name, *values, check=NAMES):
        return self.invoke('npu_test_txdone_' + name, [ctypes.c_uint32(v) for v in values], values, check=check)

    def core(self, name, *values):
        host, native = [], []
        for value in ('state', 'plan', 1, *values):
            if isinstance(value, str):
                address, _, data = self.fields[value]
                host.append(ctypes.cast(data, ctypes.POINTER(ctypes.c_uint32)))
                native.append(address)
            else:
                host.append(ctypes.c_uint32(value))
                native.append(value)
        return self.invoke('npu_cold_txdone_' + name, host, native)


def expected_events(plan):
    """Independent literal order from the original stores, never the C recipe."""
    ring = (plan[29] & 0x3fffffff) | 0x40000000
    packet, check = plan[21], (plan[19] & 0x3fffffff) | 0x40000000
    ids_pool, temporary, queue = plan[31:34]
    selected = [8000 + i * 13 % IDS for i in range(IDS)]
    occupied = [(i * 17 + 7) % CAPACITY for i in range(OCCUPIED)]
    events = [(0x3e902a7c, 2, IDS), (0x3e902cf4, 4, ids_pool)]
    for index, ident in enumerate(selected):
        address = ring + index * 16
        pointer = ((packet + ident * 2048) & 0x3fffffff | 0x80000000) + 128
        events += [(address + 4, 4, 0), (address, 4, pointer), (address + 8, 4, 0),
                   (address + 12, 4, 0), (address + 4, 4, 0x07000100), (ids_pool + index * 2, 2, ident)]
    events += [(temporary + i * 2, 2, 65535) for i in range(OCCUPIED)]
    events += [(temporary + i * 2, 2, ident) for i, ident in enumerate(occupied)]
    events += [(check + i * 2, 2, 0) for i in range(CAPACITY)]
    events += [(check + ident * 2, 2, 3) for ident in occupied]
    occupied_set = set(occupied)
    ordered = occupied + [i for i in range(CAPACITY) if i not in occupied_set]
    events += [(queue + i * 2, 2, ident) for i, ident in enumerate(ordered)]
    events += [(0x3e901bb4, 2, OCCUPIED), (0x3e901b94, 2, 0),
               (0x3e903974, 4, 0), (0x3e9046fa, 1, 1)]
    assert len(events) == STORES
    return events


def assert_trace(pair, events, count):
    assert pair.values('event_count')[0] == count
    actual = bytes(pair.fields['events'][2])
    expected = b''.join(struct.pack('<3I', *e) for e in events[:count])
    assert actual[:len(expected)] == expected, ('ordered-write-oracle', count)
    assert actual[len(expected):] == bytes(len(actual) - len(expected)), 'unwritten-event-tail'


def assert_memory(pair, plan, events):
    bases = {'ring': (plan[29] & 0x3fffffff) | 0x40000000, 'ids': plan[31], 'temp': plan[32],
             'check': (plan[19] & 0x3fffffff) | 0x40000000, 'queue': plan[33],
             'count': 0x3e902a7c, 'pointer': 0x3e902cf4, 'skb_head': 0x3e901bb4,
             'skb_tail': 0x3e901b94, 'counter': 0x3e903974, 'ready': 0x3e9046fa}
    memory = {name: bytearray([0xa5] * pair.fields[name][1]) for name in bases}
    for address, length, value in events:
        matches = [name for name, base in bases.items() if base <= address and
                   address + length <= base + len(memory[name])]
        assert len(matches) == 1, ('oracle-owned-span', hex(address))
        name = matches[0]
        offset = address - bases[name]
        memory[name][offset:offset + length] = value.to_bytes(length, 'little')
    for name, data in memory.items():
        assert bytes(pair.fields[name][2]) == data, ('whole-logical-memory-oracle', name)


def exercise(pair, *, exhaustive=True):
    assert pair.call('fresh', 0) == 0
    fresh = pair.snapshot()
    assert pair.call('begin') == 0
    started = pair.snapshot()
    plan = pair.values('plan')
    events = expected_events(plan)
    checkpoints = sorted(set([0, 1, 2, 2 + 17 * 6, DESCRIPTOR_STORES,
        DESCRIPTOR_STORES + OCCUPIED, DESCRIPTOR_STORES + OCCUPIED * 2,
        DESCRIPTOR_STORES + OCCUPIED * 2 + CAPACITY,
        DESCRIPTOR_STORES + OCCUPIED * 3 + CAPACITY,
        DESCRIPTOR_STORES + OCCUPIED * 4 + CAPACITY,
        STORES - 4, STORES - 3, STORES - 2, STORES - 1, STORES]))
    snapshots = {0: started}
    position = 0
    for endpoint in checkpoints[1:]:
        assert pair.call('run', endpoint - position, 0) == 0, ('nominal-phase', position, endpoint)
        position = endpoint
        assert_trace(pair, events, position)
        assert_memory(pair, plan, events[:position])
        owner = pair.values('state')
        assert owner[2] == 0 and owner[3] == 1 and list(owner[4:7]) == [position] * 3
        assert owner[7] == owner[8] == owner[9] and owner[7] <= IDS
        snapshots[position] = pair.snapshot()
    complete = pair.snapshot()
    assert pair.call('finish') == 0 and pair.call('live') == 1
    occupied_set = {(i * 17 + 7) % CAPACITY for i in range(OCCUPIED)}
    cursor = max(i for i in range(CAPACITY) if i not in occupied_set) + 1
    assert list(pair.values('state')[:12]) == [0x31445443, 1, 0, 0, STORES, STORES, STORES,
                                            IDS, IDS, IDS, 1, cursor]
    assert pair.values('packet')[4] == PREFIX + IDS
    assert pair.call('begin') != 0 and pair.values('state')[2] == 1
    controls = 1
    pair.restore(started)
    pair.setword('ready', 0, 1)
    assert pair.call('finish') == 5 and pair.values('state')[4:7] == (0, 0, 0)
    controls += 1
    first_id = struct.unpack_from('<I', complete['state'], OWNER_IDS)[0]
    for name, offset, value in [('rx', 8, 1), ('packet', 7 * 4, 0),
                                ('state', OWNER_IDS + 4, first_id), ('state', OWNER_BITMAP, 0xffffffff)]:
        pair.restore(complete)
        pair.setword(name, offset, value)
        assert pair.call('finish') == 5
        assert pair.values('state')[2:7] == (1, 1, STORES, STORES, STORES)
        controls += 1
    for field, size in [(30, 32768), (31, 1024), (32, 4096), (33, 16384)]:
        for address in (0, 0x3e800001, 0x3e878000 - size + 32, plan[0], plan[31 if field == 30 else 30]):
            pair.restore(fresh)
            pair.setword('plan', field * 4, address)
            assert pair.call('begin') != 0 and pair.values('state')[2] == 1
            assert pair.values('state')[4:7] == (0, 0, 0)
            controls += 1
    for position in checkpoints[:-1]:
        for fault in (1, 2, 3):
            pair.restore(snapshots[position])
            assert pair.call('run', 1, fault) != 0
            owner = pair.values('state')
            assert owner[2] == owner[3] == 1 and owner[4] == owner[5] == position + 1
            assert owner[6] == position + int(fault == 3)
            assert pair.call('live') == 0
            assert pair.call('begin') != 0 and pair.values('state')[5] == position + 1
            controls += 1
    for word in range(34):
        pair.restore(started)
        pair.setword('plan', word * 4, plan[word] ^ 1)
        assert pair.call('run', 1, 0) != 0 and pair.values('state')[2] == 1
        assert pair.values('state')[4:7] == (0, 0, 0)
        controls += 1
    rx_before = struct.unpack('<38I', fresh['rx'])
    for word in [0, 1, 2, 3, 4, 5, 6, *range(8, 38)]:
        pair.restore(fresh)
        pair.setword('rx', word * 4, rx_before[word] ^ 1)
        assert pair.call('begin') != 0 and pair.values('state')[2] == 1
        assert not any(pair.values('state')[4:7])
        controls += 1
    pkt_before = struct.unpack('<519I', fresh['packet'])
    for word in (0, 1, 2, 3, 4, 5, 6, 7, 87, 518):
        pair.restore(fresh)
        pair.setword('packet', word * 4, pkt_before[word] ^ 1)
        assert pair.call('begin') != 0 and pair.values('state')[2] == 1
        controls += 1
    pair.restore(started)
    assert pair.core('claim_reserve', 'packet') == 6
    controls += 1
    pair.restore(started)
    pair.setword('state', 7 * 4, 1)
    assert pair.core('reserve', 0x3e902a7c, 2, IDS, 0xa5a5) == 6
    assert pair.values('state')[4:7] == (0, 0, 0)
    controls += 1
    for address, width, value in ((0x3e902a80, 2, IDS), (0x3e902a7c, 4, IDS),
                                  (0x3e902a7c, 2, IDS ^ 1)):
        pair.restore(started)
        assert pair.core('reserve', address, width, value, 0xa5a5) == 6
        assert pair.values('state')[4:7] == (0, 0, 0)
        controls += 1
    pair.restore(started)
    assert pair.core('publish', 0x3e902a7c, 2, IDS) == 6
    controls += 1
    pair.restore(started)
    assert pair.core('reserve', 0x3e902a7c, 2, IDS, 0xa5a5) == 0
    assert pair.values('state')[4:7] == (1, 1, 0)
    assert pair.core('reserve', 0x3e902a7c, 2, IDS, 0xa5a5) == 6
    assert pair.values('state')[4:7] == (1, 1, 0)
    controls += 1
    for published in (0, 1):
        pair.restore(snapshots[2])
        assert pair.call('take_late', published) == 7
        owner = pair.values('state')
        assert owner[2] == owner[3] == owner[7] == owner[8] == 1
        assert owner[9] == published and pair.values('packet')[4] == PREFIX + 1
        assert pair.call('live') == 0
        controls += 1
    for kind in ('empty', 'duplicate'):
        pair.restore(snapshots[2])
        if kind == 'empty':
            pair.setbytes('tail', struct.pack('<H', PREFIX + 1))
        else:
            pool = bytearray(fresh['pool'])
            struct.pack_into('<H', pool, PREFIX * 2, 1)
            pair.setbytes('pool', pool)
        assert pair.call('take') == 7
        assert pair.values('state')[7:10] == (1, 0, 0)
        assert pair.values('packet')[4] == PREFIX
        controls += 1
    for mode in ('duplicate', 'outside'):
        pair.restore(snapshots[DESCRIPTOR_STORES])
        occupied = list(pair.values('occupied'))
        occupied[1] = occupied[0] if mode == 'duplicate' else CAPACITY
        pair.setword('occupied', 4, occupied[1])
        assert pair.call('skb_begin') == 5
        assert pair.values('state')[2] == pair.values('state')[10] == 1
        assert pair.values('state')[6] == DESCRIPTOR_STORES
        controls += 1
    pair.restore(complete)
    pair.setword('ready', 0, 0xa5a5a500)
    assert pair.call('finish') == 5 and pair.values('state')[3] == 1
    controls += 1
    if exhaustive:
        for word in range(pair.fields['state'][1] // 4):
            pair.restore(fresh)
            pair.setword('state', word * 4, 1)
            assert pair.call('begin', check=['state', 'plan', 'rx', 'packet']) == 3
            assert pair.values('state')[2] == 1
            controls += 1
        for alias in (1, 2):
            assert pair.call('fresh', alias) == pair.call('begin') == 0
            alias_plan = pair.values('plan')
            assert pair.call('run', STORES, 0) == pair.call('finish') == 0
            assert pair.call('live') == 1
            alias_events = expected_events(alias_plan)
            assert_trace(pair, alias_events, STORES)
            assert_memory(pair, alias_plan, alias_events)
    return dict(passed=True, calls=pair.calls, controls=controls,
                modeled_store_events=STORES, shared_packet_claims=IDS,
                owner_bytes=pair.fields['state'][1], phase_checkpoints=len(checkpoints))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--core-object', type=Path)
    parser.add_argument('--skip-mutants', action='store_true')
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-desc10-owner-20261013' / args.name
    assert not dest.exists()
    dest.mkdir(parents=True)
    sources = [CORE / name for name in ('cold-txdone.c', 'cold-rx-event.c', 'cold-tx-buffer.c', 'cold-packet.c')]
    fixture, linker_script = TESTS / 'cold-txdone-fixture.c', TESTS / 'cold-txdone-probe.ld'
    paths = sources + list(CORE.glob('*.h')) + [CORE / 'cold-page.c', fixture, linker_script, Path(__file__),
        Path(tx.__file__), Path(tx.loader.__file__), Path(tx.loader.extract.__file__),
        TESTS / 'test_barrier_protocol.py', CORE / 'Makefile']
    if args.core_object:
        assert args.core_object.resolve().is_relative_to(ROOT)
        paths.append(args.core_object.resolve())
    inputs = {str(p.relative_to(ROOT)): tx.loader.sha(p) for p in paths}
    command = [shutil.which('clang'), '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-I' + str(CORE)]
    linker = shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'
    rv_flags = ['--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32', '-nostdlib',
        '-ffreestanding', '-fno-builtin', '-fno-stack-protector', '--ld-path=' + str(linker),
        '-Wl,-T,' + str(linker_script)]
    shared, elf = dest / 'host.so', dest / 'owner.elf'
    tx.loader.run(command + ['-shared', '-fPIC', *sources, fixture, '-o', shared], dest / 'host-build.log')
    rv_sources = [args.core_object.resolve() if args.core_object else sources[0], *sources[1:]]
    tx.loader.run(command + [*rv_flags, *rv_sources, fixture, '-o', elf], dest / 'rv-build.log')
    result = exercise(Pair(shared, elf))
    sanitizer = dest / 'sanitize'
    tx.loader.run(command + ['-DNPU_TXDONE_SANITIZER', '-fsanitize=address,undefined',
        '-fno-sanitize-recover=all', *sources, fixture, '-o', sanitizer], dest / 'sanitize-build.log')
    tx.loader.run([sanitizer], dest / 'sanitize.log', env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1'))
    changes = {
        'ignore-finished-RX': ('!npu_cold_rx_event_live(rx, &p->prior, epoch, rx_readback) ||\n        !packet_header',
                              '(0 && !npu_cold_rx_event_live(rx, &p->prior, epoch, rx_readback)) ||\n        !packet_header'),
        'ignore-prefix-population': ('if (count != NPU_COLD_TXDONE_PREFIX)', 'if (0 && count != NPU_COLD_TXDONE_PREFIX)'),
        'ignore-fixed-ID-pool': ('|| p->ids_pool != NPU_COLD_TXDONE_IDS_POOL)', '|| (0 && p->ids_pool != NPU_COLD_TXDONE_IDS_POOL))'),
        'wrong-first-clear': ('field == 4 ? 0x07000100u : 0;', 'field == 4 ? 0x07000100u : 1;'),
        'ignore-reservation-value': ('bytes != store.bytes || value != store.value)', 'bytes != store.bytes || (0 && value != store.value))'),
        'ignore-readback': ('if (readback != store.value)', 'if (0 && readback != store.value)'),
        'omit-retained-store': ('s->reserved = ++s->committed;', 's->reserved = s->committed;'),
        'forget-committed-claim': ('s->claims_committed++;', 's->claims_committed += 0;'),
        'allow-reinitialize': ('if (words[i])', 'if (0 && words[i])'),
    }
    mutants = []
    if not args.skip_mutants:
        original = sources[0].read_text()
        for name, (old, new) in changes.items():
            assert original.count(old) == 1, name
            target = dest / 'mutants' / name
            target.mkdir(parents=True)
            source = target / 'owner.c'
            source.write_text(original.replace(old, new))
            mshared, melf = target / 'host.so', target / 'owner.elf'
            tx.loader.run(command + ['-shared', '-fPIC', source, *sources[1:], fixture, '-o', mshared], target / 'host-build.log')
            tx.loader.run(command + [*rv_flags, source, *sources[1:], fixture, '-o', melf], target / 'rv-build.log')
            rejected = False
            try:
                exercise(Pair(mshared, melf), exhaustive=False)
            except AssertionError:
                rejected = True
            assert rejected, name
            mutants.append(dict(name=name, host_sha256=tx.loader.sha(mshared), rv_sha256=tx.loader.sha(melf)))
    assert all(tx.loader.sha(ROOT / p) == digest for p, digest in inputs.items())
    result.update(inputs=inputs, mutants=mutants, sanitizers=['address', 'undefined', 'leak'],
        exact_core_object=str(args.core_object.resolve().relative_to(ROOT)) if args.core_object else None,
        binaries={str(p.relative_to(ROOT)): tx.loader.sha(p) for p in (shared, elf, sanitizer)},
        limits=['Exact compiled host-C/RV32 portable owner and logical-store fixture; RX/PKT owners use their actual portable APIs.',
                'Ordered logical store events and whole logical memory are compared with an independent literal oracle.',
                'Original DESC10 instructions, actual allocator/caller/session binding and native locks are not replayed here.',
                'This does not admit DESC10, establish physical backing/coherency/drains or full NPU acceptance.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('passed', 'calls', 'controls', 'modeled_store_events', 'owner_bytes')}))


if __name__ == '__main__':
    main()
