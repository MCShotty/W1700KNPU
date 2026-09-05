#!/usr/bin/env python3
"""Native stock ARM64/RV32 GDMA contracts under explicit device hypotheses."""
import io
import json
import struct

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import arm64_const as a
from unicorn import riscv_const as r

from test_firmware_memory_layout import NativeMemory, ROOT, OUT, sha
from test_firmware_stop_counterexample import END

GDMA = 0x1fb30000
KERNEL_SHA = 'a51e6d0a6deee620a5f715c9469f193906cdf3fcea28b97ce01cf88383aa704e'


class Device:
    def __init__(self, cpu, pc_register, channel, stale=False, clear_on_start=False,
                 done_after=None, idle_after=None):
        self.cpu, self.pc_register, self.channel = cpu, pc_register, channel
        self.done = (1 << channel if stale else 0) | (1 << 31)
        self.control = 0
        self.clear_on_start, self.done_after, self.idle_after = clear_on_start, done_after, idle_after
        self.done_reads = self.control_reads = 0
        self.events = []
        cpu.mem_map(GDMA, 0x1000)
        cpu.hook_add(UC_HOOK_MEM_READ, self.read, begin=GDMA, end=GDMA + 0xfff)
        cpu.hook_add(UC_HOOK_MEM_WRITE, self.write, begin=GDMA, end=GDMA + 0xfff)

    def event(self, kind, address, value):
        self.events.append({'kind': kind, 'offset': hex(address - GDMA), 'value': hex(value),
                            'pc': hex(self.cpu.reg_read(self.pc_register))})

    def read(self, cpu, access, address, size, _value, data):
        assert size == 4
        if address == GDMA + 0x204:
            self.done_reads += 1
            if self.done_after and self.done_reads == self.done_after:
                self.done |= 1 << self.channel
                self.control &= ~2
            value = self.done
        elif address == GDMA + self.channel * 16 + 8:
            self.control_reads += 1
            if self.idle_after and self.control_reads == self.idle_after:
                self.control &= ~2
            value = self.control
        else:
            value = struct.unpack('<I', cpu.mem_read(address, 4))[0]
        cpu.mem_write(address, struct.pack('<I', value))
        self.event('read', address, value)

    def write(self, cpu, access, address, size, value, data):
        assert size == 4
        if address == GDMA + 0x204:
            self.done &= ~value
        elif address == GDMA + self.channel * 16 + 8:
            self.control = value
            if self.clear_on_start and value & 2:
                self.done &= ~(1 << self.channel)
        self.event('write', address, value)


class Kernel:
    def __init__(self):
        data = (ROOT / 'research/stock/elf/stock-kernel.vmlinux.elf').read_bytes()
        assert sha(data) == KERNEL_SHA
        elf = ELFFile(io.BytesIO(data))
        self.cpu = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        section = elf.get_section_by_name('.kernel')
        # Preserve PC-relative displacements while moving the two kernel text pages.
        original = 0xffffffc0100cb000
        offset = original - section['sh_addr']
        assert 0 <= offset <= section['sh_size'] - 0x2000
        self.cpu.mem_map(0x100cb000, 0x2000)
        self.cpu.mem_write(0x100cb000, section.data()[offset:offset + 0x2000])
        self.cpu.mem_map(0x10c6c000, 0x1000)
        self.cpu.mem_map(0x20000000, 0x2000)
        self.cpu.mem_map(0x30000000, 0x1000)
        self.cpu.mem_write(0x10c6c138, struct.pack('<Q', 0x20000000))
        self.cpu.mem_write(0x20000008, struct.pack('<Q', GDMA))

    def call(self, offset, *args, returns=True):
        self.cpu.reg_write(a.UC_ARM64_REG_SP, 0x20002000)
        self.cpu.reg_write(a.UC_ARM64_REG_X30, 0x30000000)
        for index, value in enumerate(args):
            self.cpu.reg_write(getattr(a, 'UC_ARM64_REG_X' + str(index)), value)
        self.cpu.emu_start(0x10000000 + offset, 0x30000000, count=2000, timeout=1000000)
        assert (self.cpu.reg_read(a.UC_ARM64_REG_PC) == 0x30000000) == returns
        return self.cpu.reg_read(a.UC_ARM64_REG_X0)


def rv_helper(channel, length, stale=False, clear_on_start=False, done_after=None, returns=True):
    native = NativeMemory()
    device = Device(native.cpu, r.UC_RISCV_REG_PC, channel, stale, clear_on_start, done_after)
    values = (channel, 0x82000000, 0x82001000, length)
    for index, value in enumerate(values):
        native.cpu.reg_write(getattr(r, 'UC_RISCV_REG_A' + str(index)), value)
    native.cpu.reg_write(r.UC_RISCV_REG_SP, 0x84021e00)
    native.cpu.reg_write(r.UC_RISCV_REG_RA, END)
    native.cpu.emu_start(0x840053a6, END, count=2000, timeout=1000000)
    assert (native.cpu.reg_read(r.UC_RISCV_REG_PC) == END) == returns
    writes = [event for event in device.events if event['kind'] == 'write']
    assert [(event['offset'], int(event['value'], 16)) for event in writes[:3]] == [
        (hex(channel * 16), 0x82000000), (hex(channel * 16 + 4), 0x82001000),
        (hex(channel * 16 + 8), (length << 16 | 0x23) & 0xffffffff)]
    assert device.control_reads == 0
    if returns:
        assert len(writes) == 4 and writes[-1]['offset'] == '0x204'
        assert int(writes[-1]['value'], 16) == 1 << channel
        assert device.done == 1 << 31
    else:
        assert len(writes) == 3 and device.done_reads > 50
    return {'channel': channel, 'length': length, 'stale_initial_done': stale,
            'modeled_start_clears_done': clear_on_start, 'modeled_new_done_after_reads': done_after,
            'returned': returns, 'done_reads': device.done_reads, 'control_reads': device.control_reads,
            'control_enable_at_return_or_bound': bool(device.control & 2), 'writes': writes}


def native_kernel():
    records = []
    for channel in (0, 1, 3, 7):
        kernel = Kernel()
        device = Device(kernel.cpu, a.UC_ARM64_REG_PC, channel, stale=True, idle_after=7)
        kernel.call(0xcbfc4, channel, 0x82000000, 0x82001000, 0x4c0023, 0x1234)
        assert [(event['offset'], int(event['value'], 16)) for event in device.events] == [
            (hex(channel * 16), 0x82000000), (hex(channel * 16 + 4), 0x82001000),
            (hex(channel * 16 + 12), 0x1234), (hex(channel * 16 + 8), 0x4c0023)]
        kernel.call(0xcc120, channel)
        assert device.control_reads == 7 and device.done_reads == 0
        assert device.done & (1 << channel)
        assert kernel.call(0xcc220, channel) == 1
        kernel.call(0xcbfa0, channel)
        assert kernel.call(0xcc220, channel) == 0 and device.done == 1 << 31
        assert kernel.call(0xcc160, channel) == 0x82000000
        assert kernel.call(0xcc1c0, channel) == 0x82001000
        assert kernel.call(0xcc1f0, channel) == 0x1234
        assert kernel.call(0xcc190, channel) == 0x4c0021
        kernel.call(0xcc290, channel)
        assert device.control & 2
        device.idle_after = None
        kernel.call(0xcc120, channel, returns=False)
        assert device.control_reads > 50
        records.append({'channel': channel, 'config_and_accessors_verified': True,
                        'wait_polls_enable_not_done': True, 'done_clear_preserves_other_channel': True,
                        'enable_set_preserves_other_control_bits': True,
                        'wait_without_idle_does_not_return_within_2000_instructions': True})
    return records


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rv = [rv_helper(channel, length, done_after=7) for channel in (0, 1, 3)
          for length in (0, 0x4c, 0x700, 0xffff)]
    stalled = rv_helper(1, 0x4c, returns=False)
    stale = rv_helper(1, 0x4c, stale=True)
    cleared = rv_helper(1, 0x4c, stale=True, clear_on_start=True, done_after=7)
    assert stale['done_reads'] == 1 and stale['control_enable_at_return_or_bound']
    assert cleared['done_reads'] == 7 and not cleared['control_enable_at_return_or_bound']
    result = {'passed': True, 'kernel_sha256': KERNEL_SHA, 'kernel_cases': native_kernel(),
              'rv32_cases': rv, 'rv32_stalled': stalled,
              'conditional_stale_done': stale, 'alternative_start_clears_done': cleared,
              'scope': 'Native register accesses, not hardware DMA. Stock WAIT observes CT0.ENABLE clear; RV32 helper only observes DONE. Stale-DONE outcome is conditional on an unverified hardware start-clear rule. No physical drain witness recorded.'}
    (OUT / 'native-gdma.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'kernel_cases': len(result['kernel_cases']),
                      'rv32_normal_cases': len(rv), 'rv32_hypothesis_controls': 3}))


if __name__ == '__main__':
    main()
