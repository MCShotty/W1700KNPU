#!/usr/bin/env python3
"""Fixed packet ownership C: independent host/RV32 oracle and sanitizer mutants."""
import argparse
import json
from pathlib import Path
import re
import shutil
import struct
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
from unicorn import UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r
import test_cold_page as page

ROOT = page.ROOT
CORE = ROOT / 'firmware/npu'
IDS, UNIT, WORDS, MAGIC = 16384, 2048, 519, 0x314b5043
DEFAULT = (0x8a000000, 0x2c00000)
PROBE, SANITIZE = ROOT / 'tests/npu/cold-packet-probe.c', ROOT / 'tests/npu/cold-packet-sanitize.c'


def valid(plan):
    base, size = plan
    return 0x80000000 <= base < 0xc0000000 and base % UNIT == 0 and IDS * UNIT <= size <= 0xc0000000 - base


def oracle(words, plan, name, values, null_state=False, null_plan=False):
    state = list(words)
    result = [page.ARGUMENT, page.MAX, 0, page.MAX, 0]
    if name == 'fault':
        if not null_state:
            state[2] = 1
        return state, int(not null_state), None
    if null_state or null_plan:
        return state, page.ARGUMENT, result if name == 'take' else None
    if name == 'init':
        if any(state):
            return state, page.REINIT, None
        if not values[0] or not valid(plan):
            state[2] = 1
            return state, page.BAD_PLAN, None
        state[:7] = [MAGIC, values[0], 0, 0, 0, *plan]
        return state, page.OK, None
    epoch, head, tail, ident = values
    if state[0] != MAGIC or state[2]:
        status = page.FAULT
    elif not state[1]:
        status = page.CORRUPT
    elif not epoch or epoch != state[1]:
        result[0] = page.STALE
        return state, page.STALE, result
    elif (not valid(plan) or state[5:7] != list(plan) or not 0 <= head < IDS or
          not 0 <= tail < IDS or state[3] != head or state[4] > IDS or
          state[3] != state[4] % IDS or sum(word.bit_count() for word in state[7:]) != state[4]):
        status = page.CORRUPT
    elif (head + 1) % IDS == tail:
        status = page.EMPTY
    elif not 0 <= ident < IDS:
        status = page.ID
    elif state[7 + ident // 32] & (1 << (ident % 32)):
        status = page.DUPLICATE
    else:
        state[7 + ident // 32] |= 1 << (ident % 32)
        state[3] = (head + 1) % IDS
        state[4] += 1
        return state, page.OK, [page.OK, ident, plan[0] + ident * UNIT, state[3], 1]
    state[2] = 1
    result[0] = status
    return state, status, result


class Pair(page.Pair):
    def __init__(self, paths):
        super().__init__(paths)
        self.plan[:] = DEFAULT

    def reset(self, words=None, plan=None):
        super().reset(words, plan or DEFAULT)


def build(dest, core_object=None):
    dest.mkdir()
    source = CORE / 'cold-packet.c'
    common = ['-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-fno-builtin', '-I' + str(CORE)]
    host, rv, sanitizer = [dest / name for name in ('host.so', 'rv32.elf', 'sanitize')]
    page.run(['clang', *common, source, PROBE, '-shared', '-fPIC', '-o', host], dest, 'host-build')
    lld = shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'
    page.run(['clang', *common, core_object or source, PROBE, '--target=riscv32',
              '-march=rv32imac_zicsr', '-mabi=ilp32', '-nostdlib', '-fno-stack-protector',
              '--ld-path=' + str(lld), '-Wl,-T,' + str(page.LINKER) + ',--no-relax', '-o', rv], dest, 'rv32-build')
    page.run(['gcc', *common, source, SANITIZE, '-fno-pie', '-no-pie', '-fsanitize=address,undefined',
              '-fno-sanitize-recover=all', '-o', sanitizer], dest, 'sanitizer-build')
    return host, rv, sanitizer


def suite(pair):
    controls = 0
    for plan in (DEFAULT, (0x80000000, IDS * UNIT), (0xbe000000, IDS * UNIT)):
        pair.reset(plan=plan)
        assert pair.call('init', 1) == page.OK
        for i in range(2560):
            assert pair.call('take', 1, i, 0, i * 17 % IDS) == page.OK
        assert pair.call('init', 2) == page.REINIT
        pair.call('fault')
        assert pair.call('take', 1, 2560, 0, 15000) == page.FAULT
    for field in range(WORDS):
        pair.reset()
        pair.state[field] = 1
        assert pair.call('init', 1) == page.REINIT
        controls += 1
    for plan in ((0, IDS * UNIT), (0x40000000, IDS * UNIT), (0xc0000000, IDS * UNIT),
                 (0x8a000080, IDS * UNIT), (0x8a000000, IDS * UNIT - 1),
                 (0xbe000000, IDS * UNIT + 1)):
        pair.reset(plan=plan)
        assert pair.call('init', 1) == page.BAD_PLAN
        controls += 1
    pair.reset()
    assert pair.call('init', 1) == page.OK
    baseline = list(pair.state)
    for values, expected in (((0, 0, 0, 0), page.STALE), ((2, 0, 0, 0), page.STALE),
                             ((1, IDS, 0, 0), page.CORRUPT), ((1, 0, IDS, 0), page.CORRUPT),
                             ((1, 0, 1, 0), page.EMPTY), ((1, 0, 0, IDS), page.ID),
                             ((1, 0, 0, 65535), page.ID)):
        pair.reset(baseline)
        assert pair.call('take', *values) == expected
        controls += 1
    for field, value in ((0, 0), (1, 0), (3, 1), (4, IDS + 1), (4, 1),
                         (5, DEFAULT[0] + UNIT), (6, 1), (7, 1), (WORDS - 1, 1)):
        pair.reset(baseline)
        pair.state[field] = value
        assert pair.call('take', 1, 0, 0, 0) in (page.CORRUPT, page.FAULT)
        controls += 1
    pair.reset(baseline)
    assert pair.call('take', 1, 0, 0, 37) == page.OK
    assert pair.call('take', 1, 1, 0, 37) == page.DUPLICATE
    controls += 1
    pair.reset(baseline)
    pair.state[3] = pair.state[4] = IDS - 1
    for i in range(IDS - 1):
        pair.state[7 + i // 32] |= 1 << (i % 32)
    assert pair.call('take', 1, IDS - 1, 1, IDS - 1) == page.OK
    assert pair.state[3] == 0 and pair.state[4] == IDS
    assert pair.call('take', 1, 0, 2, 0) == page.DUPLICATE
    controls += 1
    for name, values in (('init', (1,)), ('take', (1, 0, 0, 0)), ('fault', ())):
        pair.reset()
        pair.call(name, *values, null_state=True)
        if name != 'fault':
            pair.call(name, *values, null_plan=True)
        controls += 1
    return dict(calls=pair.calls, controls=controls, nominal_claims=7680, seeded_wrap=True)


def late_fault(pair):
    pair.reset()
    assert pair.call('init', 1) == page.OK
    injected = []

    def fault(cpu, access, address, size, value, data):
        if address == page.STATE + 16:
            cpu.mem_write(page.STATE + 8, struct.pack('<I', 1))
            injected.append(hex(cpu.reg_read(r.UC_RISCV_REG_PC)))

    hook = pair.rv.cpu.hook_add(UC_HOOK_MEM_WRITE, fault)
    try:
        status, state, result = pair.rv_call('take', (1, 0, 0, 37))
    finally:
        pair.rv.cpu.hook_del(hook)
    assert len(injected) == 1 and status == page.FAULT
    assert result == [page.FAULT, 37, DEFAULT[0] + 37 * UNIT, 1, 1]
    assert state[2:5] == [1, 1, 1] and state[8] == 1 << 5
    return dict(passed=True, fault_pc=injected[0], committed_claim_retained=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--core-object', type=Path)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-cold-packet-20261010' / args.name
    assert not dest.exists(), 'Choose a fresh receipt name'
    dest.mkdir(parents=True)
    core_object = args.core_object.resolve() if args.core_object else None
    if core_object:
        assert core_object.is_relative_to(ROOT) and core_object.is_file()
    paths = build(dest / 'baseline', core_object)
    page.run([paths[2]], dest / 'baseline', 'sanitize')
    with patch.object(page, 'WORDS', WORDS), patch.object(page, 'oracle', oracle):
        pair = Pair(paths)
        result = suite(pair)
        result['late_fault'] = late_fault(pair)
    text = (CORE / 'cold-page.c').read_text()
    killed = []
    mutations = {
        'omit-id-bound': ('if (id >= NPU_COLD_PAGE_IDS)', 'if (0)'),
        'omit-duplicate': ('if (s->claimed[id >> 5] & bit)', 'if (0)'),
        'omit-history': ('s->head != (s->count & (NPU_COLD_PAGE_IDS - 1))', '0'),
        'omit-population': ('if (owned != s->count)', 'if (0)'),
        'omit-head-publication': ('*q->head = (uint16_t)result.page.next_head;', '(void)result.page.next_head;'),
    }
    for name, (old, new) in mutations.items():
        assert old in text
        directory = dest / name
        directory.mkdir()
        (directory / 'cold-page.c').write_text(text.replace(old, new))
        wrapper = directory / 'cold-packet.c'
        wrapper.write_bytes((CORE / 'cold-packet.c').read_bytes())
        binary = directory / 'sanitize'
        page.run(['gcc', '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror',
                  '-I' + str(CORE), wrapper, SANITIZE, '-fno-pie', '-no-pie',
                  '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-o', binary], directory, 'build')
        page.run([binary], directory, 'reject', fail=True)
        killed.append(name)
    inputs = [CORE / 'cold-page.c', CORE / 'cold-packet.c', CORE / 'cold-packet.h', PROBE, SANITIZE, Path(__file__)]
    if core_object:
        inputs.append(core_object)
    result.update(passed=True, rejected_mutants=killed, sanitizers=['address', 'undefined', 'leak'],
                  inputs={str(p.relative_to(ROOT)): page.sha(p) for p in inputs},
                  artifacts={str(p.relative_to(ROOT)): page.sha(p) for p in sorted(dest.rglob('*')) if p.is_file()},
                  built_object=str(core_object.relative_to(ROOT)) if core_object else None,
                  limits=['Fixed cold packet ownership and queue API,not hot recycle or physical ownership/drain proof.',
                          'Near-wrap state is independently seeded,not 16383 actual native allocations.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, calls=result['calls'], controls=result['controls'], mutants=len(killed))))


if __name__ == '__main__':
    main()
