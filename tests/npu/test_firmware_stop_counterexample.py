#!/usr/bin/env python3
"""RV32 instruction counterexample: STOP/GET zero does not stop indirect part 2."""
import hashlib
import json
from pathlib import Path
import struct

from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.riscv_const import UC_RISCV_REG_PC, UC_RISCV_REG_SP, UC_RISCV_REG_GP, UC_RISCV_REG_RA
from unicorn.riscv_const import UC_RISCV_REG_A0, UC_RISCV_REG_A1, UC_RISCV_REG_A2
from unicorn.riscv_const import UC_RISCV_REG_A3, UC_RISCV_REG_A4, UC_RISCV_REG_A5
import unicorn

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / '.local/npu-quiescence/firmware'
OUT = ROOT / 'research/checkpoints/2026-09-05-npu-reset'
CODE_SHA = 'e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643'
DATA_SHA = '61a75afb052feed2ceb2f3023e16f50317c05c78f9c8e564bf01924ce39c7ec1'
CODE, SRAM, RING, STATS = 0x84000000, 0x3e900000, 0x3e910000, 0x3e912000
WORKER, LOOP, PRINTF, ENQUEUE = 0x8400cb0e, 0x8400cbbe, 0x840048f4, 0x8400ac30
SET, GET, END = 0x8400e084, 0x8400d7ca, 0x84200000
DISPATCH, HART_ID, CORE5_WRAPPER = 0x84000104, 0x84004212, 0x8400e7f8
CORE_ROOTS = (0x84000164, 0x84000190, 0x840001a0, 0x840009bc,
              0x84000a82, 0x84000aa6, 0x84000aca, 0x84000aee)
ARGUMENTS = (UC_RISCV_REG_A0, UC_RISCV_REG_A1, UC_RISCV_REG_A2,
             UC_RISCV_REG_A3, UC_RISCV_REG_A4, UC_RISCV_REG_A5)


class Harness:
    def __init__(self, descriptor, hart=5, pause_on_root=False):
        code = (INPUT / 'en7581_MT7996_npu_rv32.bin').read_bytes()
        data = (INPUT / 'en7581_MT7996_npu_data.bin').read_bytes()
        assert hashlib.sha256(code).hexdigest() == CODE_SHA
        assert hashlib.sha256(data).hexdigest() == DATA_SHA
        self.cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        self.cpu.mem_map(CODE, 0x201000)
        self.cpu.mem_write(CODE, code)
        self.cpu.mem_map(SRAM, 0x40000)
        self.cpu.mem_write(SRAM, data)
        self.cpu.reg_write(UC_RISCV_REG_GP, 0x3e9013a8)
        self.cpu.reg_write(UC_RISCV_REG_SP, 0x84035e00)
        self.cpu.reg_write(UC_RISCV_REG_RA, END)
        self.put32(SRAM + 0x46f0, 1)
        self.put32(SRAM + 0x46ec, 1)
        self.put32(SRAM + 0x1f3c, RING)
        self.put32(SRAM + 0x1f04, STATS)
        self.put16(SRAM + 0x46e2, 0)
        self.put32(RING, descriptor)
        self.put32(RING + 4, 0x1234)
        self.put32(RING + 8, 64 << 3)
        self.put32(RING + 16, 0xfe)
        self.phase = 'bootstrap'
        self.hart = hart
        self.pause_on_root = pause_on_root
        self.entries = []
        self.root = None
        self.paused = False
        self.enqueue = None
        self.writes = []
        self.cpu.hook_add(UC_HOOK_CODE, self.code_hook, begin=PRINTF, end=PRINTF)
        self.cpu.hook_add(UC_HOOK_CODE, self.code_hook, begin=LOOP, end=LOOP)
        self.cpu.hook_add(UC_HOOK_CODE, self.code_hook, begin=ENQUEUE, end=ENQUEUE)
        for address in (DISPATCH, HART_ID, CORE5_WRAPPER, WORKER, *CORE_ROOTS):
            self.cpu.hook_add(UC_HOOK_CODE, self.code_hook, begin=address, end=address)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, self.write_hook, begin=SRAM + 0x46e2, end=SRAM + 0x46e3)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, self.write_hook, begin=RING, end=RING + 3)

    def put32(self, address, value):
        self.cpu.mem_write(address, struct.pack('<I', value))

    def put16(self, address, value):
        self.cpu.mem_write(address, struct.pack('<H', value))

    def get32(self, address):
        return struct.unpack('<I', self.cpu.mem_read(address, 4))[0]

    def get16(self, address):
        return struct.unpack('<H', self.cpu.mem_read(address, 2))[0]

    def code_hook(self, cpu, address, size, _data):
        if address in (DISPATCH, CORE5_WRAPPER, WORKER, *CORE_ROOTS):
            self.entries.append(hex(address))
        if address in CORE_ROOTS:
            self.root = address
            if self.pause_on_root:
                cpu.emu_stop()
        elif address == HART_ID:
            cpu.reg_write(UC_RISCV_REG_A0, self.hart)
            cpu.reg_write(UC_RISCV_REG_PC, cpu.reg_read(UC_RISCV_REG_RA))
        elif address == PRINTF:
            cpu.reg_write(UC_RISCV_REG_A0, 0)
            cpu.reg_write(UC_RISCV_REG_PC, cpu.reg_read(UC_RISCV_REG_RA))
        elif address == LOOP and self.phase == 'bootstrap':
            self.paused = True
            cpu.emu_stop()
        elif address == ENQUEUE:
            self.enqueue = [cpu.reg_read(register) for register in ARGUMENTS]
            cpu.emu_stop()

    def write_hook(self, cpu, access, address, size, value, _data):
        self.writes.append({'phase': self.phase, 'pc': hex(cpu.reg_read(UC_RISCV_REG_PC)),
                            'address': hex(address), 'size': size, 'value': value})

    def call(self, address, selector):
        self.cpu.reg_write(UC_RISCV_REG_SP, 0x84021e00)
        self.cpu.reg_write(UC_RISCV_REG_RA, END)
        for register in ARGUMENTS:
            self.cpu.reg_write(register, 0)
        self.cpu.reg_write(UC_RISCV_REG_A0, selector)
        self.cpu.emu_start(address, END, timeout=1000000, count=20000)
        assert self.cpu.reg_read(UC_RISCV_REG_PC) == END, 'Mailbox callback did not return'
        return self.cpu.reg_read(UC_RISCV_REG_A0)

    def stop_and_get(self):
        self.phase = 'stop'
        self.call(SET, 4)
        assert self.get32(SRAM + 0x46ec) == 0 and self.get32(SRAM + 0x46f0) == 0
        assert bytes(self.cpu.mem_read(SRAM + 0x46f5, 1)) == b'\x01'
        # Model the other three acknowledged workers as idle; these values are
        # produced by their verified idle branches, not by the indirect worker.
        self.put32(SRAM + 0x46e8, 0)
        self.cpu.mem_write(SRAM + 0x46f6, b'\x01\x01')
        self.phase = 'get'
        result = self.call(GET, 3)
        assert result == 0, 'Original GET did not report idle'
        return result


def started_worker(descriptor):
    harness = Harness(descriptor)
    harness.cpu.emu_start(DISPATCH, END, timeout=3000000, count=2000000)
    assert harness.paused and harness.cpu.reg_read(UC_RISCV_REG_PC) == LOOP
    assert harness.entries == [hex(value) for value in (DISPATCH, CORE_ROOTS[5], CORE5_WRAPPER, WORKER)]
    assert harness.get16(SRAM + 0x46e2) == 0 and not harness.writes
    worker_context = harness.cpu.context_save()
    get_result = harness.stop_and_get()
    harness.cpu.context_restore(worker_context)
    harness.phase = 'after-stop-get-zero'
    harness.cpu.emu_start(LOOP, END, timeout=1000000, count=20000)
    return harness, get_result


def main():
    roots = {}
    for hart, root in enumerate(CORE_ROOTS):
        harness = Harness(0xfe, hart=hart, pause_on_root=True)
        harness.cpu.emu_start(DISPATCH, END, timeout=1000000, count=1000)
        assert harness.root == root and harness.cpu.reg_read(UC_RISCV_REG_PC) == root
        roots[str(hart)] = hex(root)

    witness, result = started_worker(4)
    assert witness.get16(SRAM + 0x46e2) == 1
    assert witness.get32(RING) == 0xfe
    assert witness.enqueue == [0x1234, 64, 0, 0, 1, 2]
    assert len(witness.writes) == 2 and all(write['phase'] == 'after-stop-get-zero' for write in witness.writes)

    empty, _ = started_worker(0xfe)
    assert empty.get16(SRAM + 0x46e2) == 0 and not empty.writes and empty.enqueue is None

    never_started = Harness(4)
    never_started.stop_and_get()
    never_started.cpu.reg_write(UC_RISCV_REG_SP, 0x84035e00)
    never_started.cpu.reg_write(UC_RISCV_REG_RA, END)
    never_started.phase = 'stopped-before-startup'
    never_started.cpu.emu_start(DISPATCH, END, timeout=1000000, count=20000)
    assert not never_started.paused and not never_started.writes and never_started.enqueue is None
    assert never_started.get16(SRAM + 0x46e2) == 0 and never_started.get32(RING) == 4
    pc = never_started.cpu.reg_read(UC_RISCV_REG_PC)
    assert 0x8400cb3e <= pc <= 0x8400cb44, hex(pc)

    report = {'passed': True, 'unicorn': unicorn.__version__, 'firmware_sha256': CODE_SHA,
              'data_sha256': DATA_SHA, 'get_result': result, 'native_post_stop_writes': witness.writes,
              'native_core_dispatch': roots, 'core5_entry_trace': witness.entries,
              'enqueue_call_arguments': witness.enqueue,
              'controls': {'empty_ring_no_mutation': True, 'stop_before_startup_blocks_worker': True},
              'scope': 'Unmodified RV32 instructions for the post-common-init hart dispatcher, core5 wrappers, SET4, GET3 and indirect worker; serialized hart contexts share modeled SRAM. The hart-ID getter and printf are stubbed, other worker idle values are modeled, enqueue execution is stopped at entry. This demonstrates reachability and a protocol counterexample, not physical DMA activity or cache/bus containment.'}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'firmware-stop-counterexample.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
