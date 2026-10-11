#!/usr/bin/env python3
"""Independent descriptor/getter oracle, actual x86/RV32 C and native object."""
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
SOURCE = ROOT / 'firmware/npu/cold-descriptor.c'
HEADER = SOURCE.with_suffix('.h')
HARNESS = ROOT / 'tests/npu/cold-descriptor-sanitize.c'
LINKER = ROOT / 'tests/npu/cold-descriptor-probe.ld'
SELECTORS = (0, 2, 10, 11, 12, 8, 5, 7)
OFFSETS = (0, 0x22020, 0x18020, 0x19020, 0x1b020, 0x1f020, 0x6020, 0x26040)
OK, ARG, PLAN, REINIT, FAULT, STALE, CORRUPT, ORDER, PUBLISH = range(9)
STATE, WORDS, LENGTH = 0x3e904000, 0x3e920000, 1547
MAGIC, STATUS = 0x31445343, 0x80000000


def arena_valid(arena):
    return arena % 32 == 0 and 0x3e800000 <= arena <= 0x3e82dfc0


def oracle(state, words, name, args):
    s = list(state)
    def fail(error):
        s[2] = 1
        return s, error
    arena, epoch, *rest = args
    if name == 'begin' and not s[0]:
        if any(s): return s, REINIT
        if epoch != 1 or rest != [0, 0] or not arena_valid(arena): return fail(PLAN)
        s[0], s[1], s[6] = MAGIC, 1, arena
    if s[2]: return s, FAULT
    active = int(name != 'begin')
    step = s[4]
    if step > 8 or active and step == 8: return fail(CORRUPT)
    done = 0 if step < 7 else 1 if step == 7 else 3
    reserved = (1 if step == 6 else 3) if active and step >= 6 else done
    lower = 0 if step < 7 else 512
    bound = (0 if step < 6 else 512 if step == 6 else 1536) if active else (0 if step < 7 else 512 if step == 7 else 1536)
    if (not arena_valid(arena) or s[0] != MAGIC or s[1] != 1 or s[6] != arena or s[3] != active or
        s[5] != (1 << step) - 1 or s[7] != reserved or s[8] != done or
        not 0 <= s[10] <= s[9] <= bound or s[9] - s[10] > 1 or
        active and s[9] < lower or not active and (s[9] != bound or s[10] != bound)):
        return fail(CORRUPT)
    if epoch != 1: return s, STALE
    if name == 'begin':
        selector, pointer = rest
        if step == 8 or selector != SELECTORS[step] or (step < 6 and pointer or step >= 6 and (not pointer or pointer % 4)):
            return fail(ORDER)
        s[3] = 1
        if step >= 6:
            s[7] |= 1 << (step - 6)
            for index in range(lower, 512 if step == 6 else 1536):
                s[11 + index] = words[(index - lower) * 4 + 1]
    elif name == 'reserve':
        address, value, before = rest
        if (step < 6 or s[9] != s[10] or s[9] == bound or
            address != arena + OFFSETS[step] + 4 + (s[9] - lower) * 16 or value != STATUS or before != s[11 + s[9]]):
            return fail(ORDER)
        s[9] += 1
    elif name == 'publish':
        address, value = rest
        if (step < 6 or s[9] != s[10] + 1 or s[10] == bound or
            address != arena + OFFSETS[step] + 4 + (s[10] - lower) * 16 or value != STATUS):
            return fail(PUBLISH)
        s[10] += 1
    else:
        assert name == 'finish'
        reply, pointer = rest
        if (reply != (arena + OFFSETS[step]) & 0x1fffffff or s[9] != bound or s[10] != s[9] or
            (step < 6 and pointer or step >= 6 and (not pointer or pointer % 4))): return fail(PUBLISH)
        if step >= 6:
            if any(words[(index - lower) * 4 + 1] != STATUS for index in range(lower, bound)):
                return fail(PUBLISH)
            s[8] |= 1 << (step - 6)
        s[5] |= 1 << step
        s[4], s[3] = step + 1, 0
    return s, OK


class Pair:
    def __init__(self, host, elf):
        self.lib, self.rv = ctypes.CDLL(str(host)), Rv32(elf)
        self.rv.cpu.mem_map(WORDS, 0x4000)
        self.state, self.words = (ctypes.c_uint32 * LENGTH)(), (ctypes.c_uint32 * 4096)()
        self.calls = 0
        pointer = ctypes.POINTER(ctypes.c_uint32)
        for name, count in (('begin', 3), ('reserve', 5), ('publish', 4), ('finish', 3)):
            fn = getattr(self.lib, 'npu_cold_descriptor_' + name)
            fn.argtypes = [pointer] + [ctypes.c_uint32] * count + ([pointer] if name in ('begin', 'finish') else [])
            if name in ('begin', 'finish'): fn.argtypes = [pointer] + [ctypes.c_uint32] * 3 + [pointer]
            fn.restype = ctypes.c_uint32
        self.reset()

    def reset(self, state=None):
        self.state[:] = state or [0] * LENGTH
        self.words[:] = [i ^ 0x12345678 for i in range(4096)]

    def call(self, name, *args):
        want, status = oracle(self.state, self.words, name, args)
        cpu = self.rv.cpu
        cpu.mem_write(STATE, bytes(self.state)); cpu.mem_write(WORDS, bytes(self.words))
        native = list(args)
        host = list(args)
        if name in ('begin', 'finish'):
            native[-1] = WORDS if args[-1] == 1 else args[-1]
            host[-1] = self.words if args[-1] == 1 else ctypes.cast(args[-1], ctypes.POINTER(ctypes.c_uint32))
            want, status = oracle(self.state, self.words, name, (*args[:-1], native[-1]))
        for i, value in enumerate((STATE, *native)):
            cpu.reg_write(getattr(r, 'UC_RISCV_REG_A' + str(i)), value)
        cpu.reg_write(r.UC_RISCV_REG_SP, 0x84100000); cpu.reg_write(r.UC_RISCV_REG_RA, 0x84200000)
        cpu.emu_start(self.rv.symbols['npu_cold_descriptor_' + name], 0x84200000, timeout=1000000, count=300000)
        assert cpu.reg_read(r.UC_RISCV_REG_PC) == 0x84200000 and cpu.reg_read(r.UC_RISCV_REG_SP) == 0x84100000
        result = getattr(self.lib, 'npu_cold_descriptor_' + name)(self.state, *host)
        assert result == cpu.reg_read(r.UC_RISCV_REG_A0) == status, (name, args, result, status)
        assert list(self.state) == list(struct.unpack('<1547I', cpu.mem_read(STATE, 6188))) == want
        assert bytes(cpu.mem_read(WORDS, 16384)) == bytes(self.words)
        self.calls += 1
        return result

    def prefix(self, steps=6):
        self.reset()
        for step in range(steps):
            count = 0 if step < 6 else 512 if step == 6 else 1024
            self.words[:] = [i ^ (0x12345678 + step) for i in range(4096)]
            assert self.call('begin', 0x3e810000, 1, SELECTORS[step], int(bool(count))) == OK
            for i in range(count):
                address = 0x3e810000 + OFFSETS[step] + i * 16 + 4
                assert self.call('reserve', 0x3e810000, 1, address, STATUS, self.words[i * 4 + 1]) == OK
                self.words[i * 4 + 1] = STATUS
                assert self.call('publish', 0x3e810000, 1, address, STATUS) == OK
            assert self.call('finish', 0x3e810000, 1, (0x3e810000 + OFFSETS[step]) & 0x1fffffff, int(bool(count))) == OK


def suite(pair):
    controls = 0
    pair.prefix(8)
    assert list(pair.state[3:11]) == [0, 8, 255, 0x3e810000, 3, 3, 1536, 1536]
    assert pair.call('begin', 0x3e810000, 1, 0, 0) == ORDER
    pair.prefix()
    baseline = list(pair.state)
    pair.reset(baseline)
    assert pair.call('begin', 0x3e810020, 1, 5, 1) == CORRUPT
    controls += 1
    for arena in (0, 0x3e7fffff, 0x3e800001, 0x3e82dfe0, 0x3e878000, 0xffffffff):
        pair.reset(); pair.call('begin', arena, 1, 0, 0); controls += 1
    for index in range(LENGTH):
        pair.reset(); pair.state[index] = 1
        assert pair.call('begin', 0x3e810000, 1, 0, 0) != OK
        controls += 1
    for changed in range(11):
        pair.reset(baseline); pair.state[changed] ^= 1
        assert pair.call('begin', 0x3e810000, 1, 5, 1) != OK
        controls += 1
    for selector in range(16):
        if selector == 5: continue
        pair.reset(baseline)
        assert pair.call('begin', 0x3e810000, 1, selector, 1) != OK
        controls += 1
    pair.reset(baseline); assert pair.call('begin', 0x3e810000, 2, 5, 1) == STALE; controls += 1
    for mutation in range(8):
        pair.reset(baseline); assert pair.call('begin', 0x3e810000, 1, 5, 1) == OK
        address, value, before = 0x3e816024, STATUS, pair.words[1]
        if mutation == 0: address += 16
        if mutation == 1: value ^= 1
        if mutation == 2: before ^= 1
        if mutation == 3: pair.state[11] ^= 1
        if mutation == 4: pair.state[5] ^= 1
        if mutation < 5: assert pair.call('reserve', 0x3e810000, 1, address, value, before) != OK
        else:
            assert pair.call('reserve', 0x3e810000, 1, address, value, before) == OK
            pair.words[1] = STATUS
            assert pair.call('publish', 0x3e810000, 1, address + (16 if mutation == 5 else 0), STATUS ^ int(mutation == 6)) == (OK if mutation == 7 else PUBLISH)
            if mutation == 7: assert pair.call('finish', 0x3e810000, 1, 0x457, 1) == PUBLISH
        controls += 1
    pair.reset(baseline); assert pair.call('begin', 0x3e810000, 1, 5, 1) == OK
    assert pair.call('reserve', 0x3e810000, 1, 0x3e816024, STATUS, pair.words[1]) == OK
    assert pair.call('publish', 0x3e810000, 1, 0x3e816024, 0) == PUBLISH
    assert pair.state[3] == 1 and pair.state[7] == 1 and pair.state[9] == 1 and pair.state[10] == 0
    controls += 1
    pair.reset(baseline)
    assert pair.call('begin', 0x3e810000, 1, 5, 1) == OK
    for i in range(512):
        destination = 0x3e816024 + i * 16
        assert pair.call('reserve', 0x3e810000, 1, destination, STATUS, pair.words[i * 4 + 1]) == OK
        pair.words[i * 4 + 1] = STATUS
        assert pair.call('publish', 0x3e810000, 1, destination, STATUS) == OK
    active, words = list(pair.state), list(pair.words)
    for index in (0, 511):
        pair.reset(active); pair.words[:] = words; pair.words[index * 4 + 1] ^= 1
        assert pair.call('finish', 0x3e810000, 1, 0x1e816020, 1) == PUBLISH
        controls += 1
    return controls


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--name', required=True); parser.add_argument('--core-object', type=Path)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-cold-descriptor-20261010' / args.name
    assert not dest.exists(); dest.mkdir(parents=True)
    inputs = {str(path.relative_to(ROOT)): loader.sha(path) for path in (SOURCE, HEADER, HARNESS, LINKER, Path(__file__))}
    flags = ['-std=c11', '-Wall', '-Wextra', '-Werror', '-fno-builtin', '-I' + str(SOURCE.parent)]
    host, elf = dest / 'host.so', dest / 'rv32.elf'
    loader.run(['clang', *flags, '-O2', '-shared', '-fPIC', SOURCE, '-o', host], dest / 'host.log')
    obj = args.core_object.resolve() if args.core_object else SOURCE
    if args.core_object: inputs[str(obj.relative_to(ROOT))] = loader.sha(obj)
    loader.run(['clang', '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32', *flags,
                '-O2', '-nostdlib', obj, '--ld-path=' + str(shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'),
                '-Wl,-T,' + str(LINKER) + ',--no-relax', '-o', elf], dest / 'rv32.log')
    pair = Pair(host, elf); controls = suite(pair)
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1')
    sanitizer = ['clang', *flags, '-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=all']
    binary = dest / 'sanitizer'
    loader.run([*sanitizer, SOURCE, HARNESS, '-o', binary], dest / 'sanitizer-build.log')
    nominal = loader.run([binary], dest / 'sanitizer-run.log', env=env)
    mutations = {
        'skip-plan-pin': loader.once(SOURCE.read_text(), 's->arena != arena ||', ''),
        'skip-preimage': loader.once(SOURCE.read_text(), 'before != s->preimages[s->committed]', '(0 && before != s->preimages[s->committed])'),
        'skip-address': loader.once(SOURCE.read_text(), 'destination != address(s, s->committed) ||', '(0 && destination != address(s, s->committed)) ||'),
        'skip-readback': loader.once(SOURCE.read_text(), 'readback != NPU_COLD_DESCRIPTOR_STATUS', '(0 && readback != NPU_COLD_DESCRIPTOR_STATUS)'),
        'skip-full-span': loader.once(SOURCE.read_text(), 'descriptors[(i - lower(s->next)) * 4 + 1] != NPU_COLD_DESCRIPTOR_STATUS', '(0 && descriptors[(i - lower(s->next)) * 4 + 1] != NPU_COLD_DESCRIPTOR_STATUS)'),
    }
    rejected = []
    for name, text in mutations.items():
        directory = dest / name; directory.mkdir()
        source, shared = directory / 'mutant.c', directory / 'host.so'; source.write_text(text)
        loader.run(['clang', *flags, '-O2', '-shared', '-fPIC', source, '-o', shared], directory / 'build.log')
        mutant = Pair(shared, elf)
        try: suite(mutant)
        except AssertionError: rejected.append(dict(name=name, rejected=True, binary_sha256=loader.sha(shared)))
        else: raise AssertionError(('surviving-mutant', name))
    assert all(loader.sha(ROOT / path) == digest for path, digest in inputs.items())
    result = dict(passed=True, host_rv32_calls=pair.calls, controls=controls, mutants=rejected,
                  exact_core_object=bool(args.core_object), inputs=inputs,
                  sanitizer=json.loads(nominal.stdout), binary_sha256=loader.sha(elf),
                  limits=['Actual portable C with independent oracle and synthetic descriptor backing; native binding/physical ownership are separate.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, calls=pair.calls, controls=controls, mutants=len(rejected))))


if __name__ == '__main__':
    main()
