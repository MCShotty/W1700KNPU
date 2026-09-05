#!/usr/bin/env python3
"""Original worker instructions with emulator-only generation-barrier detours."""
import json
from pathlib import Path
import shutil
import subprocess
import random

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ
from unicorn import riscv_const as r

from test_barrier_protocol import BUILD, SOURCE, Rv32, digest, PARK, REFRESH
from test_barrier_core5 import SITES as CORE5_SITES, jump, stopped_at, inflight, passthrough
from test_firmware_stop_counterexample import Harness, CODE_SHA, DATA_SHA, SRAM, END
from emulation_layout import OLD, NEW

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/checkpoints/2026-09-05-npu-workers'
ASM = ROOT / 'tests/npu/barrier-workers-emulation.S'
LINKER = ASM.with_suffix('.ld')
# hart, symbol, preimage, load register, nonzero/next target, zero target.
SITES = {
    0x8400ce1c: (1, 'startup', '9c4281cf', 'A3', 0x8400ce20, 0x8400ce36),
    0x8400cf10: (1, 'outer', '1c4081ef', 'S0', 0x8400cf2a, 0x8400cf14),
    0x8400cf26: (1, 'idle', '1c40f5d7', 'S0', 0x8400cf2a, 0x8400cf14),
    0x8400ec7e: (2, 'startup', '1c43fddf', 'A4', 0x8400ec82, 0x8400ec7e),
    0x8400ecc2: (2, 'outer', '83470900', 'S2', 0x8400ecc6, None),
    0x8400ece6: (2, 'idle', '83470900', 'S2', 0x8400ecea, None),
    0x8400e440: (3, 'startup', '1c42e5db', 'A2', 0x8400e444, 0x8400e432),
    0x8400e4d4: (3, 'outer', '83c70700', 'A5', 0x8400e4d8, None),
    0x8400d0ea: (4, 'startup', '83470400', 'S0', 0x8400d0ee, None),
    0x8400d144: (4, 'outer', '83470400', 'S0', 0x8400d148, None),
    0x8400d160: (4, 'idle', '83470400', 'S0', 0x8400d164, None),
    0x8400cd3e: (6, 'startup', '9c40fddf', 'S1', 0x8400cd42, 0x8400cd3e),
    0x8400cd8a: (6, 'outer', '9c4099cb', 'S1', 0x8400cd8e, 0x8400cda2),
    0x8400cd9e: (6, 'retry', '9c40fdf7', 'S1', 0x8400cd8e, 0x8400cda2),
    0x84000b24: (7, 'startup', 'ef00f014', None, 0x84001472, None),
    0x84000b36: (7, 'outer', 'ef00100c', None, 0x840013f6, None),
}
ENTRIES = {1: 0x8400cdc6, 2: 0x8400ec48, 3: 0x8400e3fc,
           4: 0x8400d0ae, 6: 0x8400cd1a, 7: 0x84000aee}
OUTER = {hart: address for address, (hart, kind, *_) in SITES.items() if kind == 'outer'}
STARTUP_FLAGS = {1: (0x2a84, 0x4588, 0x1f44, 0x3954, 0x2ce8, 0x46ec),
                 2: (0x4708, 0x46fa, 0x46f9), 3: (0x4708, 0x46f8, 0x46f0),
                 4: (0x46fa, 0x4708, 0x46f9), 6: (0x46f0, 0x46ec)}
REFILL_SLOTS = (0x2cf0, 0x3904, 0x395c, 0x2a80, 0x4630)
REFILL_CONSUMERS = (0x460c, 0x2a98, 0x4580, 0x2ac8, 0x4598)
HELPERS = {0x8400bd96: 0, 0x8400bea8: 0, 0x8400bfba: 0,
           0x8400c0a8: 0, 0x8400c196: 0, 0x8400e87a: 0,
           0x84009da4: 0, 0x8400f638: 0, 0x8400b0a6: 1,
           0x8400c284: 1, 0x84001472: 0, 0x84001392: 0,
           0x84001528: 1, 0x84001a28: 0, 0x840017da: 0}
REFILL_HELPERS = set(tuple(HELPERS)[:5])
REGISTERS = [getattr(r, 'UC_RISCV_REG_X' + str(index)) for index in range(32)]


class MissingParkAck(AssertionError):
    pass


class StaleOwnershipCache(AssertionError):
    pass


def build_workers(define=None):
    BUILD.mkdir(parents=True, exist_ok=True)
    target = BUILD / ('barrier-workers' + ('-' + define if define else '') + '.elf')
    lld = shutil.which('ld.lld') or str(BUILD / 'lld/usr/lib/llvm-21/bin/ld.lld')
    args = [shutil.which('clang'), '--target=riscv32', '-march=rv32imac_zicsr',
            '-mabi=ilp32', '-O2', '-Wall', '-Wextra', '-Werror', '-fno-builtin',
            '-nostdlib', '-fno-stack-protector', f'--ld-path={lld}', str(SOURCE),
            str(ASM.parent / 'barrier-core5-emulation.S'), str(ASM),
            f'-Wl,-T,{LINKER},--no-relax', '-o', str(target)]
    if define:
        args.append('-D' + define)
    subprocess.run(args, check=True)
    return target


class Worker(Harness):
    def __init__(self, path, hart, omit=None):
        self.seek = self.hit = self.hold = None
        self.skip_seek = False
        self.helper_calls = []
        self.ring_reads = []
        self.tracking = False
        super().__init__(0xfe, hart=hart)
        self.cpu.mem_map(0x0c000000, 0x201000)
        self.barrier = Rv32(path, self.cpu)
        self.patches = []
        for address, (owner, kind, expected, *_) in SITES.items():
            assert bytes(self.cpu.mem_read(address, 4)).hex() == expected
            if address != omit:
                symbol = f'gate_core{owner}_{kind}'
                target = self.barrier.symbols[symbol]
                self.cpu.mem_write(address, jump(address, target))
                self.patches.append({'address': hex(address), 'hart': owner,
                                     'symbol': symbol, 'preimage': expected,
                                     'target': hex(target),
                                     'postimage': jump(address, target).hex()})
        for address in {*SITES, *HELPERS, 0x840013f6,
                        self.barrier.symbols['npu_barrier_refreshed']}:
            self.cpu.hook_add(UC_HOOK_CODE, self.worker_hook, begin=address, end=address)
        self.cpu.hook_add(UC_HOOK_MEM_READ, self.read_hook, begin=OLD, end=NEW + 0xfff)
        self.fixture()
        self.control('init')
        for owner in range(8):
            assert self.control('poll', owner) == PARK
        for domain in range(5):
            assert self.control('record_drain', domain, 1) == 1
        assert self.control('prepare', 1) == 1
        assert self.control('release', 1) == 1
        for owner in range(8):
            assert self.control('poll', owner) == REFRESH
            assert self.control('refreshed', owner, 1) == 1
        assert self.control('arm', 1) == 1
        self.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 8)

    def fixture(self):
        for offset in (0x2a84, 0x4588, 0x1f44, 0x3954, 0x2ce8,
                       0x46ec, 0x46f0, 0x4708):
            self.put32(SRAM + offset, 1)
        self.cpu.mem_write(SRAM + 0x46f8, b'\x03\x03\x01')
        self.put32(SRAM + 0x472c, 0)
        self.put32(SRAM + 0x0bac, 1)
        self.put32(SRAM + 0x4640, 1)
        for offset in (0x1f18,):
            self.put32(SRAM + offset, 0)
        for index, (slot, consumer) in enumerate(zip(REFILL_SLOTS, REFILL_CONSUMERS)):
            self.put32(SRAM + slot, OLD + index * 0x100)
            self.put32(OLD + index * 0x100 + 12, 0)
            self.put32(SRAM + consumer, 0)
        self.put32(SRAM + 0x4700, OLD + 0x600)
        self.put32(SRAM + 0x46fc, OLD + 0x700)
        self.put32(OLD + 0x60c, 0)
        self.put32(OLD + 0x70c, 0)
        self.put16(SRAM + 0x3978, 0x1ff)
        self.put16(SRAM + 0x21f4, 0x3ff)

    def code_hook(self, cpu, address, size, data):
        # Retain original printf/hart-ID modeling, not core-5 pause behavior.
        if address != 0x8400cbbe:
            super().code_hook(cpu, address, size, data)

    def worker_hook(self, cpu, address, size, data):
        if address == self.seek:
            if self.skip_seek:
                self.skip_seek = False
            else:
                self.hit, self.seek = address, None
                cpu.emu_stop()
                return
        if address == self.hold:
            self.hit = address
            cpu.emu_stop()
            return
        if address in HELPERS:
            self.helper_calls.append({'address': hex(address), 'phase': self.phase,
                                      'a0': cpu.reg_read(r.UC_RISCV_REG_A0)})
            if address in REFILL_HELPERS:
                self.put32(cpu.reg_read(r.UC_RISCV_REG_A1), cpu.reg_read(r.UC_RISCV_REG_A0))
            cpu.reg_write(r.UC_RISCV_REG_A0, HELPERS[address])
            cpu.reg_write(r.UC_RISCV_REG_PC, cpu.reg_read(r.UC_RISCV_REG_RA))

    def read_hook(self, cpu, access, address, size, value, data):
        if self.tracking:
            self.ring_reads.append({'address': hex(address), 'phase': self.phase,
                                    'pc': hex(cpu.reg_read(r.UC_RISCV_REG_PC))})

    def control(self, name, *args):
        context = self.cpu.context_save()
        result = self.barrier.call(name, *args)
        self.cpu.context_restore(context)
        return result

    def execute(self, pc=None, count=60000):
        self.cpu.emu_start(pc or self.cpu.reg_read(r.UC_RISCV_REG_PC), END,
                           timeout=3000000, count=count)

    def until(self, target, pc=None):
        self.seek, self.hit = target, None
        self.skip_seek = (pc or self.cpu.reg_read(r.UC_RISCV_REG_PC)) == target
        self.execute(pc, count=2500000)
        assert self.hit == target, (hex(target), hex(self.cpu.reg_read(r.UC_RISCV_REG_PC)))

    def park(self):
        assert self.control('stop') == 2
        self.phase = 'parking'
        self.execute()
        if self.barrier.snapshot()[5 + self.hart] != 2:
            raise MissingParkAck((self.hart, hex(self.cpu.reg_read(r.UC_RISCV_REG_PC))))
        assert not self.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
        before = len(self.helper_calls)
        self.execute()
        assert len(self.helper_calls) == before
        assert self.control('reclaimable', 2) == 0
        for owner in range(8):
            if owner != self.hart:
                assert self.control('poll', owner) == PARK
        assert self.control('workers_parked', 2) == 1
        for domain in range(5):
            assert self.control('record_drain', domain, 2) == 1
        assert self.control('reclaimable', 2) == 1

    def replace(self, base=NEW):
        for index, (slot, consumer) in enumerate(zip(REFILL_SLOTS, REFILL_CONSUMERS)):
            self.put32(SRAM + slot, base + index * 0x100)
            self.put32(base + index * 0x100 + 12, 7 + index)
            self.put32(SRAM + consumer, 7 + index)
        self.put32(SRAM + 0x4700, base + 0x600)
        self.put32(SRAM + 0x46fc, base + 0x700)
        self.put32(base + 0x60c, 34)
        self.put32(base + 0x70c, 12)
        self.put16(SRAM + 0x3978, 33)
        self.put16(SRAM + 0x21f4, 11)
        self.put32(SRAM + 0x46ec, 1)
        self.cpu.mem_write(SRAM + 0x46f8, b'\x03\x03\x01')

    def resume(self):
        self.replace()
        assert self.control('prepare', 2) == 1
        assert self.control('release', 2) == 1
        self.phase, self.tracking = 'refresh-before-arm', True
        before = len(self.helper_calls)
        self.execute()
        assert self.barrier.snapshot()[13 + self.hart] == 2
        assert len(self.helper_calls) == before
        assert self.control('reclaimable', 2) == 0
        assert self.control('arm', 2) == 0
        for owner in range(8):
            if owner != self.hart:
                assert self.control('refreshed', owner, 2) == 1
        assert self.control('arm', 2) == 1
        self.phase = 'resumed'


def stop_resume(path, site, omit=None):
    hart, kind, *_ = SITES[site]
    worker = Worker(path, hart, omit)
    if kind == 'startup':
        worker.cpu.reg_write(r.UC_RISCV_REG_PC, ENTRIES[hart])
    else:
        worker.until(OUTER[hart], ENTRIES[hart])
        if kind == 'idle':
            flag = {1: 0x46ec, 2: 0x46f9, 4: 0x46fa}[hart]
            worker.cpu.mem_write(SRAM + flag, b'\x00')
            worker.until(site)
        elif kind == 'retry':
            worker.until(site)
    worker.park()
    worker.resume()
    next_poll = 0x8400cd9e if hart == 6 else OUTER[hart]
    worker.until(OUTER[hart] if kind == 'startup' else next_poll)
    if kind == 'startup':
        worker.until(next_poll)
    assert worker.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
    if any(int(read['address'], 16) < NEW for read in worker.ring_reads):
        raise StaleOwnershipCache(('old-ring-read', hart, kind, worker.ring_reads))
    resumed_calls = [call for call in worker.helper_calls if call['phase'] == 'resumed']
    if hart in (1, 2) and resumed_calls:
        raise StaleOwnershipCache(('unexpected-empty-ring-helper', hart, kind, resumed_calls))
    if hart == 1:
        expected = {hex(NEW + index * 0x100 + 12) for index in range(5)}
        assert expected <= {read['address'] for read in worker.ring_reads}, (kind, worker.ring_reads)
    return {'hart': hart, 'site': hex(site), 'kind': kind, 'park_mie_clear': True,
            'no_work_before_arm': True, 'ring_reads': worker.ring_reads,
            'modeled_helpers': worker.helper_calls}


def preservation(path):
    cases = []
    for site, (hart, kind, _preimage, load_reg, next_pc, zero_pc) in SITES.items():
        for value in (0, 1, 3):
            for mie in (0, 8):
                results = []
                for patched in (False, True):
                    worker = Worker(path, hart, omit=site)
                    cpu = worker.cpu
                    for index, register in enumerate(REGISTERS):
                        cpu.reg_write(register, 0x12340000 + index)
                    cpu.reg_write(r.UC_RISCV_REG_SP, 0x84035dc0)
                    if load_reg:
                        cpu.reg_write(getattr(r, 'UC_RISCV_REG_' + load_reg), SRAM + 0x1800)
                    worker.put32(SRAM + 0x1800, value)
                    cpu.reg_write(r.UC_RISCV_REG_MSTATUS, mie)
                    target = zero_pc if value == 0 and zero_pc else next_pc
                    if target in HELPERS:
                        worker.seek = target
                    # Original zero branches can return to the same patch site.
                    visits = [0]
                    def halt(uc, address, size, data):
                        visits[0] += 1
                        if patched or target != site or visits[0] > 1:
                            uc.emu_stop()
                    cpu.hook_add(UC_HOOK_CODE, halt, begin=target, end=target)
                    start = worker.barrier.symbols[f'gate_core{hart}_{kind}'] if patched else site
                    worker.execute(start, count=5000)
                    assert cpu.reg_read(r.UC_RISCV_REG_PC) == target, (
                        hex(site), value, mie, patched, hex(cpu.reg_read(r.UC_RISCV_REG_PC)))
                    results.append(([cpu.reg_read(reg) for reg in REGISTERS],
                                    cpu.reg_read(r.UC_RISCV_REG_MSTATUS)))
                assert results[0] == results[1], (hex(site), value, mie, results)
                cases.append({'site': hex(site), 'value': value, 'mie': bool(mie)})
    return cases


def in_flight(path, hart, helper):
    worker = Worker(path, hart)
    worker.until(OUTER[hart], ENTRIES[hart])
    if hart == 1:
        worker.put32(OLD + 12, 1)
    elif hart == 2:
        worker.put16(SRAM + 0x21f4, 0)
    elif hart == 7:
        worker.put32(SRAM + 0x4640, 0)
    worker.hold, worker.hit = helper, None
    worker.execute(count=2500000)
    assert worker.hit == helper, (hart, hex(worker.cpu.reg_read(r.UC_RISCV_REG_PC)))
    assert worker.control('stop') == 2
    for owner in range(8):
        if owner != hart:
            assert worker.control('poll', owner) == PARK
    assert worker.barrier.snapshot()[5 + hart] == 1
    assert worker.control('workers_parked', 2) == 0
    assert worker.control('record_drain', 0, 2) == 0
    worker.hold = None
    worker.execute(count=2500000)
    assert worker.barrier.snapshot()[5 + hart] == 2, (hart, hex(worker.cpu.reg_read(r.UC_RISCV_REG_PC)))
    assert worker.control('workers_parked', 2) == 1
    return {'hart': hart, 'held_helper': hex(helper), 'ack_withheld': True,
            'ack_after_modeled_helper_and_native_iteration': True,
            'helper_calls': worker.helper_calls}


def startup_wait(path, hart, flag, omit=None):
    worker = Worker(path, hart, omit)
    worker.cpu.mem_write(SRAM + flag, b'\x00')
    worker.execute(ENTRIES[hart], count=50000)
    assert not worker.helper_calls
    worker.park()
    assert not worker.helper_calls
    return {'hart': hart, 'missing_flag': hex(SRAM + flag), 'acknowledged': True}


def refresh_interrupted(path, hart):
    worker = Worker(path, hart)
    worker.until(OUTER[hart], ENTRIES[hart])
    worker.park()
    worker.replace()
    assert worker.control('prepare', 2) == 1
    assert worker.control('release', 2) == 1
    worker.until(worker.barrier.symbols['npu_barrier_refreshed'])
    assert worker.cpu.reg_read(r.UC_RISCV_REG_A2) == 2
    assert worker.control('stop') == 3
    before = len(worker.helper_calls)
    worker.execute()
    assert worker.barrier.snapshot()[5 + hart] == 3
    assert worker.barrier.snapshot()[13 + hart] == 1
    assert not worker.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
    assert len(worker.helper_calls) == before
    for epoch in (2, 3):
        assert worker.control('reclaimable', epoch) == 0
        assert worker.control('record_drain', 0, epoch) == 0
        assert worker.control('arm', epoch) == 0
    return {'hart': hart, 'interrupted_refresh_epoch': 2, 'parked_epoch': 3,
            'stale_adapter_refresh_rejected': True}


def shared_workers(path):
    """Seven original worker contexts, one memory image; hart0/drains modeled."""
    worker = Worker(path, 1)
    for address, (symbol, expected) in CORE5_SITES.items():
        assert bytes(worker.cpu.mem_read(address, 4)).hex() == expected
        worker.cpu.mem_write(address, jump(address, worker.barrier.symbols[symbol]))
        worker.cpu.hook_add(UC_HOOK_CODE, worker.worker_hook, begin=address, end=address)
    entries = {**ENTRIES, 5: 0x8400cb0e}
    outer = {**OUTER, 5: 0x8400cbbe}
    contexts = {}
    initial = worker.cpu.context_save()
    for hart in range(1, 8):
        worker.cpu.context_restore(initial)
        worker.hart = hart
        worker.cpu.reg_write(r.UC_RISCV_REG_SP, 0x8401de00 + hart * 0x4000)
        worker.until(outer[hart], entries[hart])
        contexts[hart] = worker.cpu.context_save()
    rng = random.Random(0x7581)
    cycles = []
    for epoch in (2, 3, 4):
        assert worker.control('stop') == epoch
        order = list(range(1, 8))
        rng.shuffle(order)
        acknowledgements = []
        for hart in order:
            worker.hart = hart
            worker.cpu.context_restore(contexts[hart])
            worker.execute()
            contexts[hart] = worker.cpu.context_save()
            assert worker.barrier.snapshot()[5 + hart] == epoch
            assert not worker.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
            assert worker.control('workers_parked', epoch) == 0
            assert worker.control('record_drain', 0, epoch) == 0
            acknowledgements.append(hart)
            assert all(worker.barrier.snapshot()[5 + owner] == (
                epoch if owner in acknowledgements else epoch - 1) for owner in range(8))
        assert worker.control('poll', 0) == PARK
        assert worker.control('workers_parked', epoch) == 1
        for domain in range(5):
            assert worker.control('record_drain', domain, epoch) == 1
        assert worker.control('reclaimable', epoch) == 1
        base = OLD if epoch == 3 else NEW
        worker.replace(base)
        worker.put32(SRAM + 0x1f3c, base + 0x800)
        worker.put16(SRAM + 0x46e2, 7)
        worker.put32(base + 0x870, 0xfe)
        worker.ring_reads.clear()
        worker.tracking = True
        assert worker.control('prepare', epoch) == 1
        assert worker.control('release', epoch) == 1
        rng.shuffle(order)
        before = len(worker.helper_calls)
        refreshed = []
        for hart in order:
            worker.hart = hart
            worker.cpu.context_restore(contexts[hart])
            worker.execute()
            contexts[hart] = worker.cpu.context_save()
            assert worker.barrier.snapshot()[13 + hart] == epoch
            assert worker.control('arm', epoch) == 0
            assert worker.control('reclaimable', epoch) == 0
            assert len(worker.helper_calls) == before and worker.enqueue is None
            refreshed.append(hart)
            assert all(worker.barrier.snapshot()[13 + owner] == (
                epoch if owner in refreshed else epoch - 1) for owner in range(8))
        assert worker.control('refreshed', 0, epoch) == 1
        assert worker.control('arm', epoch) == 1
        for hart in range(1, 8):
            worker.hart = hart
            worker.cpu.context_restore(contexts[hart])
            worker.until({5: 0x8400cc0c, 6: 0x8400cd9e}.get(hart, outer[hart]))
            contexts[hart] = worker.cpu.context_save()
            assert worker.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
        assert worker.ring_reads
        assert all(base <= int(read['address'], 16) < base + 0x1000
                   for read in worker.ring_reads), (epoch, worker.ring_reads)
        worker.tracking = False
        cycles.append({'epoch': epoch, 'actual_worker_ack_order': acknowledgements,
                       'actual_worker_refresh_order': order.copy(),
                       'resource_base': hex(base), 'ring_reads': worker.ring_reads.copy(),
                       'missing_coordinator_rejected': True})
    return {'shared_sram': True, 'cycles': cycles,
            'scope': 'Serialized scheduling of seven saved RV32 worker contexts in one Unicorn memory image; coordinator0 acknowledgement and hardware domain witnesses modeled. Not simultaneous execution or physical coherency proof.'}


def main():
    path = build_workers()
    checks = preservation(path)
    cases = [stop_resume(path, site) for site in SITES]
    busy = [in_flight(path, hart, helper) for hart, helper in
            ((1, 0x8400bd96), (2, 0x8400e87a), (3, 0x8400f638),
             (4, 0x8400b0a6), (6, 0x8400c284), (7, 0x84001528))]
    startup = [startup_wait(path, hart, flag) for hart, flags in STARTUP_FLAGS.items()
               for flag in flags]
    shared = shared_workers(path)
    interrupted = [refresh_interrupted(path, hart) for hart in ENTRIES]
    negatives = {}
    for site in (0x8400cf26, 0x8400ece6, 0x8400d160, 0x8400cd9e):
        try:
            stop_resume(path, site, omit=site)
        except MissingParkAck as error:
            negatives[hex(site)] = {'rejected': True, 'assertion': str(error)}
        else:
            raise AssertionError(('missing detour accepted', hex(site)))
    cache_mutations = [('OMIT_REFILL_REFRESH', 0x8400cf10),
                       ('OMIT_FAST_REFRESH', 0x8400ecc2),
                       ('OMIT_FAST_STARTUP', 0x8400ec7e)]
    cache_mutations.extend((f'OMIT_REFILL_SLOT={index}', 0x8400cf10) for index in range(5))
    cache_mutations.extend((f'OMIT_FAST_SLOT={index}', 0x8400ecc2) for index in range(2))
    for define, site in cache_mutations:
        mutation = build_workers(define)
        try:
            stop_resume(mutation, site)
        except StaleOwnershipCache as error:
            negatives[define] = {'rejected': True, 'assertion': str(error),
                                 'elf_sha256': digest(mutation.read_bytes())}
        else:
            raise AssertionError(('missing refresh accepted', define))
    for hart, flags in STARTUP_FLAGS.items():
        site = next(address for address, details in SITES.items()
                    if details[:2] == (hart, 'startup'))
        try:
            startup_wait(path, hart, flags[0], omit=site)
        except MissingParkAck as error:
            negatives[f'missing-startup-core{hart}'] = {'rejected': True, 'assertion': str(error)}
        else:
            raise AssertionError(('missing startup accepted', hart))
    core5 = {'cases': [stopped_at(path, site) for site in CORE5_SITES],
             'inflight': inflight(path), 'preservation': passthrough(path)}
    report = {'passed': True, 'firmware_sha256': CODE_SHA, 'data_sha256': DATA_SHA,
              'elf_sha256': digest(path.read_bytes()), 'new_detours': Worker(path, 1).patches,
              'stop_resume': cases, 'register_mstatus_differential': checks,
              'inflight': busy, 'mutation_controls': negatives,
              'missing_startup_dependencies': startup, 'seven_shared_workers': shared,
              'actual_adapter_refresh_interrupted': interrupted,
              'core5_combined_elf_regression': core5,
              'source_sha256': {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in
                                (SOURCE, SOURCE.with_suffix('.h'), ASM, LINKER, Path(__file__),
                                 ASM.parent / 'barrier-core5-emulation.S',
                                 ASM.parent / 'test_barrier_protocol.py',
                                 ASM.parent / 'test_barrier_core5.py',
                                 ASM.parent / 'test_firmware_stop_counterexample.py')},
              'scope': '16 new emulator-memory detours plus four prior core5 detours in one ELF. Original worker entry/loop instructions for harts1/2/3/4/6; original core7 wrapper and IRQ registration, modeled PLIC memory. Helper returns and other-hart/domain witnesses are modeled; coordinator0, hardware IRQ delivery, asynchronous DMA/cache/bus drain, all-path closure and production placement are NOT proved. No deployable firmware blob or router test.'}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'worker-tests.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'detours': 20, 'new_stop_resume': len(cases),
                      'differential_cases': len(checks), 'inflight': len(busy),
                      'startup_dependencies': len(startup), 'shared_worker_cycles': len(shared['cycles']),
                      'interrupted_refresh': len(interrupted),
                      'negative_controls': len(negatives), 'elf_sha256': report['elf_sha256']}))


if __name__ == '__main__':
    main()
