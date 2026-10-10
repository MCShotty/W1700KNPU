#!/usr/bin/env python3
"""Retained TX write ownership, independent host/RV32 oracle and mutants."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import shutil
import struct
import sys

sys.dont_write_bytecode = True
import test_npu_firmware_loader as loader
from test_barrier_protocol import Rv32
from unicorn import riscv_const as r

ROOT = loader.ROOT
SOURCE = ROOT / 'firmware/npu/cold-tx.c'
HEADER = SOURCE.with_suffix('.h')
HARNESS = ROOT / 'tests/npu/cold-tx-sanitize.c'
LINKER = ROOT / 'tests/npu/cold-tx-probe.ld'
STATE, PLAN, VALUES = 0x3e904000, 0x3e904080, 0x3e904100
OK, ARG, BAD_PLAN, REINIT, FAULT, STALE, CORRUPT, ORDER, PUBLISH = range(9)
MAGIC = 0x31585443
ENDS, STARTS = (5, 10, 11), (0, 5, 10)


def plan_valid(p):
    arena, size, base, window, host0, host2, *_ = p
    return (arena % 32 == 0 and 0x3e800000 <= arena <= 0x3e82dfc0 and size == 303168 and
            base != 0 and base % 4096 == window % 4096 == 0 and base < 0xc0000000 and
            0xd442c <= window <= 0xc0000000 - base and host0 == base + 0xd4420 and
            (host2 == 0 or host2 - base in (0xd4450, 0xd8450) and host2 - base <= window - 12))


def fields(p, stage):
    arena, _, _, _, h0, h2, *previous = p
    if stage == 2:
        return [(0x3e900bc0, 8192, 4, previous[4])]
    regs = [arena, arena + 0x22020] if stage == 0 else [arena + 0x22020, arena + 0x4a040]
    csr = 0x1fc08030 if stage == 0 else 0x1fc48030
    return [(0x3e904700 if stage == 0 else 0x3e9046fc, h0 if stage == 0 else h2, 4, 0),
            (0x3e903978, 0, 2, 0), (0x3e9021f4, 0, 2, 0),
            (csr, regs[0] & 0x1fffffff, 4, previous[stage * 2]),
            (csr + 4, regs[1] & 0x1fffffff, 4, previous[stage * 2 + 1])]


def oracle(state, p, values, name, args):
    s = list(state)
    def fail(status):
        s[2] = 1
        return s, status
    if name == 'begin' and not s[0]:
        if any(s): return s, REINIT
        if args != (1, 0) or not plan_valid(p) or p[5]: return fail(BAD_PLAN)
        return [MAGIC, 1, 0, 1, 1, 0, 0, 0, 0, *p], OK
    if s[2]: return s, FAULT
    compared = list(p)
    if name == 'begin' and args[1] == 1:
        compared[5] = s[14]
    active = int(name != 'begin')
    stage = s[8]
    bad = (not plan_valid(compared) or s[0] != MAGIC or s[1] != 1 or s[3] != active or
           stage not in range(3) or s[9:] != compared)
    if not bad:
        bad = (s[4] != (1 << (stage + 1)) - 1 or s[5] != ((1 << stage) - 1 if active else s[4]) or
               bool(s[14]) != bool(stage) or not STARTS[stage] <= s[7] <= s[6] <= ENDS[stage] or
               s[6] - s[7] > 1 or not active and (s[6] != ENDS[stage] or s[7] != s[6]))
    if bad: return fail(CORRUPT)
    if args[0] != 1: return s, STALE
    if name == 'begin':
        if args[1] != stage + 1 or args[1] > 2 or not plan_valid(p) or not p[5]: return fail(ORDER)
        s[8], s[3], s[4], s[9:] = args[1], 1, s[4] | (1 << args[1]), list(p)
        return s, OK
    expected = fields(s[9:], stage)
    if name == 'reserve':
        if s[6] != s[7] or s[6] == ENDS[stage] or args[1:] != expected[s[6] - STARTS[stage]]:
            return fail(ORDER)
        s[6] += 1
    elif name == 'publish':
        if s[6] != s[7] + 1 or s[7] == ENDS[stage]: return fail(PUBLISH)
        address, value, size, _ = expected[s[7] - STARTS[stage]]
        if args[1:] != (address, size, value): return fail(PUBLISH)
        s[7] += 1
    else:
        assert name == 'finish'
        if s[6] != ENDS[stage] or s[7] != s[6] or list(values[:len(expected)]) != [v[1] for v in expected]:
            return fail(PUBLISH)
        s[3], s[5] = 0, s[4]
    return s, OK


class Pair:
    def __init__(self, host, elf):
        self.lib, self.rv = ctypes.CDLL(str(host)), Rv32(elf)
        self.state, self.plan = (ctypes.c_uint32 * 20)(), (ctypes.c_uint32 * 11)()
        self.values = (ctypes.c_uint32 * 5)()
        self.calls = 0
        pointer = ctypes.POINTER(ctypes.c_uint32)
        for name, count in [('begin', 2), ('reserve', 5), ('publish', 4), ('finish', 1)]:
            fn = getattr(self.lib, 'npu_cold_tx_' + name)
            fn.argtypes = [pointer, pointer] + [ctypes.c_uint32] * count + ([pointer] if name == 'finish' else [])
            fn.restype = ctypes.c_uint32
        self.reset()

    def reset(self, state=None, plan=None):
        self.state[:] = state or [0] * 20
        self.plan[:] = plan or [0x3e800000, 303168, 0x20000000, 0x100000, 0x200d4420, 0, 11, 22, 33, 44, 16384]
        self.values[:] = [0] * 5

    def call(self, name, *args):
        want, status = oracle(self.state, self.plan, self.values, name, args)
        cpu = self.rv.cpu
        cpu.mem_write(STATE, bytes(self.state)); cpu.mem_write(PLAN, bytes(self.plan)); cpu.mem_write(VALUES, bytes(self.values))
        params = (STATE, PLAN, *args, VALUES) if name == 'finish' else (STATE, PLAN, *args)
        for i, value in enumerate(params): cpu.reg_write(getattr(r, 'UC_RISCV_REG_A' + str(i)), value)
        cpu.reg_write(r.UC_RISCV_REG_SP, 0x84100000); cpu.reg_write(r.UC_RISCV_REG_RA, 0x84200000)
        cpu.emu_start(self.rv.symbols['npu_cold_tx_' + name], 0x84200000, timeout=1000000, count=300000)
        assert cpu.reg_read(r.UC_RISCV_REG_PC) == 0x84200000 and cpu.reg_read(r.UC_RISCV_REG_SP) == 0x84100000
        fn = getattr(self.lib, 'npu_cold_tx_' + name)
        result = fn(self.state, self.plan, *args, self.values) if name == 'finish' else fn(self.state, self.plan, *args)
        assert result == cpu.reg_read(r.UC_RISCV_REG_A0) == status, (name, args, status, result)
        assert list(self.state) == list(struct.unpack('<20I', cpu.mem_read(STATE, 80))) == want
        assert bytes(cpu.mem_read(PLAN, 44)) == bytes(self.plan) and bytes(cpu.mem_read(VALUES, 20)) == bytes(self.values)
        self.calls += 1
        return status

    def complete(self, stage):
        for index, event in enumerate(fields(self.plan, stage)):
            assert self.call('reserve', 1, *event) == OK
            assert self.call('publish', 1, event[0], event[2], event[1]) == OK
            self.values[index] = event[1]
        assert self.call('finish', 1) == OK


def suite(pair):
    controls = 0
    for hif in (0, 0x4000):
        pair.reset()
        for stage in range(3):
            if stage == 1: pair.plan[5] = pair.plan[2] + 0xd4450 + hif
            assert pair.call('begin', 1, stage) == OK
            pair.complete(stage)
        assert pair.state[4:8] == [7, 7, 11, 11]
    for field in range(20):
        pair.reset(); pair.state[field] = 1
        assert pair.call('begin', 1, 0) in (REINIT, CORRUPT)
        controls += 1
    for field, value in [(0,0), (0,0x3e800001), (0,0x3e82dfe0), (1,303167),
                         (2,0), (2,0x20000001), (2,0xc0000000), (3,0xd4000),
                         (3,0x100001), (3,0xb0000000), (4,0x200d4424), (5,0x200d4450)]:
        pair.reset(); pair.plan[field] = value
        assert pair.call('begin', 1, 0) == BAD_PLAN; controls += 1
    for stage in range(3):
        pair.reset()
        for previous in range(stage):
            if previous == 1: pair.plan[5] = 0x200d4450
            assert pair.call('begin', 1, previous) == OK; pair.complete(previous)
        if stage == 1: pair.plan[5] = 0x200d4450
        assert pair.call('begin', 1, stage) == OK
        baseline, plan = list(pair.state), list(pair.plan)
        assert pair.call('reserve', 2, *fields(plan, stage)[0]) == STALE
        for field in range(20):
            pair.reset(state=baseline, plan=plan); pair.state[field] ^= 1
            assert pair.call('reserve', 1, *fields(plan, stage)[0]) in (FAULT, CORRUPT, ORDER), (stage, field)
            controls += 1
        for field in range(11):
            pair.reset(state=baseline, plan=plan); pair.plan[field] ^= 1
            assert pair.call('reserve', 1, *fields(plan, stage)[0]) == CORRUPT
            controls += 1
        for index, event in enumerate(fields(plan, stage)):
            for field in range(4):
                pair.reset(state=baseline, plan=plan)
                for earlier in fields(plan, stage)[:index]:
                    assert pair.call('reserve', 1, *earlier) == OK
                    assert pair.call('publish', 1, earlier[0], earlier[2], earlier[1]) == OK
                wrong = list(event); wrong[field] ^= 1
                assert pair.call('reserve', 1, *wrong) == ORDER; controls += 1
            pair.reset(state=baseline, plan=plan)
            for earlier in fields(plan, stage)[:index]:
                assert pair.call('reserve', 1, *earlier) == OK
                assert pair.call('publish', 1, earlier[0], earlier[2], earlier[1]) == OK
            assert pair.call('reserve', 1, *event) == OK
            pending = list(pair.state)
            assert pair.call('reserve', 1, *event) == ORDER and pair.state[6] == pending[6]
            for field in range(3):
                pair.reset(state=pending, plan=plan)
                wrong = [event[0], event[2], event[1]]; wrong[field] ^= 1
                assert pair.call('publish', 1, *wrong) == PUBLISH; controls += 1
        pair.reset(state=baseline, plan=plan)
        pair.values[:len(fields(plan, stage))] = [row[1] for row in fields(plan, stage)]
        assert pair.call('finish', 1) == PUBLISH; controls += 1
    return controls


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--name', required=True); parser.add_argument('--core-object', type=Path)
    args = parser.parse_args(); assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-cold-tx-20261010' / args.name; assert not dest.exists(); dest.mkdir(parents=True)
    inputs = {str(p.relative_to(ROOT)): loader.sha(p) for p in (SOURCE, HEADER, HARNESS, LINKER, Path(__file__), Path(loader.__file__), Path(loader.extract.__file__))}
    common = [shutil.which('clang'), '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-fno-builtin', '-I' + str(SOURCE.parent)]
    host, elf = dest / 'host.so', dest / 'rv32.elf'
    loader.run(common + [SOURCE, '-shared', '-fPIC', '-o', host], dest / 'host-build.log')
    core = args.core_object.resolve() if args.core_object else SOURCE; assert core.is_relative_to(ROOT); inputs[str(core.relative_to(ROOT))] = loader.sha(core)
    lld = shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'
    loader.run(common + [core, '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32', '-nostdlib', '-fno-stack-protector',
        '--ld-path=' + str(lld), '-Wl,-T,' + str(LINKER) + ',--no-relax', '-o', elf], dest / 'rv32-build.log')
    pair = Pair(host, elf); controls = suite(pair)
    original = SOURCE.read_text()
    mutations = {
        'skip-freshness': loader.once(original, 'if (bytes[i])', 'if (0 && bytes[i])'),
        'skip-plan-pin': loader.once(original, '!same(&s->plan, p)', '(0 && !same(&s->plan, p))'),
        'skip-preimage': loader.once(original, 'before != w.before', '(before != w.before && before == 99)'),
        'skip-readback': loader.once(original, 'readback != w.value', '(readback != w.value && readback == 99)'),
        'allow-pending-claim': loader.once(original, 's->committed != s->published || s->committed == end(s->stage)', '(s->committed != s->published && s->committed == 99) || s->committed == end(s->stage)'),
        'clear-committed-fault': loader.once(original, '__atomic_store_n(&s->fault, 1, __ATOMIC_RELEASE);', '{ s->committed = s->published = 0; __atomic_store_n(&s->fault, 1, __ATOMIC_RELEASE); }'),
    }
    rows = []; sanitizer = None
    for name, contents, code in [('nominal', original, 0)] + [(n, t, -6) for n,t in mutations.items()]:
        source, binary = dest / (name + '.c'), dest / name; source.write_text(contents)
        loader.run(common + [source, HARNESS, '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-o', binary], dest / (name + '-build.log'))
        done = loader.run([binary], dest / (name + '-run.log'), accepted=code, env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1'))
        if code:
            assert 'Assertion' in done.stderr and 'AddressSanitizer' not in done.stderr
            rows.append(dict(name=name, sha256=loader.sha(binary)))
        else: sanitizer = json.loads(done.stdout)
    assert all(loader.sha(ROOT / p) == digest for p,digest in inputs.items())
    result = dict(passed=True, host_rv32_calls=pair.calls, controls=controls, mutants=rows, sanitizer=sanitizer,
                  exact_core_object=bool(args.core_object), inputs=inputs, sanitizers=['address','undefined','leak'],
                  limits=['Portable ownership C with an independent host/RV32 oracle; observations/stores/backing are modeled.',
                          'No physical register semantics, prior-user exclusion, DMA/coherency, retirement, recovery or clients are proved.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, calls=pair.calls, controls=controls, mutants=len(rows))))


if __name__ == '__main__': main()
