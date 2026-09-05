#!/usr/bin/env python3
"""Run the unpromoted barrier's actual C as native code and RV32 instructions."""
import ctypes
import hashlib
import io
import json
from pathlib import Path
import random
import shutil
import struct
import subprocess

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32
from unicorn.riscv_const import UC_RISCV_REG_A0, UC_RISCV_REG_A1, UC_RISCV_REG_A2
from unicorn.riscv_const import UC_RISCV_REG_A3, UC_RISCV_REG_SP, UC_RISCV_REG_RA
from unicorn.riscv_const import UC_RISCV_REG_PC
import unicorn
from emulation_layout import STATE, SCRATCH, map_sram

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / '.local/npu-barrier'
OUT = ROOT / 'research/checkpoints/2026-09-05-npu-barrier'
SOURCE = ROOT / 'firmware/npu/barrier.c'
LINKER = ROOT / 'tests/npu/barrier-emulation.ld'
TEXT, STACK, END = 0x84040000, 0x84100000, 0x84200000
WORDS = 26
PARK, REFRESH, RUN, FAULT = range(4)
ARGS = (UC_RISCV_REG_A0, UC_RISCV_REG_A1, UC_RISCV_REG_A2, UC_RISCV_REG_A3)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def build(source=SOURCE, tag='barrier'):
    BUILD.mkdir(parents=True, exist_ok=True)
    clang = shutil.which('clang')
    lld = shutil.which('ld.lld') or str(BUILD / 'lld/usr/lib/llvm-21/bin/ld.lld')
    common = [clang, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
              '-fno-builtin', '-I', str(SOURCE.parent), str(source)]
    native, rv32 = BUILD / f'{tag}.so', BUILD / f'{tag}.elf'
    subprocess.run(common + ['-shared', '-fPIC', '-o', str(native)], check=True)
    subprocess.run(common + ['--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
                            '-nostdlib', '-fno-stack-protector', f'--ld-path={lld}',
                            f'-Wl,-T,{LINKER},--no-relax', '-o', str(rv32)], check=True)
    return native, rv32


class Native:
    def __init__(self, path):
        self.lib = ctypes.CDLL(str(path))
        self.state = (ctypes.c_uint32 * WORDS)()
        self.epoch = ctypes.c_uint32()

    def call(self, name, *args):
        function = getattr(self.lib, 'npu_barrier_' + name)
        function.restype = None if name == 'init' else ctypes.c_uint32
        extra = [ctypes.byref(self.epoch)] if name == 'poll' else []
        return function(self.state, *[ctypes.c_uint32(arg) for arg in args], *extra)

    def snapshot(self):
        return tuple(self.state)

    def replace(self, words):
        self.state[:] = words


class Rv32:
    def __init__(self, path, cpu=None):
        self.cpu = cpu or Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        if cpu is None:
            self.cpu.mem_map(0x84000000, 0x201000)
            map_sram(self.cpu)
        self.elf = ELFFile(io.BytesIO(path.read_bytes()))
        self.symbols = {symbol.name: int(symbol['st_value'])
                        for symbol in self.elf.get_section_by_name('.symtab').iter_symbols()
                        if symbol['st_shndx'] != 'SHN_UNDEF'}
        for section in self.elf.iter_sections():
            if section['sh_flags'] & 2 and section['sh_type'] != 'SHT_NOBITS':
                self.cpu.mem_write(section['sh_addr'], section.data())

    def call(self, name, *args):
        values = [STATE, *args, *([SCRATCH] if name == 'poll' else [])]
        for register, value in zip(ARGS, values):
            self.cpu.reg_write(register, value)
        self.cpu.reg_write(UC_RISCV_REG_SP, STACK)
        self.cpu.reg_write(UC_RISCV_REG_RA, END)
        self.cpu.emu_start(self.symbols['npu_barrier_' + name], END,
                           timeout=1000000, count=10000)
        assert self.cpu.reg_read(UC_RISCV_REG_PC) == END, name
        return None if name == 'init' else self.cpu.reg_read(UC_RISCV_REG_A0)

    def snapshot(self):
        return struct.unpack('<26I', self.cpu.mem_read(STATE, WORDS * 4))

    def replace(self, words):
        self.cpu.mem_write(STATE, struct.pack('<26I', *words))


class Pair:
    def __init__(self, paths):
        self.native, self.rv32 = Native(paths[0]), Rv32(paths[1])
        self.calls = 0
        self.call('init')

    def call(self, name, *args):
        native = self.native.call(name, *args)
        rv32 = self.rv32.call(name, *args)
        assert native == rv32, (name, args, native, rv32)
        assert self.native.snapshot() == self.rv32.snapshot(), (name, args)
        if name == 'poll':
            actual = struct.unpack('<I', self.rv32.cpu.mem_read(SCRATCH, 4))[0]
            assert actual == self.native.epoch.value
        self.calls += 1
        return rv32

    def expect(self, name, args, expected):
        actual = self.call(name, *args)
        assert actual == expected, (name, args, actual, expected)

    def replace(self, words):
        self.native.replace(words)
        self.rv32.replace(words)


def park_all(pair):
    for hart in range(8):
        pair.expect('poll', (hart,), PARK)


def drain_all(pair, epoch):
    for domain in range(5):
        pair.expect('record_drain', (domain, epoch), 1)


def resume(pair, epoch):
    pair.expect('prepare', (epoch,), 1)
    pair.expect('release', (epoch,), 1)
    pair.expect('reclaimable', (epoch,), 0)
    for hart in range(8):
        pair.expect('poll', (hart,), REFRESH)
        pair.expect('refreshed', (hart, epoch), 1)
        pair.expect('poll', (hart,), PARK)
    pair.expect('arm', (epoch,), 1)
    for hart in range(8):
        pair.expect('poll', (hart,), RUN)


def suite(paths):
    calls = 0
    # Every hart, including never-started core 0/7 and indirect core 5/6, matters.
    for missing in range(8):
        pair = Pair(paths)
        pair.expect('stop', (), 1)
        pair.expect('workers_parked', (1,), 0)
        for hart in range(8):
            if hart != missing:
                pair.expect('poll', (hart,), PARK)
        pair.expect('workers_parked', (1,), 0)
        for domain in range(5):
            pair.expect('record_drain', (domain, 1), 0)
        pair.expect('reclaimable', (1,), 0)
        pair.expect('release', (1,), 0)
        pair.expect('poll', (missing,), PARK)
        pair.expect('workers_parked', (1,), 1)
        calls += pair.calls

    for missing in range(5):
        pair = Pair(paths)
        park_all(pair)
        for domain in range(5):
            if domain != missing:
                pair.expect('record_drain', (domain, 1), 1)
        pair.expect('reclaimable', (1,), 0)
        pair.expect('prepare', (1,), 0)
        pair.expect('release', (1,), 0)
        pair.expect('record_drain', (missing, 1), 1)
        pair.expect('reclaimable', (1,), 1)
        pair.expect('release', (1,), 0)  # New resources are not prepared yet.
        calls += pair.calls

    for missing in range(8):
        pair = Pair(paths)
        park_all(pair)
        drain_all(pair, 1)
        pair.expect('prepare', (1,), 1)
        pair.expect('release', (1,), 1)
        for hart in range(8):
            if hart != missing:
                pair.expect('refreshed', (hart, 1), 1)
        pair.expect('arm', (1,), 0)
        pair.expect('poll', (missing,), REFRESH)
        pair.expect('stop', (), 2)  # Stop during a partial refresh/restart.
        pair.expect('refreshed', (missing, 1), 0)
        pair.expect('arm', (1,), 0)
        pair.expect('reclaimable', (2,), 0)
        park_all(pair)
        for domain in range(5):
            pair.expect('record_drain', (domain, 1), 0)
        pair.expect('reclaimable', (2,), 0)
        drain_all(pair, 2)
        resume(pair, 2)
        calls += pair.calls

    pair = Pair(paths)
    rng = random.Random(0x7581)
    for epoch in range(1, 101):
        pair.expect('stop', (), epoch)
        order = list(range(8))
        rng.shuffle(order)
        for index, hart in enumerate(order):
            pair.expect('poll', (hart,), PARK)
            pair.expect('workers_parked', (epoch,), int(index == 7))
            pair.expect('reclaimable', (epoch,), 0)
            pair.expect('refreshed', (hart, epoch - 1), 0)
        domains = list(range(5))
        rng.shuffle(domains)
        for index, domain in enumerate(domains):
            pair.expect('record_drain', (domain, epoch - 1), 0)
            pair.expect('record_drain', (domain, epoch), 1)
            pair.expect('reclaimable', (epoch,), int(index == 4))
        resume(pair, epoch)
    calls += pair.calls

    pair = Pair(paths)
    for invalid in (8, 0xffffffff):
        pair.expect('poll', (invalid,), FAULT)
        pair.expect('refreshed', (invalid, 1), 0)
    for invalid in (5, 0xffffffff):
        pair.expect('record_drain', (invalid, 1), 0)
    for operation in ('reclaimable', 'prepare', 'release', 'arm', 'workers_parked'):
        pair.expect(operation, (0,), 0)
    words = list(pair.rv32.snapshot())
    words[0] = words[1] = 0xffffffff
    pair.replace(words)
    pair.expect('stop', (), 0)
    for hart in range(8):
        pair.expect('poll', (hart,), FAULT)
    pair.expect('reclaimable', (0xffffffff,), 0)
    pair.expect('arm', (0xffffffff,), 0)
    calls += pair.calls
    return calls


def main():
    paths = build()
    calls = suite(paths)
    mutations = {
        'missing-last-worker': ('i < NPU_BARRIER_WORKERS; i++)\n        if (load(&s->parked[i])',
                                'i < NPU_BARRIER_WORKERS - 1; i++)\n        if (load(&s->parked[i])'),
        'missing-last-domain': ('i < NPU_BARRIER_DOMAINS; i++)\n        if (load(&s->drained[i])',
                                'i < NPU_BARRIER_DOMAINS - 1; i++)\n        if (load(&s->drained[i])'),
        'missing-last-refresh': ('i < NPU_BARRIER_WORKERS; i++)\n        if (load(&s->ready[i])',
                                 'i < NPU_BARRIER_WORKERS - 1; i++)\n        if (load(&s->ready[i])'),
    }
    controls = {}
    source = SOURCE.read_text()
    for tag, (before, after) in mutations.items():
        assert source.count(before) == 1
        mutation = BUILD / (tag + '.c')
        mutation.write_text(source.replace(before, after))
        try:
            suite(build(mutation, tag))
        except AssertionError as error:
            controls[tag] = {'rejected': True, 'assertion': str(error)}
        else:
            raise AssertionError('Suite accepted mutation ' + tag)
    report = {'passed': True, 'native_rv32_call_pairs': calls, 'stop_resume_cycles': 100,
              'worker_omission_cases': 8, 'domain_omission_cases': 5,
              'partial_refresh_stop_cases': 8, 'mutation_controls': controls,
              'unicorn': unicorn.__version__, 'source_sha256': digest(SOURCE.read_bytes()),
              'rv32_elf_sha256': digest(paths[1].read_bytes()),
              'native_elf_sha256': digest(paths[0].read_bytes()),
              'scope': 'Candidate protocol actual C, compiled native and RV32; serialized API schedules and modeled drain witnesses. No firmware hooks, hardware/cache/DMA behavior, Linux recovery integration or physical-router acceptance.'}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'protocol-tests.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
