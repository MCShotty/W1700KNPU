#!/usr/bin/env python3
"""Checked cold allocation callers and faulted core0 control-mailbox service."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
from elftools.elf.elffile import ELFFile
from unicorn import riscv_const as r

import test_allocator_protocol as protocol
from test_allocator_reset import build as build_reset, install as install_reset, COLD_TYPES
from test_barrier_core5 import jump
from test_barrier_protocol import Rv32
from test_bootstrap_native import sequence, ADM, BOOT
from test_admission_protocol import packet
from test_bridge_startup import Bridge, build_guard, input_bindings
from test_firmware_memory_layout import NativeMemory, table, STACK_TOPS
from test_multihart_cold_boot import AllHarts, ELF, ELF_SHA
from test_native_wifi_boot import footprints, host_publish, L2, L2_BYTES
from emulation_layout import SRAM, SRAM_BYTES, HEAP, HEAP_BYTES, STATE

ROOT = protocol.ROOT
OUT = ROOT / 'research/checkpoints/2026-09-09-npu-cold-allocator'
BUILD = ROOT / '.local/npu-cold-allocator'
SOURCE = ROOT/'tests/npu/allocator-startup-emulation.c'
ASM, LINKER = SOURCE.with_suffix('.S'), SOURCE.with_suffix('.ld')
GETTER = 0x84005200
NATIVE_STATE = SRAM+0x1bcc
IRQ8 = SRAM+0x1870


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build(source=SOURCE, tag='startup', assembly=ASM, extra_flags=(), linker=LINKER):
    assert sha(ELF.read_bytes()) == ELF_SHA
    BUILD.mkdir(parents=True, exist_ok=True)
    path = BUILD/(tag+'.elf')
    lld = shutil.which('ld.lld') or str(ROOT/'.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld')
    command = [shutil.which('clang'), '--target=riscv32', '-march=rv32imac_zicsr',
               '-mabi=ilp32', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-fno-builtin',
               '-nostdlib', '-fno-stack-protector', f'--ld-path={lld}',
               '-I', str(protocol.SOURCE.parent), str(protocol.SOURCE), str(source), str(assembly),
               *extra_flags, '-Wl,-T,'+str(linker), '-Wl,--no-relax', '-Wl,--just-symbols='+str(ELF),
               '-o', str(path)]
    done = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stdout+done.stderr
    return path, command


def install(h, path, enabled=True):
    rv = Rv32(path, h.cpu)
    before = bytes(h.cpu.mem_read(GETTER, 4)).hex()
    assert before == '13070008' == h.code[0x5200:0x5204].hex()
    target = rv.symbols['npu_emulation_allocator_startup_dispatch']
    replacement = jump(GETTER, target)
    if enabled:
        h.cpu.mem_write(GETTER, replacement)
    h.cpu.ctl_remove_cache(GETTER, GETTER+0x84)
    h.cpu.ctl_remove_cache(0x8404e000, 0x84050000)
    return rv, dict(site=hex(GETTER), before=before, after=replacement.hex(), target=hex(target),
                    installed=enabled)


def state(h):
    return bytes(h.cpu.mem_read(NATIVE_STATE, protocol.STATE_BYTES))


class StartupCore(AllHarts):
    def __init__(self, path, reset_path, mode=None, target=0x8a, enabled=True, enforce=True):
        self.allocation_mode, self.allocation_target = mode, target
        self.allocation_triggered = False
        self.allocation_snapshot = None
        self.allocation_results = []
        self.allocation_pending = None
        self.allocation_entries = []
        self.original_lock_results = []
        self.allocation_enforce = enforce
        self.allocation_dispatches = 0
        super().__init__(ELF, plic='banked')
        self.reset_rv, self.reset_patches = install_reset(self, reset_path)
        self.allocator_rv, self.allocator_patch = install(self, path, enabled)

    def code_hook(self, cpu, pc, size, data):
        if pc == 0x84005010 and self.allocation_triggered:
            self.original_lock_results.append(cpu.reg_read(r.UC_RISCV_REG_A0))
        if pc == GETTER:
            kind = cpu.reg_read(r.UC_RISCV_REG_A0)
            if kind < 0x100:
                self.allocation_entries.append(dict(type=kind, caller=hex(cpu.reg_read(r.UC_RISCV_REG_RA)),
                                                    mstatus=cpu.reg_read(r.UC_RISCV_REG_MSTATUS),
                                                    mie=cpu.reg_read(r.UC_RISCV_REG_MIE), irq8=hex(self.get32(IRQ8)),
                                                    active=self.get32(ADM+4), boot_magic=hex(self.get32(BOOT))))
            if self.allocation_triggered and self.allocation_mode == 'denied':
                self.put32(0x1ec03048, 0x10000)
            if self.allocation_mode and not self.allocation_triggered and kind == self.allocation_target:
                self.inject(kind)
        if hasattr(self, 'allocator_rv'):
            if pc == self.allocator_rv.symbols['npu_emulation_allocator_startup_dispatch']:
                self.allocation_dispatches += 1
            if pc == self.allocator_rv.symbols['npu_allocator_allocate']:
                self.allocation_pending = cpu.reg_read(r.UC_RISCV_REG_RA)
            if pc == self.allocation_pending:
                self.allocation_results.append((cpu.reg_read(r.UC_RISCV_REG_A0), cpu.reg_read(r.UC_RISCV_REG_A1)))
                self.allocation_pending = None
        if self.allocation_snapshot and self.allocation_enforce and pc == self.allocation_snapshot['caller']:
            raise AssertionError('failed-startup-returned-to-native-caller')
        super().code_hook(cpu, pc, size, data)

    def inject(self, kind):
        self.allocation_triggered = True
        mode = self.allocation_mode
        if mode == 'denied':
            self.put32(0x1ec03048, 0x10100)
        elif mode == 'corrupt':
            self.put32(NATIVE_STATE+8, 101)
        elif mode == 'capacity':
            assert kind == 1
            injected = bytearray(protocol.state_for(protocol.definitions(), [0x89, 0x8a, 0x12, 0x1d, 0x84, 0x85]))
            injected[4:8] = injected[12:16] = bytes(4)
            self.cpu.mem_write(NATIVE_STATE, bytes(injected))
        elif mode == 'bad-lock-id':
            self.put32(NATIVE_STATE, 19)
        elif mode == 'wrong-type':
            self.cpu.reg_write(r.UC_RISCV_REG_A0, 0x80)
        elif mode == 'prior-fault':
            self.put32(STATE+16, 1)
        elif mode == 'active-context':
            self.put32(ADM+4, 1)
        elif mode == 'mie-off':
            self.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, self.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & ~8)
        elif mode == 'external-irq-off':
            self.cpu.reg_write(r.UC_RISCV_REG_MIE, 0)
        elif mode == 'bad-irq8':
            self.put32(IRQ8, 0)
        elif mode == 'masked-mailbox':
            value = self.plic_banks[0][0x0c002000] & ~(1 << 9)
            self.plic_banks[0][0x0c002000] = value
            self.put32(0x0c002000, value)
        else:
            assert mode == 'fault-at-release'
        self.allocation_snapshot = dict(kind=kind, caller=self.cpu.reg_read(r.UC_RISCV_REG_RA),
                                        metadata=state(self), sram=bytes(self.cpu.mem_read(SRAM, SRAM_BYTES)),
                                        heap=bytes(self.cpu.mem_read(HEAP, HEAP_BYTES)),
                                        l2=bytes(self.cpu.mem_read(L2, L2_BYTES)), mmio=len(self.mmio),
                                        results=len(self.allocation_results))

    def write_hook(self, cpu, access, address, size, value, data):
        if (self.allocation_mode == 'fault-at-release' and self.allocation_snapshot and
                address == 0x1ec03248):
            self.put32(STATE+16, 1)
        super().write_hook(cpu, access, address, size, value, data)


def advance(h):
    window = h.rv.symbols['npu_emulation_idle_irq_window']
    hold = h.allocator_rv.symbols['npu_emulation_allocator_startup_hold']
    faults = [window, hold]
    h.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 8)
    stopped = h.run(0x84000000, [0x8400420a, *faults])
    if stopped in faults:
        return stopped
    for words in sequence():
        assert h.message(words)['flags'] == 7
    stopped = h.run(stopped, [0x8400d1d4, *faults])
    if stopped in faults:
        return stopped
    assert bytes(h.cpu.mem_read(L2, L2_BYTES)) == bytes(L2_BYTES)
    h.l2_clear_active = False
    stopped = h.run(stopped, [0x8400f836, *faults])
    if stopped in faults:
        return stopped
    h.cold_footprint = footprints(h)
    host_publish(h, staggered=False)
    h.contexts[0] = h.cpu.context_save()
    return window


def fault_case(path, reset_path, mode, target=0x8a, enabled=True):
    h = StartupCore(path, reset_path, mode, target, enabled)
    stopped = advance(h)
    snap = h.allocation_snapshot
    assert snap is not None, 'fault injection not reached'
    service = mode not in ('active-context', 'mie-off', 'external-irq-off', 'bad-irq8', 'masked-mailbox')
    expected_stop = h.rv.symbols['npu_emulation_idle_irq_window'] if service else h.allocator_rv.symbols['npu_emulation_allocator_startup_hold']
    assert stopped == expected_stop, 'fault service boundary'
    assert bool(h.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8) == service, 'fault mailbox interrupts unavailable'
    no_core = mode in ('wrong-type', 'prior-fault', 'active-context', 'mie-off',
                       'external-irq-off', 'bad-irq8', 'masked-mailbox')
    expected_result, metadata, counts = protocol.oracle(protocol.Case(
        'startup-failure', protocol.definitions(), target, int(target < 0x81), snap['metadata'],
        deny=int(mode in ('denied', 'bad-lock-id'))))
    if no_core:
        expected_result, metadata, counts = None, snap['metadata'], (0, 0)
    assert h.allocation_results[snap['results']:] == ([] if no_core else [expected_result]), 'unexpected allocation result'
    expected_sram = bytearray(snap['sram'])
    expected_sram[NATIVE_STATE-SRAM:NATIVE_STATE-SRAM+protocol.STATE_BYTES] = metadata
    for address in (ADM, ADM+8, STATE+16):
        struct.pack_into('<I', expected_sram, address-SRAM, 1)
    assert bytes(h.cpu.mem_read(SRAM, SRAM_BYTES)) == bytes(expected_sram), 'fault SRAM footprint'
    assert bytes(h.cpu.mem_read(HEAP, HEAP_BYTES)) == snap['heap'], 'failed caller wrote heap'
    assert bytes(h.cpu.mem_read(L2, L2_BYTES)) == snap['l2'], 'failed caller wrote L2'
    mmio = h.mmio[snap['mmio']:]
    actual_counts = tuple(sum(row['kind'] == 'mmio-write' and row['address'] == address for row in mmio)
                          for address in ('0x1ec031c8', '0x1ec03248'))
    if mode == 'bad-lock-id':
        counts = (0, 0)
    assert actual_counts == counts
    before = bytes(h.cpu.mem_read(SRAM, SRAM_BYTES))
    replies = []
    if service:
        for operation in (0, 3, 2, 3):
            reply = h.message(packet(operation, 1, (0x10203040, 0x50607080)))
            assert reply['flags'] == 7
            assert reply['words'][9:] == [0 if operation == 0 else 6, 7, 0, 0, 0, 0, 0]
            assert not reply['callbacks']
            replies.append(reply['words'])
            assert h.run(stopped, [stopped]) == stopped
        rejected = h.message([0x30, 10, 0])
        assert rejected['flags'] == 3 and not rejected['callbacks']
        assert bytes(h.cpu.mem_read(SRAM, SRAM_BYTES)) == before
    else:
        assert h.run(stopped, [stopped]) == stopped
    assert bytes(h.cpu.mem_read(HEAP, HEAP_BYTES)) == snap['heap'], 'fault service changed heap'
    assert bytes(h.cpu.mem_read(L2, L2_BYTES)) == snap['l2'], 'fault service changed L2'
    sp = h.cpu.reg_read(r.UC_RISCV_REG_SP)
    assert STACK_TOPS[0]-0x4000 <= sp < STACK_TOPS[0]
    assert state(h) == metadata and h.get32(STATE+20) == 0
    return dict(mode=mode, target=hex(target), caller=hex(snap['caller']), service_available=service,
                result=expected_result, lock_operations=actual_counts, control_replies=replies,
                whole_sram_compared=SRAM_BYTES, whole_heap_unchanged=HEAP_BYTES,
                whole_l2_unchanged=L2_BYTES, metadata_unchanged=metadata == snap['metadata'],
                before_state_sha256=sha(snap['metadata']), after_state_sha256=sha(metadata),
                retained_active=h.get32(ADM+4), core0_parked=0, stack=hex(sp),
                original_allocation_entries=h.allocation_entries, startup_patch=h.allocator_patch)


def success(path, reset_path):
    h = StartupCore(path, reset_path)
    assert advance(h) == h.rv.symbols['npu_emulation_idle_irq_window']
    assert len(h.allocation_results) == 7 and all(row[0] == protocol.OK for row in h.allocation_results), 'missing checked cold allocation'
    expected = bytearray(protocol.state_for(protocol.definitions(), COLD_TYPES))
    expected[4:8] = expected[12:16] = bytes(4)
    assert state(h) == bytes(expected)
    assert h.get32(STATE+20) == 1 and h.get32(STATE+16) == h.get32(ADM+8) == 0
    assert [row['type'] for row in h.allocation_entries] == COLD_TYPES
    assert all(row['mstatus'] & 8 and row['mie'] & 0x800 and not row['active'] and
               row['irq8'] == hex(h.rv.symbols['npu_emulation_mailbox']) for row in h.allocation_entries)
    return dict(checked_allocations=h.allocation_results, metadata_sha256=sha(state(h)),
                native_entries=h.allocation_entries, fixed_l2_footprint=h.cold_footprint,
                getter_dispatches=h.allocation_dispatches, core0_parked=1)


def baseline(path, reset_path):
    h = StartupCore(path, reset_path, 'denied', 0x8a, enabled=False, enforce=False)
    assert advance(h) == h.rv.symbols['npu_emulation_idle_irq_window']
    assert h.allocation_triggered and h.get32(STATE+16) == 0 and h.get32(STATE+20) == 1
    assert h.get32(SRAM+0x4708) == 1 and not h.allocation_results
    assert h.original_lock_results[0] == 0xffffffff
    return dict(denied_type='0x8a', original_initialization_returned=True,
                ignored_acquire_return=hex(h.original_lock_results[0]),
                core0_parked=1, fault=0, metadata_sha256=sha(state(h)))


def fallback(path):
    rows = []
    h = NativeMemory()
    rv, patch = install(h, path)
    for group, address in (('dynamic-high', 0x8401b224), ('dynamic-low', 0x8401cfc8),
                           ('fixed-high', 0x8401b20c), ('fixed-low', 0x8401cf70)):
        for row in table(h.code, address):
            seed = protocol.empty()
            h.cpu.mem_write(NATIVE_STATE, seed)
            value = h.call(GETTER, row['type'])
            if group.startswith('fixed'):
                assert value == row['value'] and state(h) == seed
            else:
                expected, metadata, _ = protocol.oracle(protocol.Case(group, protocol.definitions(),
                                                                       row['type'], int(row['type'] < 0x81), seed))
                assert expected == (protocol.OK, value) and state(h) == metadata, 'unrelated getter changed'
            rows.append(dict(group=group, type=row['type'], address=hex(value)))
    return rows


class StartupBridge(Bridge):
    def __init__(self, path, reset_path, omit_start=True):
        self.allocator_path, self.reset_path = path, reset_path
        self.startup_results, self.startup_pending = [], None
        super().__init__(omit_start)
        guards, _ = build_guard()
        self.install_guards(guards)

    def coordinator(self):
        self.reset_rv, self.reset_patches = install_reset(self, self.reset_path)
        self.allocator_rv, self.allocator_patch = install(self, self.allocator_path)
        return super().coordinator()

    def code_hook(self, cpu, pc, size, data):
        if hasattr(self, 'allocator_rv'):
            if pc == self.allocator_rv.symbols['npu_allocator_allocate']:
                self.startup_pending = cpu.reg_read(r.UC_RISCV_REG_RA)
            if pc == self.startup_pending:
                self.startup_results.append((cpu.reg_read(r.UC_RISCV_REG_A0), cpu.reg_read(r.UC_RISCV_REG_A1)))
                self.startup_pending = None
        super().code_hook(cpu, pc, size, data)


def bridge_cases(path, reset_path):
    h = StartupBridge(path, reset_path)
    assert len(h.startup_results) == 7 and all(row[0] == 0 for row in h.startup_results)
    rows = []
    for mode in ('normal', 'denied', 'corrupt', 'prior-fault', 'already-parked'):
        h.prepare(bad_owner=mode == 'denied')
        h.startup_results, h.startup_pending = [], None
        if mode == 'corrupt':
            h.put32(NATIVE_STATE+20, 0)
        if mode == 'prior-fault':
            h.put32(STATE+16, 1)
        if mode == 'already-parked':
            h.put32(STATE+20+7*4, 1)
        before = bytes(h.cpu.mem_read(SRAM, SRAM_BYTES))
        before_state = state(h)
        heap = bytes(h.cpu.mem_read(HEAP, HEAP_BYTES))
        expected, metadata, counts = protocol.oracle(protocol.Case(mode, protocol.definitions(),
                                                                 0x81, 0, before_state, deny=int(mode == 'denied')))
        no_core = mode in ('prior-fault', 'already-parked')
        if no_core:
            expected, metadata, counts = None, before_state, (0, 0)
        hold = h.allocator_rv.symbols['npu_emulation_allocator_startup_hold']
        stopped = h.run(0x84000b24, [0x84000b36, hold])
        held = mode != 'normal'
        assert stopped == (hold if held else 0x84000b36)
        assert h.startup_results == ([] if no_core else [expected])
        assert state(h) == metadata and bytes(h.cpu.mem_read(HEAP, HEAP_BYTES)) == heap
        actual_counts = tuple(sum(row['kind'] == 'mmio-write' and row['address'] == address for row in h.mmio)
                              for address in ('0x1ec031c8', '0x1ec03e48'))
        assert actual_counts == counts
        expected_sram = bytearray(before)
        expected_sram[NATIVE_STATE-SRAM:NATIVE_STATE-SRAM+protocol.STATE_BYTES] = metadata
        if held:
            assert not h.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
            struct.pack_into('<I', expected_sram, STATE-SRAM+16, 1)
            assert not any(0x1ec12000 <= int(row['address'], 16) < 0x1ec13000 for row in h.mmio)
            assert h.run(hold, [hold]) == hold
        else:
            struct.pack_into('<I', expected_sram, 0x184c, expected[1])
            expected_sram[0xc54:0xc90] = bytes(60)
            poll = h.rv.symbols['npu_barrier_poll']
            assert h.run(0x84000b36, [poll]) == poll
            assert h.run(poll, [poll]) == poll
            struct.pack_into('<I', expected_sram, STATE-SRAM+20+7*4, 1)
        assert bytes(h.cpu.mem_read(SRAM, SRAM_BYTES)) == bytes(expected_sram)
        status = h.control(3)
        mask = 0x81 if mode in ('normal', 'already-parked') else 1
        assert status[9:] == [6 if held else 0, 7, mask, 0, 0, 0, 0]
        assert h.get32(ADM+8) == 0, 'hart7 changed coordinator-owned admission fault'
        rows.append(dict(mode=mode, result=expected, held=held, status=status, lock_operations=actual_counts,
                         whole_sram_compared=SRAM_BYTES, whole_heap_unchanged=HEAP_BYTES,
                         metadata_unchanged=metadata == before_state,
                         existing_parked_slot_retained=mode == 'already-parked'))
    return rows


def retained_gate(path, reset_path):
    h = StartupBridge(path, reset_path, omit_start=False)
    h.prepare()
    h.startup_results, h.startup_pending = [], None
    poll = h.rv.symbols['npu_barrier_poll']
    assert h.run(0x84000b24, [poll]) == poll
    assert h.run(poll, [poll]) == poll
    h.contexts[7] = h.cpu.context_save()
    for hart in range(1, 7):
        h.worker(hart)
    for hart in range(8):
        h.repoll(hart)
    status = h.control(3)
    assert status[9:] == [0, 7, 255, 0, 0, 0, 0]
    assert not h.startup_results and not h.guard_entries
    return dict(installed_detours=len(h.patches)+len(h.installed_guards)+len(h.reset_patches)+1,
                all_parked=[1]*8, initial_gate_retained=True, status=status,
                no_hart7_bridge_or_allocator_execution=True, plic='serialized banked storage model')


def mutations(path, reset_path):
    rows = []
    source = SOURCE.read_text()
    irq_restore = '''            __asm__ volatile ("csrw mstatus, %0" :: "r"(status) : "memory");
            npu_emulation_idle();'''
    for name, old, new, mode, expected in (
        ('ignore-allocation-failure', 'if (result.status != NPU_ALLOCATOR_OK || load(&BARRIER->fault))',
         'if (0)', 'denied', 'failed-startup-returned-to-native-caller'),
        ('omit-coordinator-fault', 'npu_admission_fail(ADMISSION, BARRIER);',
         'npu_barrier_fail(BARRIER);', 'denied', 'fault SRAM footprint'),
        ('lose-control-interrupts', irq_restore, '            (void)status;\n            npu_emulation_idle();',
         'denied', 'fault mailbox interrupts unavailable'),
        ('drop-control-service', 'if (service) {', 'if (service && 0) {',
         'denied', 'fault service boundary'),
        ('allocate-after-prior-fault', 'load(&BARRIER->fault) || load(&BARRIER->request) != 1',
         'load(&BARRIER->request) != 1', 'prior-fault', 'unexpected allocation result'),
    ):
        assert source.count(old) == 1
        mutant = BUILD/(name+'.c')
        mutant.write_text(source.replace(old, new, 1))
        candidate, _ = build(mutant, name)
        try:
            fault_case(candidate, reset_path, mode)
        except AssertionError as error:
            assert str(error) == expected, (name, str(error))
            rows.append(dict(name=name, detected=True, assertion=str(error), elf_sha256=sha(candidate.read_bytes())))
        else:
            raise AssertionError('surviving startup mutant: '+name)
    try:
        fault_case(path, reset_path, 'denied', enabled=False)
    except AssertionError as error:
        assert str(error) == 'failed-startup-returned-to-native-caller'
        rows.append(dict(name='missing-getter-hook', detected=True, assertion=str(error)))
    else:
        raise AssertionError('missing getter hook not detected')
    text = ASM.read_text()
    for name, old, new, check, expected in (
        ('changed-native-fallback', 'li a4, 0x80', 'li a4, 0x81', fallback, 'unrelated getter changed'),
        ('missing-control-word-caller', 'caller 0x84005a34', 'caller 0x84005a36',
         lambda candidate: success(candidate, reset_path), 'missing checked cold allocation'),
    ):
        assert text.count(old) == 1
        mutant = BUILD/(name+'.S')
        mutant.write_text(text.replace(old, new, 1))
        candidate, _ = build(tag=name, assembly=mutant)
        try:
            check(candidate)
        except AssertionError as error:
            assert str(error) == expected, (name, str(error))
            rows.append(dict(name=name, detected=True, assertion=str(error), elf_sha256=sha(candidate.read_bytes())))
        else:
            raise AssertionError('surviving startup dispatch mutant: '+name)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output', type=Path, default=OUT/'allocator-startup.json')
    args = parser.parse_args()
    inputs = input_bindings()
    inputs.update({str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in
                   (SOURCE, ASM, LINKER, Path(__file__), ROOT/'tests/npu/allocator-reset-emulation.ld')})
    path, command = build()
    with path.open('rb') as stream:
        elf = ELFFile(stream)
        sections = [(s.name, s['sh_addr'], s['sh_size']) for s in elf.iter_sections()
                    if s['sh_flags'] & 2 and s['sh_size']]
    assert [name for name, _, _ in sections] == ['.text', '.rodata']
    assert sections[0][1] == 0x8404e000 and sections[0][2] > 0
    assert sections[1][1] == (sum(sections[0][1:])+3) & ~3
    assert sections[1][2] == 32 and sum(sections[1][1:]) <= 0x84050000
    reset_path, _ = build_reset()
    healthy = success(path, reset_path)
    original = baseline(path, reset_path)
    rows = []
    for mode, target in [('denied', kind) for kind in COLD_TYPES] + [
            ('corrupt', 0x8a), ('capacity', 1), ('bad-lock-id', 0x8a),
            ('wrong-type', 0x8a), ('prior-fault', 0x8a), ('fault-at-release', 0x12),
            ('active-context', 0x8a), ('mie-off', 0x8a), ('external-irq-off', 0x8a),
            ('bad-irq8', 0x8a), ('masked-mailbox', 0x8a)]:
        rows.append(fault_case(path, reset_path, mode, target))
        print(json.dumps(dict(mode=mode, target=hex(target), passed=True)), flush=True)
    preserved = fallback(path)
    bridge = bridge_cases(path, reset_path)
    gate = retained_gate(path, reset_path)
    mutants = mutations(path, reset_path)
    assert all(sha((ROOT/name).read_bytes()) == digest for name, digest in inputs.items())
    result = dict(schema=1, command=command, elf_sha256=sha(path.read_bytes()), sections=sections,
                  disassembly=subprocess.check_output(['riscv64-linux-gnu-objdump', '-d', str(path)],
                                                      text=True, timeout=30),
                  healthy=healthy, original=original, failures=rows, fallback=preserved,
                  bridge=bridge, retained_gate=gate, mutants=mutants,
                  inputs_before_after=inputs,
                  limits=['Only seven core0 startup callers and the hart7 bridge caller are selected; other native callers stay unchanged.',
                          'Core0 control availability is verified only with no active callback and installed/enabled control IRQ.',
                          'IRQ dispatch, mailbox/PLIC/lock storage and host publication remain explicit models; no physical delivery/drain proof.',
                          'No router, image, INODE-provider correction or native DESC5/6/7/8 callback.'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output = args.output
    encoded = (json.dumps(result, indent=2)+'\n').encode()
    if args.check:
        assert output.read_bytes() == encoded, 'startup allocation replay differs'
    else:
        output.write_bytes(encoded)
    print(json.dumps(dict(cold_allocations=len(healthy['checked_allocations']), failures=len(rows),
                          fallback_cases=len(preserved), bridge_cases=len(bridge), mutants=len(mutants),
                          evidence_sha256=sha(encoded))))


if __name__ == '__main__':
    main()
