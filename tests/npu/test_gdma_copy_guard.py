#!/usr/bin/env python3
"""Execute the candidate guard and original caller with explicit DMA models."""
import json
import struct

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r

from test_admission_native import build_platform
from test_admission_protocol import packet
from test_barrier_core5 import jump
from test_barrier_protocol import Rv32, digest, BUILD
from test_firmware_memory_layout import NativeMemory
from test_firmware_stop_counterexample import ROOT, END, HART_ID
from emulation_layout import STATE, SRAM, HEAP

OUT = ROOT / 'research/checkpoints/2026-09-06-npu-copy'
SOURCE = ROOT / 'firmware/npu/gdma.c'
GDMA, DATA, SRC, DST = 0x1fb30000, 0x42000000, 0x82000010, 0x82020000
DESCRIPTOR = HEAP + 0x1000
REGS = [getattr(r, 'UC_RISCV_REG_A' + str(i)) for i in range(8)]
SAVED = [getattr(r, 'UC_RISCV_REG_S' + str(i)) for i in range(12)]


class CompletionDevice:
    def __init__(self, harness, channel=0, initial_done=False, early_done=False,
                 idle_at=5, busy_before=0, stuck_pre_clear=False,
                 stuck_post_clear=False, lost_done=False):
        self.h = harness
        self.channel, self.bit = channel, 1 << channel
        self.done = (self.bit if initial_done else 0) | (1 << 31)
        self.control = 2 if busy_before else 0
        self.busy_before, self.idle_at = busy_before, idle_at
        self.early_done, self.lost_done = early_done, lost_done
        self.stuck_pre_clear, self.stuck_post_clear = stuck_pre_clear, stuck_post_clear
        self.launches = self.post_reads = self.pre_reads = self.copies = 0
        self.irq_enabled_accesses = 0
        self.finished = self.overwrote_busy = False
        self.source, self.destination, self.length = SRC, DST, 0
        self.events = []
        harness.cpu.mem_map(GDMA, 0x1000)
        harness.cpu.hook_add(UC_HOOK_MEM_READ, self.read, begin=GDMA, end=GDMA + 0xfff)
        harness.cpu.hook_add(UC_HOOK_MEM_WRITE, self.write, begin=GDMA, end=GDMA + 0xfff)

    def complete(self):
        if not self.finished:
            src = self.source & 0x3fffffff | 0x40000000
            dst = self.destination & 0x3fffffff | 0x40000000
            if self.length:
                self.h.cpu.mem_write(dst, bytes(self.h.cpu.mem_read(src, self.length)))
            self.copies += 1
            self.finished = True
            self.control &= ~2
            if not self.lost_done:
                self.done |= self.bit

    def read(self, cpu, access, address, size, value, data):
        assert size == 4
        self.irq_enabled_accesses += bool(cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8)
        if address == GDMA + 0x204:
            if self.launches and not self.finished:
                self.post_reads += 1
                if self.idle_at is not None and self.post_reads >= self.idle_at:
                    self.complete()
            value = self.done
        elif address == GDMA + self.channel * 16 + 8:
            if not self.launches:
                self.pre_reads += 1
                if self.busy_before >= 0 and self.pre_reads >= self.busy_before:
                    self.control &= ~2
            value = self.control
        else:
            value = self.h.get32(address)
        self.h.put32(address, value)
        self.events.append(('read', address - GDMA, value))

    def write(self, cpu, access, address, size, value, data):
        assert size == 4
        self.irq_enabled_accesses += bool(cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8)
        self.events.append(('write', address - GDMA, value))
        if address == GDMA + 0x204:
            ignore = self.stuck_post_clear if self.launches else self.stuck_pre_clear
            if not ignore:
                self.done &= ~value
        elif address == GDMA + self.channel * 16:
            self.source = value
        elif address == GDMA + self.channel * 16 + 4:
            self.destination = value
        elif address == GDMA + self.channel * 16 + 8:
            self.overwrote_busy |= bool(self.control & 2)
            self.launches += 1
            self.control, self.length = value, value >> 16
            if self.early_done:
                self.done |= self.bit
            if self.h.pause_on_launch:
                self.h.pause_pending = True
            if self.h.fault_on_launch:
                self.h.put32(STATE + 16, 1)

    def summary(self):
        return {'launches': self.launches, 'copies': self.copies, 'post_done_reads': self.post_reads,
                'pre_control_reads': self.pre_reads, 'enable': bool(self.control & 2),
                'irq_enabled_accesses': self.irq_enabled_accesses,
                'overwrote_busy': self.overwrote_busy,
                'writes': [[hex(offset), hex(value)] for kind, offset, value in self.events if kind == 'write']}


class CopyCaller(NativeMemory):
    def __init__(self, path, guarded=True, hart=3, channel=0, **model):
        self.hart = hart
        self.pause_on_launch = self.pause_pending = self.paused = False
        self.fault_on_launch = self.skip_park = False
        super().__init__()
        self.rv = Rv32(path, self.cpu)
        self.rv.call('init')
        self.admission_snapshot = struct.pack('<11I', 0, 2, 0, 0x12345678, 0x87654321, 1, 2, 4, 8, 16, 32)
        self.cpu.mem_write(STATE + 0x100, self.admission_snapshot)
        self.cpu.mem_map(DATA, 0x40000)
        payload = bytes(i % 251 for i in range(0x10000))
        self.cpu.mem_write(DATA + 0x10, payload)
        self.cpu.mem_write(DATA + 0x20000, b'\xa5' * 0x10000)
        self.cpu.mem_write(DATA + 0x32, b'\x44\x33')
        self.put32(DATA, 0x4c << 18)
        self.put32(DATA + 4, 0xabcdef01)
        self.put32(SRAM + 0x2acc, DESCRIPTOR)
        self.put32(DESCRIPTOR, DST)
        self.device = CompletionDevice(self, channel=channel, **model)
        self.park = self.rv.symbols['npu_emulation_gdma_fault_park']
        self.cpu.hook_add(UC_HOOK_CODE, self.watch)
        if guarded:
            assert bytes(self.cpu.mem_read(0x840053a6, 4)).hex() == '93174500'
            self.cpu.mem_write(0x840053a6, jump(0x840053a6, self.rv.symbols['npu_emulation_gdma_copy']))

    def skip(self, cpu, address, size, data):
        cpu.reg_write(r.UC_RISCV_REG_A0, self.hart if address == HART_ID else 0)
        cpu.reg_write(r.UC_RISCV_REG_PC, cpu.reg_read(r.UC_RISCV_REG_RA))

    def watch(self, cpu, address, size, data):
        if self.pause_pending:
            self.pause_pending, self.paused = False, True
            cpu.emu_stop()
        elif address == self.park:
            if self.skip_park:
                self.skip_park = False
            else:
                cpu.emu_stop()

    def execute(self, entry, args=(), status=8, count=50000, timeout=3000000):
        self.cpu.reg_write(r.UC_RISCV_REG_SP, 0x84021e00)
        self.cpu.reg_write(r.UC_RISCV_REG_RA, END)
        self.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, status)
        for index, value in enumerate(args):
            if index < 8:
                self.cpu.reg_write(REGS[index], value)
            else:
                self.put32(0x84021e00 + (index - 8) * 4, value)
        self.cpu.emu_start(entry, END, count=count, timeout=timeout)
        return self.cpu.reg_read(r.UC_RISCV_REG_PC)

    def direct(self, hart, channel, length=0x4c, polls=8):
        assert self.execute(self.rv.symbols['npu_gdma_copy'], (hart, channel, SRC, DST, length, polls), 0) == END
        return self.cpu.reg_read(r.UC_RISCV_REG_A0)

    def caller(self):
        return self.execute(0x8400f0c4, (0, DATA))

    def assert_completed(self):
        assert self.device.finished and not self.device.control & 2, 'metadata published before copy completion'
        assert self.get32(DESCRIPTOR + 12) & 0xff == 1
        assert self.get32(DESCRIPTOR + 8) & 0xffff == 0x3344
        assert self.get32(SRAM + 0x462c) & 0xffff == 1

    def assert_fault_held(self):
        assert self.cpu.reg_read(r.UC_RISCV_REG_PC) == self.park, 'failed void copy returned to publisher'
        assert self.get32(STATE + 16) == 1, 'shared fault not latched'
        assert bytes(self.cpu.mem_read(STATE + 0x100, 44)) == self.admission_snapshot, 'worker wrote coordinator admission state'
        assert not self.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
        context = self.cpu.context_save()
        assert self.rv.call('reclaimable', 1) == 0
        assert self.rv.call('record_drain', 1, 1) == 0
        self.cpu.context_restore(context)

    def assert_retained(self):
        self.assert_fault_held()
        assert self.get32(DESCRIPTOR + 12) & 0xff == 0
        assert self.get32(SRAM + 0x462c) & 0xffff == 0

    def late_completion(self, check=None):
        if self.device.launches:
            self.device.complete()
        self.skip_park = True
        self.cpu.emu_start(self.park, END, count=100, timeout=1000000)
        (check or self.assert_retained)()


FAILURES = {
    'busy_before_start': ({'busy_before': -1}, 2),
    'preclear_not_observed': ({'initial_done': True, 'stuck_pre_clear': True}, 3),
    'done_while_active': ({'early_done': True, 'idle_at': None}, 4),
    'missing_completion': ({'idle_at': None}, 4),
    'idle_without_done': ({'lost_done': True}, 4),
    'postclear_not_observed': ({'stuck_post_clear': True}, 5),
}


def normal_cases(path):
    cases = []
    for hart, channel in ((2, 1), (3, 0), (3, 3)):
        for initial_done in (False, True):
            for early_done in (False, True):
                for length in (0, 0x4c, 0x700, 0xffff):
                    h = CopyCaller(path, hart=hart, channel=channel, initial_done=initial_done, early_done=early_done)
                    assert h.direct(hart, channel, length) == 0
                    assert h.device.launches == h.device.copies == 1 and not h.device.overwrote_busy
                    assert h.device.done == 1 << 31 and not h.device.control & 2
                    assert bytes(h.cpu.mem_read(DATA + 0x20000, length)) == bytes(h.cpu.mem_read(DATA + 0x10, length))
                    writes = h.device.summary()['writes']
                    assert [int(row[0], 16) for row in writes] == [0x204, channel * 16, channel * 16 + 4, channel * 16 + 8, 0x204]
                    cases.append({'hart': hart, 'channel': channel, 'length': length,
                                  'initial_done': initial_done, 'early_done': early_done})
    return cases


def owner_and_limit_cases(path):
    rejected = []
    for hart in range(8):
        for channel in range(8):
            if (hart, channel) in ((2, 1), (3, 0), (3, 3)):
                continue
            h = CopyCaller(path)
            assert h.direct(hart, channel) == 1 and not h.device.events, 'foreign hart admitted'
            rejected.append([hart, channel])
    for hart, channel, length, polls in ((3, 0, 0x10000, 8), (3, 0, 1, 0), (3, 32, 1, 8), (0xffffffff, 0, 1, 8)):
        h = CopyCaller(path)
        assert h.direct(hart, channel, length, polls) == 1 and not h.device.events
        rejected.append([hart, channel, length, polls])
    return rejected


def failure_cases(path):
    cases = {}
    for name, (model, expected) in FAILURES.items():
        direct = CopyCaller(path, **model)
        assert direct.direct(3, 0) == expected, name
        if name == 'busy_before_start':
            assert not direct.device.summary()['writes'], 'busy channel overwritten'
        if name == 'preclear_not_observed':
            assert direct.device.launches == 0
        caller = CopyCaller(path, **model)
        caller.caller()
        caller.assert_retained()
        caller.late_completion()
        cases[name] = {'result': expected, 'retained_after_late_completion': True,
                       'device': caller.device.summary()}
    for name in ('wrong_hart', 'already_faulted', 'fault_during_copy'):
        h = CopyCaller(path, hart=0 if name == 'wrong_hart' else 3)
        if name == 'already_faulted':
            h.put32(STATE + 16, 1)
        h.fault_on_launch = name == 'fault_during_copy'
        h.caller()
        h.assert_retained()
        h.late_completion()
        if name != 'fault_during_copy':
            assert not h.device.events
        cases[name] = {'retained_after_late_completion': True, 'device': h.device.summary()}
    return cases


def caller_counterexample(path):
    old = CopyCaller(path, guarded=False, initial_done=True, early_done=True)
    assert old.caller() == END
    assert old.get32(DESCRIPTOR + 12) & 0xff == 1
    assert old.get32(DESCRIPTOR + 8) & 0xffff == 0xa5a5
    assert old.device.control & 2 and not old.device.finished
    guarded = CopyCaller(path, initial_done=True, early_done=True)
    assert guarded.caller() == END
    guarded.assert_completed()
    return {'conditional_original_ready_before_copy': True,
            'original_sequence': '0xa5a5', 'guarded_sequence': '0x3344',
            'guarded_device': guarded.device.summary()}


def stop_inflight(path):
    h = CopyCaller(path, early_done=True)
    for hart in range(8):
        h.rv.call('poll', hart)
    for domain in range(5):
        assert h.rv.call('record_drain', domain, 1) == 1
    assert h.rv.call('prepare', 1) == h.rv.call('release', 1) == 1
    for hart in range(8):
        h.rv.call('refreshed', hart, 1)
    assert h.rv.call('arm', 1) == 1
    h.pause_on_launch = True
    h.caller()
    assert h.paused and h.device.launches == 1
    context = h.cpu.context_save()
    assert h.rv.call('stop') == 2
    for hart in range(8):
        if hart != 3:
            h.rv.call('poll', hart)
    assert h.rv.call('workers_parked', 2) == 0
    assert h.get32(STATE + (5 + 3) * 4) == 1
    h.cpu.context_restore(context)
    h.cpu.emu_start(h.cpu.reg_read(r.UC_RISCV_REG_PC), END, count=50000, timeout=3000000)
    assert h.cpu.reg_read(r.UC_RISCV_REG_PC) == END
    h.assert_completed()
    assert h.get32(STATE + (5 + 3) * 4) == 1, 'copy helper emitted a premature worker ACK'
    assert h.rv.call('reclaimable', 2) == 0
    return {'completed_admitted_copy_after_stop': True, 'no_ack_from_copy_helper': True,
            'other_hart_polls_and_initial_drain_witnesses_modeled': True}


def abi_cases(path):
    cases = []
    for hart, channel in ((2, 1), (3, 0), (3, 3)):
        for status in (0, 8):
            h = CopyCaller(path, hart=hart, channel=channel)
            values = [0x55550000 + index for index in range(len(SAVED))]
            for register, value in zip(SAVED, values):
                h.cpu.reg_write(register, value)
            assert h.execute(0x840053a6, (channel, SRC, DST, 0x4c), status) == END
            assert [h.cpu.reg_read(register) for register in SAVED] == values
            assert h.cpu.reg_read(r.UC_RISCV_REG_SP) == 0x84021e00
            assert h.cpu.reg_read(r.UC_RISCV_REG_GP) == SRAM + 0x13a8
            assert h.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8 == status
            assert not h.device.irq_enabled_accesses, 'copy MMIO with IRQ admission open'
            cases.append({'hart': hart, 'channel': channel, 'incoming_mie': status})
    return cases


def coordinator_observes_fault(path):
    h = CopyCaller(path, idle_at=None)
    h.caller()
    h.assert_retained()
    worker = h.cpu.context_save()
    h.hart = 0
    control = STATE + 0x200
    h.cpu.mem_write(control, struct.pack('<16I', *packet(3)))
    assert h.execute(h.rv.symbols['npu_admission_control'], (STATE + 0x100, STATE, control, 64), 0) == END
    reply = struct.unpack('<16I', h.cpu.mem_read(control, 64))
    assert reply[9] == 6 and reply[10] == 7
    assert h.execute(h.rv.symbols['npu_admission_begin_legacy'], (STATE + 0x100, STATE), 0) == END
    assert h.cpu.reg_read(r.UC_RISCV_REG_A0) == 0
    assert bytes(h.cpu.mem_read(STATE + 0x100, 44)) == h.admission_snapshot
    h.cpu.context_restore(worker)
    h.assert_retained()
    return {'status_reports_shared_fault': True, 'reclaim_and_restart_caps_clear': True,
            'new_handler_denied': True, 'coordinator_owned_state_unchanged_by_worker': True,
            'scope': 'Native coordinator C functions with hart-zero fixture; not physical IRQ delivery.'}


def native_fast_caller(path, band, guarded=True, **model):
    h = CopyCaller(path, guarded=guarded, hart=2, channel=1, **model)
    tx, payload, registers = HEAP + 0x3000, DATA + 0x24000, 0x20000000
    h.cpu.mem_map(registers, 0x1000)
    desc_slot, cursor, tx_slot, payload_slot, tx_cursor, register_slot = (
        (0x2acc, 0x395a, 0x21ec, 0x2cf8, 0x3978, 0x4700) if band == 0 else
        (0x21e8, 0x390c, 0x459c, 0x2ab4, 0x21f4, 0x46fc))
    for offset, value in ((desc_slot, DESCRIPTOR), (tx_slot, tx), (payload_slot, payload),
                          (register_slot, registers)):
        h.put32(SRAM + offset, value)
    h.put32(DESCRIPTOR, SRC)
    h.put32(DESCRIPTOR + 4, 0xabcde001)
    h.put32(DESCRIPTOR + 8, 0x004c1234)
    h.put32(DESCRIPTOR + 12, 1)
    h.put32(tx + 4, 0x80000000)
    h.put32(tx + 20, 0x80000000)
    h.execute(0x8400e87a, (band,))

    def retained():
        h.assert_fault_held()
        assert h.get32(DESCRIPTOR + 12) & 0xff == 1
        assert h.get32(DESCRIPTOR + 4) == 0xabcde001
        assert h.get32(tx + 4) == 0x80000000
        assert h.get32(SRAM + cursor) & 0xffff == 0
        assert h.get32(registers + 8) == 0

    if h.cpu.reg_read(r.UC_RISCV_REG_PC) == h.park:
        retained()
        h.late_completion(retained)
    else:
        assert h.cpu.reg_read(r.UC_RISCV_REG_PC) == END
        assert h.get32(tx + 4) == 0x004c4048
        assert h.get32(tx + 8) == 0xabcde001
        assert h.get32(DESCRIPTOR + 12) & 0xff == 0
        assert h.get32(DESCRIPTOR + 4) == 0
        assert h.get32(registers + 8) == h.get32(SRAM + tx_cursor) & 0xffff == 1
        if guarded:
            assert h.device.finished and not h.device.control & 2, 'fast caller released before copy completion'
            assert bytes(h.cpu.mem_read(payload, 0x20)) == bytes(h.cpu.mem_read(DATA + 0x10, 0x20))
        else:
            assert not h.device.finished and h.device.control & 2
    return h


def native_fragment_caller(path, length, fragment, guarded=True, **model):
    h = CopyCaller(path, guarded=guarded, hart=3, channel=3, **model)
    desc, stats = HEAP + 0x3000, HEAP + 0x6000
    h.put32(SRAM + 0x1f08, stats)
    h.put32(desc + 12, DST)
    h.execute(0x8400f528, (desc, SRC, length, 0x1234, 7, 2, fragment, 1, 0x11223344))

    def retained():
        h.assert_fault_held()
        assert h.get32(desc) & 1 == 0
        assert h.get32(desc + 8) == 0

    if h.cpu.reg_read(r.UC_RISCV_REG_PC) == h.park:
        retained()
        h.late_completion(retained)
    else:
        assert h.cpu.reg_read(r.UC_RISCV_REG_PC) == END
        assert h.get32(desc) & 1 == 1 and h.get32(desc + 8) == 0x11223344
        assert h.device.length == (length if length <= 0x700 else min(fragment, 0x700))
        if guarded:
            assert h.device.finished and not h.device.control & 2, 'fragment published before copy completion'
        else:
            assert not h.device.finished and h.device.control & 2
    return h


def other_callers(path):
    rows = []
    for band in (0, 1):
        for name, options in (('early-done', {'initial_done': True, 'early_done': True}),
                              ('timeout', {'idle_at': None}), ('ack-failure', {'stuck_post_clear': True})):
            h = native_fast_caller(path, band, **options)
            rows.append({'caller': '0x8400e87a', 'band': band, 'case': name, 'device': h.device.summary()})
        native_fast_caller(path, band, guarded=False, initial_done=True, early_done=True)
    for length, fragment in ((0, 0), (0x4c, 0x4c), (0x701, 0x123), (0x4000, 0x900)):
        for name, options in (('early-done', {'initial_done': True, 'early_done': True}),
                              ('timeout', {'idle_at': None})):
            h = native_fragment_caller(path, length, fragment, **options)
            rows.append({'caller': '0x8400f528', 'length': length, 'fragment': fragment,
                         'case': name, 'device': h.device.summary()})
    native_fragment_caller(path, 0x4c, 0x4c, guarded=False, initial_done=True, early_done=True)
    return rows


def mutations():
    binding = ROOT / 'tests/npu/gdma-platform-emulation.c'
    source_text, binding_text = SOURCE.read_text(), binding.read_text()
    variants = {
        'done_only': (SOURCE, 'if ((done & bit) && !(read32(base + 8) & GDMA_ENABLE))',
                      'if (done & bit)', 'metadata published before copy completion'),
        'skip_pre_idle': (SOURCE, 'for (left = poll_limit; left; left--)\n        if (!(read32(base + 8) & GDMA_ENABLE))\n            break;',
                          'left = 1;', 'busy channel overwritten'),
        'ignore_owner': (SOURCE, '!((hart == 2 && channel == 1) || (hart == 3 && (channel == 0 || channel == 3))))',
                         '(hart > 7 || channel > 7))', 'foreign hart admitted'),
        'timeout_is_success': (SOURCE, 'return NPU_GDMA_TIMEOUT;', 'return NPU_GDMA_OK;', 'done_while_active'),
        'no_fault_latch': (binding, 'npu_barrier_fail(barrier);', '(void)barrier;', 'shared fault not latched'),
        'worker_writes_admission': (binding, 'npu_barrier_fail(barrier);',
                                   '*(volatile uint32_t *)((uintptr_t)barrier + 0x100) = 1;\n        npu_barrier_fail(barrier);',
                                   'worker wrote coordinator admission state'),
        'irq_not_gated': (binding, 'csrrci %0, mstatus, 8', 'csrr %0, mstatus', 'copy MMIO with IRQ admission open'),
        'fault_returns': (binding, 'for (;;) {', 'do {', 'failed void copy returned to publisher'),
    }
    results = {}
    for name, (input_path, before, after, expected) in variants.items():
        content = source_text if input_path == SOURCE else binding_text
        assert content.count(before) == 1, name
        content = content.replace(before, after)
        if name == 'fault_returns':
            end = '\n        }\n    }\n    __asm__'
            assert content.count(end) == 1
            content = content.replace(end, '\n        } while (0);\n    }\n    __asm__')
        mutant = BUILD / ('gdma-mutant-' + name + '.c')
        mutant.write_text(content)
        path = build_platform(gdma_source=mutant if input_path == SOURCE else SOURCE,
                              gdma_binding=mutant if input_path == binding else None, poll_limit=64)
        try:
            if name == 'done_only':
                caller_counterexample(path)
            elif name == 'skip_pre_idle':
                h = CopyCaller(path, busy_before=-1)
                h.direct(3, 0)
                assert not h.device.overwrote_busy, 'busy channel overwritten'
            elif name == 'ignore_owner':
                owner_and_limit_cases(path)
            elif name == 'irq_not_gated':
                abi_cases(path)
            else:
                failure_cases(path)
        except AssertionError as error:
            assert str(error) == expected, (name, str(error))
            results[name] = {'rejected': True, 'assertion': expected, 'elf_sha256': digest(path.read_bytes())}
        else:
            raise AssertionError('unsafe mutation survived: ' + name)
    return results


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    path = build_platform(gdma_source=SOURCE, poll_limit=64)
    result = {'passed': True, 'elf_sha256': digest(path.read_bytes()), 'poll_limit': 64,
              'normal_cases': normal_cases(path), 'rejected_owners_and_limits': owner_and_limit_cases(path),
              'failure_retention': failure_cases(path), 'caller_counterexample': caller_counterexample(path),
              'stop_inflight': stop_inflight(path), 'abi_cases': abi_cases(path),
              'coordinator_fault_observation': coordinator_observes_fault(path),
              'other_native_callers': other_callers(path),
              'mutation_controls': mutations(),
              'scope': 'Actual RV32 guard, legacy caller and failure park; GDMA completion/data writes and hart ID are modeled. Not a hardware drain, full boot or production host recovery proof.'}
    (OUT / 'copy-guard-tests.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'normal': len(result['normal_cases']),
                      'rejections': len(result['rejected_owners_and_limits']),
                      'retention_cases': len(result['failure_retention']), 'abi': len(result['abi_cases']),
                      'other_native_caller_cases': len(result['other_native_callers'])}))


if __name__ == '__main__':
    main()
