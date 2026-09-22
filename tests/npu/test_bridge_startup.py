#!/usr/bin/env python3
"""Original hart-7 post-gate startup with explicit bridge/timer/lock models."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
from unicorn import riscv_const as r
from unicorn import __version__ as UNICORN_VERSION
from elftools.elf.elffile import ELFFile

from test_multihart_cold_boot import AllHarts, ELF, ELF_SHA, ROOT, STARTUPS
from test_barrier_protocol import Rv32
from test_barrier_core5 import jump
from test_native_wifi_boot import L2, L2_BYTES
from test_firmware_memory_layout import STACK_TOPS, table
from test_boot_irq_installation import UnmodeledAccess, GHIDRA, CODE_SHA, DATA_SHA
from emulation_layout import SRAM, SRAM_BYTES, HEAP, HEAP_BYTES, STATE

OUT = ROOT / 'research/checkpoints/2026-09-09-npu-bridge-startup'
BRIDGE = 0x1ec12000
START = 0x84000b24
OUTER = 0x84000b36
CHANNELS = tuple(BRIDGE+0x210+i*16 for i in range(8))
ASM = ROOT / 'tests/npu/bridge-startup-emulation.S'
LINKER = ASM.with_suffix('.ld')
BUILD = ROOT / '.local/npu-bridge-startup'
GUARDS = {0x8400148a: ('base', 'aa87aa85'), 0x84001500: ('channel', '91e35685')}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build_guard(define=None):
    assert sha(ELF.read_bytes()) == ELF_SHA
    BUILD.mkdir(parents=True, exist_ok=True)
    output = BUILD / ('bridge' + ('-' + define if define else '') + '.elf')
    lld = shutil.which('ld.lld') or str(ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld')
    command = [shutil.which('clang'), '--target=riscv32', '-march=rv32imac_zicsr',
               '-mabi=ilp32', '-nostdlib', '-fno-stack-protector', f'--ld-path={lld}',
               str(ASM), '-Wl,-T,' + str(LINKER), '-Wl,--no-relax',
               '-Wl,--just-symbols=' + str(ELF), '-o', str(output)]
    if define:
        command.append('-D' + define)
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    with output.open('rb') as stream:
        elf = ELFFile(stream)
        allocated = [(s.name, s['sh_addr'], s['sh_size']) for s in elf.iter_sections()
                     if s['sh_flags'] & 2 and s['sh_size']]
    assert allocated and all(0x84048000 <= address and address+size <= 0x84049000
                             for _, address, size in allocated)
    return output, dict(command=command, elf_sha256=sha(output.read_bytes()), sections=allocated)


class Bridge(AllHarts):
    def __init__(self, omit_start=True):
        self.bridge_active = False
        self.timer_reads = 0
        self.timer_value = 0xfffffff0
        self.channel_write_mode = 'storage'
        self.bad_owner = False
        self.pending_w1c = None
        self.guarded = False
        self.guard_rv = None
        self.installed_guards = []
        self.initial_gate_omitted = omit_start
        super().__init__(ELF, plic='banked', omit=START if omit_start else None)
        self.cpu.mem_map(BRIDGE, 0x1000)
        self.coordinator_footprint = self.coordinator()
        self.hart = 7
        self.cpu.context_restore(self.fresh)
        assert self.reset(START) == START
        self.start_context = self.cpu.context_save()
        self.regions = [(SRAM, SRAM_BYTES), (HEAP, HEAP_BYTES), (L2, L2_BYTES),
                        (STACK_TOPS[7]-0x4000, 0x4000), (BRIDGE, 0x1000),
                        (0x1ec10000, 0x1000), (0x1ec03000, 0x1000)]
        self.saved_memory = [(address, bytes(self.cpu.mem_read(address, size)))
                             for address, size in self.regions]
        self.base_count = self.get32(SRAM+0x1bd4)
        self.base_used = self.get32(SRAM+0x1be0)
        self.bridge_type = next(row for row in table(self.code, 0x8401b224)
                                if row['type'] == 0x81)

    def install_guards(self, path, omit=None):
        for previous in self.installed_guards:
            assert bytes(self.cpu.mem_read(previous['site'], 4)).hex() == previous['after']
            self.cpu.mem_write(previous['site'], bytes.fromhex(previous['before']))
        self.installed_guards = []
        self.guard_rv = Rv32(path, self.cpu)
        assert self.guard_rv.symbols['npu_barrier_fail'] == self.rv.symbols['npu_barrier_fail']
        assert self.guard_rv.symbols['npu_emulation_barrier_state'] == STATE
        for site, (kind, expected) in GUARDS.items():
            assert bytes(self.cpu.mem_read(site, 4)).hex() == expected
            if site == omit:
                continue
            target = self.guard_rv.symbols[f'npu_emulation_bridge_{kind}_guard']
            replacement = jump(site, target)
            self.cpu.mem_write(site, replacement)
            self.installed_guards.append(dict(site=site, kind=kind, before=expected,
                                              after=replacement.hex(), target=hex(target)))
        self.cpu.ctl_remove_cache(0x84001460, 0x84001582)
        self.cpu.ctl_remove_cache(0x84048000, 0x84049000)
        self.guarded = True

    def register_model(self, address, write):
        if address == self.missing:
            return None
        if address in CHANNELS or address in (BRIDGE+8, BRIDGE+0x10, BRIDGE+0x18):
            return 'bridge configuration/status storage hypothesis; no DMA, ingress, reset or completion proof'
        if address == 0x1ec10108:
            return 'synthetic decreasing timer counter; no real-time/clock-frequency proof'
        if address in (0x1ec03c48, 0x1ec03e48):
            return 'hart7 allocator mutex bank; synthetic owner readback, no contention/atomicity proof'
        return super().register_model(address, write)

    def read_hook(self, cpu, access, address, size, value, data):
        if self.bridge_active and address == 0x1ec10108:
            self.timer_reads += 1
            self.timer_value = (self.timer_value - 65536) & 0xffffffff
            self.put32(address, self.timer_value)
        if self.bridge_active and address == 0x1ec03c48:
            self.put32(address, 0x10000 | (0 if self.bad_owner else 7 << 8))
        super().read_hook(cpu, access, address, size, value, data)

    def code_hook(self, cpu, pc, size, data):
        if self.pending_w1c is not None:
            address, value = self.pending_w1c
            self.put32(address, value)
            self.pending_w1c = None
        if self.bridge_active and pc == 0x84000b28:
            self.bridge_return = cpu.reg_read(r.UC_RISCV_REG_A0)
        if self.bridge_active and pc == 0x84005010:
            self.lock_result = cpu.reg_read(r.UC_RISCV_REG_A0)
        if self.bridge_active and self.guard_rv:
            for kind in ('base', 'channel'):
                if pc == self.guard_rv.symbols[f'npu_emulation_bridge_{kind}_guard']:
                    self.guard_entries[kind] += 1
            if 0x84048000 <= pc < 0x84049000 and self.get32(pc) == 0x0ff0000f:
                self.guard_io_fences.append(self.tick)
        super().code_hook(cpu, pc, size, data)

    def write_hook(self, cpu, access, address, size, value, data):
        if self.bridge_active and STATE <= address < STATE+0x158:
            self.protocol_writes.append(dict(hart=self.hart, address=hex(address), size=size,
                                             value=value, pc=hex(cpu.reg_read(r.UC_RISCV_REG_PC)), step=self.tick))
        if self.bridge_active and self.channel_write_mode == 'w1c' and address in CHANNELS:
            assert self.pending_w1c is None and size == 4
            self.pending_w1c = (address, self.get32(address) & ~value)
        super().write_hook(cpu, access, address, size, value, data)

    def prepare(self, mask=255, exhausted=False, timer=True, w1c=False, bad_owner=False):
        self.cpu.context_restore(self.start_context)
        for address, data in self.saved_memory:
            self.cpu.mem_write(address, data)
        self.hart = 7
        self.events, self.mmio, self.logs, self.allocations = [], [], [], []
        self.pending_call = None
        self.pending_w1c = None
        self.stub_counts, self.stub_returns = {}, {}
        self.bridge_return = self.lock_result = None
        self.protocol_writes = []
        self.guard_entries = Counter()
        self.guard_io_fences = []
        self.unmodeled = None
        self.timer_reads, self.timer_value = 0, 0xfffffff0
        self.channel_write_mode = 'w1c' if w1c else 'storage'
        self.bad_owner = bad_owner
        self.bridge_active = True
        for channel, address in enumerate(CHANNELS):
            self.put32(address, 0xa5000000 | ((mask >> channel) & 1))
        self.put32(0x1ec10100, int(timer))
        self.put32(0x1ec10104, 0xffffffff)
        if exhausted:
            self.put32(SRAM+0x1be0, HEAP_BYTES)
        self.cpu.mem_write(SRAM+0xc54, b'\xa5' * 60)
        self.put32(SRAM+0x184c, 0x55aa55aa)
        self.input_sram = bytes(self.cpu.mem_read(SRAM, SRAM_BYTES))
        self.input_mstatus = self.cpu.reg_read(r.UC_RISCV_REG_MSTATUS)

    def probe(self, mask=255, exhausted=False, timer=True, w1c=False, bad_owner=False):
        assert self.initial_gate_omitted
        self.prepare(mask, exhausted, timer, w1c, bad_owner)
        before = {hex(address): sha(bytes(self.cpu.mem_read(address, size)))
                  for address, size in self.regions}
        fault_kind = ('base' if exhausted else 'channel' if mask != 255 else None) if self.guarded else None
        faults = {kind: self.guard_rv.symbols[f'npu_emulation_bridge_{kind}_fault_park']
                  for kind in ('base', 'channel')} if self.guard_rv else {}
        stop = self.run(START, [OUTER, *faults.values()])
        assert stop == (faults[fault_kind] if fault_kind else OUTER), (hex(stop), fault_kind)
        base = self.get32(SRAM+0x184c)
        expected_base = 0x55aa55aa if fault_kind == 'base' else 0 if exhausted else (HEAP+self.base_used+31) & ~31
        assert base == expected_base
        assert bytes(self.cpu.mem_read(SRAM+0xc54, 60)) == (b'\xa5' if fault_kind else b'\0') * 60
        logged_failures = 0 if self.guarded else 8-mask.bit_count()
        assert len([row for row in self.logs if 'buf init fail' in row['format']]) == logged_failures
        writes = [(int(row['address'], 16), row['value']) for row in self.mmio
                  if row['kind'] == 'mmio-write' and BRIDGE <= int(row['address'], 16) < BRIDGE+0x1000]
        ack_count = next(i for i in range(8) if not mask & (1 << i)) if fault_kind == 'channel' else 8
        expected_writes = [] if fault_kind == 'base' else [
            (BRIDGE+8, base & 0x1fffffff), (BRIDGE+0x10, 0x40800), (BRIDGE+0x18, 1),
            *[(address, 1) for address in CHANNELS[:ack_count]]]
        assert writes == expected_writes
        expected_channels = [0xa5000000 | ((mask >> i) & 1) for i in range(8)]
        if fault_kind != 'base':
            for i in range(ack_count):
                expected_channels[i] = 0xa5000000 if w1c else 1
        assert [self.get32(address) for address in CHANNELS] == expected_channels
        assert self.get32(STATE+16) == int(bool(fault_kind)), 'missing cross-hart fault'
        if fault_kind:
            assert len(self.guard_io_fences) == 1, 'I/O fence missing before fault'
            assert self.guard_io_fences[0] < self.protocol_writes[-1]['step']
        else:
            assert not self.guard_io_fences
        assert self.get32(STATE+20+7*4) == 0
        assert self.bridge_return == (None if fault_kind else 0)
        assert self.lock_result == (0xffffffff if bad_owner else 0)
        assert sha(bytes(self.cpu.mem_read(L2, L2_BYTES))) == self.coordinator_footprint['l2_sha256']
        late_ready = []
        if fault_kind:
            before_writes = len(self.mmio)
            assert self.run(stop, [stop]) == stop
            if fault_kind == 'channel':
                for address in CHANNELS[ack_count:]:
                    value = self.get32(address) | 1
                    self.put32(address, value)
                    late_ready.append(dict(address=hex(address), value=value))
            assert self.run(stop, [stop]) == stop
            assert len(self.mmio) == before_writes
            assert self.get32(STATE+20+7*4) == 0
        else:
            poll = self.rv.symbols['npu_barrier_poll']
            assert self.run(OUTER, [poll]) == poll
            assert self.run(poll, [poll]) == poll
            assert self.get32(STATE+20+7*4) == 1
        assert not self.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8, 'datapath IRQs remained enabled'
        assert [self.get32(STATE+52+i*4) for i in range(13)] == [0]*13
        expected = bytearray(self.input_sram)
        attempts = struct.unpack_from('<I', expected, 0x1bdc)[0]
        struct.pack_into('<I', expected, 0x1bdc, attempts+1)
        if not exhausted:
            allocated_base = (HEAP+self.base_used+31) & ~31
            struct.pack_into('<I', expected, 0x1bd4, self.base_count+1)
            struct.pack_into('<I', expected, 0x1be0, allocated_base-HEAP+self.bridge_type['value'])
            struct.pack_into('<H', expected, 0x1be4+self.base_count*8, 0x81)
            struct.pack_into('<I', expected, 0x1be8+self.base_count*8, allocated_base)
        if fault_kind != 'base':
            struct.pack_into('<I', expected, 0x184c, expected_base)
        if not fault_kind:
            expected[0xc54:0xc90] = bytes(60)
            struct.pack_into('<I', expected, STATE-SRAM+20+7*4, 1)
        else:
            struct.pack_into('<I', expected, STATE-SRAM+16, 1)
        actual = bytes(self.cpu.mem_read(SRAM, SRAM_BYTES))
        assert actual == bytes(expected), [(hex(i), a, b) for i, (a, b) in
                                            enumerate(zip(actual, expected)) if a != b][:20]
        expected_protocol = [(hex(STATE+16 if fault_kind else STATE+20+7*4), 1)]
        assert [(row['address'], row['value']) for row in self.protocol_writes] == expected_protocol
        assert all(row['hart'] == 7 for row in self.protocol_writes)
        assert bytes(self.cpu.mem_read(HEAP, HEAP_BYTES)) == dict(self.saved_memory)[HEAP]
        if self.guarded:
            expected_entries = dict(base=1)
            if fault_kind != 'base':
                expected_entries['channel'] = ack_count+1 if fault_kind else 8
            assert dict(self.guard_entries) == expected_entries
        entries = Counter(event['pc'] for event in self.events if event['kind'] == 'entry')
        result = dict(mask=mask, exhausted=exhausted, timer=timer, w1c=w1c,
                      bad_owner=bad_owner, bridge_type=self.bridge_type,
                      native_bridge_base=hex(base), native_return_to_outer=not fault_kind,
                      guarded=self.guarded, installed_guards=self.installed_guards,
                      fault_kind=fault_kind, final_pc=hex(stop), lock_result=hex(self.lock_result),
                      initial_mstatus=hex(self.input_mstatus),
                      guard_entries=dict(self.guard_entries),
                      guard_io_fences=len(self.guard_io_fences),
                      late_ready_model=late_ready, late_ready_did_not_resume=bool(late_ready),
                      bridge_writes=[dict(address=hex(a), value=v) for a, v in writes],
                      channel_failure_logs=logged_failures, timer_reads=self.timer_reads,
                      allocator_before=dict(count=self.base_count, used=self.base_used),
                      allocator_after=dict(count=self.get32(SRAM+0x1bd4), used=self.get32(SRAM+0x1be0)),
                      allocations=[row for row in self.allocations if row['type'] == 0x81],
                      native_entries=dict(entries), mmio=self.mmio,
                      memory_before=before,
                      memory_after={hex(a): sha(bytes(self.cpu.mem_read(a, size))) for a, size in self.regions},
                      channel_final=[hex(self.get32(address)) for address in CHANNELS],
                      whole_sram_compared_bytes=SRAM_BYTES, whole_heap_unchanged_bytes=HEAP_BYTES,
                      whole_l2_unchanged_bytes=L2_BYTES, protocol_writes=self.protocol_writes,
                      native_initializer_allocator_delay_stubs=False,
                      existing_stub_counts=self.stub_counts,
                      initial_gate_omitted_for_analysis=hex(START),
                      final_gate_retained=hex(OUTER), parked=int(not fault_kind), ready=0, drains=0,
                      released=self.get32(STATE+4), armed=self.get32(STATE+8))
        protocol_before = bytes(self.cpu.mem_read(STATE, 0x158))
        result['mmio'] = list(self.mmio)
        result['protocol_writes'] = list(self.protocol_writes)
        status = self.control(3)
        assert status[6] == 1 and status[9] == (6 if fault_kind else 0)
        assert status[10:] == [7, 1 if fault_kind else 0x81, 0, 0, 0, 0]
        assert bytes(self.cpu.mem_read(STATE, 0x158)) == protocol_before
        result['coordinator_status'] = status
        print(json.dumps({key: result[key] for key in ('guarded', 'mask', 'exhausted', 'timer', 'w1c', 'bad_owner', 'fault_kind', 'native_bridge_base')}), flush=True)
        return result


def input_bindings():
    paths = {ASM, LINKER, ELF, GHIDRA}
    for module in tuple(sys.modules.values()):
        value = getattr(module, '__file__', None)
        if value:
            path = Path(value).resolve()
            if path.is_relative_to(ROOT) and path.suffix in ('.py', '.c', '.h', '.S', '.ld'):
                paths.add(path)
    paths.update((ROOT / 'firmware/npu').glob('*.[ch]'))
    paths.update((ROOT / 'tests/npu').glob('*-emulation.[Sc]'))
    paths.update(ROOT / name for name in ('firmware/source-lock.json', 'firmware/patches/openwrt.patch',
                                        'firmware/patches/luci.patch', 'firmware/build.config'))
    return {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in sorted(paths)}


def source_spans():
    text = GHIDRA.read_text()
    rows = []
    for address in (0x84001392, 0x84001466, 0x84001472, 0x84003712,
                    0x84004ff8, 0x84005200, 0x840064b4, 0x8400651c):
        match = re.search(r'^FUNCTION [^\n]* @ ram:' + f'{address:08x}' +
                          r'\n.*?(?=^FUNCTION |\Z)', text, re.M | re.S)
        assert match and 'decompiled=true' in match[0]
        rows.append(dict(address=hex(address), line=text[:match.start()].count('\n')+1,
                         sha256=sha(match[0].encode())))
    return rows


def closed_gate(path):
    h = Bridge(omit_start=False)
    h.install_guards(path)
    h.prepare()
    before = bytes(h.cpu.mem_read(SRAM, SRAM_BYTES))
    poll = h.rv.symbols['npu_barrier_poll']
    assert h.run(START, [poll]) == poll
    assert h.run(poll, [poll]) == poll
    expected = bytearray(before)
    struct.pack_into('<I', expected, STATE-SRAM+20+7*4, 1)
    assert bytes(h.cpu.mem_read(SRAM, SRAM_BYTES)) == bytes(expected)
    assert not h.guard_entries and not h.allocations
    assert not any(BRIDGE <= int(row['address'], 16) < BRIDGE+0x1000 for row in h.mmio)
    assert not h.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
    h.contexts[7] = h.cpu.context_save()
    for hart in range(1, 7):
        h.worker(hart)
    for hart in range(8):
        h.repoll(hart)
    assert [h.get32(STATE+20+i*4) for i in range(8)] == [1]*8
    assert not h.guard_entries and not h.allocations
    assert not any(BRIDGE <= int(row['address'], 16) < BRIDGE+0x1000 for row in h.mmio)
    status = h.control(3)
    assert status[9:] == [0, 7, 255, 0, 0, 0, 0]
    return dict(initial_gate_retained=True, installed_detours=len(h.patches)+len(h.installed_guards),
                parked=1, fault=0, ready=0, drained=0, released=0, armed=0,
                whole_sram_compared_bytes=SRAM_BYTES, no_bridge_access=True,
                all_parked=[1]*8, status=status, reset_order=[0, 7, 1, 2, 3, 4, 5, 6],
                plic='banked storage hypothesis', all_harts_repolled=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--check', action='store_true', help='replay and compare without rewriting the receipt')
    args = parser.parse_args()
    assert sha(ELF.read_bytes()) == ELF_SHA
    inputs_before = input_bindings()
    h = Bridge()
    parameters = [{}]
    if not args.smoke:
        parameters += [dict(mask=255 ^ (1 << channel)) for channel in range(8)]
        parameters += [dict(mask=0), dict(exhausted=True), dict(timer=False), dict(bad_owner=True)]
        parameters = [{**params, 'w1c': w1c} for w1c in (False, True) for params in parameters]
    cases = [h.probe(**params) for params in parameters]
    path, compiled = build_guard()
    compiled['disassembly'] = subprocess.check_output(
        ['riscv64-linux-gnu-objdump', '-d', str(path)], text=True, timeout=30)
    compiled['compiler'] = subprocess.check_output(
        [compiled['command'][0], '--version'], text=True, timeout=30).splitlines()[0]
    h.install_guards(path)
    guarded = [h.probe(**params) for params in parameters]
    for params, before, after in zip(parameters, cases, guarded, strict=True):
        if params.get('exhausted') or params.get('mask', 255) != 255:
            assert before['native_return_to_outer'] and not after['native_return_to_outer']
        else:
            assert before['memory_after'] == after['memory_after']
            assert before['bridge_writes'] == after['bridge_writes']
    mutants, missing_models = [], []
    if not args.smoke:
        for define, omit, params, expected_error in (
            ('OMIT_BRIDGE_BASE_CHECK', None, dict(exhausted=True), (hex(OUTER), 'base')),
            ('OMIT_BRIDGE_CHANNEL_CHECK', None, dict(mask=254), (hex(OUTER), 'channel')),
            (None, 0x8400148a, dict(exhausted=True), (hex(OUTER), 'base')),
            (None, 0x84001500, dict(mask=127), (hex(OUTER), 'channel')),
            ('OMIT_BRIDGE_IRQ_MASK', None, dict(exhausted=True), 'datapath IRQs remained enabled'),
            ('OMIT_BRIDGE_FAULT_PUBLICATION', None, dict(mask=254), 'missing cross-hart fault'),
            ('OMIT_BRIDGE_IO_FENCE', None, dict(mask=254), 'I/O fence missing before fault'),
        ):
            mutant_path, details = build_guard(define)
            h.install_guards(mutant_path, omit)
            try:
                h.probe(**params)
            except AssertionError as error:
                assert error.args and error.args[0] == expected_error, error
                mutants.append(dict(define=define, omitted_site=hex(omit) if omit else None,
                                    killed=True, binary=details))
            else:
                raise AssertionError('surviving bridge guard mutant')
        h.install_guards(path)
        for address in (BRIDGE+8, CHANNELS[0], 0x1ec03c48, 0x1ec10108):
            h.missing = address
            try:
                h.probe()
            except UnmodeledAccess as error:
                assert hex(address) in str(error)
                missing_models.append(dict(address=hex(address), error=str(error)))
            else:
                raise AssertionError('missing bridge model silently accepted')
        h.missing = None
    retained_gate = closed_gate(path)
    assert input_bindings() == inputs_before
    OUT.mkdir(parents=True, exist_ok=True)
    result = dict(schema=1, elf_sha256=ELF_SHA, test_sha256=sha(Path(__file__).read_bytes()),
                  python=sys.version.split()[0], unicorn=UNICORN_VERSION,
                  firmware_sha256=CODE_SHA, data_sha256=DATA_SHA,
                  assembly_sha256=sha(ASM.read_bytes()), linker_sha256=sha(LINKER.read_bytes()),
                  compiled_guard=compiled, cases=cases, guarded=guarded, mutants=mutants,
                  missing_models=missing_models, initial_gate_control=retained_gate,
                  inputs_before_after=inputs_before, ghidra_source_spans=source_spans())
    path = OUT / ('native-smoke.json' if args.smoke else 'native-startup.json')
    encoded = (json.dumps(result, indent=2) + '\n').encode()
    if args.check:
        assert path.read_bytes() == encoded, 'bridge evidence replay differs'
    else:
        path.write_bytes(encoded)
    print(json.dumps(dict(cases=len(cases), guarded=len(guarded), mutants=len(mutants),
                          missing_models=len(missing_models), initial_gate_retained=True,
                          evidence_sha256=sha(path.read_bytes()))))


if __name__ == '__main__':
    main()
