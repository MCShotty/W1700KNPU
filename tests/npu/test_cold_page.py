#!/usr/bin/env python3
"""Same cold-page ownership C on host/RV32, independent oracle and fault controls."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
from unicorn import UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r
from test_barrier_protocol import Rv32

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'firmware/npu/cold-page.c'
HEADER = SOURCE.with_suffix('.h')
PROBE = ROOT / 'tests/npu/cold-page-probe.c'
LINKER = PROBE.with_suffix('.ld')
SANITIZE = ROOT / 'tests/npu/cold-page-sanitize.c'
STATE, PLAN, RESULT = 0x3e906000, 0x3e907000, 0x3e907020
WORDS, MAGIC, MAX = 263, 0x31475043, 0xffffffff
OK, ARGUMENT, BAD_PLAN, REINIT, FAULT, STALE, CORRUPT, EMPTY, ID, DUPLICATE = range(10)
REGS = [getattr(r, 'UC_RISCV_REG_A' + str(i)) for i in range(8)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, dest, name, fail=False):
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1')
    result = subprocess.run(list(map(str, command)), cwd=ROOT, capture_output=True,
                            text=True, timeout=180, env=env)
    (dest / (name + '.stdout')).write_text(result.stdout)
    (dest / (name + '.stderr')).write_text(result.stderr)
    assert (result.returncode != 0 if fail else result.returncode == 0), (command, result.returncode, result.stderr[-3000:])
    return result


def build(dest, source=SOURCE):
    dest.mkdir()
    common = ['-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror',
              '-fno-builtin', '-I' + str(SOURCE.parent), source]
    lib, elf, sanitizer = (dest / name for name in ('host.so', 'rv32.elf', 'sanitize'))
    run(['clang', *common, PROBE, '-shared', '-fPIC', '-o', lib], dest, 'host-build')
    lld = shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'
    run(['clang', *common, PROBE, '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
         '-nostdlib', '-fno-stack-protector', '--ld-path=' + str(lld),
         '-Wl,-T,' + str(LINKER) + ',--no-relax', '-o', elf], dest, 'rv32-build')
    run(['gcc', *common, SANITIZE, '-fno-pie', '-no-pie', '-fsanitize=address,undefined',
         '-fno-sanitize-recover=all', '-o', sanitizer], dest, 'sanitizer-build')
    return lib, elf, sanitizer


def plan_valid(p):
    base, size = p
    return 0x80000000 <= base < 0xc0000000 and base % 128 == 0 and 0x100000 <= size <= 0xc0000000 - base


def oracle(words, plan, name, values, null_state=False, null_plan=False):
    state = list(words)
    result = [ARGUMENT, MAX, 0, MAX, 0]
    if name == 'fault':
        if not null_state:
            state[2] = 1
        return state, int(not null_state), None
    if null_state or null_plan:
        return state, ARGUMENT, result if name == 'take' else None
    if name == 'init':
        if any(state):
            return state, REINIT, None
        if not values[0] or not plan_valid(plan):
            state[2] = 1
            return state, BAD_PLAN, None
        state[:7] = [MAGIC, values[0], 0, 0, 0, *plan]
        return state, OK, None
    epoch, head, tail, ident = values
    if state[0] != MAGIC or state[2]:
        status = FAULT
    elif not state[1]:
        status = CORRUPT
    elif not epoch or epoch != state[1]:
        result[0] = STALE
        return state, STALE, result
    elif (not plan_valid(plan) or state[5:7] != list(plan) or not 0 <= head < 8192 or
          not 0 <= tail < 8192 or state[3] != head or state[4] > 8192 or
          state[3] != state[4] % 8192 or
          sum(x.bit_count() for x in state[7:]) != state[4]):
        status = CORRUPT
    elif (head + 1) % 8192 == tail:
        status = EMPTY
    elif not 0 <= ident < 8192:
        status = ID
    elif state[7 + ident // 32] & (1 << (ident % 32)):
        status = DUPLICATE
    else:
        state[7 + ident // 32] |= 1 << (ident % 32)
        state[3] = (head + 1) % 8192
        state[4] += 1
        result = [OK, ident, plan[0] + ident * 128, state[3], 1]
        return state, OK, result
    state[2] = 1
    result[0] = status
    return state, status, result


class Pair:
    def __init__(self, paths):
        self.lib = ctypes.CDLL(str(paths[0]))
        self.rv = Rv32(paths[1])
        self.state = (ctypes.c_uint32 * WORDS)()
        self.plan = (ctypes.c_uint32 * 2)(0x90c0e000, 0x200000)
        self.result = (ctypes.c_uint32 * 5)()
        self.calls = 0
        for name, args in (('init', 1), ('take', 4), ('fault', 0)):
            function = getattr(self.lib, 'probe_' + name)
            function.argtypes = [ctypes.POINTER(ctypes.c_uint32)]
            if name != 'fault':
                function.argtypes += [ctypes.POINTER(ctypes.c_uint32)] + [ctypes.c_uint32] * args
            if name == 'take':
                function.argtypes += [ctypes.POINTER(ctypes.c_uint32)]
            function.restype = ctypes.c_uint32

    def reset(self, words=None, plan=None):
        self.state[:] = words or [0] * WORDS
        self.plan[:] = plan or [0x90c0e000, 0x200000]

    def rv_call(self, name, values, null_state=False, null_plan=False):
        cpu = self.rv.cpu
        cpu.mem_write(STATE, struct.pack('<' + 'I' * WORDS, *self.state))
        cpu.mem_write(PLAN, struct.pack('<2I', *self.plan))
        cpu.mem_write(RESULT, bytes(20))
        args = [0 if null_state else STATE]
        if name != 'fault':
            args += [0 if null_plan else PLAN, *values]
        if name == 'take':
            args.append(RESULT)
        for register, value in zip(REGS, args):
            cpu.reg_write(register, value)
        cpu.reg_write(r.UC_RISCV_REG_SP, 0x84100000)
        cpu.reg_write(r.UC_RISCV_REG_RA, 0x84200000)
        cpu.emu_start(self.rv.symbols['probe_' + name], 0x84200000, timeout=1000000, count=200000)
        assert cpu.reg_read(r.UC_RISCV_REG_PC) == 0x84200000
        assert cpu.reg_read(r.UC_RISCV_REG_SP) == 0x84100000
        return (cpu.reg_read(r.UC_RISCV_REG_A0),
                list(struct.unpack('<' + 'I' * WORDS, cpu.mem_read(STATE, WORDS * 4))),
                list(struct.unpack('<5I', cpu.mem_read(RESULT, 20))) if name == 'take' else None)

    def call(self, name, *values, null_state=False, null_plan=False):
        wanted, status, output = oracle(self.state, self.plan, name, values, null_state, null_plan)
        rv_status, rv_state, rv_output = self.rv_call(name, values, null_state, null_plan)
        arguments = [None if null_state else self.state]
        if name != 'fault':
            arguments += [None if null_plan else self.plan, *values]
        if name == 'take':
            arguments.append(self.result)
        native = getattr(self.lib, 'probe_' + name)(*arguments)
        assert native == rv_status == status, (name, values, native, rv_status, status)
        assert list(self.state) == rv_state == wanted, (name, values, 'state')
        if name == 'take':
            assert list(self.result) == rv_output == output, (name, values, 'result')
        self.calls += 1
        return status


def suite(pair):
    controls = 0
    for plan in ((0x90c0e000, 0x200000), (0x80000000, 0x100000), (0xbff00000, 0x100000)):
        pair.reset(plan=plan)
        assert pair.call('init', 1) == OK
        for i in range(1792):
            ident = (i * 17) % 8192
            assert pair.call('take', 1, i, 0, ident) == OK
        assert pair.state[4] == 1792
        assert pair.call('init', 2) == REINIT
        pair.call('fault')
        assert pair.call('take', 1, 1792, 0, 8000) == FAULT
        assert pair.call('init', 3) == REINIT
    for plan in ((0, 0x100000), (0x40000000, 0x100000), (0xc0000000, 0x100000),
                 (0x80000001, 0x100000), (0x80000000, 0), (0x80000000, 0xfffff),
                 (0xbff00000, 0x100001), (0x90c0e000, MAX)):
        pair.reset(plan=plan)
        assert pair.call('init', 1) == BAD_PLAN
        assert pair.call('init', 2) == REINIT
        controls += 1
    for field in range(WORDS):
        pair.reset()
        pair.state[field] = 1
        assert pair.call('init', 1) == REINIT
        controls += 1
    pair.reset()
    assert pair.call('init', 0) == BAD_PLAN
    assert pair.call('init', 1) == REINIT
    pair.reset()
    assert pair.call('init', 1) == OK
    baseline = list(pair.state)
    for field, value in ((0, 0), (1, 0), (2, 1), (3, 1), (4, 8193), (4, 1),
                         (5, 0x90c0e080), (6, 0x100000), (7, 1), (WORDS - 1, 1)):
        pair.reset(baseline)
        pair.state[field] = value
        assert pair.call('take', 1, 0, 0, 3) in (FAULT, CORRUPT)
        controls += 1
    for values, expected in (((0, 0, 0, 3), STALE), ((2, 0, 0, 3), STALE),
                              ((1, 8192, 0, 3), CORRUPT), ((1, 0, 8192, 3), CORRUPT),
                              ((1, 0, 1, 3), EMPTY), ((1, 0, 0, 8192), ID),
                              ((1, 0, 0, MAX), ID)):
        pair.reset(baseline)
        assert pair.call('take', *values) == expected
        controls += 1
    pair.reset(baseline)
    assert pair.call('take', 1, 0, 0, 11) == OK
    assert pair.call('take', 1, 1, 0, 11) == DUPLICATE
    assert pair.call('take', 1, 1, 0, 12) == FAULT
    assert pair.call('init', 2) == REINIT
    controls += 1
    # Matching native and private cursors can still contradict claim history.
    pair.reset(baseline)
    pair.state[3] = 17
    assert pair.call('take', 1, 17, 0, 12) == CORRUPT
    controls += 1
    # A reachable near-wrap state, generated by the independent ownership set.
    pair.reset(baseline)
    pair.state[3] = pair.state[4] = 8191
    for i in range(8191):
        pair.state[7 + i // 32] |= 1 << (i % 32)
    assert pair.call('take', 1, 8191, 1, 8191) == OK
    assert pair.state[3] == 0 and pair.state[4] == 8192
    assert pair.call('take', 1, 0, 2, 0) == DUPLICATE
    controls += 1
    for name, values in (('init', (1,)), ('take', (1, 0, 0, 0)), ('fault', ())):
        pair.reset()
        pair.call(name, *values, null_state=True)
        if name != 'fault':
            pair.call(name, *values, null_plan=True)
        controls += 1
    return dict(differential_calls=pair.calls, controls=controls, nominal_claims=5376,
                seeded_wrap_control=True, physical_ownership_proved=False)


def late_fault(pair):
    pair.reset()
    assert pair.call('init', 1) == OK
    injected = []

    def fault(cpu, access, address, size, value, _):
        if address == STATE + 16:
            cpu.mem_write(STATE + 8, struct.pack('<I', 1))
            injected.append(dict(pc=hex(cpu.reg_read(r.UC_RISCV_REG_PC)), address=hex(address)))

    hook = pair.rv.cpu.hook_add(UC_HOOK_MEM_WRITE, fault)
    try:
        status, state, result = pair.rv_call('take', (1, 0, 0, 37))
    finally:
        pair.rv.cpu.hook_del(hook)
    assert len(injected) == 1 and status == FAULT
    assert result == [FAULT, 37, pair.plan[0] + 37 * 128, 1, 1]
    assert state[2:5] == [1, 1, 1] and state[8] == 1 << 5
    return dict(passed=True, injected=injected, status=status, result=result,
                ownership_retained=True, native_queue_commit_or_readiness_proved=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-cold-page-20261001' / args.name
    assert not dest.exists(), 'Choose a fresh result name'
    dest.mkdir(parents=True)
    paths = build(dest / 'baseline')
    sanitized = run([paths[2]], dest / 'baseline', 'sanitize')
    assert 'PASS cold-page sanitizer' in sanitized.stdout
    pair = Pair(paths)
    result = suite(pair)
    result['late_fault'] = late_fault(pair)
    text = SOURCE.read_text()
    mutations = {
        'omit-reinit-metadata': text.replace('if (s->magic || s->epoch || faulted(s) || s->head || s->count ||\n        s->packet_base || s->packet_bytes)', 'if (0)'),
        'omit-id-bound': text.replace('if (id >= NPU_COLD_PAGE_IDS)', 'if (0)'),
        'omit-duplicate': text.replace('if (s->claimed[id >> 5] & bit)', 'if (0)'),
        'omit-epoch': text.replace('if (!epoch || epoch != s->epoch)', 'if (!epoch && epoch != s->epoch)'),
        'omit-head-match': text.replace('s->head != head ||', ''),
        'omit-cursor-history': text.replace('s->head != (s->count & (NPU_COLD_PAGE_IDS - 1))', '0'),
        'omit-population': text.replace('if (owned != s->count)', 'if (owned != s->count && s->count > NPU_COLD_PAGE_IDS)'),
        'omit-claim-record': text.replace('s->claimed[id >> 5] |= bit;', '(void)bit;'),
        'clear-fault': text.replace('__atomic_store_n(&s->fault, 1, __ATOMIC_RELEASE);', '__atomic_store_n(&s->fault, 0, __ATOMIC_RELEASE);'),
        'omit-backing-end': text.replace('p->packet_bytes <= 0xc0000000u - p->packet_base', 'p->packet_bytes <= UINT32_MAX - p->packet_base'),
    }
    killed = []
    for name, source in mutations.items():
        assert source != text
        directory = dest / name
        directory.mkdir()
        file = directory / 'cold-page.c'
        file.write_text(source)
        binary = directory / 'sanitize'
        run(['gcc', '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror',
             '-I' + str(SOURCE.parent), file, SANITIZE, '-fno-pie', '-no-pie',
             '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-o', binary], directory, 'build')
        run([binary], directory, 'reject', fail=True)
        killed.append(name)
    result.update(passed=True, rejected_mutants=killed,
                  sanitizers=dict(address=True, undefined=True, leak=True),
                  inputs={str(p.relative_to(ROOT)): sha(p) for p in (SOURCE, HEADER, PROBE, LINKER, SANITIZE, Path(__file__))},
                  artifacts={str(p.relative_to(ROOT)): sha(p) for p in sorted(dest.rglob('*')) if p.is_file()},
                  limits=['Shared cold ownership core, not a wired native callback or physical page-pool proof.',
                          'Queue snapshot validity, exclusion, storage and native-head publication remain caller contracts.',
                          'RV32 late-fault injection proves retained core state,not physical drain/reclaim/readiness.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result | {'inputs': len(result['inputs']), 'artifacts': len(result['artifacts'])}))


if __name__ == '__main__':
    main()
