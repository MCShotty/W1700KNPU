#!/usr/bin/env python3
"""Compare native C and RV32 startup transitions, including fault controls."""
import ctypes
import json
from pathlib import Path
import random
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
from unicorn import riscv_const as r
from test_startup_native import ROOT, OUT, BUILD, STARTUP, MAGIC, sha
from test_admission_native import build_platform
from test_barrier_protocol import Rv32, STATE, STACK, END

SOURCE = ROOT / 'firmware/npu/startup.c'
REGS = [getattr(r, 'UC_RISCV_REG_A' + str(i)) for i in range(8)]
WAIT, INITIALIZE, CONTINUE, FAULT = range(4)


def build(source=SOURCE):
    BUILD.mkdir(parents=True, exist_ok=True)
    native = BUILD / (source.stem + '-protocol.so')
    subprocess.run([shutil.which('clang'), '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-fno-builtin', '-shared', '-fPIC', '-I', str(SOURCE.parent),
                    str(SOURCE.parent / 'barrier.c'), str(SOURCE.parent / 'admission.c'),
                    str(source), '-o', str(native)], check=True)
    return native, build_platform(startup=True, startup_source=source)


class Pair:
    def __init__(self, paths):
        self.native = ctypes.CDLL(str(paths[0]))
        self.rv = Rv32(paths[1])
        self.data = {'s': (ctypes.c_uint32 * 16)(), 'b': (ctypes.c_uint32 * 26)(),
                     'a': (ctypes.c_uint32 * 11)(), 'm': (ctypes.c_uint32 * 6)()}
        self.address = {'s': STARTUP, 'b': STATE, 'a': STATE+0x100, 'm': STATE+0x140}
        self.prefix = {'s': 'npu_startup_', 'b': 'npu_barrier_', 'a': 'npu_admission_'}
        self.calls = 0
        for group, value in self.data.items():
            self.replace(group, [0]*len(value))
        self.replace('s', [MAGIC, 1, 64] + [0]*13)

    def replace(self, group, values):
        self.data[group][:] = values
        self.rv.cpu.mem_write(self.address[group], struct.pack('<'+'I'*len(values), *values))

    def poke(self, group, index, value):
        values = list(self.data[group])
        values[index] = value
        self.replace(group, values)

    def check_equal(self):
        for group, values in self.data.items():
            actual = struct.unpack('<'+'I'*len(values), self.rv.cpu.mem_read(self.address[group], len(values)*4))
            assert actual == tuple(values), (group, actual, tuple(values))

    def call(self, group, name, *args):
        groups = [group]
        if group == 's' and name == 'publish':
            groups += ['b', 'a', 'm']
        elif group == 'a' and name == 'begin_legacy':
            groups += ['b']
        function = getattr(self.native, self.prefix[group] + name)
        void = group in ('b', 'a') and name == 'init'
        function.restype = None if void else ctypes.c_uint32
        expected = function(*[self.data[k] for k in groups], *[ctypes.c_uint32(n) for n in args])
        for register, value in zip(REGS, [self.address[k] for k in groups] + list(args)):
            self.rv.cpu.reg_write(register, value)
        self.rv.cpu.reg_write(r.UC_RISCV_REG_SP, STACK)
        self.rv.cpu.reg_write(r.UC_RISCV_REG_RA, END)
        self.rv.cpu.emu_start(self.rv.symbols[self.prefix[group]+name], END, count=20000, timeout=1000000)
        assert self.rv.cpu.reg_read(r.UC_RISCV_REG_PC) == END, (group, name)
        actual = None if void else self.rv.cpu.reg_read(r.UC_RISCV_REG_A0)
        assert actual == expected, (group, name, args, actual, expected)
        self.check_equal()
        self.calls += 1
        return actual

    def initialized(self):
        assert self.call('s', 'arrive', 0, 0) == INITIALIZE
        self.call('b', 'init')
        self.call('a', 'init')


def suite(paths):
    calls = cases = 0

    def finish(pair):
        nonlocal calls, cases
        calls += pair.calls
        cases += 1

    for seed in range(64):
        pair = Pair(paths)
        order = list(range(8))
        random.Random(seed).shuffle(order)
        ready = False
        for hart in order:
            expected = INITIALIZE if hart == 0 else CONTINUE if ready else WAIT
            assert pair.call('s', 'arrive', hart, 0) == expected, ('arrival', seed, hart)
            if hart == 0:
                pair.call('b', 'init')
                pair.call('a', 'init')
                assert pair.call('s', 'publish', 0) == 1
                ready = True
            assert pair.call('s', 'poll', hart) == (CONTINUE if ready else WAIT)
        assert list(pair.data['b']) == [1] + [0]*25
        assert pair.call('a', 'begin_legacy') == 0
        for hart in range(8):
            assert pair.call('s', 'poll', hart) == CONTINUE
        finish(pair)
    for group, indices in [('b', range(26)), ('a', range(11)), ('m', range(6))]:
        for index in indices:
            pair = Pair(paths)
            pair.initialized()
            pair.poke(group, index, 99)
            assert pair.call('s', 'publish', 0) == 0, ('dirty initializer', group, index)
            assert pair.data['s'][3:5] == [3, 1]
            finish(pair)
    for index, value in [(0, 0), (1, 2), (2, 60), (3, 99), (4, 1), (13, 1), (14, 1), (15, 1)]:
        for hart in (0, 1, 7):
            pair = Pair(paths)
            pair.poke('s', index, value)
            assert pair.call('s', 'arrive', hart, 0) == FAULT, ('bad header', index, hart)
            assert pair.call('s', 'poll', hart) == FAULT
            finish(pair)
    for hart in range(8):
        for warm in (1, 0xffffffff):
            pair = Pair(paths)
            assert pair.call('s', 'arrive', hart, warm) == FAULT, ('warm', hart, warm)
            finish(pair)
        pair = Pair(paths)
        pair.initialized()
        assert pair.call('s', 'publish', 0) == 1
        if hart:
            assert pair.call('s', 'arrive', hart, 0) == CONTINUE
        assert pair.call('s', 'arrive', hart, 0) == FAULT, ('duplicate', hart)
        assert pair.call('s', 'poll', 0) == FAULT
        finish(pair)
        pair = Pair(paths)
        assert pair.call('s', 'poll', hart) == FAULT, ('unregistered poll', hart)
        finish(pair)
    for hart in (8, 0xffffffff):
        pair = Pair(paths)
        assert pair.call('s', 'arrive', hart, 0) == FAULT
        finish(pair)
    for hart in range(1, 8):
        pair = Pair(paths)
        pair.initialized()
        assert pair.call('s', 'publish', hart) == 0, ('noncoordinator publish', hart)
        finish(pair)
    pair = Pair(paths)
    pair.initialized()
    pair.poke('s', 4, 1)
    assert pair.call('s', 'publish', 0) == 0
    assert pair.call('s', 'arrive', 1, 0) == FAULT
    finish(pair)
    return {'cases': cases, 'differential_calls': calls}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    paths = build()
    result = suite(paths)
    source = SOURCE.read_text()
    variants = {
        'missing-identity': ('load(&s->magic) != NPU_STARTUP_MAGIC', '(load(&s->magic) & 0)'),
        'missing-warm-rejection': ('|| warm ||', '|| (warm & 0) ||'),
        'erase-entry-before-check': ('/* A repeated reset entry',
                                     '__atomic_store_n(&s->arrived[hart], 0, __ATOMIC_RELAXED);\n    /* A repeated reset entry'),
        'wrong-initializer-owner': ('if (hart)\n        return npu_startup_poll',
                                    'if (hart == UINT32_MAX)\n        return npu_startup_poll'),
        'missing-initialized-epoch': ('load(&b->request) != 1', '(load(&b->request) & 0)'),
        'missing-mask-clear-check': ('a->deferred[i] || masked[i]', 'a->deferred[i] || (masked[i] & 0)'),
    }
    killed = {}
    for name, (old, new) in variants.items():
        assert old in source
        path = BUILD / (name + '.c')
        path.write_text(source.replace(old, new))
        mutant = build(path)
        try:
            suite(mutant)
        except AssertionError as error:
            killed[name] = str(error)
        else:
            raise AssertionError('Mutation survived: ' + name)
    result.update({'passed': True, 'source_sha256': sha(SOURCE.read_bytes()),
                   'native_sha256': sha(paths[0].read_bytes()), 'elf_sha256': sha(paths[1].read_bytes()),
                   'mutations_killed': killed,
                   'scope': 'Actual C and RV32 transitions; serialized instruction execution, not hardware atomics/cache/containment or complete boot.'})
    (OUT / 'startup-protocol-tests.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
