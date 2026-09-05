#!/usr/bin/env python3
"""Differential native/RV32 execution of coordinator admission and control ABI."""
import ctypes
import json
from pathlib import Path
import shutil
import struct
import subprocess

from unicorn import riscv_const as r

from test_barrier_protocol import ROOT, BUILD, SOURCE, Rv32, STATE, STACK, END, SCRATCH, digest

ADMISSION = ROOT / 'firmware/npu/admission.c'
OUT = ROOT / 'research/checkpoints/2026-09-05-npu-admission'
ADM, PACKET = STATE + 0x100, STATE + 0x200
REGS = (r.UC_RISCV_REG_A0, r.UC_RISCV_REG_A1, r.UC_RISCV_REG_A2, r.UC_RISCV_REG_A3)


def build_admission(source=ADMISSION, tag='admission'):
    BUILD.mkdir(parents=True, exist_ok=True)
    lld = shutil.which('ld.lld') or str(BUILD / 'lld/usr/lib/llvm-21/bin/ld.lld')
    common = [shutil.which('clang'), '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
              '-fno-builtin', '-I', str(SOURCE.parent), str(SOURCE), str(source)]
    native, rv = BUILD / (tag + '.so'), BUILD / (tag + '.elf')
    subprocess.run(common + ['-shared', '-fPIC', '-o', str(native)], check=True)
    subprocess.run(common + ['--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
                            '-nostdlib', '-fno-stack-protector', f'--ld-path={lld}',
                            '-Wl,-T,' + str(ROOT / 'tests/npu/barrier-emulation.ld') + ',--no-relax',
                            '-o', str(rv)], check=True)
    return native, rv


def packet(operation=0, epoch=0, nonce=(0, 0)):
    return [0x3f, 0, 0x3143514e, 1, 64, operation, epoch, *nonce, *([0] * 7)]


class Pair:
    def __init__(self, paths):
        self.lib = ctypes.CDLL(str(paths[0]))
        self.native_b = (ctypes.c_uint32 * 26)()
        self.native_a = (ctypes.c_uint32 * 11)()
        self.native_p = (ctypes.c_uint32 * 16)()
        self.native_epoch = ctypes.c_uint32()
        self.rv = Rv32(paths[1])
        self.calls = 0
        self.call('b:init')
        self.call('a:init')

    def call(self, operation, *args):
        group, name = operation.split(':')
        function = getattr(self.lib, ('npu_barrier_' if group == 'b' else 'npu_admission_') + name)
        native_args = [self.native_b] if group == 'b' else [self.native_a]
        rv_args = [STATE] if group == 'b' else [ADM]
        if group == 'a' and name != 'init':
            native_args.append(self.native_b)
            rv_args.append(STATE)
        if name == 'control':
            native_args.append(self.native_p)
            rv_args.append(PACKET)
        native_args.extend(ctypes.c_uint32(value) for value in args)
        rv_args.extend(args)
        if group == 'b' and name == 'poll':
            native_args.append(ctypes.byref(self.native_epoch))
            rv_args.append(SCRATCH)
        void = name == 'init' or (group == 'a' and name in ('leave', 'fail'))
        function.restype = None if void else ctypes.c_uint32
        native = function(*native_args)
        cpu = self.rv.cpu
        for register, value in zip(REGS, rv_args):
            cpu.reg_write(register, value)
        cpu.reg_write(r.UC_RISCV_REG_SP, STACK)
        cpu.reg_write(r.UC_RISCV_REG_RA, END)
        symbol = ('npu_barrier_' if group == 'b' else 'npu_admission_') + name
        cpu.emu_start(self.rv.symbols[symbol], END, count=20000, timeout=1000000)
        assert cpu.reg_read(r.UC_RISCV_REG_PC) == END, operation
        actual = None if void else cpu.reg_read(r.UC_RISCV_REG_A0)
        assert actual == native, (operation, args, actual, native)
        assert self.rv.snapshot() == tuple(self.native_b), operation
        assert struct.unpack('<11I', cpu.mem_read(ADM, 44)) == tuple(self.native_a), operation
        assert struct.unpack('<16I', cpu.mem_read(PACKET, 64)) == tuple(self.native_p), operation
        self.calls += 1
        return actual

    def expect(self, operation, args, value):
        actual = self.call(operation, *args)
        assert actual == value, (operation, args, actual, value)

    def message(self, words, length=64):
        self.native_p[:] = words
        self.rv.cpu.mem_write(PACKET, struct.pack('<16I', *words))
        handled = self.call('a:control', length)
        return handled, list(self.native_p)

    def force_active(self, value):
        self.native_a[1] = value
        self.rv.cpu.mem_write(ADM + 4, struct.pack('<I', value))


def parked(pair, epoch):
    for hart in range(1, 8):
        pair.expect('b:poll', (hart,), 0)
    pair.expect('a:idle', (), 0)
    pair.expect('b:workers_parked', (epoch,), 1)


def drained(pair, epoch):
    for domain in range(5):
        pair.expect('b:record_drain', (domain, epoch), 1)


def start(pair, epoch):
    pair.expect('b:prepare', (epoch,), 1)
    pair.expect('b:release', (epoch,), 1)
    for hart in range(1, 8):
        pair.expect('b:refreshed', (hart, epoch), 1)
    pair.expect('a:idle', (), 0)
    pair.expect('b:arm', (epoch,), 1)
    pair.expect('a:begin_legacy', (), 0)
    pair.expect('a:open', (), 1)


def running(paths):
    pair = Pair(paths)
    parked(pair, 1)
    drained(pair, 1)
    start(pair, 1)
    return pair


def suite(paths):
    count = 0
    pair = Pair(paths)
    for source in range(192):
        pair.expect('a:irq', (source,), 2 if source == 8 else 0)
        assert pair.native_b[5] == 0, 'IRQ path prematurely acknowledged coordinator'
    for invalid in (192, 193, 0xffffffff):
        pair.expect('a:irq', (invalid,), 3)
    pair.expect('a:open', (), 0)
    pair.expect('a:retire_irq', (22, 1), 0)
    parked(pair, 1)
    drained(pair, 1)
    for source in range(192):
        if source != 8:
            pair.expect('a:retire_irq', (source, 0), 0)
            pair.expect('a:retire_irq', (source, 1), 1)
    start(pair, 1)
    for source in range(192):
        pair.expect('a:irq', (source,), 2 if source == 8 else 1)
        if source != 8:
            pair.call('a:leave')
    count += pair.calls

    pair = running(paths)
    pair.expect('a:begin_legacy', (), 1)
    pair.expect('a:begin_legacy', (), 1)
    pair.expect('a:close', (), 2)
    pair.expect('a:irq', (22,), 0)
    pair.expect('a:idle', (), 0)
    assert pair.native_b[5] == 1, 'active handler acknowledged idle'
    pair.call('a:leave')
    pair.expect('a:idle', (), 0)
    assert pair.native_b[5] == 1, 'nested active handler acknowledged idle'
    pair.call('a:leave')
    parked(pair, 2)
    drained(pair, 2)
    pair.expect('a:retire_irq', (22, 1), 0)
    pair.expect('a:retire_irq', (22, 2), 1)
    start(pair, 2)
    count += pair.calls

    pair = running(paths)
    pair.expect('a:close', (), 2)
    pair.expect('a:irq', (95,), 0)
    parked(pair, 2)
    drained(pair, 2)
    pair.expect('b:prepare', (2,), 1)
    pair.expect('b:release', (2,), 1)
    for hart in range(1, 8):
        pair.expect('b:refreshed', (hart, 2), 1)
    pair.expect('a:idle', (), 0)
    assert pair.native_b[13] == 1, 'deferred IRQ incorrectly marked READY'
    pair.expect('b:arm', (2,), 0)
    pair.expect('a:open', (), 0)
    pair.expect('a:retire_irq', (95, 2), 0)
    pair.expect('a:close', (), 3)
    parked(pair, 3)
    drained(pair, 3)
    pair.expect('a:retire_irq', (95, 3), 1)
    start(pair, 3)
    count += pair.calls

    pair = running(paths)
    pair.expect('a:close', (), 2)
    parked(pair, 2)
    drained(pair, 2)
    pair.expect('b:prepare', (2,), 1)
    pair.expect('b:release', (2,), 1)
    for hart in range(1, 8):
        pair.expect('b:refreshed', (hart, 2), 1)
    pair.expect('a:idle', (), 0)
    pair.expect('a:irq', (95,), 0)
    pair.expect('b:arm', (2,), 1)
    pair.expect('a:open', (), 0)
    pair.expect('b:reclaimable', (2,), 0)
    count += pair.calls

    pair = running(paths)
    pair.expect('a:close', (), 2)
    parked(pair, 2)
    drained(pair, 2)
    pair.expect('b:reclaimable', (2,), 1)
    pair.expect('a:irq', (95,), 0)
    pair.expect('b:reclaimable', (2,), 0)
    assert pair.native_b[4] == pair.native_a[2] == 1
    count += pair.calls

    for fault in ('underflow', 'overflow', 'platform-mask-failure'):
        pair = running(paths)
        if fault == 'overflow':
            pair.force_active(0xffffffff)
            pair.expect('a:begin_legacy', (), 0)
        else:
            pair.call('a:leave' if fault == 'underflow' else 'a:fail')
        pair.expect('b:poll', (0,), 3)
        pair.expect('a:open', (), 0)
        pair.expect('a:irq', (8,), 2)
        handled, response = pair.message(packet(3))
        assert handled == 1 and response[9] == 6
        count += pair.calls

    pair = running(paths)
    for length in range(257):
        words = packet()
        handled, response = pair.message(words, length)
        assert handled == int(length == 64)
        if length != 64:
            assert response == words
    for field, value in ((0, 0x3e), (1, 1), (2, 0), (2, 0x3152514e)):
        words = packet()
        words[field] = value
        assert pair.message(words) == (0, words)
    for field, value in ((3, 0), (3, 2), (4, 0), (4, 60), (4, 68)):
        words = packet(2, 1, (0x12345678, 0x87654321))
        words[field] = value
        assert pair.message(words)[1][9] == 1
        assert pair.native_b[0] == 1
    assert pair.message(packet(2, 1))[1][9] == 2, 'unbound STOP accepted'
    assert pair.message(packet(1, 1))[1][9] == 2
    nonce = (0x12345678, 0x87654321)
    assert pair.message(packet(1, 2, nonce))[1][9] == 3
    assert pair.message(packet(1, 1, nonce))[1][9] == 0
    assert pair.message(packet(1, 1, nonce))[1][9] == 0
    assert pair.message(packet(1, 1, (nonce[0], 1)))[1][9] == 2
    assert pair.message(packet(2, 1, (nonce[0], 1)))[1][9] == 2
    assert pair.message(packet(4, 1, nonce))[1][9] == 4
    handled, response = pair.message(packet(2, 1, nonce))
    assert handled == 1 and response[6] == 2 and response[9] == 0
    assert response[10] == 7 and response[11:14] == [0, 0, 0]
    assert pair.native_a[0] == 1 and pair.native_b[5] == 1
    assert pair.message(packet(2, 1, nonce))[1][9] == 3
    assert pair.message(packet(2, 2, nonce))[1][9] == 0
    parked(pair, 2)
    response = pair.message(packet(3))[1]
    assert response[11] == 0xff and response[13] == 0
    count += pair.calls
    return count


def main():
    paths = build_admission()
    count = suite(paths)
    source = ADMISSION.read_text()
    changes = {
        'missing-active-check': ('if (s->active)\n        return NPU_BARRIER_PARK;', 'if (0)\n        return NPU_BARRIER_PARK;'),
        'missing-closed-check': ('s->fault || s->closed || !running(b)', 's->fault || !running(b)'),
        'missing-ready-pending-check': ('if (!pending(s))\n            npu_barrier_refreshed', 'if (1)\n            npu_barrier_refreshed'),
        'missing-open-pending-check': ('s->fault || s->active || pending(s) || !running(b)', 's->fault || s->active || !running(b)'),
        'missing-barrier-fault': ('__atomic_store_n(&b->fault, 1, __ATOMIC_RELEASE);', '(void)b;'),
        'missing-stop-session': ('if (!session(s, p))\n            status = NPU_CONTROL_BAD_SESSION;', 'if (0)\n            status = NPU_CONTROL_BAD_SESSION;'),
    }
    mutations = {}
    for tag, (before, after) in changes.items():
        assert source.count(before) == 1, tag
        mutation = BUILD / (tag + '.c')
        mutation.write_text(source.replace(before, after))
        try:
            suite(build_admission(mutation, tag))
        except AssertionError as error:
            mutations[tag] = {'rejected': True, 'assertion': str(error)}
        else:
            raise AssertionError('Admission suite accepted ' + tag)
    report = {'passed': True, 'native_rv32_call_pairs': count,
              'irq_sources_checked': 192, 'wire_lengths_checked': 257,
              'mutation_controls': mutations,
              'source_sha256': digest(ADMISSION.read_bytes()),
              'header_sha256': digest(ADMISSION.with_suffix('.h').read_bytes()),
              'native_elf_sha256': digest(paths[0].read_bytes()),
              'rv32_elf_sha256': digest(paths[1].read_bytes()),
              'scope': 'Actual C compiled natively and for RV32, serialized coordinator API schedules and modeled hardware drain/retirement witnesses. No native IRQ wrapper or physical device behavior in this suite.'}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'admission-protocol-tests.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
