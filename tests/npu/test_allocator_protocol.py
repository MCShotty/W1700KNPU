#!/usr/bin/env python3
"""Checked allocation C, native/RV32 differential tests and an independent oracle."""
import ctypes as ct
import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
from unicorn import riscv_const as r
from unicorn import UC_HOOK_MEM_READ

from test_barrier_protocol import Rv32
from test_firmware_memory_layout import NativeMemory, table as native_table
from test_firmware_stop_counterexample import ROOT, CODE_SHA, DATA_SHA

SOURCE = ROOT / 'firmware/npu/allocator.c'
HEADER = SOURCE.with_suffix('.h')
BINDING = ROOT / 'tests/npu/allocator-test-binding.c'
LINKER = ROOT / 'tests/npu/allocator-emulation.ld'
BUILD = ROOT / '.local/npu-allocator'
OUT = ROOT / 'research/checkpoints/2026-09-09-npu-allocator'
STATE_BYTES = 824
OK, ARGUMENT, LAYOUT, UNKNOWN, DENIED, CORRUPT, CAPACITY = range(7)
U32 = 0xffffffff
BASE, BYTES = 0x3e800000, 0x78000
END, STACK = 0x84200000, 0x84100000
REGS = [getattr(r, 'UC_RISCV_REG_A' + str(i)) for i in range(8)]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def definitions():
    native = NativeMemory()
    return [[(row['type'], row['alignment_tag'], row['reserved'], row['value'])
             for row in native_table(native.code, address)]
            for address in (0x8401b224, 0x8401cfc8)]


def empty():
    value = bytearray(STATE_BYTES)
    struct.pack_into('<6I', value, 0, 18, 0xabc12345, 0, 0x1234abcd, 0, 0)
    return bytes(value)


def state_for(defs, types, attempts=None):
    value = bytearray(empty())
    rows = {d[0]: d for entries in defs for d in entries}
    end = 0
    for index, kind in enumerate(types):
        _, tag, _, size = rows[kind]
        align = 16 if tag else 32
        start = ((end + align - 1) // align) * align
        struct.pack_into('<HHI', value, 24+index*8, kind, 0, BASE+start)
        end = start+size
    struct.pack_into('<I', value, 8, len(types))
    struct.pack_into('<II', value, 16, len(types) if attempts is None else attempts, end)
    return bytes(value)


def changed(state, offset, fmt, value):
    result = bytearray(state)
    struct.pack_into('<'+fmt, result, offset, value)
    return bytes(result)


@dataclass
class Case:
    name: str
    defs: list
    type: int
    table: int
    state: bytes = empty()
    base: int = BASE
    size: int = BYTES
    deny: int = 0
    after_lock: bytes | None = None


def oracle(case):
    current = case.state
    if case.table not in (0, 1) or not 0 <= case.type < 256 or ((case.type < 129) != (case.table == 1)):
        return (ARGUMENT, 0), current, (0, 0)
    if not case.base or case.base % 32 or not case.size or case.base+case.size > U32:
        return (LAYOUT, 0), current, (0, 0)
    known = {}
    for group, rows in enumerate(case.defs):
        if len(rows) > 128:
            return (LAYOUT, 0), current, (0, 0)
        for kind, tag, reserved, size in rows:
            if not 0 <= kind < 256 or ((kind < 129) != (group == 1)) or tag not in (0, 1) or reserved or not size or kind in known:
                return (LAYOUT, 0), current, (0, 0)
            known[kind] = (tag, size)
    if not known:
        return (LAYOUT, 0), current, (0, 0)
    if case.type not in known:
        return (UNKNOWN, 0), current, (0, 0)
    if case.deny:
        return (DENIED, 0), current, (1, 0)
    current = case.after_lock if case.after_lock is not None else current
    count = struct.unpack_from('<I', current, 8)[0]
    attempts, used = struct.unpack_from('<II', current, 16)
    if count > 100 or used > case.size:
        return (CORRUPT, 0), current, (1, 1)
    end, occupied, addresses = 0, set(), {}
    for index in range(count):
        kind, reserved, address = struct.unpack_from('<HHI', current, 24+index*8)
        if kind not in known or reserved or kind in occupied:
            return (CORRUPT, 0), current, (1, 1)
        alignment = 16 if known[kind][0] else 32
        start = ((end + alignment - 1) // alignment) * alignment
        end = start + known[kind][1]
        if end > case.size or address != case.base + start:
            return (CORRUPT, 0), current, (1, 1)
        occupied.add(kind)
        addresses[kind] = address
    if end != used:
        return (CORRUPT, 0), current, (1, 1)
    if case.type in addresses:
        return (OK, addresses[case.type]), current, (1, 1)
    alignment = 16 if known[case.type][0] else 32
    start = ((end + alignment - 1) // alignment) * alignment
    end = start + known[case.type][1]
    if count == 100 or end > case.size:
        return (CAPACITY, 0), current, (1, 1)
    result = bytearray(current)
    struct.pack_into('<HHI', result, 24+count*8, case.type, 0, case.base+start)
    struct.pack_into('<I', result, 8, count+1)
    struct.pack_into('<II', result, 16, (attempts+1) & U32, end)
    return (OK, case.base+start), bytes(result), (1, 1)


class Result(ct.Structure):
    _fields_ = [('status', ct.c_uint32), ('address', ct.c_uint32)]


def build(source=SOURCE, tag='allocator'):
    BUILD.mkdir(parents=True, exist_ok=True)
    native, rv = BUILD / (tag+'.so'), BUILD / (tag+'.elf')
    common = ['-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-fno-builtin',
              '-I', str(SOURCE.parent), str(source), str(BINDING)]
    commands = [[shutil.which('gcc'), *common, '-shared', '-fPIC', '-fsanitize=undefined',
                 '-fno-sanitize-recover=all', '-o', str(native)]]
    lld = shutil.which('ld.lld') or str(ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld')
    commands.append([shutil.which('clang'), *common, '--target=riscv32', '-march=rv32imac_zicsr',
                     '-mabi=ilp32', '-nostdlib', '-fno-stack-protector', f'--ld-path={lld}',
                     '-Wl,-T,'+str(LINKER)+',--no-relax', '-o', str(rv)])
    for command in commands:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
        assert completed.returncode == 0, completed.stdout+completed.stderr
    return native, rv, commands


class Pair:
    def __init__(self, paths):
        self.lib = ct.CDLL(str(paths[0]))
        self.lib.npu_allocator_test_setup.argtypes = [ct.c_uint32]*4
        self.lib.npu_allocator_test_allocate.argtypes = [ct.c_uint32]*2
        self.lib.npu_allocator_test_allocate.restype = Result
        self.rv = Rv32(paths[1])

    def put(self, name, data):
        symbol = 'npu_allocator_test_'+name
        buffer = (ct.c_ubyte * len(data)).in_dll(self.lib, symbol)
        buffer[:] = data
        self.rv.cpu.mem_write(self.rv.symbols[symbol], bytes(data))

    def read(self, name, size):
        symbol = 'npu_allocator_test_'+name
        native = bytes((ct.c_ubyte * size).in_dll(self.lib, symbol))
        actual = bytes(self.rv.cpu.mem_read(self.rv.symbols[symbol], size))
        assert actual == native, name
        return actual

    def rv_call(self, name, *args):
        cpu = self.rv.cpu
        for register, value in zip(REGS, args):
            cpu.reg_write(register, value)
        cpu.reg_write(r.UC_RISCV_REG_SP, STACK)
        cpu.reg_write(r.UC_RISCV_REG_RA, END)
        cpu.emu_start(self.rv.symbols['npu_allocator_test_'+name], END,
                      count=3000000, timeout=10000000)
        assert cpu.reg_read(r.UC_RISCV_REG_PC) == END, name
        return tuple(cpu.reg_read(reg) for reg in REGS[:2])

    def case(self, case, differential=True, configure=None, expected=None):
        definitions = bytearray(2048)
        for group, rows in enumerate(case.defs):
            assert len(rows) <= 128
            for index, row in enumerate(rows):
                struct.pack_into('<HBBI', definitions, group*1024+index*8, *row)
        self.put('definitions', definitions)
        args = (case.base, case.size, len(case.defs[0]), len(case.defs[1]))
        self.lib.npu_allocator_test_setup(*args)
        self.rv_call('setup', *args)
        if configure is not None:
            configure()
        self.put('state', case.state)
        self.put('after_lock', case.after_lock or case.state)
        self.put('at_unlock', b'\xa5'*STATE_BYTES)
        self.put('deny', struct.pack('<I', case.deny))
        self.put('replace', struct.pack('<I', int(case.after_lock is not None)))
        native = self.lib.npu_allocator_test_allocate(case.type, case.table) if differential else None
        actual = self.rv_call('allocate', case.type, case.table)
        expected_result, expected_state, lock_counts = oracle(case) if expected is None else expected
        assert actual == expected_result, (case.name, actual, expected_result)
        if native is not None:
            assert (native.status, native.address) == actual
        def read(name, size):
            if differential:
                return self.read(name, size)
            return bytes(self.rv.cpu.mem_read(self.rv.symbols['npu_allocator_test_'+name], size))
        state = read('state', STATE_BYTES)
        assert state == expected_state, case.name
        counts = [struct.unpack('<I', read(name, 4))[0] for name in ('acquires', 'releases')]
        assert tuple(counts) == lock_counts, (case.name, counts, lock_counts)
        assert read('owned', 4) == read('error', 4) == bytes(4)
        released = read('at_unlock', STATE_BYTES)
        assert released == (state if counts[1] else b'\xa5'*STATE_BYTES), case.name
        return dict(name=case.name, result=actual, lock_counts=counts,
                    state_before_sha256=sha(case.state), state_after_sha256=sha(state),
                    metadata_unchanged=state == (case.after_lock or case.state))


def cases():
    pinned = definitions()
    result = []
    for group, rows in enumerate(pinned):
        for kind, _, _, _ in rows:
            result.append(Case(f'pinned-{kind:x}-new', pinned, kind, group))
            result.append(Case(f'pinned-{kind:x}-cached', pinned, kind, group, state_for(pinned, [kind])))
    sequence = [0x8a, 18, 29, 1, 11, 25, 0x81]
    for index, kind in enumerate(sequence):
        result.append(Case(f'cold-sequence-{index}', pinned, kind, int(kind < 129), state_for(pinned, sequence[:index])))
    result += [Case('post-bridge-rx2-capacity', pinned, 2, 1, state_for(pinned, sequence)),
               Case('denied-owner', pinned, 0x81, 0, deny=1),
               Case('unknown-type', pinned, 0x80, 1, state_for(pinned, [1])),
               Case('bad-category', pinned, 0x81, 1),
               Case('bad-table-index', pinned, 1, U32),
               Case('bad-type-width', pinned, U32, 0),
               Case('base-overflow', pinned, 1, 1, base=0xffffffe0, size=64),
               Case('zero-base', pinned, 1, 1, base=0),
               Case('unaligned-base', pinned, 1, 1, base=BASE+1),
               Case('zero-capacity', pinned, 1, 1, size=0)]
    one = state_for(pinned, [0x8a])
    for name, offset, fmt, value in (
        ('count-101', 8, 'I', 101), ('count-max', 8, 'I', U32),
        ('used-too-large', 20, 'I', BYTES+1), ('rewound-cursor', 20, 'I', 0),
        ('cached-null', 28, 'I', 0), ('cached-outside', 28, 'I', BASE+BYTES),
        ('cached-misaligned', 28, 'I', BASE+1), ('unknown-cached-type', 24, 'H', 0xff),
        ('reserved-cache-field', 26, 'H', 1),
    ):
        result.append(Case(name, pinned, 0x8a, 0, changed(one, offset, fmt, value)))
    duplicate = state_for(pinned, [0x8a, 2])
    result.append(Case('duplicate-cache-type', pinned, 0x8a, 0, changed(duplicate, 32, 'H', 0x8a)))
    result.append(Case('mutation-at-grant', pinned, 2, 1, after_lock=one))
    result.append(Case('cached-appears-at-grant', pinned, 0x8a, 0, after_lock=one))
    result.append(Case('corruption-at-grant', pinned, 2, 1,
                       after_lock=changed(one, 20, 'I', 0)))
    result.append(Case('attempt-counter-wrap', pinned, 2, 1,
                       state_for(pinned, [0x8a], attempts=U32)))
    for field, value, name in ((1, 2, 'bad-alignment-tag'), (2, 1, 'reserved-definition'), (3, 0, 'zero-definition-size')):
        rows = [[list(row) for row in group] for group in pinned]
        rows[0][0][field] = value
        result.append(Case(name, rows, 0x81, 0))
    rows = [list(group) for group in pinned]
    rows[0].append(rows[0][0])
    result.append(Case('duplicate-definition', rows, 0x81, 0))
    many = [[], [(kind, 0, 0, 32) for kind in range(1, 103)]]
    full = state_for(many, list(range(1, 101)))
    result += [Case('full-cache-reuse', many, 100, 1, full),
               Case('full-cache-new', many, 101, 1, full),
               Case('count-101-populated', many, 101, 1, changed(full, 8, 'I', 101))]
    aligned = [[], [(1, 0, 0, 33), (2, 0, 0, 4)]]
    result.append(Case('alignment-32-boundary', aligned, 2, 1, state_for(aligned, [1])))
    rng = random.Random(0x170081)
    for iteration in range(80):
        defs = [[], [(kind, rng.randrange(2), 0, rng.randrange(1, 4000)) for kind in range(1, 16)]]
        order = list(range(1, 16))
        rng.shuffle(order)
        for index in range(16):
            kind = order[index] if index < 15 else order[0]
            state = state_for(defs, order[:index])
            result.append(Case(f'random-{iteration}-{index}', defs, kind, 1, state,
                               size=rng.choice([BYTES, struct.unpack_from('<I', state, 20)[0] or 1])))
    return result


def mutations(cases_by_name):
    text = SOURCE.read_text()
    before_lock = '''    result.status = NPU_ALLOCATOR_LOCK_DENIED;
    if (lock->acquire(lock->context))
        return result;
    ownership_fence();
    result.status = NPU_ALLOCATOR_CORRUPT;
    if (!valid_state(state, layout, type, &cached))
        goto unlock;'''
    invalid_order = '''    result.status = NPU_ALLOCATOR_CORRUPT;
    if (!valid_state(state, layout, type, &cached))
        return result;
    result.status = NPU_ALLOCATOR_LOCK_DENIED;
    if (lock->acquire(lock->context))
        return result;
    ownership_fence();'''
    variants = [
        ('ignore-lock', 'if (lock->acquire(lock->context))', 'if ((lock->acquire(lock->context), 0))', 'denied-owner'),
        ('ignore-extent', 'd->bytes > layout->bytes - used - padding', '0', 'post-bridge-rx2-capacity'),
        ('ignore-full-cache', 'count == NPU_ALLOCATOR_ENTRIES || ', '', 'full-cache-new'),
        ('ignore-cursor', 'return cursor == state->used;', 'return 1;', 'rewound-cursor'),
        ('ignore-cached-address', ' || entry->address != address', '', 'cached-null'),
        ('align-16-only', 'd->alignment_tag ? 16 : 32', '((void)d, 16)', 'alignment-32-boundary'),
        ('read-before-lock', before_lock, invalid_order, 'cached-appears-at-grant'),
        ('ignore-count-bound', 'state->count > NPU_ALLOCATOR_ENTRIES || ', '', 'count-101-populated'),
    ]
    results = []
    for name, old, new, case_name in variants:
        assert text.count(old) == 1, name
        source = BUILD / (name+'.c')
        source.write_text(text.replace(old, new, 1))
        paths = build(source, name)
        pair = Pair(paths)
        if name == 'ignore-count-bound':
            end = pair.rv.symbols['npu_allocator_test_state']+STATE_BYTES
            def outside(cpu, access, address, size, value, data):
                raise AssertionError('metadata-read-outside-cache')
            pair.rv.cpu.hook_add(UC_HOOK_MEM_READ, outside, begin=end, end=end+7)
        try:
            pair.case(cases_by_name[case_name], differential=False)
        except AssertionError as error:
            assert str(error) == 'metadata-read-outside-cache' if name == 'ignore-count-bound' else case_name in str(error)
            results.append(dict(name=name, detected=True, assertion=str(error),
                                source_sha256=sha(source.read_bytes()), rv32_sha256=sha(paths[1].read_bytes())))
        else:
            raise AssertionError('surviving allocator mutant: '+name)
    return results


def concurrency(placements=False):
    source = ROOT / 'tests/npu/allocator-concurrency.c'
    binary = BUILD / ('allocator-concurrency-placed' if placements else 'allocator-concurrency')
    command = ['gcc', '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-pthread',
               '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
               '-I', str(SOURCE.parent), str(SOURCE), str(source), '-o', str(binary)]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert compiled.returncode == 0, compiled.stderr
    result = subprocess.run([str(binary), *(['--placements'] if placements else [])],
                            capture_output=True, text=True, timeout=120,
                            env={**os.environ, 'ASAN_OPTIONS': 'detect_leaks=1:abort_on_error=1',
                                 'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'})
    assert result.returncode == 0 and not result.stderr, result.stdout+result.stderr
    return dict(command=command, source_sha256=sha(source.read_bytes()),
                binary_sha256=sha(binary.read_bytes()), result=json.loads(result.stdout),
                scope='ASan/UBSan with real pthread mutexes, not hardware NPU lock or DMA/cache proof.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    inputs = {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in
              (SOURCE, HEADER, BINDING, LINKER, Path(__file__), ROOT/'tests/npu/allocator-concurrency.c')}
    paths = build()
    pair = Pair(paths)
    scenarios = cases()
    rows = [pair.case(case) for case in scenarios]
    mutants = mutations({case.name: case for case in scenarios})
    threads = concurrency()
    assert all(sha((ROOT/name).read_bytes()) == value for name, value in inputs.items())
    OUT.mkdir(parents=True, exist_ok=True)
    result = dict(schema=1, firmware_sha256=CODE_SHA, data_sha256=DATA_SHA,
                  source_sha256=sha(SOURCE.read_bytes()), header_sha256=sha(HEADER.read_bytes()),
                  binding_sha256=sha(BINDING.read_bytes()), test_sha256=sha(Path(__file__).read_bytes()),
                  native_sha256=sha(paths[0].read_bytes()), rv32_sha256=sha(paths[1].read_bytes()),
                  commands=paths[2], cases=rows, mutants=mutants, concurrency=threads,
                  inputs_before_after=inputs,
                  limits=['Same allocation C under native/UBSan and RV32 execution; independent arithmetic/state oracle.',
                          'Lock callbacks model ownership and state changes at acquisition, not physical mutex grants.',
                          'Addresses are computed; heap packet memory, DMA, cache coherency and caller failure policy are not proved.'])
    path = OUT / 'allocator-protocol.json'
    encoded = (json.dumps(result, indent=2)+'\n').encode()
    if args.check:
        assert path.read_bytes() == encoded, 'allocator protocol replay differs'
    else:
        path.write_bytes(encoded)
    print(json.dumps(dict(cases=len(rows), mutants=len(mutants), concurrency=threads['result'],
                          evidence_sha256=sha(path.read_bytes()))))


if __name__ == '__main__':
    main()
