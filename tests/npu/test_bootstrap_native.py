#!/usr/bin/env python3
"""Fresh reset, installed strict IRQ8, and original MT7996 bootstrap wrappers."""
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ
from unicorn import riscv_const as r

from test_boot_irq_installation import Installation, IRQ8, WIFI_SLOT, ISR, TX
from test_startup_native import cold_data, SITES, STARTUP
from test_admission_native import build_platform, HOOKS
from test_admission_protocol import packet as control_packet
from test_barrier_protocol import Rv32
from test_barrier_core5 import jump
from test_firmware_stop_counterexample import ROOT, CODE_SHA, DATA_SHA, END
from test_firmware_memory_layout import STACK_TOPS
from test_firmware_mailbox_dispatch import MBOX, PAYLOAD, DISPATCH
from emulation_layout import CODE, SRAM, STATE
from preflight_dtb_cases import npu_properties, properties

OUT = ROOT / 'research/checkpoints/2026-09-06-npu-bootstrap'
BUILD = ROOT / '.local/npu-bootstrap'
BOOT, PLAN, ADM = STATE+0x200, STATE+0x300, STATE+0x100
REQUEST = 0x82000000
DTB = ROOT / '.local/npu-bootmem/candidate/an7581-w1700k-ubi.dtb'
SOURCE = ROOT / 'firmware/npu/bootstrap.c'
CALLBACKS = {18: 0x8400ff88, 32: 0x8400fb84, 8: 0x8400febe,
             23: 0x8400fb2e, 7: 0x8400feac, 12: 0x8400ff0c}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plan():
    assert sha(DTB) == 'dfe83e60933b9905712ebd1dc35f182cf943acbbd6f03902031be3856cf70344'
    info = npu_properties(properties(DTB))
    assert info['firmware_names'] == ['airoha/en7581_MT7996_npu_rv32.bin',
                                      'airoha/en7581_MT7996_npu_data.bin']
    resources = info['resources']
    result = [(resources[name]['start'], resources[name]['size'])
              for name in ('binary', 'tx-bufid', 'pkt', 'tx-pkt', 'ba')]
    return [*result, (REQUEST, 256)]


def bootstrap_data():
    image = bytearray(PLAN+48-SRAM)
    original = cold_data()
    image[:len(original)] = original
    struct.pack_into('<12I', image, PLAN-SRAM, *[word for row in plan() for word in row])
    return bytes(image)


class Bootstrap(Installation):
    def __init__(self, path, omit=None):
        super().__init__()
        self.cpu.mem_write(SRAM, bootstrap_data())
        self.rv = Rv32(path, self.cpu)
        assert self.rv.symbols['npu_emulation_bootstrap_state'] == BOOT
        assert self.rv.symbols['npu_emulation_bootstrap_plan'] == PLAN
        self.patches = []
        sites = {**SITES, **HOOKS, 0x84003f2e: ('npu_emulation_mailbox_register', 'eff06fb2')}
        for site, (name, expected) in sites.items():
            assert bytes(self.cpu.mem_read(site, 4)).hex() == expected
            if site != omit:
                replacement = jump(site, self.rv.symbols[name])
                self.cpu.mem_write(site, replacement)
                self.patches.append({'site': hex(site), 'name': name, 'before': expected,
                                     'after': replacement.hex(), 'target': hex(self.rv.symbols[name])})
        self.payload_reads = []
        self.callback_entries = []
        self.mutate_api = None
        self.fail_api = None
        self.strict_callback_witness = omit != 0x84003f2e
        self.cpu.hook_add(UC_HOOK_MEM_READ, self.request_read, begin=PAYLOAD, end=PAYLOAD+255)
        self.cpu.hook_add(UC_HOOK_CODE, self.native_callback)

    def request_read(self, cpu, access, address, size, value, data):
        self.payload_reads.append({'offset': address-PAYLOAD, 'size': size})

    def native_callback(self, cpu, pc, size, data):
        if pc not in (*CALLBACKS.values(), 0x840101a6):
            return
        api = 10 if pc == 0x840101a6 else next(k for k, value in CALLBACKS.items() if value == pc)
        self.callback_entries.append(hex(pc))
        if not self.strict_callback_witness:
            return
        assert cpu.reg_read(r.UC_RISCV_REG_A0) == BOOT+20
        assert self.get32(BOOT+12) == self.get32(ADM+4) == 1
        if api == self.mutate_api:
            self.cpu.mem_write(PAYLOAD, struct.pack('<3I', 0x11, 32, 0xffffffff))
        if api == self.fail_api:
            cpu.reg_write(r.UC_RISCV_REG_A0, 0)
            cpu.reg_write(r.UC_RISCV_REG_PC, cpu.reg_read(r.UC_RISCV_REG_RA))

    def message(self, words, length=None, flags=1, address=REQUEST):
        context = self.cpu.context_save()
        encoded = struct.pack('<'+'I'*len(words), *words)
        assert len(encoded) <= 256
        self.cpu.mem_write(PAYLOAD, encoded + bytes(256-len(encoded)))
        self.put32(MBOX+0x30, address)
        self.put32(MBOX+0x34, len(encoded) if length is None else length)
        self.put32(MBOX+0x3c, flags)
        self.payload_reads.clear()
        self.callback_entries.clear()
        self.cpu.reg_write(r.UC_RISCV_REG_SP, STACK_TOPS[0]-0x1000)
        self.cpu.reg_write(r.UC_RISCV_REG_RA, END)
        self.cpu.reg_write(r.UC_RISCV_REG_A0, 8)
        self.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 0)
        assert self.run(DISPATCH, []) == END
        result = {'flags': self.get32(MBOX+0x3c),
                  'words': list(struct.unpack('<'+'I'*len(words), self.cpu.mem_read(PAYLOAD, len(encoded)))),
                  'callbacks': self.callback_entries.copy(), 'reads': self.payload_reads.copy()}
        self.cpu.context_restore(context)
        return result

    def boot_snapshot(self):
        return bytes(self.cpu.mem_read(BOOT, 80))


def sequence():
    regions = plan()
    return [[0x11, 18, 0], *[[0x10, api, regions[index][0]]
                             for index, api in enumerate((32, 8, 23, 7), 1)], [0x10, 12, 0]]


def integrated(path):
    h = Bootstrap(path)
    # First IRQ8 registration has returned, before native callback-array clear.
    assert h.reset(0x84003f32) == 0x84003f32
    assert h.get32(IRQ8) == h.rv.symbols['npu_emulation_mailbox']
    assert h.get32(0x0c002000) & (1 << 9)
    assert h.get32(WIFI_SLOT) == 0
    assert h.get32(STARTUP+12) == 2 and h.get32(BOOT) == 0x31505342
    assert h.get32(MBOX+0x140) == 0xffffffff
    early = h.message([0x30, 10, 0])
    assert early['flags'] == 7 and early['words'] == [0x30, 10, 0x457]
    assert early['callbacks'] == ['0x840101a6']
    assert h.get32(BOOT+8) == 0
    assert h.run(0x84003f32, [0x8400420a]) == 0x8400420a
    assert h.get32(IRQ8) == h.rv.symbols['npu_emulation_mailbox']
    assert h.get32(WIFI_SLOT) == 0x84003a9c and h.clear_count == 0
    replies = []
    for index, words in enumerate(sequence()):
        reply = h.message(words)
        assert reply['flags'] == 7 and reply['words'] == words
        assert reply['callbacks'] == [hex(CALLBACKS[words[1]])]
        assert h.get32(BOOT+8) == index+1 and h.get32(BOOT+12) == h.get32(ADM+4) == 0
        replies.append(reply)
        if index == 1:
            assert h.get32(SRAM+0x469c) == TX
            assert h.get32(SRAM+0x396c) == h.get32(SRAM+0x2ab8) == h.get32(SRAM+0x2ce4) == 0
            assert h.run(h.cpu.reg_read(r.UC_RISCV_REG_PC), [0x8400e330]) == 0x8400e330
            assert h.clear_count == 0x7000 and bytes(h.cpu.mem_read(TX, 0xe000)) == bytes(0xe000)
    assert h.get32(BOOT+16) == 0x1e
    assert h.get32(SRAM+0x396c) == plan()[2][0]
    assert h.get32(SRAM+0x2ab8) == plan()[3][0]
    assert h.get32(SRAM+0x2ce4) == plan()[4][0]
    assert h.message([0x30, 10, 0])['words'][2] == 0x457
    status = h.message(control_packet(0))
    assert status['flags'] == 7 and status['words'][10] == 7
    assert status['words'][11:16] == [0]*5
    assert h.get32(STATE+8) == 0 and h.get32(ADM) == 1
    return {'early_version': early, 'provider_replies': replies,
            'control_capabilities': status['words'][10], 'retained_mask': h.get32(BOOT+16),
            'cleared_bytes': h.clear_count*2, 'core0_boundary': '0x8400e330', 'patches': h.patches}


def rejected(path):
    h = Bootstrap(path)
    h.reset()
    cases = [([0x10, 32, plan()[1][0]], {}), ([0x10, 18, 0], {}),
             ([0x11, 18, 1], {}), ([0x30, 10, 1], {}), ([0x31, 10, 0], {}),
             ([0x12, 24, 0], {}), ([0x10, 14, 0], {})]
    for length in (0, 4, 8, 11, 13, 16, 63, 65, 256, 257, 0xffffffff):
        cases.append(([0x30, 10, 0], {'length': length}))
    for flags in (0, 3, 0x21, 0x801, 0x6001, 0x6021, 0x8001, 0x10001, 0xffffffff):
        cases.append(([0x30, 10, 0], {'flags': flags}))
    for address in (0, REQUEST+4, REQUEST-4, REQUEST | 0x40000000,
                    REQUEST & 0x3fffffff, 0x84000000, 0x90c00000, 0xffffffff):
        cases.append(([0x30, 10, 0], {'address': address}))
    rows = []
    for words, kwargs in cases:
        before = h.boot_snapshot()
        reply = h.message(words, **kwargs)
        assert reply['flags'] & 0x1c == 0 and not reply['callbacks'], (words, kwargs, reply)
        assert h.boot_snapshot() == before and h.get32(SRAM+0x469c) == 0
        if kwargs:
            assert not reply['reads'], kwargs
        rows.append({'words': words, **kwargs, 'payload_read_count': len(reply['reads'])})
    for words in sequence():
        assert h.message(words)['flags'] == 7
        before = h.boot_snapshot()
        assert h.message(words)['flags'] == 3 and h.boot_snapshot() == before
    for words in ([0x10, 14, 0], [0x10, 1, 1536], [0x12, 24, 0], [0x30, 4, 0]):
        assert h.message(words)['flags'] == 3
    return {'invalid_requests': rows, 'duplicate_commands_rejected': 6,
            'post_reservation_mt76_commands_still_closed': 4}


def controls(path):
    h = Bootstrap(path, omit=0x84003f2e)
    h.reset()
    assert h.get32(IRQ8) == ISR
    reply = h.message([0x10, 32, 0x90c00001])
    assert reply['flags'] == 7 and h.get32(SRAM+0x469c) == TX+1
    assert h.get32(BOOT+8) == 0
    rows = [{'name': 'missing-registration-detour', 'unaligned_out_of_order_address_accepted': True}]
    for defect in ('missing-plan', 'short-txcheck', 'request-overlap'):
        h = Bootstrap(path)
        if defect == 'missing-plan':
            h.cpu.mem_write(PLAN, bytes(48))
        elif defect == 'short-txcheck':
            h.put32(PLAN+12, 0x6800)
        else:
            h.put32(PLAN+40, plan()[0][0])
        stop = h.rv.symbols['npu_emulation_startup_fault']
        assert h.reset(stop) == stop
        assert h.get32(STARTUP+12) == 3 and h.get32(BOOT+4) == h.get32(STATE+16) == 1
        assert not h.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
        assert h.get32(MBOX+0x140) == 0 and h.get32(IRQ8) == 0
        assert not any(event['kind'] == 'mmio-write' for event in h.mmio)
        assert h.clear_count == 0
        rows.append({'name': defect, 'rejected_before_native_irq_setup': True})
    for failure in ('callback-table', 'callback-return'):
        h = Bootstrap(path)
        h.reset()
        assert h.message(sequence()[0])['flags'] == 7
        if failure == 'callback-table':
            h.put32(SRAM+0x178+32*4, 0)
        else:
            h.fail_api = 32
        assert h.message(sequence()[1])['flags'] == 3
        assert h.get32(BOOT+4) == h.get32(STATE+16) == h.get32(ADM+8) == 1
        assert h.get32(BOOT+12) == h.get32(ADM+4) == 1 and h.get32(BOOT+16) == 2
        assert h.get32(BOOT+8) == 1 and h.get32(SRAM+0x469c) == 0
        status = h.message(control_packet(3))
        assert status['flags'] == 7 and status['words'][9] == 6
        assert status['words'][11:16] == [0]*5
        assert h.message([0x30, 10, 0])['flags'] == 3
        rows.append({'name': failure, 'retained_mask': 2, 'active': 1, 'status_available': True})
    h = Bootstrap(path)
    h.reset()
    assert h.message(sequence()[0])['flags'] == 7
    h.mutate_api = 32
    assert h.message(sequence()[1])['flags'] == 7
    assert h.get32(SRAM+0x469c) == TX and h.get32(BOOT+28) == plan()[1][0]
    rows.append({'name': 'host-payload-mutation-after-validation', 'private_snapshot_used': True})
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    path = build_platform(startup=True, bootstrap_source=SOURCE,
                          gdma_source=ROOT / 'firmware/npu/gdma.c')
    first = path.read_bytes()
    assert build_platform(startup=True, bootstrap_source=SOURCE,
                          gdma_source=ROOT / 'firmware/npu/gdma.c').read_bytes() == first
    positive = integrated(path)
    negative = rejected(path)
    checks = controls(path)
    (BUILD / 'bootstrap-cold-sram-test-input.bin').write_bytes(bootstrap_data())
    result = {'passed': True, 'firmware_sha256': CODE_SHA, 'data_sha256': DATA_SHA,
              'elf': str(path.relative_to(ROOT)), 'elf_sha256': sha(path),
              'dtb_sha256': sha(DTB), 'plan': plan(), 'cold_data_bytes': len(bootstrap_data()),
              'cold_data_sha256': hashlib.sha256(bootstrap_data()).hexdigest(),
              'integrated': positive, 'rejected': negative, 'controls': checks,
              'scope': 'Original reset/common initialization and TXcheck consumer with candidate cold/IRQ/bootstrap adapters. Stops before native Wi-Fi main initialization at 0x8400e330. Serialized IRQ frames and explicit MMIO models; no physical boot, containment, cache, IRQ delivery, full mt76 attach or packet-footprint proof.'}
    sources = [*sorted((ROOT / 'firmware/npu').glob('*.[ch]')),
               *[ROOT / 'tests/npu' / name for name in (
                   'test_bootstrap_native.py', 'test_boot_irq_installation.py',
                   'test_startup_native.py', 'test_admission_native.py',
                   'admission-platform-emulation.c', 'admission-emulation.S',
                   'startup-platform-emulation.c', 'startup-emulation.S',
                   'bootstrap-platform-emulation.c', 'bootstrap-emulation.S',
                   'gdma-platform-emulation.c', 'barrier-core5-emulation.S',
                   'barrier-workers-emulation.S', 'barrier-workers-emulation.ld')]]
    result['source_sha256'] = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    (OUT / 'bootstrap-native.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'passed': True, 'elf_sha256': result['elf_sha256'],
                      'invalid_requests': len(negative['invalid_requests']), 'controls': len(checks)}))


if __name__ == '__main__':
    main()
