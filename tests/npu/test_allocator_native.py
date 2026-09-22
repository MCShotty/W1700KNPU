#!/usr/bin/env python3
"""Original allocator comparison and checked hart7 bridge integration, offline."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
from unicorn import UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r

import test_allocator_protocol as protocol
from test_firmware_memory_layout import NativeMemory
from test_bridge_startup import Bridge, ELF, ELF_SHA, GUARDS, build_guard, input_bindings
from test_barrier_protocol import Rv32
from test_barrier_core5 import jump
from test_bootstrap_native import ROOT
from emulation_layout import SRAM, SRAM_BYTES, HEAP, HEAP_BYTES, STATE

OUT, BUILD = protocol.OUT, protocol.BUILD
SOURCE, HEADER = protocol.SOURCE, protocol.HEADER
BINDING = ROOT / 'tests/npu/allocator-bridge-emulation.c'
NATIVE_STATE = SRAM+0x1bcc
CALL = 0x84001486


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Original(NativeMemory):
    def __init__(self):
        self.tracing = False
        self.writes = []
        super().__init__()
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, self.write)

    def write(self, cpu, access, address, size, value, data):
        if self.tracing and not 0x84000000 <= address < 0x84201000:
            self.writes.append(dict(address=hex(address), size=size, value=value,
                                    pc=hex(cpu.reg_read(r.UC_RISCV_REG_PC))))

    def fresh(self, state=None, denied=False):
        self.tracing = False
        self.call(0x84005296)
        self.put32(SRAM+0x1bdc, 0)
        if state is not None:
            self.cpu.mem_write(NATIVE_STATE, state)
        self.put32(0x1ec03048, 0x10100 if denied else 0x10000)
        self.tracing, self.writes = True, []

    def state(self):
        return bytes(self.cpu.mem_read(NATIVE_STATE, protocol.STATE_BYTES))


def original_cases():
    h = Original()
    definitions = protocol.definitions()
    rows, rejected = [], []
    for group, values in enumerate(definitions):
        for kind, _, _, _ in values:
            h.fresh()
            for cached in (False, True):
                before = h.state()
                case = protocol.Case(f'original-{kind:x}-{int(cached)}', definitions, kind, group, before)
                expected, state, _ = protocol.oracle(case)
                value = h.call(0x84005200, kind)
                assert expected == (protocol.OK, value) and h.state() == state
                rows.append(dict(type=kind, cached=cached, address=hex(value),
                                 state_before_sha256=sha(before), state_after_sha256=sha(state)))
    h.fresh(denied=True)
    before = h.state()
    value = h.call(0x84005200, 0x81)
    assert value == HEAP and h.state() != before
    assert any(row['address'] == '0x1ec03248' for row in h.writes)
    rejected.append(dict(name='failed-lock-still-allocates-and-releases', value=hex(value),
                         state_before_sha256=sha(before), state_after_sha256=sha(h.state()), writes=h.writes))

    h.fresh()
    first = h.call(0x84005200, 1)
    before = h.state()
    assert h.call(0x84005200, 0x80) == 0 and h.get32(SRAM+0x1be0) == 0
    next_ = h.call(0x84005200, 0x8a)
    assert first == next_ == HEAP
    rejected.append(dict(name='unknown-type-rewinds-cursor-and-overlaps', first=hex(first), next=hex(next_),
                         state_before_sha256=sha(before), state_after_sha256=sha(h.state()), writes=h.writes))

    h.fresh()
    for kind in (0x8a, 18, 29, 1, 11, 25, 0x81):
        h.call(0x84005200, kind)
    before = h.state()
    value = h.call(0x84005200, 2)
    end = value + next(row[3] for row in definitions[1] if row[0] == 2)
    assert value < HEAP+HEAP_BYTES < end
    assert h.get32(SRAM+0x1be0) > HEAP_BYTES
    rejected.append(dict(name='start-only-check-permits-extent-overrun', address=hex(value),
                         requested_end=hex(end), heap_end=hex(HEAP+HEAP_BYTES),
                         state_before_sha256=sha(before), state_after_sha256=sha(h.state()), writes=h.writes,
                         scope='Typed allocation sequence only; no native RX callback or DMA access.'))

    h.fresh()
    state = bytearray(h.state())
    struct.pack_into('<I', state, 8, 100)
    for index in range(100):
        struct.pack_into('<HHI', state, 24+index*8, index, 0, HEAP)
    h.cpu.mem_write(NATIVE_STATE, bytes(state))
    h.put32(SRAM+0x1f04, 0x12345678)
    h.put32(SRAM+0x1f08, 0x87654321)
    h.writes = []
    assert h.call(0x84005200, 0x81) == HEAP
    assert h.get32(SRAM+0x1f04) != 0x12345678 and h.get32(SRAM+0x1f08) == HEAP
    rejected.append(dict(name='corrupt-count-100-overwrites-following-globals', writes=h.writes,
                         scope='Explicitly corrupted metadata, not a valid observed cold allocation sequence.'))
    return dict(valid_comparisons=rows, counterexamples=rejected)


def build_bridge():
    assert sha(ELF.read_bytes()) == ELF_SHA
    BUILD.mkdir(parents=True, exist_ok=True)
    path = BUILD / 'allocator-bridge.elf'
    lld = shutil.which('ld.lld') or str(ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld')
    command = [shutil.which('clang'), '--target=riscv32', '-march=rv32imac_zicsr',
               '-mabi=ilp32', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-fno-builtin',
               '-nostdlib', '-fno-stack-protector', f'--ld-path={lld}', '-I', str(SOURCE.parent),
               str(SOURCE), str(BINDING), '-Wl,-T,'+str(protocol.LINKER), '-Wl,--no-relax',
               '-Wl,-e,npu_emulation_bridge_allocate', '-Wl,--just-symbols='+str(ELF), '-o', str(path)]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stdout+completed.stderr
    return path, command


class CheckedBridge(Bridge):
    def __init__(self, path, omit_start=True):
        super().__init__(omit_start=omit_start)
        bridge_guards, _ = build_guard()
        self.install_guards(bridge_guards)
        self.checked = Rv32(path, self.cpu)
        self.pending_checked = None
        self.checked_results = []
        self.fault_on_unlock = False
        self.checked_fences = []
        target = self.checked.symbols['npu_emulation_bridge_allocate']
        self.preimage = bytes(self.cpu.mem_read(CALL, 4)).hex()
        assert self.preimage == self.code[CALL-0x84000000:CALL-0x84000000+4].hex()
        original = int.from_bytes(bytes.fromhex(self.preimage), 'little')
        displacement = ((original >> 31) << 20 | ((original >> 21) & 1023) << 1 |
                        ((original >> 20) & 1) << 11 | ((original >> 12) & 255) << 12)
        if displacement & (1 << 20):
            displacement -= 1 << 21
        assert original & 127 == 0x6f and (original >> 7) & 31 == 1
        assert CALL+displacement == 0x84005200
        word = int.from_bytes(jump(CALL, target), 'little') | 0x80
        self.cpu.mem_write(CALL, struct.pack('<I', word))
        self.cpu.ctl_remove_cache(0x84001460, 0x84001582)
        self.cpu.ctl_remove_cache(0x8404a000, 0x84050000)
        self.call_patch = dict(site=hex(CALL), before=self.preimage,
                               after=struct.pack('<I', word).hex(), target=hex(target), link_register=1)
        native = Original()
        native.fresh()
        for kind in (0x8a, 18, 29, 1, 11, 25, 2, 3):
            assert native.call(0x84005200, kind)
        self.capacity_state = native.state()

    def code_hook(self, cpu, pc, size, data):
        if self.bridge_active and hasattr(self, 'checked'):
            if self.pending_checked == pc:
                self.checked_results.append((cpu.reg_read(r.UC_RISCV_REG_A0), cpu.reg_read(r.UC_RISCV_REG_A1)))
                self.pending_checked = None
            if pc == self.checked.symbols['npu_allocator_allocate']:
                assert self.pending_checked is None
                self.pending_checked = cpu.reg_read(r.UC_RISCV_REG_RA)
            if 0x8404a000 <= pc < 0x84050000 and self.get32(pc) == 0x0ff0000f:
                self.checked_fences.append(self.tick)
        super().code_hook(cpu, pc, size, data)

    def write_hook(self, cpu, access, address, size, value, data):
        if self.bridge_active and getattr(self, 'fault_on_unlock', False) and address == 0x1ec03e48:
            self.put32(STATE+16, 1)
        super().write_hook(cpu, access, address, size, value, data)

    def run_checked(self, name, *, deny=False, corrupt=False, capacity=False,
                    cached=False, bad_lock_id=False, prior_fault=False, fault_on_unlock=False):
        self.prepare(bad_owner=deny)
        self.pending_checked, self.checked_results, self.checked_fences = None, [], []
        self.fault_on_unlock = fault_on_unlock
        definitions = protocol.definitions()
        if capacity:
            self.cpu.mem_write(NATIVE_STATE, self.capacity_state)
        if cached:
            self.cpu.mem_write(NATIVE_STATE, protocol.state_for(definitions, [0x8a, 18, 29, 1, 11, 25, 0x81]))
        if corrupt:
            self.put32(SRAM+0x1be0, 0)
        if bad_lock_id:
            self.put32(NATIVE_STATE, 19)
        if prior_fault:
            self.put32(STATE+16, 1)
        before = bytes(self.cpu.mem_read(SRAM, SRAM_BYTES))
        before_state = bytes(self.cpu.mem_read(NATIVE_STATE, protocol.STATE_BYTES))
        expected, metadata, counts = protocol.oracle(protocol.Case(name, definitions, 0x81, 0, before_state,
                                                                  deny=int(deny or bad_lock_id)))
        if prior_fault:
            expected, metadata, counts = None, before_state, (0, 0)
        fault = self.checked.symbols['npu_emulation_allocator_fault_park']
        stop = self.run(0x84000b24, [0x84000b36, fault])
        must_hold = prior_fault or expected[0] != protocol.OK or fault_on_unlock
        assert stop == (fault if must_hold else 0x84000b36)
        assert self.checked_results == ([] if prior_fault else [expected])
        assert bytes(self.cpu.mem_read(NATIVE_STATE, protocol.STATE_BYTES)) == metadata
        acquires = [row for row in self.mmio if row['kind'] == 'mmio-write' and row['address'] == '0x1ec031c8']
        releases = [row for row in self.mmio if row['kind'] == 'mmio-write' and row['address'] == '0x1ec03e48']
        physical_counts = (0, 0) if bad_lock_id or prior_fault else counts
        assert (len(acquires), len(releases)) == physical_counts
        assert self.checked_fences
        expected_sram = bytearray(before)
        expected_sram[0x1bcc:0x1bcc+protocol.STATE_BYTES] = metadata
        if must_hold:
            struct.pack_into('<I', expected_sram, STATE-SRAM+16, 1)
            assert not self.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
            assert self.get32(SRAM+0x184c) == 0x55aa55aa
            assert not any(0x1ec12000 <= int(row['address'], 16) < 0x1ec13000 for row in self.mmio)
            at_hold = len(self.mmio)
            self.put32(0x1ec03c48, 0x10700)
            assert self.run(fault, [fault]) == fault
            assert self.run(fault, [fault]) == fault
            assert len(self.mmio) == at_hold
        else:
            struct.pack_into('<I', expected_sram, 0x184c, expected[1])
            expected_sram[0xc54:0xc90] = bytes(60)
            poll = self.rv.symbols['npu_barrier_poll']
            assert self.run(0x84000b36, [poll]) == poll
            assert self.run(poll, [poll]) == poll
            struct.pack_into('<I', expected_sram, STATE-SRAM+20+7*4, 1)
        actual = bytes(self.cpu.mem_read(SRAM, SRAM_BYTES))
        assert actual == bytes(expected_sram), [(hex(i), x, y) for i, (x, y) in
                                               enumerate(zip(actual, expected_sram)) if x != y][:20]
        assert bytes(self.cpu.mem_read(HEAP, HEAP_BYTES)) == dict(self.saved_memory)[HEAP]
        status = self.control(3)
        assert status[9:] == [6 if must_hold else 0, 7, 1 if must_hold else 0x81, 0, 0, 0, 0]
        return dict(name=name, result=expected, held=must_hold, lock_counts=counts,
                    physical_lock_operations=physical_counts, bad_lock_id=bad_lock_id, prior_fault=prior_fault,
                    metadata_unchanged=metadata == before_state, fault_injected_at_unlock=fault_on_unlock,
                    whole_sram_compared_bytes=SRAM_BYTES, whole_heap_unchanged_bytes=HEAP_BYTES,
                    state_before_sha256=sha(before_state), state_after_sha256=sha(metadata),
                    status=status, mmio=self.mmio, checked_fences=len(self.checked_fences),
                    initial_gate_omitted_for_analysis=True, base_elf_unchanged=ELF_SHA)


def retained_gate(path):
    h = CheckedBridge(path, omit_start=False)
    h.prepare()
    h.checked_results, h.checked_fences, h.pending_checked = [], [], None
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
    assert not h.checked_results and not h.guard_entries
    assert not any(0x1ec12000 <= int(row['address'], 16) < 0x1ec13000 for row in h.mmio)
    return dict(installed_detours=len(h.patches)+len(h.installed_guards)+1,
                initial_gate_retained=True, all_parked=[1]*8, status=status,
                no_bridge_or_allocator_execution=True, plic='banked storage hypothesis')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    inputs = input_bindings()
    inputs.update({str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in (BINDING, protocol.LINKER)})
    original = original_cases()
    path, command = build_bridge()
    h = CheckedBridge(path)
    rows = [h.run_checked('native-cold-state'), h.run_checked('denied-owner', deny=True),
            h.run_checked('corrupt-cursor', corrupt=True), h.run_checked('capacity', capacity=True),
            h.run_checked('external-fault-after-commit', fault_on_unlock=True),
            h.run_checked('cached-bridge', cached=True), h.run_checked('bad-lock-id', bad_lock_id=True),
            h.run_checked('prior-fault', prior_fault=True)]
    gate = retained_gate(path)
    assert all(sha((ROOT/name).read_bytes()) == value for name, value in inputs.items())
    OUT.mkdir(parents=True, exist_ok=True)
    result = dict(schema=1, source_sha256=sha(SOURCE.read_bytes()), header_sha256=sha(HEADER.read_bytes()),
                  binding_sha256=sha(BINDING.read_bytes()), test_sha256=sha(Path(__file__).read_bytes()),
                  bridge_guard_sha256=sha((ROOT/'tests/npu/bridge-startup-emulation.S').read_bytes()),
                  baseline_elf_sha256=ELF_SHA, candidate_elf_sha256=sha(path.read_bytes()), command=command,
                  original=original, bridge=rows, call_patch=h.call_patch, retained_gate=gate,
                  inputs_before_after=inputs,
                  limits=['Only the hart7 bridge allocation call is redirected; core0/native other callers remain unchanged.',
                          'Metadata/lock/bounds checks are implemented, but physical lock/cache/heap geometry and global caller integration remain open.',
                          'No INODE or DESC5/6/7/8 callback, router access, image or hardware execution.'])
    output = OUT/'allocator-native.json'
    encoded = (json.dumps(result, indent=2)+'\n').encode()
    if args.check:
        assert output.read_bytes() == encoded
    else:
        output.write_bytes(encoded)
    print(json.dumps(dict(original_valid=len(original['valid_comparisons']),
                          counterexamples=len(original['counterexamples']), bridge_cases=len(rows),
                          evidence_sha256=sha(encoded))))


if __name__ == '__main__':
    main()
