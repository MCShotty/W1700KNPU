#!/usr/bin/env python3
"""Full six-selector C/RV32 owner with an independent original-store oracle."""
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
SOURCE = ROOT / 'firmware/npu/cold-tx-buffer.c'
HEADER = SOURCE.with_suffix('.h')
HARNESS = ROOT / 'tests/npu/cold-tx-buffer-sanitize.c'
LINKER = ROOT / 'tests/npu/cold-tx-buffer-probe.ld'
STATE, PLAN, META, RECORDS, END = 0x84140000, 0x84180000, 0x3e908000, 0x3e910000, 0x84200000
WORDS, STORES = 53300, 53260
SELECTORS, COUNTS = (0, 5, 10, 2, 7, 12), (1, 16385, 2052, 1, 32769, 2052)
PROFILE = [0x3e810000, 0x20000000, 0x100000,
           *[0x96000000 + i * 0x100000 for i in range(6)],
           *[0x83000000 + i * 0x100000 for i in range(8)],
           0x84000000, 0xa00000, 0x90c00000, 0xe000, 0x8a000000, 0x2c00000,
           0x8cc00000, 0x4000000, 0x90c0e000, 0x200000, 0x83000000, 256]


def metadata_count(step):
    return 4 if step in (2, 5) else 1


def original(step, index, profile=PROFILE):
    slots = (0x3e902cf8, 0x3e901f38, 0x3e903960, 0x3e902ab4, 0x3e902abc, 0x3e902a88)
    counters = ((0x3e90462c, 0x3e90395a, 0x3e902acc), (0x3e902a8c, 0x3e90390c, 0x3e9021e8))
    band, internal = int(step >= 3), step in (1, 4)
    base = profile[0] + (0x2a040 if band else 0x8020) if internal else (0x3e8a4020 if band else 0x3e8a2000)
    if index == 0:
        return slots[step], 4, base if internal else (profile[3 + step] & 0x3fffffff) | 0x40000000
    if index < metadata_count(step):
        return counters[band][index - 1], 2 if index < 3 else 4, 0 if index < 3 else base
    word = index - metadata_count(step)
    if internal:
        return base + 4 * word, 4, 0x100000 if word % 32 == 0 else 0x10000 if word % 32 == 31 else 0
    return base + 4 * word, 1 if word % 4 == 3 else 4, 0 if word % 4 else ((profile[3 + step] + word // 4 * 256) & 0x3fffffff) | 0x80000000


class Pair:
    def __init__(self, host, elf):
        self.lib, self.rv = ctypes.CDLL(str(host)), Rv32(elf)
        self.rv.cpu.mem_map(META, 0x28000)
        self.state = (ctypes.c_uint32 * WORDS)()
        self.plan = (ctypes.c_uint32 * 29)(*PROFILE)
        self.metadata = (ctypes.c_uint32 * 4)()
        self.records = (ctypes.c_uint32 * 32768)()
        pointer, integer = ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint32
        signatures = {
            'begin': [pointer, pointer, integer, integer, integer, pointer, pointer],
            'reserve': [pointer, pointer, integer, integer, integer, integer, integer],
            'publish': [pointer, pointer, integer, integer, integer, integer],
            'finish': [pointer, pointer, integer, pointer, pointer],
            'dma_valid': [pointer, integer], 'plan_valid': [pointer]
        }
        for name, signature in signatures.items():
            function = getattr(self.lib, 'npu_cold_txbuf_' + name)
            function.argtypes, function.restype = signature, integer
        self.calls = self.stores = 0
        self.restore((bytes(self.state), bytes(self.plan), bytes(self.metadata), bytes(self.records)))

    def invoke(self, name, host, native):
        actual = getattr(self.lib, 'npu_cold_txbuf_' + name)(*host)
        cpu = self.rv.cpu
        for i, value in enumerate(native):
            cpu.reg_write(getattr(r, 'UC_RISCV_REG_A' + str(i)), value)
        cpu.reg_write(r.UC_RISCV_REG_SP, 0x84100000)
        cpu.reg_write(r.UC_RISCV_REG_RA, END)
        cpu.emu_start(self.rv.symbols['npu_cold_txbuf_' + name], END, timeout=2000000, count=4000000)
        assert cpu.reg_read(r.UC_RISCV_REG_PC) == END and cpu.reg_read(r.UC_RISCV_REG_SP) == 0x84100000
        assert actual == cpu.reg_read(r.UC_RISCV_REG_A0), (name, actual)
        assert bytes(self.state)[:160] == bytes(cpu.mem_read(STATE, 160)), name
        self.calls += 1
        return actual

    def call(self, name, *args, epoch=1):
        host, native = [self.state, self.plan, epoch], [STATE, PLAN, epoch]
        if name == 'begin':
            step = args[0]
            host += [SELECTORS[step], self.plan[3 + step], self.metadata, self.records if COUNTS[step] > 1 else None]
            native += [SELECTORS[step], self.plan[3 + step], META, RECORDS if COUNTS[step] > 1 else 0]
        elif name == 'finish':
            step = args[0]
            host += [self.metadata, self.records if COUNTS[step] > 1 else None]
            native += [META, RECORDS if COUNTS[step] > 1 else 0]
        else:
            host += list(args)
            native += list(args)
        return self.invoke(name, host, native)

    def snapshot(self):
        values = tuple(bytes(value) for value in (self.state, self.plan, self.metadata, self.records))
        for address, value in zip((STATE, PLAN, META, RECORDS), values):
            assert bytes(self.rv.cpu.mem_read(address, len(value))) == value
        return values

    def restore(self, values):
        for address, array, value in zip((STATE, PLAN, META, RECORDS), (self.state, self.plan, self.metadata, self.records), values):
            ctypes.memmove(array, value, len(value))
            self.rv.cpu.mem_write(address, value)

    def inputs(self, step):
        self.metadata[:] = [0xdeadbeef, 0x1234, 0xabcd, 0xcafef00d]
        self.records[:] = [(i * 0x9e3779b1 ^ 0xa5c3e7f9) & 0xffffffff for i in range(32768)]
        self.rv.cpu.mem_write(META, bytes(self.metadata))
        self.rv.cpu.mem_write(RECORDS, bytes(self.records))

    def cell(self, step, index, value=None):
        meta = metadata_count(step)
        array, offset, address = (self.metadata, index, META) if index < meta else (self.records, index - meta, RECORDS)
        before = array[offset]
        if value is not None:
            array[offset] = value
            self.rv.cpu.mem_write(address + offset * 4, struct.pack('<I', value))
        return before


def suite(pair):
    controls, partials, starts, ends = 0, [], [], []
    total = 0
    for step, count in enumerate(COUNTS):
        pair.inputs(step)
        assert pair.call('begin', step) == 0
        starts.append(pair.snapshot())
        meta = metadata_count(step)
        preimages = list(pair.metadata)[:meta] + list(pair.records)[:count - meta]
        assert list(pair.state)[40 + total:40 + total + count] == preimages
        for index in range(count):
            address, width, value = original(step, index)
            before = pair.cell(step, index)
            if index == count - 1:
                partials.append(pair.snapshot())
            assert pair.call('reserve', address, width, value, before) == 0
            assert pair.state[7] == total + index + 1 and pair.state[8] == total + index
            assert pair.state[40 + total + index] == before
            readback = before & 0xffffff00 | value if width == 1 else value
            pair.cell(step, index, readback)
            assert pair.call('publish', address, width, readback) == 0
            pair.stores += 1
        ends.append(pair.snapshot())
        assert pair.call('finish', step) == 0
        total += count
        assert list(pair.state)[:11] == [0x31425443, 1, 0, 0, step + 1, (1 << (step + 1)) - 1,
                                         (1 << (step + 1)) - 1, total, total, total, total]
        pair.snapshot()
        print(json.dumps(dict(stage='rv32-sequence', selector=SELECTORS[step], stores=count)), flush=True)
    assert total == STORES
    for step, count in enumerate(COUNTS):
        address, width, value = original(step, count - 1)
        pair.restore(partials[step])
        before = pair.cell(step, count - 1)
        assert pair.call('reserve', address, width, value, before) == 0
        assert pair.call('publish', address, width, value ^ 1) == 8
        assert pair.state[2:4] == [1, 1] and pair.state[7] == sum(COUNTS[:step + 1]) and pair.state[8] == pair.state[7] - 1
        retained = pair.snapshot()
        assert pair.call('finish', step) == 4 and pair.snapshot() == retained
        controls += 1
        for index in (0, count - 1):
            pair.restore(ends[step])
            pair.cell(step, index, pair.cell(step, index) ^ 0x01000000)
            assert pair.call('finish', step) == 8 and pair.state[2:4] == [1, 1]
            controls += 1
    for word in range(40):
        pair.restore(starts[0])
        pair.state[word] ^= 1
        pair.rv.cpu.mem_write(STATE + word * 4, struct.pack('<I', pair.state[word]))
        assert pair.call('reserve', *original(0, 0), pair.metadata[0]) != 0 and pair.state[2]
        controls += 1
    for change in range(7):
        pair.restore(starts[0])
        address, width, value = original(0, 0)
        before = pair.metadata[0]
        if change < 4:
            arguments = [address, width, value, before]
            arguments[change] ^= 1
            assert pair.call('reserve', *arguments) == 7 and pair.state[7:9] == [0, 0]
        elif change == 4:
            assert pair.call('publish', address, width, value) == 8
        elif change == 5:
            assert pair.call('finish', 0) == 8
        else:
            assert pair.call('reserve', address, width, value, before) == 0
            assert pair.call('reserve', address, width, value, before) == 7 and pair.state[7:9] == [1, 0]
        controls += 1
    pair.restore(starts[0])
    retained = pair.snapshot()
    assert pair.call('reserve', *original(0, 0), pair.metadata[0], epoch=2) == 5
    assert pair.snapshot() == retained
    controls += 1
    for enrolled in range(15):
        pair.restore(starts[0])
        pair.plan[3:17] = [0] * 14
        for i in range(enrolled):
            index = 9 + i if i < 8 else 3 + i - 8
            pair.plan[index] = PROFILE[index]
        pair.rv.cpu.mem_write(PLAN, bytes(pair.plan))
        assert pair.invoke('dma_valid', [pair.plan, enrolled], [PLAN, enrolled]) == 1
        if enrolled < 14:
            index = 9 + enrolled if enrolled < 8 else 3 + enrolled - 8
            pair.plan[index] = PROFILE[index]
            pair.rv.cpu.mem_write(PLAN, bytes(pair.plan))
            assert pair.invoke('dma_valid', [pair.plan, enrolled], [PLAN, enrolled]) == 0
            controls += 1
    return controls


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--core-object', type=Path)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    destination = ROOT / '.local/npu-tx-buffer-20261013' / args.name
    assert not destination.exists()
    destination.mkdir(parents=True)
    dependencies = [SOURCE, HEADER, HARNESS, LINKER, Path(__file__).resolve(),
                    ROOT / 'firmware/npu/bootstrap.h', ROOT / 'firmware/npu/cold-descriptor.h',
                    ROOT / 'tests/npu/test_barrier_protocol.py', ROOT / 'tests/npu/emulation_layout.py',
                    Path(loader.__file__), Path(loader.extract.__file__)]
    dependencies += list(SOURCE.parent.glob('*.h'))
    inputs = {str(path.relative_to(ROOT)): loader.sha(path) for path in dependencies}
    flags = ['-std=c11', '-Wall', '-Wextra', '-Werror', '-fno-builtin', '-I' + str(SOURCE.parent)]
    host, elf = destination / 'host.so', destination / 'rv32.elf'
    loader.run(['clang', *flags, '-O2', '-shared', '-fPIC', SOURCE, '-o', host], destination / 'host.log')
    obj = args.core_object.resolve() if args.core_object else SOURCE
    if args.core_object:
        inputs[str(obj.relative_to(ROOT))] = loader.sha(obj)
    lld = shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'
    loader.run(['clang', *flags, '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
                '-Os', '-nostdlib', '-fno-stack-protector', obj, '--ld-path=' + str(lld),
                '-Wl,-T,' + str(LINKER) + ',--no-relax', '-o', elf], destination / 'rv32.log')
    pair = Pair(host, elf)
    assert pair.rv.elf['e_machine'] == 'EM_RISCV'
    controls = suite(pair)
    flags += ['-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=all']
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1')
    binary = destination / 'sanitizer'
    loader.run(['clang', *flags, SOURCE, HARNESS, '-o', binary], destination / 'sanitizer-build.log')
    sanitized = json.loads(loader.run([binary], destination / 'sanitizer-run.log', env=env).stdout)
    rejected = []
    text = SOURCE.read_text()
    changes = {
        'skip-plan-pin': ('!npu_cold_txbuf_plan_equal(&s->plan, p) ||', ''),
        'skip-preimage': ('before != s->preimages[s->committed]', '(0 && before != s->preimages[s->committed])'),
        'skip-address': ('address != store.address || bytes != store.bytes || value != store.value ||', '(0 && address != store.address) || bytes != store.bytes || value != store.value ||'),
        'skip-readback': ('readback != expected(s, s->published, &store)', '(0 && readback != expected(s, s->published, &store))'),
        'clobber-byte-tail': ('(s->preimages[index] & 0xffffff00u) | store->value', '(s->preimages[index] & 0u) | store->value'),
        'wrong-internal-head': ('item % 32 == 0 ? 0x100000u', 'item % 32 == 0 ? 0x100001u'),
        'wrong-record-width': ('out->bytes = item % 4 == 3 ? 1 : 4;', 'out->bytes = 4;')
    }
    for name, (old, new) in changes.items():
        folder = destination / name
        folder.mkdir()
        source, mutant = folder / 'mutant.c', folder / 'test'
        source.write_text(loader.once(text, old, new))
        loader.run(['clang', *flags, source, HARNESS, '-o', mutant], folder / 'build.log')
        done = loader.run([mutant], folder / 'run.log', env=env, accepted=11)
        assert 'FAIL[txbuf]' in done.stderr and 'AddressSanitizer' not in done.stderr
        rejected.append(dict(name=name, exit_code=done.returncode, binary_sha256=loader.sha(mutant)))
    assert all(loader.sha(ROOT / path) == digest for path, digest in inputs.items())
    receipt = dict(passed=True, stores=pair.stores, calls=pair.calls, controls=controls,
                   sanitized=sanitized, mutants=rejected, inputs=inputs,
                   host_sha256=loader.sha(host), elf_sha256=loader.sha(elf),
                   sanitizers=['address', 'undefined', 'leak'],
                   limits=['Actual host C and exact RV32 owner instructions with an independent original-store oracle.',
                           'Preimage spans, plan/backing and software writes are synthetic caller-owned fixtures.',
                           'Snapshot restores are test-only; there is no production reset or retirement.',
                           'This does not bind API21 native hooks or prove physical ownership/drains/router/client acceptance.'])
    (destination / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(passed=True, stores=pair.stores, calls=pair.calls, controls=controls, mutants=len(rejected))))


if __name__ == '__main__':
    main()
