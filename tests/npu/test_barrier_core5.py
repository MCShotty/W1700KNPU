#!/usr/bin/env python3
"""Exercise test-only RV32 detours against the original core-5 counterexample."""
import json
import shutil
import struct
import subprocess

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.riscv_const import UC_RISCV_REG_A0, UC_RISCV_REG_RA, UC_RISCV_REG_PC
from unicorn.riscv_const import UC_RISCV_REG_SP, UC_RISCV_REG_MSTATUS
from unicorn import riscv_const

from test_barrier_protocol import BUILD, SOURCE, LINKER, OUT, Rv32, digest, STATE
from test_barrier_protocol import PARK, REFRESH, RUN, build
from test_firmware_stop_counterexample import Harness, CODE, CODE_SHA, DATA_SHA
from test_firmware_stop_counterexample import DISPATCH, LOOP, END, SET, RING, SRAM, ENQUEUE

SITES = {
    0x8400cb3e: ('gate_core5_startup', '1c43fddf'),
    0x8400cbbe: ('gate_core5_outer', '83570a00'),
    0x8400cbca: ('gate_core5_empty_first', '83576100'),
    0x8400cc0c: ('gate_core5_empty_repeat', '83576100'),
}
NEW_RING = RING + 0x1000


class MissingParkAck(AssertionError):
    pass


def build_detours():
    build()
    clang = shutil.which('clang')
    lld = shutil.which('ld.lld') or str(BUILD / 'lld/usr/lib/llvm-21/bin/ld.lld')
    target = BUILD / 'barrier-core5.elf'
    subprocess.run([clang, '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
                    '-O2', '-Wall', '-Wextra', '-Werror', '-fno-builtin', '-nostdlib',
                    '-fno-stack-protector', f'--ld-path={lld}', str(SOURCE),
                    str(SOURCE.parents[2] / 'tests/npu/barrier-core5-emulation.S'),
                    f'-Wl,-T,{LINKER},--no-relax', '-o', str(target)], check=True)
    return target


def jump(source, target):
    offset = target - source
    assert not offset & 1 and -(1 << 20) <= offset < 1 << 20
    value = ((offset >> 20 & 1) << 31 | (offset >> 1 & 0x3ff) << 21 |
             (offset >> 11 & 1) << 20 | (offset >> 12 & 0xff) << 12 | 0x6f)
    return struct.pack('<I', value)


class Worker(Harness):
    def __init__(self, path, descriptor=4, omit=None):
        super().__init__(descriptor)
        self.finish_enqueue = False
        self.seek = None
        self.hit = None
        self.barrier = Rv32(path, self.cpu)
        self.patches = []
        for address, (symbol, expected) in SITES.items():
            original = bytes(self.cpu.mem_read(address, 4))
            assert original.hex() == expected
            if address == omit:
                continue
            target = self.barrier.symbols[symbol]
            self.cpu.mem_write(address, jump(address, target))
            self.patches.append({'address': hex(address), 'target': hex(target),
                                 'preimage': expected, 'postimage': jump(address, target).hex()})
        for address in SITES:
            self.cpu.hook_add(UC_HOOK_CODE, self.seek_hook, begin=address, end=address)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, self.write_hook, begin=NEW_RING,
                          end=NEW_RING + 0xfff)
        saved = self.cpu.context_save()
        self.barrier.call('init')
        for hart in range(8):
            assert self.barrier.call('poll', hart) == PARK
        for domain in range(5):
            assert self.barrier.call('record_drain', domain, 1) == 1
        self.start_protocol(1)
        self.cpu.context_restore(saved)
        self.cpu.reg_write(UC_RISCV_REG_MSTATUS, 8)

    def start_protocol(self, epoch):
        assert self.barrier.call('prepare', epoch) == 1
        assert self.barrier.call('release', epoch) == 1
        for hart in range(8):
            assert self.barrier.call('poll', hart) == REFRESH
            assert self.barrier.call('refreshed', hart, epoch) == 1
        assert self.barrier.call('arm', epoch) == 1

    def code_hook(self, cpu, address, size, data):
        if address == ENQUEUE and self.finish_enqueue:
            # Complete the already-entered helper in the model; its physical
            # device operations are outside this adapter test.
            cpu.reg_write(UC_RISCV_REG_A0, 0)
            cpu.reg_write(UC_RISCV_REG_PC, cpu.reg_read(UC_RISCV_REG_RA))
            return
        super().code_hook(cpu, address, size, data)

    def seek_hook(self, cpu, address, size, _data):
        if address == self.seek:
            self.hit = address
            cpu.emu_stop()

    def execute(self, pc=None, count=50000):
        self.cpu.emu_start(pc or self.cpu.reg_read(UC_RISCV_REG_PC), END,
                           timeout=2000000, count=count)

    def control(self, function, *args):
        saved = self.cpu.context_save()
        result = self.barrier.call(function, *args)
        self.cpu.context_restore(saved)
        return result

    def mailbox_stop(self):
        saved = self.cpu.context_save()
        assert self.barrier.call('stop') == 2
        self.stop_and_get()
        self.cpu.context_restore(saved)
        self.phase = 'after-stop-get-zero'

    def assert_parked(self):
        if self.barrier.snapshot()[5 + 5] != 2:
            raise MissingParkAck(hex(self.cpu.reg_read(UC_RISCV_REG_PC)))
        assert self.cpu.reg_read(UC_RISCV_REG_MSTATUS) & 8 == 0
        assert self.control('reclaimable', 2) == 0

    def acknowledge_other_owners(self):
        for hart in range(8):
            if hart != 5:
                assert self.control('poll', hart) == PARK
        assert self.control('workers_parked', 2) == 1
        assert self.control('reclaimable', 2) == 0
        for domain in range(5):
            assert self.control('record_drain', domain, 2) == 1
        assert self.control('reclaimable', 2) == 1

    def replace_and_resume(self):
        self.put32(SRAM + 0x1f3c, NEW_RING)
        self.put16(SRAM + 0x46e2, 7)
        self.put32(NEW_RING + 7 * 16, 4)
        self.put32(NEW_RING + 7 * 16 + 4, 0x2222)
        self.put32(NEW_RING + 7 * 16 + 8, 80 << 3)
        saved = self.cpu.context_save()
        self.put32(SRAM + 0x2ac0, SRAM + 0x14000)
        self.call(SET, 2)
        self.call(SET, 7)
        self.cpu.context_restore(saved)
        assert self.control('prepare', 2) == 1
        assert self.control('release', 2) == 1
        self.phase = 'refresh-before-arm'
        self.execute()
        assert self.barrier.snapshot()[13 + 5] == 2
        assert self.enqueue is None and not self.writes
        assert self.control('reclaimable', 2) == 0
        assert self.control('arm', 2) == 0
        for hart in range(8):
            if hart != 5:
                assert self.control('refreshed', hart, 2) == 1
        assert self.control('arm', 2) == 1
        self.phase = 'new-generation-running'
        self.execute(count=2000000)
        assert self.enqueue == [0x2222, 80, 0, 0, 1, 2], self.enqueue
        assert self.get16(SRAM + 0x46e2) == 8
        assert self.get32(NEW_RING + 7 * 16) == 0xfe
        assert self.cpu.reg_read(UC_RISCV_REG_MSTATUS) & 8
        assert len(self.writes) == 2 and all(
            write['phase'] == 'new-generation-running' for write in self.writes)


def stopped_at(path, site, omit=None):
    worker = Worker(path, 4 if site in (0x8400cb3e, LOOP) else 0xfe, omit)
    if site == 0x8400cb3e:
        worker.cpu.reg_write(UC_RISCV_REG_PC, DISPATCH)
        worker.mailbox_stop()
    else:
        worker.execute(DISPATCH, count=2000000)
        assert worker.paused
        if site != LOOP:
            worker.seek = site
            worker.phase = 'seek-empty-poll'
            worker.execute(LOOP)
            assert worker.hit == site, hex(worker.cpu.reg_read(UC_RISCV_REG_PC))
            worker.seek = None
        worker.mailbox_stop()
    worker.execute()
    worker.assert_parked()
    assert not worker.writes and worker.enqueue is None
    assert worker.get16(SRAM + 0x46e2) == 0
    old_descriptor = worker.get32(RING)
    worker.acknowledge_other_owners()
    worker.replace_and_resume()
    assert worker.get32(RING) == old_descriptor
    return {'site': hex(site), 'old_ring_unchanged': True,
            'consumer_reloaded': 7, 'new_enqueue': worker.enqueue,
            'writes': worker.writes}


def inflight(path):
    worker = Worker(path)
    worker.execute(DISPATCH, count=2000000)
    worker.phase = 'active'
    worker.execute(LOOP)
    assert worker.enqueue == [0x1234, 64, 0, 0, 1, 2]
    worker.mailbox_stop()
    for hart in range(8):
        if hart != 5:
            assert worker.control('poll', hart) == PARK
    assert worker.barrier.snapshot()[10] == 1
    assert worker.control('workers_parked', 2) == 0
    assert worker.control('record_drain', 0, 2) == 0
    worker.finish_enqueue = True
    worker.execute(ENQUEUE)
    worker.assert_parked()
    assert worker.control('workers_parked', 2) == 1
    return {'ack_withheld_until_helper_returns': True,
            'helper_return_is_modeled': True, 'writes_before_stop': worker.writes}


def passthrough(path):
    cases = []
    continuations = {LOOP: 0x8400cbc2, 0x8400cbca: 0x8400cbce, 0x8400cc0c: 0x8400cc10}
    registers = [getattr(riscv_const, 'UC_RISCV_REG_X' + str(index)) for index in range(32)]
    for site, (symbol, _expected) in SITES.items():
        for mie in (0, 8):
            for startup_value in ((0, 1) if site == 0x8400cb3e else (1,)):
                worker = Worker(path)
                cpu = worker.cpu
                worker.phase = 'register-preservation'
                for index, register in enumerate(registers):
                    cpu.reg_write(register, 0x12340000 + index)
                cpu.reg_write(UC_RISCV_REG_SP, 0x84035dc0)
                cpu.reg_write(riscv_const.UC_RISCV_REG_A4, SRAM + 0x1800)
                cpu.reg_write(riscv_const.UC_RISCV_REG_S4, SRAM + 0x46e2)
                cpu.reg_write(UC_RISCV_REG_MSTATUS, mie)
                worker.put32(SRAM + 0x1800, startup_value)
                worker.put16(SRAM + 0x46e2, 0x135)
                worker.put16(0x84035dc6, 0x246)
                before = [cpu.reg_read(register) for register in registers]
                expected = before.copy()
                expected[15] = startup_value if site == 0x8400cb3e else (
                    0x135 if site == LOOP else 0x246)
                target = (0x8400cb42 if startup_value else 0x8400cb3e) if site == 0x8400cb3e else continuations[site]
                cpu.hook_add(UC_HOOK_CODE, lambda uc, *_args: uc.emu_stop(), begin=target, end=target)
                worker.execute(worker.barrier.symbols[symbol], count=5000)
                assert cpu.reg_read(UC_RISCV_REG_PC) == target
                assert [cpu.reg_read(register) for register in registers] == expected, hex(site)
                assert cpu.reg_read(UC_RISCV_REG_MSTATUS) & 8 == mie
                cases.append({'site': hex(site), 'mie': bool(mie), 'startup_value': startup_value})
    return cases


def main():
    path = build_detours()
    preservation = passthrough(path)
    cases = [stopped_at(path, address) for address in SITES]
    busy = inflight(path)
    # Without the repeated-empty-loop detour an idle worker never acknowledges.
    try:
        stopped_at(path, 0x8400cc0c, omit=0x8400cc0c)
    except MissingParkAck as error:
        negative = {'rejected': True, 'assertion': str(error)}
    else:
        raise AssertionError('Missing empty-loop detour was not detected')
    report = {'passed': True, 'firmware_sha256': CODE_SHA, 'data_sha256': DATA_SHA,
              'detour_elf_sha256': digest(path.read_bytes()), 'cases': cases,
              'inflight': busy, 'missing_detour_control': negative,
              'register_mie_preservation_cases': preservation,
              'patches': Worker(path).patches,
              'scope': 'Actual RV32 protocol and four instruction detours in emulator memory, original core-5 dispatcher/worker and SET4/GET3/SET2/SET7. Other harts and drain witnesses are modeled; printf/hart ID are stubbed; enqueue halts at entry or has a modeled return. Reserved addresses are emulation-only. No deployable patched blob, all-hart hook integration, cache/bus/DMA proof or router test.'}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'core5-detour-tests.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
