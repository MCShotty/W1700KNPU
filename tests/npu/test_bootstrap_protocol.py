#!/usr/bin/env python3
"""Bounded bootstrap policy differential/mutation tests, not full native boot.

Run with PYTHONPATH=.local/npu-reset/python-lib python3 -B
tests/npu/test_bootstrap_protocol.py. Generated files stay in protocol scratch
and the single protocol checkpoint. No platform/production host is exercised.
"""
import ctypes
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True

from unicorn import riscv_const as r

from test_barrier_protocol import ROOT, Rv32, STATE, STACK, END, digest

SOURCE = ROOT / 'firmware/npu/bootstrap.c'
BUILD = ROOT / '.local/npu-bootstrap/protocol'
REPORT = ROOT / 'research/checkpoints/2026-09-06-npu-bootstrap/bootstrap-protocol.json'
MAGIC = 0x31505342
U32 = 0xffffffff
REGS = tuple(getattr(r, 'UC_RISCV_REG_A' + str(i)) for i in range(8))
FIELDS = {'b': (0, 26), 'a': (0x100, 11), 's': (0x200, 20),
          'p': (0x300, 3), 'plan': (0x400, 12), 'control': (0x500, 16),
          'epoch': (0x600, 1)}
ARENA_WORDS = 0x800 // 4
APIS = (18, 32, 8, 23, 7, 12)
VERSION = (0x30, 10, 0)
PLAN = (0x84000000, 0x240000, 0x90c00000, 0xe000,
        0x92000000, 0x100000, 0x93000000, 0x100000,
        0x94000000, 0x10000, 0x95000000, 256)
LINKER = '''/* Standalone policy test addresses, not production placement. */
ENTRY(npu_bootstrap_init)
SECTIONS {
    . = 0x84040000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) *(.sdata*) }
    .bss : { *(.bss*) *(.sbss*) *(COMMON) }
    ASSERT(. < 0x84048000, "bootstrap policy text overflow")
}
'''


def require(condition, label, detail=None):
    if not condition:
        raise AssertionError(f'{label}: {detail}')


def words(arena, group):
    offset, count = FIELDS[group]
    return list(arena[offset // 4:offset // 4 + count])


def replace(arena, group, values):
    offset, count = FIELDS[group]
    require(len(values) == count, 'fixture layout', group)
    arena[offset // 4:offset // 4 + count] = values


def valid_plan(plan):
    # Unbounded Python endpoints and sorted neighbors avoid mirroring C's
    # unsigned subtraction and nested overlap implementation.
    ranges = sorted((plan[i], plan[i] + plan[i + 1]) for i in range(0, 12, 2))
    return (all(0x80000000 <= start < stop <= 0xc0000000 and start % 4 == 0
                for start, stop in ranges)
            and all(left[1] <= right[0] for left, right in zip(ranges, ranges[1:]))
            and plan[1] >= 0x240000 and plan[3] >= 0xe000 and plan[11] == 256)


def command(step, plan=PLAN):
    return (0x11 if step == 0 else 0x10, APIS[step],
            plan[2 * step] if 1 <= step <= 4 else 0)


def model(arena, operation, args):
    """Independent return/full-state oracle for the four bootstrap entrypoints."""
    expected = list(arena)
    s, a, b = (words(expected, group) for group in ('s', 'a', 'b'))
    plan, packet = words(expected, 'plan'), words(expected, 'p')
    fresh = (a[0] == 1 and not any(a[2:5]) and b[0] == 1
             and not any(b[1:5]))
    result = 0
    if operation == 'init':
        if not any(s) and valid_plan(plan):
            s[0], s[8:], result = MAGIC, plan, 1
        else:
            s[1] = 1
    elif operation == 'transport':
        address, length, flags = args
        result = int(s[0] == MAGIC and address == s[18] and flags == 1
                     and length in (12, 64))
    elif operation == 'begin':
        eligible = (s[0] == MAGIC and not s[1] and not s[3] and not a[1]
                    and fresh and args == (12,))
        is_version = tuple(packet) == VERSION
        is_set = s[2] < 6 and tuple(packet) == command(s[2], s[8:])
        if eligible and (is_version or is_set):
            s[5:8], s[3], a[1], result = packet, 1, 1, 1
            if not is_version and s[2] in (1, 2, 3, 4):
                s[4] |= 1 << s[2]
    elif operation == 'finish':
        if (s[0] == MAGIC and not s[1] and s[3] == a[1] == 1
                and fresh and args == (1,)):
            s[2] += int(s[5] != 0x30)
            s[3], a[1], result = 0, 0, 1
        else:
            s[1], a[0], a[2], b[4] = 1, 1, 1, 1
    else:
        raise ValueError(operation)
    for group, value in (('s', s), ('a', a), ('b', b)):
        replace(expected, group, value)
    return result, expected


def compile_pair(source=SOURCE, tag='bootstrap'):
    BUILD.mkdir(parents=True, exist_ok=True)
    linker = BUILD / 'protocol.ld'
    linker.write_text(LINKER)
    clang = shutil.which('clang')
    lld = shutil.which('ld.lld') or str(ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld')
    require(clang is not None and Path(lld).exists(), 'clang/lld available')
    common = [clang, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
              '-fno-builtin', '-I', str(SOURCE.parent),
              str(SOURCE.parent / 'barrier.c'), str(SOURCE.parent / 'admission.c'), str(source)]
    native, rv = BUILD / (tag + '.so'), BUILD / (tag + '.elf')
    commands = [common + ['-shared', '-fPIC', '-o', str(native)],
                common + ['--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
                          '-nostdlib', '-fno-stack-protector', f'--ld-path={lld}',
                          f'-Wl,-T,{linker},--no-relax', '-o', str(rv)]]
    logs = []
    for argv in commands:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=90,
                                env={**os.environ, 'TMPDIR': str(BUILD)})
        logs.append({'argv': argv, 'returncode': result.returncode,
                     'stdout': result.stdout, 'stderr': result.stderr})
        (BUILD / (tag + '-compile.json')).write_text(json.dumps(logs, indent=2) + '\n')
        require(result.returncode == 0, 'compile failed (not a mutant kill)', logs[-1])
    return native, rv


class Pair:
    def __init__(self, paths):
        self.lib = ctypes.CDLL(str(paths[0]))
        self.arena = (ctypes.c_uint32 * ARENA_WORDS)()
        self.rv = Rv32(paths[1])
        self.calls = self.bootstrap_calls = 0
        self.trace = []
        self.label = ''

    def reset(self, label):
        self.label, self.trace = label, []
        self.arena[:] = [0xa5a5a5a5] * ARENA_WORDS
        for group, (_, count) in FIELDS.items():
            replace(self.arena, group, [0] * count)
        self.rv.cpu.mem_write(STATE, bytes(self.arena))
        self.set('plan', PLAN)
        self.call('b:init')
        self.call('a:init')
        require(self.get('b') == [1] + [0] * 25, 'barrier initial state')
        require(self.get('a') == [1] + [0] * 10, 'admission initial state')

    def get(self, group):
        return words(self.arena, group)

    def set(self, group, values):
        replace(self.arena, group, values)
        self.rv.cpu.mem_write(STATE + FIELDS[group][0], struct.pack('<' + 'I' * len(values), *values))

    def poke(self, group, index, value):
        values = self.get(group)
        values[index] = value
        self.set(group, values)

    def call(self, operation, *args):
        group, name = operation.split(':')
        symbol = {'s': 'npu_bootstrap_', 'a': 'npu_admission_', 'b': 'npu_barrier_'}[group] + name
        groups = [group]
        if group == 's':
            if name == 'init':
                groups += ['plan']
            elif name in ('begin', 'finish'):
                groups += ['a', 'b'] + (['p'] if name == 'begin' else [])
        elif group == 'a' and name != 'init':
            groups += ['b'] + (['control'] if name == 'control' else [])
        native_args = [ctypes.byref(self.arena, FIELDS[key][0]) for key in groups]
        rv_args = [STATE + FIELDS[key][0] for key in groups]
        native_args += [ctypes.c_uint32(arg) for arg in args]
        rv_args += list(args)
        types = [ctypes.c_void_p] * len(groups) + [ctypes.c_uint32] * len(args)
        if group == 'b' and name == 'poll':
            native_args += [ctypes.byref(self.arena, FIELDS['epoch'][0])]
            rv_args += [STATE + FIELDS['epoch'][0]]
            types += [ctypes.c_void_p]
        is_void = (group == 'b' and name in ('init', 'fail')) or (group == 'a' and name in ('init', 'fail', 'leave'))
        function = getattr(self.lib, symbol)
        function.argtypes, function.restype = types, None if is_void else ctypes.c_uint32
        before = list(self.arena)
        oracle = model(before, name, args) if group == 's' else None
        native = function(*native_args)
        cpu = self.rv.cpu
        for register, value in zip(REGS, rv_args):
            cpu.reg_write(register, value)
        cpu.reg_write(r.UC_RISCV_REG_SP, STACK)
        cpu.reg_write(r.UC_RISCV_REG_RA, END)
        cpu.emu_start(self.rv.symbols[symbol], END, count=20000, timeout=1000000)
        require(cpu.reg_read(r.UC_RISCV_REG_PC) == END, 'RV32 bounded return', operation)
        actual = None if is_void else cpu.reg_read(r.UC_RISCV_REG_A0)
        self.trace.append({'operation': operation, 'args': list(args), 'return': native})
        require(actual == native, 'native/RV32 return', (self.label, operation, actual, native))
        require(bytes(cpu.mem_read(STATE, ARENA_WORDS * 4)) == bytes(self.arena),
                'native/RV32 full state and canaries', (self.label, operation))
        self.calls += 1
        if oracle is not None:
            self.bootstrap_calls += 1
            expected_return, expected_state = oracle
            require(native == expected_return, 'policy oracle return',
                    (self.label, operation, args, native, expected_return,
                     {key: words(before, key) for key in ('s', 'a', 'b', 'p', 'plan')}))
            differences = [(i, want, got) for i, (want, got) in
                           enumerate(zip(expected_state, self.arena)) if want != got]
            require(not differences, 'policy oracle state', (self.label, operation, differences))
        return native

    def expect(self, operation, args, expected):
        require(self.call(operation, *args) == expected, 'scenario expected return',
                (self.label, operation, args, expected))

    def init(self, plan=PLAN):
        self.set('plan', plan)
        self.expect('s:init', (), 1)

    def begin(self, packet, expected=1, length=12):
        self.set('p', packet)
        self.expect('s:begin', (length,), expected)

    def advance(self, count):
        for step in range(count):
            self.begin(command(step, self.get('s')[8:]))
            self.expect('s:finish', (1,), 1)

    def control(self, operation, epoch=1, nonce=(0, 0), status=0):
        self.set('control', [0x3f, 0, 0x3143514e, 1, 64, operation, epoch, *nonce, *([0] * 7)])
        self.expect('a:control', (64,), 1)
        reply = self.get('control')
        require(reply[2] == 0x3152514e and reply[9] == status, 'control response', reply)
        require(reply[10] == 7, 'no physical reclaim/restart capability', reply)
        return reply


def sequence(pair):
    pair.init()
    immutable_plan = pair.get('s')[8:]
    pair.set('plan', [U32] * 12)
    for step in range(7):
        for _ in range(2):
            pair.begin(VERSION)
            pair.set('p', [0x10, 32, 0xbad00000])
            require(pair.get('s')[5:8] == list(VERSION), 'version private snapshot')
            pair.expect('s:finish', (1,), 1)
            require(pair.get('s')[2] == step, 'GET must not advance SET step')
        if step == 6:
            break
        request = command(step, immutable_plan)
        pair.begin(request)
        retained = sum(1 << region for region in range(1, min(step, 4) + 1))
        require(pair.get('s')[2:5] == [step, 1, retained] and pair.get('a')[1] == 1,
                'active and retained before callback', step)
        pair.set('p', [U32, U32, U32])
        require(pair.get('s')[5:8] == list(request), 'SET private request snapshot')
        pair.begin(request, 0)
        pair.begin(VERSION, 0)
        pair.expect('s:finish', (1,), 1)
    require(pair.get('s')[2:5] == [6, 0, 30], 'six SETs retain four resource regions')
    for step in range(6):
        pair.begin(command(step), 0)


def invalid_plan(pair, plan):
    require(not valid_plan(plan), 'invalid plan fixture', plan)
    pair.set('plan', plan)
    pair.expect('s:init', (), 0)
    pair.set('plan', PLAN)
    pair.expect('s:init', (), 0)
    pair.expect('s:transport', (PLAN[10], 12, 1), 0)
    pair.begin(command(0), 0)


def accepted_plan(pair, plan):
    require(valid_plan(plan), 'valid structural plan fixture', plan)
    pair.init(plan)
    pair.advance(6)
    pair.begin(VERSION)
    pair.expect('s:finish', (1,), 1)


def transport(pair):
    pair.expect('s:transport', (PLAN[10], 12, 1), 0)
    pair.init()
    addresses = (PLAN[10], PLAN[10] + 4, PLAN[10] + 244, PLAN[10] + 256,
                 PLAN[10] - 4, PLAN[10] & 0x1fffffff, 0, U32, PLAN[0])
    flags = (0, 1, 2, 3, 0x80000001, U32)
    for length in (*range(257), U32):
        pair.expect('s:transport', (PLAN[10], length, 1), int(length in (12, 64)))
    for address in addresses:
        for flag in flags:
            for length in (0, 12, 63, 64, 65, 256, U32):
                pair.expect('s:transport', (address, length, flag),
                            int(address == PLAN[10] and flag == 1 and length in (12, 64)))
    # Faulted/active sessions still need strict control/status transport.
    pair.begin(command(0))
    pair.expect('s:transport', (PLAN[10], 64, 1), 1)
    pair.expect('s:finish', (0,), 0)
    pair.expect('s:transport', (PLAN[10], 64, 1), 1)
    pair.begin(VERSION, 0)


def bad_commands(pair):
    pair.init()
    for step in range(6):
        good = command(step)
        for other in range(6):
            if other != step:
                pair.begin(command(other), 0)
        for field, values in ((0, (*range(256), 0x10000010, U32)),
                              (1, (0, 7, 8, 10, 12, 18, 23, 32, 33, U32)),
                              (2, (0, 1, U32, good[2] ^ 4, *PLAN[::2]))):
            for value in sorted(set(values) - {good[field]}):
                altered = list(good)
                altered[field] = value
                pair.begin(altered, 0)
        for length in (*range(257), U32):
            if length != 12:
                pair.begin(good, 0, length)
        for malformed in ((0x31, 10, 0), (0x30, 0, 0), (0x30, 10, 1),
                          (0x10, 10, 0), (0x3f, 10, 0)):
            pair.begin(malformed, 0)
        pair.begin(VERSION, 0, 64)
        pair.begin(good)
        pair.expect('s:finish', (1,), 1)


def guard(pair, group, index, value, finishing=False):
    pair.init()
    if finishing:
        pair.advance(1)
        pair.begin(command(1))
    pair.poke(group, index, value)
    if finishing:
        pair.expect('s:finish', (1,), 0)
        pair.begin(VERSION, 0)
    else:
        pair.begin(command(0), 0)
        pair.begin(VERSION, 0)


def repeat_init(pair, step, inflight):
    pair.init()
    pair.advance(step)
    if inflight:
        pair.begin(command(step) if step < 6 else VERSION)
    previous = pair.get('s')
    pair.expect('s:init', (), 0)
    retained = pair.get('s')
    previous[1] = 1
    require(retained == previous, 'reinit only latches failure, preserves ownership')
    pair.begin(VERSION, 0)
    if inflight:
        pair.expect('s:finish', (1,), 0)


def partial_failure(pair, step, result, version=False):
    pair.init()
    pair.advance(step)
    pair.begin(VERSION if version else command(step))
    retained = pair.get('s')[2:]
    pair.expect('s:finish', (result,), 0)
    require(pair.get('s')[2:] == retained and pair.get('a')[1] == 1,
            'callback failure retains stage, inflight, packet, plan, resources')
    pair.expect('s:finish', (1,), 0)
    pair.begin(VERSION, 0)
    pair.expect('s:init', (), 0)
    pair.expect('a:idle', (), 3)
    require(pair.get('b')[5] == 0, 'failed callback never acknowledged')
    pair.control(3, status=6)


def completion_boundary(pair, phase):
    if phase != 'uninitialized':
        pair.init()
    if phase == 'duplicate-set':
        pair.advance(2)
    elif phase == 'duplicate-version':
        pair.begin(VERSION)
        pair.expect('s:finish', (1,), 1)
    previous = pair.get('s')[2:]
    pair.expect('s:finish', (1,), 0)
    require(pair.get('s')[2:] == previous, 'spurious finish retains completed state')
    require(pair.get('s')[1] == pair.get('a')[2] == pair.get('b')[4] == 1,
            'spurious finish faults all policy owners')
    pair.begin(VERSION, 0)
    pair.begin(command(0), 0)


def uninitialized_begin(pair):
    pair.begin(VERSION, 0)
    pair.begin(command(0), 0)
    pair.init()
    pair.begin(command(0))
    pair.expect('s:finish', (1,), 1)


def active_handler(pair):
    pair.init()
    pair.advance(1)
    pair.begin(command(1))
    for hart in range(1, 8):
        pair.expect('b:poll', (hart,), 0)
    pair.expect('a:idle', (), 0)
    require(pair.get('b')[5] == 0, 'coordinator ACK withheld by active handler')
    pair.expect('b:workers_parked', (1,), 0)
    for domain in range(5):
        pair.expect('b:record_drain', (domain, 1), 0)
    pair.expect('b:prepare', (1,), 0)
    pair.control(1, nonce=(1, 2), status=5)
    require(pair.get('a')[3:5] == [0, 0], 'active bind does not acquire session')
    pair.expect('a:irq', (8,), 2)
    pair.expect('a:irq', (22,), 0)
    pair.expect('a:begin_legacy', (), 0)
    pair.begin(command(2), 0)
    pair.expect('s:finish', (1,), 1)
    pair.expect('a:idle', (), 0)
    require(pair.get('b')[5] == 1, 'coordinator ACK only after successful callback')
    pair.expect('b:workers_parked', (1,), 1)
    pair.expect('b:reclaimable', (1,), 0)


def barrier_phase(pair, phase):
    pair.init()
    for hart in range(1, 8):
        pair.expect('b:poll', (hart,), 0)
    pair.expect('a:idle', (), 0)
    # Synthetic witnesses only, to enter the actual barrier phase APIs.
    for domain in range(5):
        pair.expect('b:record_drain', (domain, 1), 1)
    pair.expect('b:prepare', (1,), 1)
    if phase in ('released', 'armed', 'stopped'):
        pair.expect('b:release', (1,), 1)
    if phase in ('armed', 'stopped'):
        for hart in range(1, 8):
            pair.expect('b:refreshed', (hart, 1), 1)
        pair.expect('a:idle', (), 0)
        pair.expect('b:arm', (1,), 1)
    if phase == 'stopped':
        pair.expect('a:open', (), 1)
        pair.expect('a:close', (), 2)
    pair.begin(command(0), 0)
    pair.begin(VERSION, 0)


def bound_stop(pair, nonce, stopping):
    pair.init()
    pair.advance(3)
    pair.control(1, nonce=nonce)
    if stopping:
        reply = pair.control(2, nonce=nonce)
        require(reply[6] == 1, 'already stopped epoch remains one')
    pair.begin(command(3), 0)
    pair.begin(VERSION, 0)
    require(pair.get('s')[4] == 6, 'bind/STOP preserves published resources')


def unbound_stop(pair):
    pair.init()
    pair.control(2, nonce=(1, 2), status=2)
    pair.begin(command(0))
    pair.expect('s:finish', (1,), 1)


def fault_during(pair, group, inflight):
    pair.init()
    pair.advance(1)
    if inflight:
        pair.begin(command(1))
    pair.call(group + ':fail')
    pair.begin(VERSION, 0)
    pair.begin(command(1), 0)
    if inflight:
        pair.expect('s:finish', (1,), 0)
        require(pair.get('s')[3:5] == [1, 2], 'fault retains active resources')


def cases():
    result = {}

    def add(name, function, *args):
        require(name not in result, 'duplicate case', name)
        result[name] = lambda pair, fn=function, values=args: fn(pair, *values)

    add('six-commands-and-version-snapshot', sequence)
    add('strict-transport', transport)
    add('wrong-packet-fields-order-length', bad_commands)
    add('active-withholds-coordinator-ack', active_handler)
    add('unbound-stop-does-not-make-session', unbound_stop)
    add('uninitialized-begin-no-side-effects', uninitialized_begin)
    add('begin-active-single', guard, 'a', 1, 1)
    for phase in ('uninitialized', 'before-begin', 'duplicate-set', 'duplicate-version'):
        add('completion-' + phase, completion_boundary, phase)
    for region in range(6):
        for field, value, label in ((0, 0, 'zero-base'), (0, 0x7ffffffc, 'below-range'),
                                    (0, 0xc0000000, 'above-range'), (0, U32, 'wrapped-base'),
                                    (0, PLAN[2 * region] + 1, 'unaligned'),
                                    (0, 0xbffffffc, 'end-overflow'), (1, 0, 'empty'),
                                    (1, U32, 'wrapped-size')):
            plan = list(PLAN)
            plan[2 * region + field] = value
            add(f'plan-{region}-{label}', invalid_plan, plan)
    for left in range(6):
        for right in range(left + 1, 6):
            for partial in (False, True):
                plan = list(PLAN)
                plan[2 * right] = plan[2 * left] + (4 if partial else 0)
                add(f'plan-overlap-{left}-{right}-{int(partial)}', invalid_plan, plan)
    for field, values in ((1, (1, 0x23ffff)), (3, (1, 0x6800, 0xdfff)),
                          (11, (1, 12, 64, 255, 257, 512))):
        for value in values:
            plan = list(PLAN)
            plan[field] = value
            add(f'plan-size-{field}-{value}', invalid_plan, plan)
    for label, plan in (
            ('minimum-only', (0x80000000, 0x240000, 0x80240000, 0xe000,
                              0x8024e000, 1, 0x8024e004, 1, 0x8024e008, 1, 0xbfffff00, 256)),
            ('adjacent-unsorted', (0xa0000000, 0x240000, 0x81000000, 0xe000,
                                   0x8100e000, 4, 0x8100e004, 4, 0x80000000, 4, 0x8100e008, 256)),
            ('txcheck-upper-end', (0x84000000, 0x240000, 0xbfff2000, 0xe000, *PLAN[4:]))):
        add('structural-valid-' + label, accepted_plan, plan)
    for index in range(20):
        def dirty(pair, index=index):
            pair.poke('s', index, 1)
            pair.expect('s:init', (), 0)
        add(f'nonzero-initial-state-{index}', dirty)
    guards = [('s', 0, 0), ('s', 0, MAGIC ^ 1), ('s', 1, 1), ('s', 3, 2),
              ('a', 0, 0), ('a', 0, 2), ('a', 1, 2), ('a', 1, U32),
              ('a', 2, 1), ('a', 3, 1), ('a', 4, 1),
              ('b', 0, 0), ('b', 0, 2), ('b', 0, U32),
              ('b', 1, 1), ('b', 2, 1), ('b', 3, 1), ('b', 4, 1)]
    for group, index, value in guards:
        add(f'begin-guard-{group}-{index}-{value}', guard, group, index, value)
        add(f'finish-guard-{group}-{index}-{value}', guard, group, index, value, True)
    for group in ('s', 'a'):
        add('finish-missing-active-' + group, guard, group, 3 if group == 's' else 1, 0, True)
    for step in range(7):
        for inflight in (False, True):
            add(f'reinit-{step}-{int(inflight)}', repeat_init, step, inflight)
        for value in (0, 2, U32):
            if step < 6:
                add(f'partial-failure-{step}-{value}', partial_failure, step, value)
            add(f'version-failure-{step}-{value}', partial_failure, step, value, True)
    for phase in ('prepared', 'released', 'armed', 'stopped'):
        add('barrier-phase-' + phase, barrier_phase, phase)
    for group in ('a', 'b'):
        for inflight in (False, True):
            add(f'fault-{group}-{int(inflight)}', fault_during, group, inflight)
    for nonce in ((1, 0), (0, 1), (0x12345678, 0x87654321)):
        for stopping in (False, True):
            add(f'bound-stop-{nonce[0]}-{nonce[1]}-{int(stopping)}', bound_stop, nonce, stopping)
    return result


def suite(paths, selected=None):
    pair = Pair(paths)
    counts = {}
    for label, run in cases().items():
        if selected is not None and label != selected:
            continue
        start = pair.calls
        pair.reset(label)
        run(pair)
        counts[label] = pair.calls - start
    require(bool(counts), 'selected witness exists', selected)
    return {'scenarios': len(counts), 'native_rv32_call_pairs': pair.calls,
            'bootstrap_oracle_call_pairs': pair.bootstrap_calls, 'case_call_pairs': counts}


def mutations():
    return {
        'short-txcheck-accepted': ('plan->region[NPU_BOOT_TXCHECK].bytes < 0xe000u',
                                 'plan->region[NPU_BOOT_TXCHECK].bytes < 0x6800u', 'plan-size-3-26624'),
        'overlap-accepted': ('if (r->base < other->base + other->bytes &&',
                            'if (0 && r->base < other->base + other->bytes &&', 'plan-overlap-0-1-0'),
        'offset-transport-accepted': ('address == s->plan.region[NPU_BOOT_REQUEST].base &&',
                                     'address >= s->plan.region[NPU_BOOT_REQUEST].base &&', 'strict-transport'),
        'wrong-transport-flags': ('flags == 1 &&', '(flags & 1) &&', 'strict-transport'),
        'wrong-first-index': ('s->step ? 0x10u : 0x11u', 's->step ? 0x10u : 0x10u',
                              'wrong-packet-fields-order-length'),
        'wrong-address-accepted': ('if (p->value != expected)', 'if (0 && p->value != expected)',
                                   'wrong-packet-fields-order-length'),
        'begin-missing-active': ('s->inflight || a->active ||', 's->inflight ||', 'begin-guard-a-1-2'),
        'request-not-copied': ('s->packet = *p;', '(void)p;', 'six-commands-and-version-snapshot'),
        'missing-retention': ('s->retained_mask |= 1u << region;', 's->retained_mask |= 0u << region;',
                              'six-commands-and-version-snapshot'),
        'version-advances-stage': ('if (s->packet.header != 0x30)', 'if (1)',
                                   'six-commands-and-version-snapshot'),
        'failed-callback-clears-inflight': ('s->failed = 1;\n    npu_admission_fail(a, b);',
                                            's->failed = 1;\n    s->inflight = a->active = 0;\n    npu_admission_fail(a, b);',
                                            'partial-failure-1-0'),
        'non-one-callback-succeeds': ('result != 1)', 'result == 0)', 'partial-failure-1-2'),
        'reinit-clears-retained': ('invalid:\n    s->failed = 1;',
                                  'invalid:\n    s->retained_mask = 0;\n    s->failed = 1;', 'reinit-2-0'),
        'bound-session-accepted': ('!a->nonce_lo && !a->nonce_hi &&', '1 &&', 'bound-stop-1-0-0'),
    }


def main():
    tracked = [SOURCE.parent / filename for filename in
               ('bootstrap.c', 'bootstrap.h', 'barrier.c', 'barrier.h', 'admission.c', 'admission.h')]
    tracked += [Path(__file__).resolve(), ROOT / 'tests/npu/test_barrier_protocol.py',
                ROOT / 'tests/npu/emulation_layout.py']
    inputs = {str(path.relative_to(ROOT)): digest(path.read_bytes()) for path in tracked}
    source = SOURCE.read_text()
    paths = compile_pair()
    results = suite(paths)
    controls = {}
    for tag, (before, after, witness) in mutations().items():
        require(source.count(before) == 1, 'unique mutation anchor', tag)
        candidate = BUILD / (tag + '.c')
        candidate.write_text(source.replace(before, after))
        mutant_paths = compile_pair(candidate, tag)
        # Compilation is outside the catch: a broken mutant is never evidence.
        try:
            suite(mutant_paths, witness)
        except AssertionError as error:
            require(str(error).startswith('policy oracle '), 'independent oracle killed mutant', str(error))
            controls[tag] = {'compiled_native_and_rv32': True, 'rejected': True,
                             'witness': witness, 'assertion': str(error),
                             'source_sha256': digest(candidate.read_bytes()),
                             'native_elf_sha256': digest(mutant_paths[0].read_bytes()),
                             'rv32_elf_sha256': digest(mutant_paths[1].read_bytes())}
        else:
            raise AssertionError('Mutation survived: ' + tag)
    require(all(digest(path.read_bytes()) == inputs[str(path.relative_to(ROOT))] for path in tracked),
            'inputs unchanged during run; rerun after concurrent edits')
    report = {'passed': True, **results, 'mutation_controls': controls,
              'mutants_compiled_and_killed': len(controls), 'inputs_sha256': inputs,
              'native_elf_sha256': digest(paths[0].read_bytes()),
              'rv32_elf_sha256': digest(paths[1].read_bytes()),
              'linker_sha256': digest((BUILD / 'protocol.ld').read_bytes()),
              'bounds': {'rv32_instructions_per_call': 20000, 'rv32_timeout_us_per_call': 1000000,
                         'compiler_timeout_seconds': 90, 'arena_bytes_compared_per_call': 2048},
              'run': 'PYTHONPATH=.local/npu-reset/python-lib python3 -B tests/npu/test_bootstrap_protocol.py',
              'scope': 'Actual bootstrap/barrier/admission C compiled as native shared library and standalone RV32. '
                       'Independent Python policy oracle; serialized coordinator calls; completed callback result modeled. '
                       'Cold-loader supplies plan. Valid means structural ranges and known binary/TX-check/request extents, '
                       'not all packet footprints or physical containment. Synthetic drain witnesses only for phase rejection. '
                       'No original native callback integration, production host, full bootstrap, platform, hardware, router or flash proof.',
              'write_scope': ['tests/npu/test_bootstrap_protocol.py', str(REPORT.relative_to(ROOT)),
                              str(BUILD.relative_to(ROOT)) + '/'],
              'ledger': 'Unchanged by this scoped test task; parent owns documentation and policy/platform changes.'}
    REPORT.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in
                      ('passed', 'scenarios', 'native_rv32_call_pairs', 'bootstrap_oracle_call_pairs',
                       'mutants_compiled_and_killed', 'native_elf_sha256', 'rv32_elf_sha256')}, indent=2))
    print('report_sha256=' + digest(REPORT.read_bytes()))


if __name__ == '__main__':
    main()
