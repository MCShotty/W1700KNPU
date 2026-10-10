#!/usr/bin/env python3
"""One-shot indication owner: independent host/RV32 oracle and sanitizer mutants."""
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
SOURCE = ROOT / 'firmware/npu/cold-indication.c'
HEADER = SOURCE.with_suffix('.h')
HARNESS = ROOT / 'tests/npu/cold-indication-sanitize.c'
LINKER = ROOT / 'tests/npu/cold-indication-probe.ld'
COUNT, STATUS, MAGIC = 1536, 0xe0000000, 0x31444e49
STATE, PLAN, WORDS = 0x3e904000, 0x3e904040, 0x3e900000
OK, ARGUMENT, BAD_PLAN, REINIT, FAULT, STALE, CORRUPT, FRESHNESS, ORDER, PUBLISH = range(10)


def oracle(state, plan, words, name, args):
    s = list(state)
    base, size = plan
    valid = base % 32 == 0 and 0x3e800000 <= base <= 0x3e878000 - COUNT * 8 and size == COUNT * 8
    if name == 'begin':
        if any(s): return s, REINIT
        if args[0] != 1 or not valid: s[2] = 1; return s, BAD_PLAN
        if any(words): s[2] = 1; return s, FRESHNESS
        return [MAGIC, 1, 0, 1, 0, 0, base, COUNT], OK
    if s[2]: return s, FAULT
    if (not valid or s[0] != MAGIC or s[1] != 1 or s[3] != 1 or s[6] != base or s[7] != COUNT or
        not 0 <= s[5] <= s[4] <= COUNT or s[4] - s[5] > 1):
        s[2] = 1; return s, CORRUPT
    if args[0] != 1: return s, STALE
    if name == 'reserve':
        index = s[4]
        bad = (index != s[5] or index == COUNT or args[1] != base + index * 8 or
               args[2] != STATUS or words[index * 2] or words[index * 2 + 1])
        if not bad: s[4] += 1; return s, OK
        s[2] = 1; return s, ORDER
    if name in ('pending', 'publish'):
        index = s[5]
        bad = s[4] != index + 1 or index == COUNT or args[1] != base + index * 8
        if not bad:
            bad = words[index * 2] != 0 or words[index * 2 + 1] != (STATUS if name == 'publish' else 0)
            if name == 'pending': bad |= args[2] != STATUS
        if bad: s[2] = 1; return s, PUBLISH if name == 'publish' else ORDER
        if name == 'publish': s[5] += 1
        return s, OK
    assert name == 'finish'
    if s[4] != COUNT or s[5] != COUNT: s[2] = 1; return s, ORDER
    if any(words[i * 2] or words[i * 2 + 1] != STATUS for i in range(COUNT)):
        s[2] = 1; return s, PUBLISH
    s[3] = 0
    return s, OK


class Pair:
    def __init__(self, host, elf):
        self.lib, self.rv = ctypes.CDLL(str(host)), Rv32(elf)
        self.state = (ctypes.c_uint32 * 8)()
        self.plan = (ctypes.c_uint32 * 2)()
        self.words = (ctypes.c_uint32 * (COUNT * 2))()
        self.calls = 0
        pointer = ctypes.POINTER(ctypes.c_uint32)
        for name, n in (('begin', 1), ('reserve', 3), ('pending', 3), ('publish', 2), ('finish', 1)):
            fn = getattr(self.lib, 'npu_cold_indication_' + name)
            fn.argtypes = [pointer, pointer] + [ctypes.c_uint32] * n + [pointer]
            fn.restype = ctypes.c_uint32
        self.reset()

    def reset(self, state=None, plan=None):
        self.state[:] = state or [0] * 8
        self.plan[:] = plan or [0x3e800000, COUNT * 8]
        self.words[:] = [0] * (COUNT * 2)

    def call(self, name, *args):
        want, status = oracle(self.state, self.plan, self.words, name, args)
        cpu = self.rv.cpu
        cpu.mem_write(STATE, struct.pack('<8I', *self.state))
        cpu.mem_write(PLAN, struct.pack('<2I', *self.plan))
        before = struct.pack('<' + 'I' * (COUNT * 2), *self.words)
        cpu.mem_write(WORDS, before)
        for i, value in enumerate((STATE, PLAN, *args, WORDS)):
            cpu.reg_write(getattr(r, 'UC_RISCV_REG_A' + str(i)), value)
        cpu.reg_write(r.UC_RISCV_REG_SP, 0x84100000)
        cpu.reg_write(r.UC_RISCV_REG_RA, 0x84200000)
        cpu.emu_start(self.rv.symbols['npu_cold_indication_' + name], 0x84200000,
                      timeout=1000000, count=300000)
        assert cpu.reg_read(r.UC_RISCV_REG_PC) == 0x84200000 and cpu.reg_read(r.UC_RISCV_REG_SP) == 0x84100000
        result = getattr(self.lib, 'npu_cold_indication_' + name)(self.state, self.plan, *args, self.words)
        assert result == cpu.reg_read(r.UC_RISCV_REG_A0) == status, (name, args, result, status)
        assert list(self.state) == list(struct.unpack('<8I', cpu.mem_read(STATE, 32))) == want
        assert bytes(cpu.mem_read(WORDS, len(before))) == before
        assert struct.pack('<' + 'I' * (COUNT * 2), *self.words) == before
        self.calls += 1
        return status


def suite(pair):
    controls = 0
    for base in (0x3e800000, 0x3e875000):
        pair.reset(plan=(base, COUNT * 8))
        assert pair.call('begin', 1) == OK
        for index in range(COUNT):
            address = base + index * 8
            assert pair.call('reserve', 1, address, STATUS) == OK
            assert pair.call('pending', 1, address, STATUS) == OK
            # Modeled platform store, not a write performed by the ownership core.
            pair.words[index * 2 + 1] = STATUS
            assert pair.call('publish', 1, address) == OK
        assert pair.call('finish', 1) == OK and pair.state[3] == 0
        assert pair.call('begin', 1) == REINIT
    for field in range(8):
        pair.reset(); pair.state[field] = 1
        assert pair.call('begin', 1) == REINIT
        controls += 1
    for field in range(COUNT * 2):
        pair.reset(); pair.words[field] = 1
        assert pair.call('begin', 1) == FRESHNESS
        controls += 1
    for plan in ((0, 12288), (0x3e800001, 12288), (0x3e875020, 12288),
                 (0x3e800000, 12287), (0x3e800000, 12289)):
        pair.reset(plan=plan); assert pair.call('begin', 1) == BAD_PLAN
        controls += 1
    pair.reset(); assert pair.call('begin', 0) == BAD_PLAN; controls += 1
    pair.reset(); assert pair.call('begin', 1) == OK
    baseline = list(pair.state)
    for name, args, expected in (
        ('reserve', (2, 0x3e800000, STATUS), STALE),
        ('reserve', (1, 0x3e800004, STATUS), ORDER),
        ('reserve', (1, 0x3e800000, STATUS | 1), ORDER),
        ('publish', (1, 0x3e800000), PUBLISH), ('finish', (1,), ORDER)):
        pair.reset(state=baseline)
        assert pair.call(name, *args) == expected; controls += 1
    for phase in range(4):
        pair.reset(state=baseline)
        assert pair.call('reserve', 1, 0x3e800000, STATUS) == OK
        if phase == 0:
            assert pair.call('reserve', 1, 0x3e800008, STATUS) == ORDER
        elif phase == 1:
            assert pair.call('publish', 1, 0x3e800000) == PUBLISH
        elif phase == 2:
            pair.state[2] = 1
            assert pair.call('pending', 1, 0x3e800000, STATUS) == FAULT
        else:
            pair.words[1] = STATUS; pair.state[2] = 1
            assert pair.call('publish', 1, 0x3e800000) == FAULT
        assert pair.state[4] == 1 and pair.state[5] == 0 and pair.state[3] == 1
        controls += 1
    return controls


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--core-object', type=Path)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-cold-indication-20261010' / args.name
    assert not dest.exists()
    dest.mkdir(parents=True)
    inputs = {str(p.relative_to(ROOT)): loader.sha(p) for p in
              (SOURCE, HEADER, HARNESS, LINKER, Path(__file__), Path(loader.__file__), Path(loader.extract.__file__))}
    common = [shutil.which('clang'), '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-fno-builtin', '-I' + str(SOURCE.parent)]
    lib, elf = dest / 'host.so', dest / 'rv32.elf'
    loader.run(common + [SOURCE, '-shared', '-fPIC', '-o', lib], dest / 'host-build.log')
    lld = shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'
    core = args.core_object.resolve() if args.core_object else SOURCE
    assert core.is_relative_to(ROOT)
    inputs[str(core.relative_to(ROOT))] = loader.sha(core)
    loader.run(common + [core, '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
        '-nostdlib', '-fno-stack-protector', '--ld-path=' + str(lld), '-Wl,-T,' + str(LINKER) + ',--no-relax', '-o', elf], dest / 'rv32-build.log')
    pair = Pair(lib, elf)
    controls = suite(pair)
    flags = ['-fsanitize=address,undefined', '-fno-sanitize-recover=all']
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1')
    def sanitized(name, source, expected=0):
        path = dest / (name + '.c'); path.write_text(source)
        binary = dest / name
        loader.run(common + [path, HARNESS, *flags, '-o', binary], dest / (name + '-build.log'))
        done = loader.run([binary], dest / (name + '-run.log'), env=env, accepted=expected)
        return done, binary
    original = SOURCE.read_text()
    nominal, _ = sanitized('sanitize', original)
    mutations = {
        'skip-freshness': loader.once(original, 'if (words[i])', 'if (0 && words[i])'),
        'allow-pending-reserve': loader.once(original, 'if (index != s->published || index == s->count ||', 'if ((index != s->published && index == 9999) || index == s->count ||'),
        'allow-wrong-value': original.replace('value != NPU_COLD_INDICATION_STATUS', '(value != NPU_COLD_INDICATION_STATUS && value == 99)'),
        'skip-readback': loader.once(original, 'words[index * 2 + 1] != NPU_COLD_INDICATION_STATUS)', '(words[index * 2 + 1] != NPU_COLD_INDICATION_STATUS && words[index * 2 + 1] == 99))'),
        'clear-committed-fault': loader.once(original, '__atomic_store_n(&s->fault, 1, __ATOMIC_RELEASE);', '{ s->committed = s->published = 0; __atomic_store_n(&s->fault, 1, __ATOMIC_RELEASE); }'),
        'allow-partial-finish': loader.once(original, 'if (s->committed != s->count || s->published != s->count)', 'if (0 && (s->committed != s->count || s->published != s->count))'),
        'skip-complete-span': loader.once(original, 'if (words[i * 2] || words[i * 2 + 1] != NPU_COLD_INDICATION_STATUS)', 'if (0 && (words[i * 2] || words[i * 2 + 1] != NPU_COLD_INDICATION_STATUS))'),
    }
    rejected = []
    for name, source in mutations.items():
        done, binary = sanitized(name, source, -6)
        assert 'Assertion' in done.stderr and 'AddressSanitizer' not in done.stderr
        rejected.append(dict(name=name, sha256=loader.sha(binary)))
    assert all(loader.sha(ROOT / p) == expected for p, expected in inputs.items())
    result = dict(passed=True, host_rv32_calls=pair.calls, controls=controls, sanitizer=json.loads(nominal.stdout),
                  mutants=rejected, inputs=inputs, exact_core_object=bool(args.core_object),
                  rv32_elf_sha256=loader.sha(elf), sanitizers=['address', 'undefined', 'leak'],
                  limits=['Actual ownership core C on host and RV32 against an independent oracle; backing/platform stores modeled.',
                          'Native caller integration and physical exclusion/coherency/drains are separate contracts. No reset/retirement API exists.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, host_rv32_calls=pair.calls, controls=controls, mutants=len(rejected))))


if __name__ == '__main__':
    main()
