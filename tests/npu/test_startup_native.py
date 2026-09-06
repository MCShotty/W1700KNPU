#!/usr/bin/env python3
"""Execute reset gates without externally calling barrier/admission init."""
import hashlib
import json
from pathlib import Path
import random
import struct
import sys

sys.dont_write_bytecode = True
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r

from test_admission_native import build_platform
from test_barrier_core5 import jump
from test_barrier_protocol import Rv32
from test_firmware_memory_layout import NativeMemory, BSS_START, BSS_END, STACK_TOPS
from test_firmware_stop_counterexample import ROOT, INPUT, CODE_SHA, DATA_SHA, END, HART_ID
from emulation_layout import CODE, SRAM, SRAM_BYTES, STATE

OUT = ROOT / 'research/checkpoints/2026-09-06-npu-startup'
BUILD = ROOT / '.local/npu-startup'
STARTUP = STATE + 0x180
MAGIC = 0x3153504e
REGS = [getattr(r, 'UC_RISCV_REG_X' + str(i)) for i in range(32)]
SITES = {CODE + 0x74: ('npu_emulation_before_bss', 'b7c2c01e'),
         CODE + 0xf0: ('npu_emulation_reset_gate', '97000000')}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def cold_data():
    original = (INPUT / 'en7581_MT7996_npu_data.bin').read_bytes()
    assert sha(original) == DATA_SHA
    image = bytearray(STARTUP + 64 - SRAM)
    assert len(original) <= 0xc10 and len(image) <= SRAM_BYTES
    image[:len(original)] = original
    struct.pack_into('<16I', image, STARTUP-SRAM, MAGIC, 1, 64, *([0] * 13))
    return bytes(image)


class Startup(NativeMemory):
    def __init__(self, path, omit=None, template=True):
        self.hart = 0
        super().__init__()
        self.image = cold_data()
        self.cpu.mem_write(SRAM + 3084, b'\xa5' * (SRAM_BYTES - 3084))
        if template:
            self.cpu.mem_write(SRAM, self.image)
        self.rv = Rv32(path, self.cpu)
        assert self.rv.symbols['npu_emulation_startup_state'] == STARTUP
        assert STARTUP + 64 <= SRAM + SRAM_BYTES
        self.hits = []
        self.init_calls = []
        self.bss_writes = 0
        self.pause_init = False
        self.stop = None
        self.skip_stop = None
        self.patches = []
        for address, (name, expected) in SITES.items():
            assert bytes(self.cpu.mem_read(address, 4)).hex() == expected
            if address != omit:
                target = self.rv.symbols[name]
                replacement = jump(address, target)
                self.cpu.mem_write(address, replacement)
                self.patches.append({'site': hex(address), 'target': hex(target),
                                     'before': expected, 'after': replacement.hex()})
        for offset in (0x24, 0x2e, 0x38, 0x42, 0x4c, 0x56, 0x60, 0x6a):
            self.cpu.hook_add(UC_HOOK_CODE, self.hart_csr, begin=CODE+offset, end=CODE+offset)
        for name in ['npu_emulation_precheck_hart_csr', 'npu_emulation_startup_hart_csr']:
            address = self.rv.symbols[name]
            self.cpu.hook_add(UC_HOOK_CODE, self.hart_csr, begin=address, end=address)
        self.stops = {CODE + 0xf4: 'native-continuation'}
        for name in ['npu_emulation_startup_wait', 'npu_emulation_startup_fault',
                     'npu_emulation_startup_precheck_fault']:
            self.stops[self.rv.symbols[name]] = name
        for address in self.stops:
            self.cpu.hook_add(UC_HOOK_CODE, self.stop_hook, begin=address, end=address)
        for name in ['npu_barrier_init', 'npu_emulation_admission_init']:
            address = self.rv.symbols[name]
            self.cpu.hook_add(UC_HOOK_CODE, self.initialize_hook, begin=address, end=address)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, self.bss_write, begin=BSS_START, end=BSS_END-1)

    def skip(self, cpu, address, size, data):
        cpu.reg_write(r.UC_RISCV_REG_A0, self.hart if address == HART_ID else 0)
        cpu.reg_write(r.UC_RISCV_REG_PC, cpu.reg_read(r.UC_RISCV_REG_RA))

    def hart_csr(self, cpu, address, size, data):
        word = self.get32(address)
        assert word >> 20 == 0xf14 and word & 0x707f == 0x2073
        destination = (word >> 7) & 31
        cpu.reg_write(REGS[destination], self.hart)
        cpu.reg_write(r.UC_RISCV_REG_PC, address+4)

    def stop_hook(self, cpu, address, size, data):
        if self.skip_stop == address:
            self.skip_stop = None
            return
        self.stop = self.stops[address]
        self.hits.append((self.hart, self.stop))
        cpu.emu_stop()

    def initialize_hook(self, cpu, address, size, data):
        self.init_calls.append((self.hart, hex(address)))
        if self.pause_init and address == self.rv.symbols['npu_barrier_init']:
            self.stop = 'initializing'
            cpu.emu_stop()

    def bss_write(self, cpu, access, address, size, value, data):
        self.bss_writes += 1

    def execute(self, hart, context=None, seed=123):
        self.hart = hart
        if context is None:
            rng = random.Random(seed)
            for reg in REGS[1:]:
                self.cpu.reg_write(reg, rng.getrandbits(32))
            self.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 8)
            start = CODE
        else:
            self.cpu.context_restore(context)
            start = self.cpu.reg_read(r.UC_RISCV_REG_PC)
        self.stop = None
        self.skip_stop = start if context is not None and start in self.stops else None
        self.cpu.emu_start(start, END, count=100000, timeout=2000000)
        assert self.stop, hex(self.cpu.reg_read(r.UC_RISCV_REG_PC))
        assert not self.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
        return self.stop, self.cpu.context_save()

    def verify_initialized(self):
        assert self.get32(STARTUP+12) == 2 and self.get32(STARTUP+16) == 0
        assert struct.unpack('<26I', self.cpu.mem_read(STATE, 104)) == (1, *([0]*25))
        assert struct.unpack('<11I', self.cpu.mem_read(STATE+0x100, 44)) == (1, *([0]*10))
        assert bytes(self.cpu.mem_read(STATE+0x140, 24)) == bytes(24)
        assert all(hart == 0 for hart, address in self.init_calls)


def schedules(path):
    results = []
    for seed in range(32):
        h = Startup(path)
        order = list(range(8))
        random.Random(seed).shuffle(order)
        waiting = {}
        for hart in order:
            stop, context = h.execute(hart, seed=seed)
            if 0 not in order[:order.index(hart)+1]:
                assert stop == 'npu_emulation_startup_wait'
                assert not h.init_calls and h.get32(STATE) == 0
                waiting[hart] = context
            else:
                assert stop == 'native-continuation', (hart, order, stop)
                assert h.cpu.reg_read(r.UC_RISCV_REG_SP) == STACK_TOPS[hart]
                assert h.cpu.reg_read(r.UC_RISCV_REG_GP) == SRAM+0x13a8
        for hart, context in waiting.items():
            stop, _ = h.execute(hart, context)
            assert stop == 'native-continuation'
        h.verify_initialized()
        assert len(h.init_calls) == 2
        assert list(struct.unpack('<8I', h.cpu.mem_read(STARTUP+20, 32))) == [1]*8
        assert bytes(h.cpu.mem_read(STARTUP+64, 32)) == b'\xa5'*32
        results.append(order)
    return results


def register_equivalence(path):
    checks = 0
    for hart in range(8):
        for seed in range(4):
            candidate = Startup(path)
            if hart:
                candidate.execute(0)
            assert candidate.execute(hart, seed=seed)[0] == 'native-continuation'
            actual = [candidate.cpu.reg_read(reg) for reg in REGS]
            original = NativeMemory()
            original.set_hart(hart)
            rng = random.Random(seed)
            for reg in REGS[1:]:
                original.cpu.reg_write(reg, rng.getrandbits(32))
            original.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 8)
            original.cpu.emu_start(CODE, CODE+0xf4, count=30000, timeout=1000000)
            assert actual == [original.cpu.reg_read(reg) for reg in REGS], (hart, seed)
            assert candidate.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) == original.cpu.reg_read(r.UC_RISCV_REG_MSTATUS)
            checks += 1
    return checks


def rejection_cases(path):
    results = []
    for word, value in [(0, 0), (1, 2), (2, 60), (3, 1), (3, 2), (3, 3),
                        (4, 1), (5, 1), (13, 1), (14, 1), (15, 1)]:
        h = Startup(path)
        h.cpu.mem_write(BSS_START, b'\x96'*(BSS_END-BSS_START))
        h.put32(STARTUP+4*word, value)
        stop, _ = h.execute(0)
        assert stop == 'npu_emulation_startup_precheck_fault'
        assert not h.init_calls and not h.bss_writes
        assert bytes(h.cpu.mem_read(BSS_START, BSS_END-BSS_START)) == b'\x96'*(BSS_END-BSS_START)
        results.append(f'bad-template-word-{word}-{value}')
    for hart in range(8):
        h = Startup(path)
        h.cpu.mem_write(BSS_START, b'\x96'*(BSS_END-BSS_START))
        h.put32(0x1ec0c140, 0xffffffff)
        stop, _ = h.execute(hart)
        assert stop in ('npu_emulation_startup_precheck_fault', 'npu_emulation_startup_fault')
        assert not h.init_calls and not h.bss_writes
        results.append(f'warm-hart-{hart}')
    for hart in range(8):
        h = Startup(path)
        h.execute(0)
        if hart:
            h.execute(hart)
        prior = bytes(h.cpu.mem_read(STATE, 104))
        h.cpu.mem_write(BSS_START, b'\x96'*(BSS_END-BSS_START))
        h.bss_writes = 0
        count = len(h.init_calls)
        stop, _ = h.execute(hart)
        assert stop in ('npu_emulation_startup_precheck_fault', 'npu_emulation_startup_fault')
        assert len(h.init_calls) == count and not h.bss_writes
        expected = bytearray(prior)
        struct.pack_into('<I', expected, 16, 1)
        assert bytes(h.cpu.mem_read(STATE, 104)) == expected
        results.append(f'duplicate-hart-{hart}')
    for hart in (8, 0xffffffff):
        h = Startup(path)
        assert h.execute(hart)[0] == 'npu_emulation_startup_precheck_fault'
        assert not h.init_calls and not h.bss_writes
        results.append(f'invalid-hart-{hart}')
    h = Startup(path, template=False)
    assert h.execute(0)[0] == 'npu_emulation_startup_precheck_fault'
    assert not h.init_calls and not h.bss_writes
    results.append('unextended-original-data')
    return results


def interrupted_initialization(path):
    h = Startup(path)
    stop, worker = h.execute(1)
    assert stop == 'npu_emulation_startup_wait'
    h.pause_init = True
    stop, coordinator = h.execute(0)
    assert stop == 'initializing' and h.get32(STARTUP+12) == 1
    h.pause_init = False
    assert h.execute(1)[0] == 'npu_emulation_startup_fault'
    assert h.execute(0, coordinator)[0] == 'npu_emulation_startup_fault'
    assert h.get32(STARTUP+12) == 3 and h.get32(STARTUP+16) == h.get32(STATE+16) == 1
    assert h.execute(1, worker)[0] == 'npu_emulation_startup_fault'


def negative_controls(path):
    controls = {}
    h = Startup(path, omit=CODE+0xf0)
    assert h.execute(1)[0] == 'native-continuation' and not h.init_calls and h.get32(STATE) == 0
    controls['missing-entry-gate'] = 'worker reaches native startup before initialization'
    h = Startup(path, omit=CODE+0x74)
    h.cpu.mem_write(BSS_START, b'\x96'*(BSS_END-BSS_START))
    h.put32(STARTUP, 0)
    assert h.execute(0)[0] == 'npu_emulation_startup_fault' and h.bss_writes
    controls['missing-pre-bss-gate'] = 'invalid template rejected only after native BSS destruction'
    return controls


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    path = build_platform(startup=True, gdma_source=ROOT / 'firmware/npu/gdma.c')
    first = path.read_bytes()
    assert build_platform(startup=True, gdma_source=ROOT / 'firmware/npu/gdma.c').read_bytes() == first
    image = cold_data()
    (BUILD / 'cold-sram-test-input.bin').write_bytes(image)
    orders = schedules(path)
    registers = register_equivalence(path)
    rejected = rejection_cases(path)
    interrupted_initialization(path)
    controls = negative_controls(path)
    result = {'passed': True, 'firmware_sha256': CODE_SHA, 'original_data_sha256': DATA_SHA,
              'extension_elf': str(path.relative_to(ROOT)), 'elf_sha256': sha(first),
              'cold_data_bytes': len(image), 'cold_data_sha256': sha(image),
              'template_preserves_original_prefix': image[:3084] == (INPUT / 'en7581_MT7996_npu_data.bin').read_bytes(),
              'reset_orders': orders, 'register_cases': registers,
              'rejection_cases': rejected, 'fault_during_initialization_retained': True,
              'negative_controls': controls, 'patches': Startup(path).patches,
              'scope': 'Original reset instructions plus candidate adapters with eight serialized saved contexts and modeled MHARTID. Loader upload/cache/previous-user containment and subsequent native startup/IRQ/bootstrap are not hardware-proved. No flashable firmware is emitted.'}
    (OUT / 'startup-native-tests.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['passed', 'elf_sha256', 'cold_data_bytes', 'register_cases']}))
    print(f'reset orders={len(orders)} rejected entries={len(rejected)} missing-hook controls={len(controls)}')


if __name__ == '__main__':
    main()
