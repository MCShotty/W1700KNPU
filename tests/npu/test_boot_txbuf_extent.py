#!/usr/bin/env python3
"""Native boot clear after the real TX-check-address mailbox callback."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r

from test_firmware_mailbox_dispatch import Mailbox, MBOX
from test_firmware_memory_layout import fdt
from test_firmware_stop_counterexample import ROOT, CODE_SHA, DATA_SHA, SRAM, END
from test_barrier_protocol import digest

OUT = ROOT / 'research/checkpoints/2026-09-06-npu-bootmem'
OLD_DTB = ROOT / '.local/npu-barrier/w1700k-r1.dtb'
TX_SIZE = 0xe000


class Boot(Mailbox):
    def __init__(self, physical, reserved_bytes):
        super().__init__()
        self.cpu.mem_map(0x1ec03000, 0x1000)
        self.put32(0x1ec03048, 0x10000)
        self.base = physical & 0x3fffffff | 0x40000000
        assert self.base % 0x1000 == 0
        self.cpu.mem_map(self.base, 0x30000)
        self.cpu.mem_write(self.base, b'\xa5' * 0x30000)
        self.reserved_bytes = reserved_bytes
        self.clear_writes = self.outside = 0
        self.first = self.last = self.first_outside_pc = None
        self.waiting = False
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, self.write_range, begin=self.base, end=self.base + 0x2ffff)
        self.cpu.hook_add(UC_HOOK_CODE, self.wait_boundary, begin=0x8400420a, end=0x8400420a)

    def invoke(self, address, args, halt=None):
        # Model IRQ function invocation below the separately saved main frame.
        self.cpu.reg_write(r.UC_RISCV_REG_SP, 0x84020e00)
        self.cpu.reg_write(r.UC_RISCV_REG_RA, END)
        for index, value in enumerate(args):
            self.cpu.reg_write(getattr(r, 'UC_RISCV_REG_A' + str(index)), value)
        self.cpu.emu_start(address, END, count=30000, timeout=1000000)
        assert self.cpu.reg_read(r.UC_RISCV_REG_PC) == (halt or END)

    def wait_boundary(self, cpu, address, size, data):
        self.waiting = True
        cpu.emu_stop()

    def write_range(self, cpu, access, address, size, value, data):
        assert size == 2 and value == 0
        assert address == self.base + self.clear_writes * 2
        self.clear_writes += 1
        self.first = address if self.first is None else self.first
        self.last = address + size
        if address + size > self.base + self.reserved_bytes:
            self.outside += size
            if self.first_outside_pc is None:
                self.first_outside_pc = cpu.reg_read(r.UC_RISCV_REG_PC)

    def initialize(self):
        self.cpu.reg_write(r.UC_RISCV_REG_SP, 0x84021e00)
        self.cpu.reg_write(r.UC_RISCV_REG_RA, END)
        self.cpu.emu_start(0x84005296, END, count=2000000, timeout=3000000)
        assert self.cpu.reg_read(r.UC_RISCV_REG_PC) == END
        self.cpu.reg_write(r.UC_RISCV_REG_RA, END)
        self.cpu.emu_start(0x84004e76, END, count=2000000, timeout=3000000)
        assert self.waiting and self.cpu.reg_read(r.UC_RISCV_REG_PC) == 0x8400420a
        assert self.clear_writes == 0 and self.get32(SRAM + 0x469c) == 0


def region(dtb, name):
    node = '/reserved-memory/' + name
    cells = fdt(dtb, node, 'reg', 'x')
    assert len(cells) == 4 and cells[0] == cells[2] == 0
    return cells[1], cells[3]


def reproduce(dtb, ba_node):
    base, size = region(dtb, 'npu-txbufid@90c00000')
    ba, ba_size = region(dtb, ba_node)
    h = Boot(base, size)
    h.initialize()
    main = h.cpu.context_save()
    reply = h.message([0x10, 32, base])
    assert reply['flags'] == 7 and h.get32(SRAM + 0x469c) == h.base
    ba_reply = h.message([0x10, 7, ba])
    assert ba_reply['flags'] == 7 and h.get32(SRAM + 0x2ce4) == ba
    h.cpu.context_restore(main)
    # Complete the paused environmental delay; the subsequent boot code is native.
    h.cpu.reg_write(r.UC_RISCV_REG_PC, h.cpu.reg_read(r.UC_RISCV_REG_RA))
    h.cpu.emu_start(h.cpu.reg_read(r.UC_RISCV_REG_PC), END, count=2000000, timeout=3000000)
    assert h.cpu.reg_read(r.UC_RISCV_REG_PC) == END
    assert h.clear_writes == 0x7000 and h.first == h.base and h.last == h.base + TX_SIZE
    assert bytes(h.cpu.mem_read(h.base, TX_SIZE)) == bytes(TX_SIZE)
    assert bytes(h.cpu.mem_read(h.base + TX_SIZE, 32)) == b'\xa5' * 32
    overlap = max(0, min(base + TX_SIZE, ba + ba_size) - max(base, ba))
    assert h.outside == max(0, TX_SIZE - size)
    if overlap:
        assert bytes(h.cpu.mem_read(h.base + ba - base, overlap)) == bytes(overlap)
    else:
        assert bytes(h.cpu.mem_read(h.base + ba - base, 32)) == b'\xa5' * 32
    return {'dtb_sha256': digest(dtb.read_bytes()), 'tx_base': hex(base), 'reserved_bytes': size,
            'ba_base': hex(ba), 'native_cleared_bytes': TX_SIZE, 'out_of_reservation_bytes': h.outside,
            'ba_overlap_bytes': overlap, 'first_outside_pc': hex(h.first_outside_pc) if h.first_outside_pc else None,
            'waited_for_host_before_clear': True, 'mailbox_set_api': 32, 'mailbox_flags': reply['flags'],
            'relocated_ba_address_accepted_by_native_api7': True,
            'scope': 'Original allocator/boot/mailbox instructions; mutex owner, IRQ invocation and one delay completion modeled. No live NPU memory access.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate-dtb', type=Path)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    old = reproduce(OLD_DTB, 'npu-ba@90c06800')
    assert old['reserved_bytes'] == 0x6800 and old['ba_overlap_bytes'] == 0x7800
    result = {'passed': True, 'firmware_sha256': CODE_SHA, 'data_sha256': DATA_SHA, 'retained_r1': old}
    if args.candidate_dtb:
        candidate = reproduce(args.candidate_dtb, 'npu-ba@90c0e000')
        assert candidate['reserved_bytes'] == TX_SIZE and candidate['ba_overlap_bytes'] == 0
        result['candidate'] = candidate
        controls = {}
        for name, node, cells in (
            ('short_table', 'npu-txbufid@90c00000', ('0', '90c00000', '0', '6800')),
            ('unmoved_ba', 'npu-ba@90c0e000', ('0', '90c06800', '0', '200000'))):
            mutant = args.candidate_dtb.with_name(name + '.dtb')
            shutil.copyfile(args.candidate_dtb, mutant)
            subprocess.run(['fdtput', '-t', 'x', str(mutant), '/reserved-memory/' + node, 'reg', *cells], check=True)
            bad = reproduce(mutant, 'npu-ba@90c0e000')
            assert bad['out_of_reservation_bytes'] or bad['ba_overlap_bytes'], 'partial fix accepted'
            controls[name] = {'rejected': True, 'out_of_reservation_bytes': bad['out_of_reservation_bytes'],
                              'ba_overlap_bytes': bad['ba_overlap_bytes']}
        result['partial_fix_controls'] = controls
    (OUT / 'native-txbuf-extent.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
