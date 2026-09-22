#!/usr/bin/env python3
"""Native egress width guards and nonreturning, ownership-retaining faults."""
import json
from pathlib import Path
import random
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
from unicorn import UC_HOOK_CODE
from unicorn import riscv_const as r
from elftools.elf.elffile import ELFFile

import test_tunnel_header_bounds as headers
from test_barrier_protocol import Rv32
from test_barrier_core5 import jump
from test_bridge_startup import ELF, input_bindings, UnmodeledAccess
from test_firmware_memory_layout import STACK_TOPS
from emulation_layout import CODE, SRAM, STATE

ROOT = headers.ROOT
BUILD = ROOT/'.local/npu-egress'
OUT = ROOT/'research/checkpoints/2026-09-10-npu-egress'
ASM = ROOT/'tests/npu/egress-emulation.S'
LINKER = ASM.with_suffix('.ld')
END, BRIDGE, DESC = headers.allocator.END, headers.BRIDGE, headers.DESC
SITES = {0x84001582: 'channel', 0x8400159e: 'slots', 0x8400178e: 'extent'}
REGS = [getattr(r, 'UC_RISCV_REG_X'+str(i)) for i in range(1, 32)]
ARGS = [getattr(r, 'UC_RISCV_REG_A'+str(i)) for i in range(8)]
SAVED = [getattr(r, 'UC_RISCV_REG_S'+str(i)) for i in range(12)]
STACK = STACK_TOPS[7]
FENCE = 0x0ff0000f


def build(define=None):
    BUILD.mkdir(parents=True, exist_ok=True)
    path = BUILD/('egress'+('-'+define if define else '')+'.elf')
    lld = shutil.which('ld.lld') or str(ROOT/'.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld')
    command = [shutil.which('clang'), '--target=riscv32', '-march=rv32imac_zicsr',
               '-mabi=ilp32', '-nostdlib', '-g', f'--ld-path={lld}', str(ASM),
               '-Wl,-T,'+str(LINKER)+',--no-relax', '-Wl,--just-symbols='+str(ELF), '-o', str(path)]
    if define:
        command.append('-D'+define)
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout+result.stderr
    with path.open('rb') as stream:
        elf = ELFFile(stream)
        sections = [dict(name=s.name, address=s['sh_addr'], bytes=s['sh_size'])
                    for s in elf.iter_sections() if s['sh_flags'] & 2 and s['sh_size']]
    assert sections and all(0x84058000 <= s['address'] < s['address']+s['bytes'] <= 0x8405a000
                            for s in sections)
    return path, dict(command=command, sections=sections, sha256=headers.sha(path.read_bytes()))


def install(h, path):
    for site in SITES:
        h.cpu.mem_write(site, h.code[site-CODE:site-CODE+4])
    rv = Rv32(path, h.cpu)
    assert rv.symbols['npu_emulation_barrier_state'] == STATE
    assert rv.symbols['npu_barrier_fail'] == h.rv.symbols['npu_barrier_fail']
    patches = []
    for site, name in SITES.items():
        before = bytes(h.cpu.mem_read(site, 4))
        target = rv.symbols['npu_emulation_egress_'+name]
        replacement = jump(site, target)
        h.cpu.mem_write(site, replacement)
        patches.append(dict(site=hex(site), target=hex(target), name=name,
                            before=before.hex(), after=replacement.hex()))
    h.cpu.ctl_remove_cache(CODE, CODE+0x201000)
    return rv, patches


def memory(h):
    return {base: bytes(h.cpu.mem_read(base, size)) for base, size in h.spaces}


def io(commands):
    return [(BRIDGE+channel*32+offset, 4, value)
            for channel, address, *words in commands
            for offset, value in zip((0x104, 0x108, 0x10c, 0x110, 0x114, 0x118, 0x100), (*words, address))]


class Egress(headers.Headers):
    def __init__(self, profile, reset, header_path, egress_path=None):
        self.egress_tracking = False
        self.egress_rv = None
        self.egress_missing = None
        super().__init__(profile, reset)
        self.header_rv, _ = headers.install(self, header_path)
        self.spaces = (*self.spaces, (STACK-1024, 1024))
        self.snapshot = [(base, bytes(self.cpu.mem_read(base, size))) for base, size in self.spaces]
        if egress_path:
            self.egress_rv, self.egress_patches = install(self, egress_path)

    def register_model(self, address, write):
        if self.egress_tracking and address == self.egress_missing:
            return None
        return super().register_model(address, write)

    def read_hook(self, cpu, access, address, size, value, data):
        if self.egress_tracking:
            self.reads.append((address, size))
            if address in range(BRIDGE+0x50, BRIDGE+0x70, 4):
                index = len(self.availability)
                available = self.statuses[index] if index < len(self.statuses) else 0x100
                self.put32(address, available)
                self.availability.append((address, available))
        super().read_hook(cpu, access, address, size, value, data)

    def write_hook(self, cpu, access, address, size, value, data):
        if self.egress_tracking and address == STATE+16:
            self.fault_writes.append((self.tick, size, value))
        super().write_hook(cpu, access, address, size, value, data)

    def code_hook(self, cpu, pc, size, data):
        if self.egress_tracking and self.egress_rv:
            if pc == self.egress_rv.symbols['npu_emulation_egress_fault']:
                assert self.failure is None
                self.failure = dict(args=[cpu.reg_read(reg) for reg in ARGS],
                                    caller=cpu.reg_read(r.UC_RISCV_REG_RA),
                                    reason=cpu.reg_read(r.UC_RISCV_REG_T1),
                                    mstatus=cpu.reg_read(r.UC_RISCV_REG_MSTATUS),
                                    sp=cpu.reg_read(r.UC_RISCV_REG_SP), memory=memory(self),
                                    commands=len(self.commands), slots=len(self.availability))
            if 0x84058000 <= pc < 0x8405a000 and self.get32(pc) == FENCE:
                self.fences.append(self.tick)
        super().code_hook(cpu, pc, size, data)

    def execute(self, entry, args, statuses=(), worker=False, header_length=128, canary=False):
        self.egress_tracking = False
        self.prepare()
        self.hart = 7
        self.failure = None
        self.fences, self.fault_writes, self.availability, self.reads = [], [], [], []
        self.statuses = statuses
        for index, reg in enumerate(REGS):
            if reg not in (r.UC_RISCV_REG_GP, r.UC_RISCV_REG_TP):
                self.cpu.reg_write(reg, 0x13570000+index*0x101)
        self.cpu.reg_write(r.UC_RISCV_REG_RA, END)
        self.cpu.reg_write(r.UC_RISCV_REG_SP, STACK-64)
        self.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 8)
        self.cpu.reg_write(r.UC_RISCV_REG_MIE, 0x800)
        self.input_status = self.cpu.reg_read(r.UC_RISCV_REG_MSTATUS)
        self.cpu.mem_write(STACK-1024, b'\xa5'*1024)
        for index, value in enumerate(args):
            if index < 8:
                self.cpu.reg_write(ARGS[index], value)
            else:
                self.put32(STACK-64+(index-8)*4, value)
        self.cpu.mem_write(headers.LENGTHS, bytes([header_length])*8)
        if worker:
            assert entry == 0x84000b4a and args[0] == 7
            self.put32(STACK-64+8, args[1])
            self.put32(STACK-64+12, DESC)
            self.cpu.reg_write(r.UC_RISCV_REG_S1, 0xffffffff)
            self.put32(DESC, 14 << 20 | (args[1] & 0xffff))
            self.put32(DESC+4, 0)
            self.put32(DESC+20, 41)
        if canary:
            for index in range(1, 26):
                if index != 4:
                    self.put32(STATE+index*4, 0x24680000+index)
        self.before = memory(self)
        self.abi_before = [self.cpu.reg_read(reg) for reg in SAVED+[r.UC_RISCV_REG_GP, r.UC_RISCV_REG_TP]]
        self.header_tracking = self.egress_tracking = True
        self.return_pc = 0x84000b36 if worker else END
        stops = [self.return_pc]
        if self.egress_rv:
            stops.append(self.egress_rv.symbols['npu_emulation_egress_hold'])
        self.stop_pc = self.run(entry, stops)
        self.header_tracking = self.egress_tracking = False
        self.after = memory(self)
        self.writes = [(a, size, value) for a, size, value, _ in self.header_writes]
        self.io_writes = [row for row in self.writes if BRIDGE <= row[0] < BRIDGE+4096]
        return self.cpu.reg_read(r.UC_RISCV_REG_A0)


def assert_hold(h, reason, prefix):
    assert h.egress_rv and h.stop_pc == h.egress_rv.symbols['npu_emulation_egress_hold'], 'fault-hold'
    assert h.failure and h.failure['reason'] == reason, 'fault-reason'
    assert h.io_writes == io(prefix), 'submitted-prefix'
    assert h.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) == (h.input_status & ~8), 'interrupt-mask'
    assert h.cpu.reg_read(r.UC_RISCV_REG_MIE) == 0x800, 'mie-preserved'
    assert len(h.fences) == 1 and len(h.fault_writes) == 1, 'fault-publication'
    assert h.fences[0] < h.fault_writes[0][0], 'fault-order'
    frame = h.failure['sp']-48
    words = [*h.failure['args'], h.failure['caller'], reason, h.failure['mstatus'], 0]
    assert bytes(h.cpu.mem_read(frame, 48)) == struct.pack('<12I', *words), 'failed-request-frame'
    assert h.cpu.reg_read(r.UC_RISCV_REG_SP) == frame, 'held-stack'
    wanted = {base: bytearray(data) for base, data in h.failure['memory'].items()}
    struct.pack_into('<I', wanted[SRAM], STATE+16-SRAM, 1)
    wanted[STACK-1024][frame-(STACK-1024):frame-(STACK-1024)+48] = struct.pack('<12I', *words)
    assert h.after == {base: bytes(data) for base, data in wanted.items()}, 'post-fault-memory'
    assert not h.logs, 'no-fault-logging-or-release'
    h.put32(BRIDGE+0x50+7*4, 0x100)
    late = memory(h)
    reads, writes = len(h.reads), len(h.header_writes)
    h.header_tracking = h.egress_tracking = True
    assert h.run(h.stop_pc, [h.stop_pc]) == h.stop_pc
    h.header_tracking = h.egress_tracking = False
    assert memory(h) == late and len(h.reads) == reads and len(h.header_writes) == writes, 'late-ready-hold'
    return dict(reason=reason, retained_request=words, frame=hex(frame), prefix_commands=len(prefix),
                slot_reads=h.availability, irq_masked=True, late_ready_stays_held=True,
                whole_post_fault_memory_bytes=sum(map(len, h.after.values())))


def accepted_pair(original, checked, entry, args):
    old = original.execute(entry, args)
    new = checked.execute(entry, args)
    assert old == new == 0 and checked.stop_pc == END, 'successful-return'
    assert original.commands == checked.commands
    assert original.io_writes == checked.io_writes == io(checked.commands), 'successful-command-writes'
    assert original.after == checked.after, 'successful-whole-memory'
    assert original.reads == checked.reads and original.writes == checked.writes, 'successful-footprints'
    assert [original.cpu.reg_read(reg) for reg in REGS] == [checked.cpu.reg_read(reg) for reg in REGS], 'successful-registers'
    assert [checked.cpu.reg_read(reg) for reg in SAVED+[r.UC_RISCV_REG_GP, r.UC_RISCV_REG_TP]] == checked.abi_before
    assert checked.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) == checked.input_status
    assert checked.cpu.reg_read(r.UC_RISCV_REG_MIE) == 0x800
    assert not checked.fences and not checked.fault_writes and not checked.failure
    if entry == 0x8400178e:
        channel, address, length, offset, mode, first, last, *patches = args
        flags = channel | ((mode & 7) << 24) | (bool(first) << 31) | (bool(last) << 30)
        assert checked.commands == [(channel, address & 0x1fffffff, length << 16 | offset, flags, *patches)]
    return dict(entry=hex(entry), args=args, commands=checked.commands,
                compared_bytes=sum(map(len, checked.after.values())))


def accepted_cases(original, checked):
    rows = []
    for channel in range(8):
        rows.append(accepted_pair(original, checked, 0x84001582,
                                 [channel, 0x1000, 64 << 16 | 32, 0xc0000000 | channel, 11, 22, 33, 44]))
        for length, offset, address in ((0, 0, 0), (0xffff, 0xffff, 0x1000),
                                         (1, 0, 0xffffffff), (0, 1, 0xffffffff)):
            rows.append(accepted_pair(original, checked, 0x8400178e,
                                     [channel, address, length, offset, 5, 1, 1, 11, 22, 33, 44]))
    rng = random.Random(0xe9e55)
    for _ in range(96):
        channel, mode = rng.randrange(8), rng.randrange(8)
        rows.append(accepted_pair(original, checked, 0x8400178e,
                                 [channel, rng.randrange(0x1ff00000) | (rng.randrange(8) << 29),
                                  rng.randrange(0x10000), rng.randrange(0x10000), mode,
                                  rng.randrange(3), rng.randrange(3), *[rng.getrandbits(32) for _ in range(4)]]))
    return rows


def invalid_cases(h):
    rows = []
    for channel in (8, 9, 255, 0x40000000, 0xffffffff):
        h.execute(0x84001582, [channel, 0x1000, 64 << 16, 0xc0000000, 11, 22, 33, 44])
        row = assert_hold(h, 1, [])
        assert not h.availability and not h.reads, 'channel-before-mmio'
        rows.append(dict(kind='channel', value=channel, **row))
    for length, offset, address in ((0x10000, 0, 0x1000), (0xffffffff, 0, 0x1000),
                                      (32, 0x10000, 0x1000), (32, 0xffffffff, 0x1000),
                                      (2, 0, 0xffffffff), (1, 1, 0xffffffff),
                                      (0, 2, 0xffffffff), (0xffff, 0xffff, 0x1fff0000)):
        h.execute(0x8400178e, [7, address, length, offset, 5, 1, 1, 11, 22, 33, 44])
        row = assert_hold(h, 3, [])
        assert not h.commands and not h.availability and not h.reads, 'extent-before-mmio'
        rows.append(dict(kind='extent', length=length, offset=offset, address=address, **row))
    return rows


def chains(original, checked):
    cases = [
        ('copy', 0x8400160c, [7, DESC, 0, 256, 0], 1, False),
        ('split-copy', 0x8400160c, [7, DESC, 1, 256, 14], 2, False),
        ('insert', 0x840016c8, [7, original.header_base, 1, 50, DESC, 1, 256, 14, 11, 22, 33, 44], 3, False),
        ('encoded', 0x8400178e, [7, DESC, 64, 32, 1, 1, 1, 11, 22, 33, 44], 1, False),
        ('drop', 0x840017da, [7, 256, DESC], 1, False),
        ('rewrite', 0x84001e10, [7, 256, DESC], 1, False),
        ('worker-srv6', 0x84000b4a, [7, 256, DESC], 3, True),
    ]
    rows = []
    for name, entry, args, count, worker in cases:
        original.execute(entry, args, worker=worker)
        baseline = list(original.commands)
        assert len(baseline) == count and original.io_writes == io(baseline), name
        checked.execute(entry, args, worker=worker)
        assert checked.stop_pc == checked.return_pc and checked.commands == baseline
        assert original.after == checked.after and original.io_writes == checked.io_writes
        for fail_at in range(count):
            status = [0x100]*count
            status[fail_at] = 0
            old_return = original.execute(entry, args, statuses=status, worker=worker)
            assert original.io_writes == io(baseline[:fail_at]+baseline[fail_at+1:]), name
            assert original.stop_pc == original.return_pc and len(original.availability) == count
            checked.execute(entry, args, statuses=status, worker=worker)
            row = assert_hold(checked, 2, baseline[:fail_at])
            assert len(checked.availability) == fail_at+1
            assert checked.header_entries[0x840017da] == int(name == 'drop')
            rows.append(dict(name=name, failed_command=fail_at, original_return=old_return,
                             original_submissions=count-1, original_continued=True, **row))
    # The original worker reaches the drop path for a rejected header; its own failure must hold too.
    checked.execute(0x84000b4a, [7, 256, DESC], statuses=[0], worker=True, header_length=0)
    row = assert_hold(checked, 2, [])
    assert checked.header_entries[0x840017da] == 1 and len(checked.commands) == 1
    rows.append(dict(name='worker-drop-failure', **row))
    # A short packet underflows only after two submissions. The builder must not truncate -1.
    original.execute(0x84000b4a, [7, 45, DESC], worker=True)
    assert original.commands[-1][2] == 0xffff002e
    checked.execute(0x84000b4a, [7, 45, DESC], worker=True)
    row = assert_hold(checked, 3, original.commands[:2])
    assert len(checked.commands) == 2 and checked.header_entries[0x840017da] == 0
    rows.append(dict(name='worker-tail-underflow', original_encoded_bytes=65535, **row))
    checked.execute(0x84001582, [7, 0x1000, 64 << 16, 0xc0000007, 0, 0, 0, 0], statuses=[0], canary=True)
    rows.append(dict(name='preexisting-protocol-fields-retained', **assert_hold(checked, 2, [])))
    return rows


def controls(original, checked):
    rows = []
    for status in (0, 1, 0xff, 0x10000, 0xffff00ff):
        checked.execute(0x84001582, [7, 0x1000, 64 << 16, 0xc0000007, 0, 0, 0, 0], statuses=[status])
        rows.append(dict(status=status, **assert_hold(checked, 2, [])))
    for status in (0x100, 0x8000, 0xff00, 0xffffffff):
        checked.execute(0x84001582, [7, 0x1000, 64 << 16, 0xc0000007, 0, 0, 0, 0], statuses=[status])
        assert checked.stop_pc == END and len(checked.io_writes) == 7 and not checked.failure
        rows.append(dict(status=status, accepted=True))
    checked.egress_missing = BRIDGE+0x50+7*4
    try:
        checked.execute(0x8400178e, [7, DESC, 64, 0, 1, 1, 1, 0, 0, 0, 0])
    except UnmodeledAccess as error:
        assert hex(checked.egress_missing) in str(error) and not checked.failure
        rows.append(dict(missing_model=str(error), interpreted_as_engine_failure=False))
    else:
        raise AssertionError('missing model accepted')
    finally:
        checked.egress_missing = None
    checked.execute(0x8400178e, [7, DESC, 64, 0, 1, 1, 1, 0, 0, 0, 0])
    assert checked.stop_pc == END and checked.commands[0][2] >> 16 == 64
    rows.append(dict(declared_fixture_backing=16, encoded_bytes=64, actual_dma_executed=False,
                     backing_proved=False, note='Width/aperture checks still permit a command beyond a hypothetical short allocation.'))
    return rows


def mutants(h):
    rows = []
    variants = [
        ('OMIT_EGRESS_CHANNEL', 0x84001582, [8, 0x1000, 64 << 16, 0xc0000000, 0, 0, 0, 0], (), 1),
        ('OMIT_EGRESS_LENGTH', 0x8400178e, [7, 0x1000, 0x10000, 0, 1, 1, 1, 0, 0, 0, 0], (), 3),
        ('OMIT_EGRESS_OFFSET', 0x8400178e, [7, 0x1000, 32, 0x10000, 1, 1, 1, 0, 0, 0, 0], (), 3),
        ('OMIT_EGRESS_APERTURE', 0x8400178e, [7, 0xffffffff, 2, 0, 1, 1, 1, 0, 0, 0, 0], (), 3),
    ]
    variants += [(define, 0x84001582, [7, 0x1000, 64 << 16, 0xc0000007, 0, 0, 0, 0], (0,), 2)
                 for define in ('OMIT_EGRESS_SLOTS', 'OMIT_EGRESS_IRQ_MASK', 'OMIT_EGRESS_FENCE', 'OMIT_EGRESS_FAULT')]
    for define, entry, args, statuses, reason in variants:
        path, binary = build(define)
        h.egress_rv, _ = install(h, path)
        try:
            h.execute(entry, args, statuses=statuses)
            assert_hold(h, reason, [])
        except (AssertionError, UnmodeledAccess) as error:
            rows.append(dict(define=define, detected=True, failure=str(error), binary=binary))
        else:
            raise AssertionError('undetected mutant '+define)
    return rows


def retained_gate(egress, header, profile, reset):
    ring, _, _ = headers.order.build()
    tx, _ = headers.txdone.build()
    executions = []
    def extra(h):
        _, first = headers.order.install(h, ring)
        _, second = headers.install(h, header)
        _, third = install(h, egress)
        def code(cpu, pc, size, data):
            if 0x84054000 <= pc < 0x8405a000:
                executions.append(pc)
        h.cpu.hook_add(UC_HOOK_CODE, code)
        return first+second+third
    result = headers.txdone.retained_gate(tx, profile, reset, bridge_bytes=headers.layout.LAYOUT_HYPOTHESIS,
                                         install_extra=extra)
    assert result['name'] == 'all48-detours-installed-before-reset' and not executions
    return result


def main():
    inputs = input_bindings()
    paths = [Path(__file__), ASM, LINKER, headers.SOURCE, headers.HEADER, headers.ASM, headers.LINKER,
             headers.layout.LINKER, headers.order.LINKER, headers.txdone.LINKER]
    inputs.update({str(p.relative_to(ROOT)): headers.sha(p.read_bytes()) for p in paths})
    path, binary = build()
    header = headers.build()[1]
    profile, _ = headers.layout.build()
    reset, _ = headers.layout.build_reset()
    original = Egress(profile, reset, header)
    checked = Egress(profile, reset, header, path)
    accepted = accepted_cases(original, checked)
    invalid = invalid_cases(checked)
    integration = chains(original, checked)
    limitations = controls(original, checked)
    mutation = mutants(checked)
    gate = retained_gate(path, header, profile, reset)
    assert all(headers.sha((ROOT/name).read_bytes()) == value for name, value in inputs.items())
    result = dict(schema=1, inputs_before_after=inputs, binary=binary,
                  patches=checked.egress_patches, accepted_pairs=accepted, invalid_cases=invalid,
                  native_chains=integration, controls=limitations, mutants=mutation, retained_gate=gate,
                  limits=['Only the generic 178e builder gets pre-truncation length/offset/aperture checks; other encoders remain open.',
                          'Zero-length and upper source aliases retain native behavior; neither is physical validity proof.',
                          'Faults retain prior submissions and the failed call frame; no rollback, drain, reclamation or recovery is claimed.',
                          'Availability is an explicit per-read fixture model, not reservation, concurrency or DMA-completion proof.',
                          'Worker dispatch/drop instructions execute from the post-ingress slice; ingress ownership and full worker boot remain open.',
                          'Packet format, checksum/MTU arithmetic, source backing, cache/PMA and full NPU lifecycle/parity remain open.',
                          'No admission expansion, packaged firmware, router, Wi-Fi, protected-data or subagent change.'])
    OUT.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(result, indent=2)+'\n').encode()
    (OUT/'egress-guards.json').write_bytes(encoded)
    print(json.dumps(dict(accepted_pairs=len(accepted), invalid_cases=len(invalid), native_chains=len(integration),
                          controls=len(limitations), mutants=len(mutation), evidence_sha256=headers.sha(encoded))))


if __name__ == '__main__':
    main()
