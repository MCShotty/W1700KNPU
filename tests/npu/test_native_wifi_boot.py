#!/usr/bin/env python3
"""Bounded native Wi-Fi initialization; hardware models remain explicit."""
import json
import hashlib
import re
import struct
from collections import Counter
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from unicorn import riscv_const as r

from test_bootstrap_native import Bootstrap, sequence, SOURCE, ROOT
from test_boot_irq_installation import Installation, UnmodeledAccess
from test_admission_native import build_platform
from test_bootstrap_native import plan, sha, DTB, CODE_SHA, DATA_SHA, BOOT, ADM
from test_boot_irq_installation import GHIDRA, IRQ_TABLE
from test_firmware_memory_layout import table
from emulation_layout import SRAM, STATE

OUT = ROOT / 'research/checkpoints/2026-09-06-npu-nativewifi'
L2, L2_BYTES, L2_CONTROL = 0x3e880000, 0x40000, 0x1ec0f200
WIFI_REGISTERS = (0x1fb50800, 0x1fb50804, 0x1fb50808, 0x1fb50a2c,
                  0x1fb50a28, 0x1fb50a04, 0x1fb52230, 0x1fb521f0,
                  0x1fb50fe8, 0x1fb54710, 0x1fb50900, 0x1fb50904,
                  0x1fb50910, 0x1fb50914, 0x1fb50908, 0x1fb5090c,
                  0x1fb50918, 0x1fb5091c)
HOST_REGISTERS = tuple(0x1ec0d000+n for n in (0xa0, 0xa4, 0xb0, 0xb4, 0x180, 0x190))
HOST_FIXTURE = {0x1ec0d0a0: 0x81000000, 0x1ec0d0a4: 1024,
                0x1ec0d0b0: 0x81100000, 0x1ec0d0b4: 512,
                0x1ec0d180: 0x81200000, 0x1ec0d190: 0x81300000}


class NativeWifi(Bootstrap):
    def __init__(self, path, missing=None):
        self.missing = missing
        self.allocations, self.returns, self.logs = [], [], []
        self.pending_call = None
        super().__init__(path)
        self.cpu.mem_map(L2, L2_BYTES)
        self.cpu.mem_write(L2, b'\xa5' * L2_BYTES)
        self.cpu.mem_map(0x1ec0f000, 0x1000)
        self.cpu.mem_map(0x1ec0d000, 0x1000)
        for base in sorted({address & ~0xfff for address in WIFI_REGISTERS}):
            self.cpu.mem_map(base, 0x1000)
        self.l2_writes = 0
        self.l2_clear_pcs = set()
        self.l2_clear_active = True
        self.l2_later = {}

    @staticmethod
    def is_memory(address, size):
        return (L2 <= address and address+size <= L2+L2_BYTES or
                Installation.is_memory(address, size))

    def register_model(self, address, write):
        if address == self.missing:
            return None
        if address == L2_CONTROL:
            return 'native L2 mode register storage only; no physical cache/mode transition'
        if address in WIFI_REGISTERS:
            return 'native Wi-Fi ring/configuration storage only; no DMA or IRQ side effects'
        if address in (0x1ec031cc, 0x1ec0304c, 0x1ec0324c):
            return 'SKB allocator mutex storage; single hart, no contention or hardware ownership'
        if address in HOST_REGISTERS and not write:
            return 'host adapter register input; explicit synthetic host publication, no physical ring proof'
        return Installation.register_model(address, write)

    def code_hook(self, cpu, pc, size, data):
        super().code_hook(cpu, pc, size, data)
        if self.pending_call and pc == self.pending_call['return_pc']:
            row = {**self.pending_call, 'value': cpu.reg_read(r.UC_RISCV_REG_A0)}
            self.allocations.append(row)
            self.pending_call = None
        if pc == 0x84005200:
            assert self.pending_call is None
            self.pending_call = {'type': cpu.reg_read(r.UC_RISCV_REG_A0),
                                 'return_pc': cpu.reg_read(r.UC_RISCV_REG_RA)}
        if pc in (0x8400e37a, 0x8400e37e):
            self.returns.append({'pc': hex(pc), 'a0': cpu.reg_read(r.UC_RISCV_REG_A0)})

    def skip(self, cpu, pc, size, data):
        if pc == 0x840048f4:
            address = cpu.reg_read(r.UC_RISCV_REG_A0)
            value = bytes(cpu.mem_read(address, 256)).split(b'\0', 1)[0]
            self.logs.append({'format': value.decode('ascii', errors='replace'),
                              'return_pc': hex(cpu.reg_read(r.UC_RISCV_REG_RA))})
        super().skip(cpu, pc, size, data)

    def write_hook(self, cpu, access, address, size, value, data):
        super().write_hook(cpu, access, address, size, value, data)
        if L2 <= address < L2+L2_BYTES:
            pc = hex(cpu.reg_read(r.UC_RISCV_REG_PC))
            if self.l2_clear_active:
                assert size == 4 and value == 0, (hex(address), size, hex(value), pc, self.l2_writes)
                assert address == L2 + self.l2_writes*4
                self.l2_writes += 1
                self.l2_clear_pcs.add(pc)
            else:
                row = self.l2_later.setdefault(pc, {'writes': 0, 'bytes': 0, 'first': address, 'end': address+size})
                row['writes'] += 1
                row['bytes'] += size
                row['first'] = min(row['first'], address)
                row['end'] = max(row['end'], address+size)


def to_wifi(path, delayed=False, missing=None, exhausted=False, register_seed=0):
    h = NativeWifi(path, missing)
    for address in WIFI_REGISTERS:
        h.put32(address, register_seed)
    h.reset()
    for words in sequence()[:2] if delayed else sequence():
        assert h.message(words)['flags'] == 7
    start = h.cpu.reg_read(r.UC_RISCV_REG_PC)
    assert h.run(start, [0x8400d1d4]) == 0x8400d1d4
    assert h.l2_writes*4 == L2_BYTES and h.get32(L2_CONTROL) == 1
    assert bytes(h.cpu.mem_read(L2, L2_BYTES)) == bytes(L2_BYTES)
    h.l2_clear_active = False
    if exhausted:
        assert not delayed
        assert h.run(0x8400d1d4, [0x84009fc8]) == 0x84009fc8
        h.cpu.mem_write(SRAM+0x1b94, struct.pack('<H', 1))
        assert bytes(h.cpu.mem_read(SRAM+0x1bb4, 2)) == bytes(2)
    if delayed:
        assert h.run(0x8400d1d4, [0x8400a04a]) == 0x8400a04a
        assert h.get32(SRAM+0x2ab8) == 0 and h.get32(SRAM+0x4708) == 0
        assert h.run(0x8400a04a, [0x8400a04a]) == 0x8400a04a
        for words in sequence()[2:]:
            assert h.message(words)['flags'] == 7
    assert h.run(h.cpu.reg_read(r.UC_RISCV_REG_PC), [0x8400f836]) == 0x8400f836
    return h


def footprints(h, exhausted=False, register_seed=0):
    tx_region = plan()[3]
    fixed = {row['type']: row['value'] for row in table(h.code, 0x8401b20c)}
    fixed.update({row['type']: row['value'] for row in table(h.code, 0x8401cf70)})
    rx, tx, ids = (fixed[kind] for kind in (0x181, 0x182, 0x106))
    expected = bytearray(L2_BYTES)
    struct.pack_into('<8192H', expected, ids-L2, *range(8192))
    for index in range(2048):
        struct.pack_into('<I', expected, rx-L2+index*32+20, 0x7f4087ff)
        expected[rx-L2+index*32+7] = 0x80
        if not exhausted:
            pointer = ((tx_region[0]+index*2048) & 0x3fffffff) | 0x80000000
            struct.pack_into('<II', expected, tx-L2+index*32+4, 2048, pointer)
    actual = bytes(h.cpu.mem_read(L2, L2_BYTES))
    assert actual == bytes(expected), 'native L2 contents differ from complete descriptor/table footprint'
    assert h.get32(SRAM+0x46dc) == (0 if exhausted else 2048)
    assert h.get32(SRAM+0x46d4) == (2048 if exhausted else 0)
    warnings = [row for row in h.logs if 'maclloc failed' in row['format']]
    assert len(warnings) == (2048 if exhausted else 0)
    assert h.get32(SRAM+0x1f1c) == rx
    assert [h.get32(SRAM+0x1f28+n*4) for n in (0, 1)] == [tx, tx+0x8000]
    assert h.get32(IRQ_TABLE+95*4) == 0x84008f6e
    assert h.get32(0x0c00200c) & 1
    assert h.get32(0x1fb50800) == rx & 0x1fffffff
    assert h.get32(0x1fb50804) == 2048 and h.get32(0x1fb50808) == 0
    for index in (0, 1):
        base = 0x1fb50900+index*16
        assert h.get32(base) == (tx+index*0x8000) & 0x1fffffff
        assert h.get32(base+4) == (register_seed & 0xffffe000) | 0x400
        assert h.get32(base+8) == 0x3ff and h.get32(base+12) == 0
    assert h.get32(0x1fb50a04) == register_seed | 0x75
    assert h.get32(0x1fb54710) == register_seed | 0x80000000
    return {'l2_sha256': hashlib.sha256(actual).hexdigest(), 'whole_l2_compared_bytes': L2_BYTES,
            'id_table': {'start': hex(ids), 'entries': 8192, 'bytes': 16384},
            'rx_descriptors': {'start': hex(rx), 'entries': 2048, 'stride': 32},
            'tx_descriptors': {'start': hex(tx), 'rings': 2, 'entries_per_ring': 1024, 'stride': 32},
            'tx_packet_pointers': {'first': hex(tx_region[0]),
                                   'last_end': hex(tx_region[0]+2048*2048),
                                   'reservation_end': hex(sum(tx_region)),
                                   'valid_entries': 0 if exhausted else 2048,
                                   'backing_packet_memory_accessed': False},
            'allocation_failures': len(warnings), 'register_seed': hex(register_seed),
            'native_tx_count_register': hex(h.get32(0x1fb50904))}


def host_publish(h, staggered, malformed=False):
    assert h.get32(SRAM+0x4708) == h.get32(STATE+20) == 0
    assert h.run(0x8400f836, [0x8400f836]) == 0x8400f836
    if not staggered and not malformed:
        for address, value in HOST_FIXTURE.items():
            if address != 0x1ec0d0b0:
                h.put32(address, value)
        for _ in range(8):
            assert h.run(0x8400f836, [0x8400f836]) == 0x8400f836
        assert h.get32(SRAM+0x4708) == h.get32(STATE+20) == 0
    values = ({address: 0 for address in HOST_REGISTERS} if malformed else HOST_FIXTURE.copy())
    if malformed:
        values[0x1ec0d0b0] = values[0x1ec0d190] = 1
    for address, value in values.items():
        if not staggered or address != 0x1ec0d190:
            h.put32(address, value)
    if staggered:
        assert h.run(0x8400f836, [0x8400f880]) == 0x8400f880
        assert h.get32(SRAM+0x4708) == h.get32(STATE+20) == 0
        assert h.run(0x8400f880, [0x8400f880]) == 0x8400f880
        h.put32(0x1ec0d190, values[0x1ec0d190])
    assert h.run(h.cpu.reg_read(r.UC_RISCV_REG_PC), [0x84000188]) == 0x84000188
    assert h.get32(SRAM+0x4708) == 1 and h.get32(STATE+20) == 0
    for source, dest, alias in ((0xa0, 0x4718, True), (0xb0, 0x4714, True),
                                (0xa4, 0x4728, False), (0xb4, 0x4724, False),
                                (0x180, 0x4710, True), (0x190, 0x470c, True)):
        value = values[0x1ec0d000+source]
        assert h.get32(SRAM+dest) == (value & 0x3fffffff | 0x40000000 if alias else value)
    assert h.returns == [{'pc': '0x8400e37a', 'a0': 0}, {'pc': '0x8400e37e', 'a0': 0}]
    window = h.rv.symbols['npu_emulation_idle_irq_window']
    assert h.run(0x84000188, [window]) == window
    assert h.get32(STATE+20) == 1
    assert [h.get32(STATE+20+index*4) for index in range(1, 8)] == [0]*7
    assert [h.get32(STATE+52+index*4) for index in range(13)] == [0]*13
    assert h.get32(STATE+8) == 0 and h.get32(ADM) == 1
    assert h.get32(BOOT+8) == 6 and h.get32(BOOT+16) == 0x1e
    return values


def probe(path, delayed=False, malformed=False, exhausted=False, register_seed=0):
    h = to_wifi(path, delayed, exhausted=exhausted, register_seed=register_seed)
    memory = footprints(h, exhausted, register_seed)
    values = host_publish(h, staggered=delayed, malformed=malformed)
    assert hashlib.sha256(h.cpu.mem_read(L2, L2_BYTES)).hexdigest() == memory['l2_sha256']
    assert set(h.stub_counts) <= {'0x840048f4', '0x84004212', '0x84004130',
                                  '0x8400452a', 'mhartid-csr'}
    assert all(row['return_pc'] not in ('0x8400e3ba', '0x8400e3e4', '0x8400e3f2')
               for row in h.logs)
    groups = {}
    for event in h.mmio:
        key = (event['kind'], event['pc'], event['address'], event['value'], event['model'])
        row = groups.setdefault(key, {**event, 'count': 0})
        row['count'] += 1
    # Entry hooks precede breakpoint handling; paused instructions have not run.
    paused = {event['step'] for event in h.events if event['kind'] == 'paused'}
    entries = Counter(event['pc'] for event in h.events
                      if event['kind'] == 'entry' and event['step'] not in paused)
    assert entries['0x8400d1d4'] == entries['0x84009fc8'] == 1
    return {'core0_native_return': True, 'coordinator_idle_ack': 1,
            'other_workers_parked': 0, 'physical_domains_drained': 0,
            'delayed_api23_and_host_rx': delayed, 'malformed_host_registers': malformed,
            'missing_tx1_wait_checked': not delayed and not malformed,
            'exhausted_skb_fixture': exhausted, 'footprints': memory,
            'host_fixture': {hex(k): hex(v) for k, v in values.items()},
            'l2_clear_bytes': h.l2_writes*4, 'l2_clear_pcs': sorted(h.l2_clear_pcs),
            'l2_later_writes': h.l2_later,
            'native_entry_counts': dict(entries),
            'allocations': h.allocations, 'log_counts': [
                {'format': key[0], 'return_pc': key[1], 'count': count}
                for key, count in Counter((row['format'], row['return_pc']) for row in h.logs).items()],
            'returns': h.returns,
            'stub_counts': h.stub_counts,
            'stub_returns': {k: sorted(v) for k, v in h.stub_returns.items()},
            'mmio_grouped': list(groups.values()), 'patches': h.patches}


def fail_closed_models(path):
    rows = []
    for address, expected in ((L2_CONTROL, 'write 0x1ec0f200/4 at 0x8400d1c0'),
                               (0x1fb50a04, 'read 0x1fb50a04/4 at 0x8400989e'),
                               (0x1ec0d0b0, 'read 0x1ec0d0b0/4 at 0x8400f836')):
        try:
            h = to_wifi(path, missing=address)
            h.run(0x8400f836, [0x8400f836])
        except UnmodeledAccess as error:
            assert str(error) == expected, str(error)
            rows.append({'missing_register': hex(address), 'error': str(error)})
        else:
            raise AssertionError('unmodeled register silently accepted')
    return rows


def source_spans():
    text = GHIDRA.read_text()
    rows = []
    for address in (0x84004c16, 0x84005200, 0x8400981c, 0x84009fc8,
                    0x8400a364, 0x8400a3bc, 0x8400b928, 0x8400baae,
                    0x8400d1a0, 0x8400d1d4, 0x8400e330, 0x8400f832, 0x8400fab2):
        match = re.search(r'^FUNCTION [^\n]* @ ram:' + f'{address:08x}' +
                          r'\n.*?(?=^FUNCTION |\Z)', text, re.M | re.S)
        assert match and 'decompiled=true' in match.group(), hex(address)
        rows.append({'address': hex(address), 'first_line': text[:match.start()].count('\n')+1,
                     'last_line': text[:match.end()].count('\n'),
                     'normalized_text_sha256': hashlib.sha256(match.group().encode()).hexdigest()})
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    path = build_platform(startup=True, bootstrap_source=SOURCE,
                          gdma_source=ROOT / 'firmware/npu/gdma.c')
    first = path.read_bytes()
    assert build_platform(startup=True, bootstrap_source=SOURCE,
                          gdma_source=ROOT / 'firmware/npu/gdma.c').read_bytes() == first
    result = {'passed': True, 'firmware_sha256': CODE_SHA, 'data_sha256': DATA_SHA,
              'elf_sha256': sha(path), 'dtb_sha256': sha(DTB), 'ghidra_sha256': sha(GHIDRA),
              'test_sha256': sha(Path(__file__)), 'cases': []}
    for delayed, malformed, exhausted, seed in ((False, False, False, 0), (True, False, False, 0),
                                               (False, True, False, 0), (False, False, True, 0),
                                               (False, False, False, 0xffffffff)):
        result['cases'].append(probe(path, delayed, malformed, exhausted, seed))
        print(json.dumps({'core0_native_return': True, 'delayed': delayed,
                          'malformed_host_inputs': malformed, 'exhausted_skb': exhausted,
                          'register_seed': seed}), flush=True)
    result['model_controls'] = fail_closed_models(path)
    result['source_spans'] = source_spans()
    old = json.loads((ROOT / 'research/checkpoints/2026-09-06-npu-bootstrap/bootstrap-native.json').read_text())
    assert result['elf_sha256'] == old['elf_sha256']
    result['source_sha256'] = {name: sha(ROOT / name) for name in old['source_sha256']}
    assert result['source_sha256'] == old['source_sha256']
    result['source_sha256']['tests/npu/test_native_wifi_boot.py'] = sha(Path(__file__))
    for name in ('test_barrier_protocol.py', 'test_barrier_core5.py', 'test_firmware_memory_layout.py',
                 'test_firmware_mailbox_dispatch.py', 'test_firmware_stop_counterexample.py',
                 'test_firmware_stop_irqs.py', 'test_boot_txbuf_extent.py',
                 'emulation_layout.py', 'preflight_dtb_cases.py', 'test_txbuf_dtbs.py'):
        result['source_sha256']['tests/npu/'+name] = sha(ROOT / 'tests/npu' / name)
    result['scope'] = ('Original core0 reset through native Wi-Fi return and candidate idle acknowledgement. '
                       'Explicit synthetic host publication, serialized IRQ frames and named storage-only MMIO; '
                       'no physical L2/cache/DMA/IRQ, all-worker boot, real ring validity, mt76 attach or packet proof.')
    (OUT / 'native-wifi-probe.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'passed': True, 'cases': len(result['cases'])}))


if __name__ == '__main__':
    main()
