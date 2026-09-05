#!/usr/bin/env python3
"""Original IRQ instructions: worker STOP/GET is not an IRQ ownership barrier."""
import json

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ
from unicorn.riscv_const import UC_RISCV_REG_A0, UC_RISCV_REG_A1, UC_RISCV_REG_A2
from unicorn.riscv_const import UC_RISCV_REG_SP, UC_RISCV_REG_RA, UC_RISCV_REG_PC

from test_firmware_stop_counterexample import Harness, CODE_SHA, DATA_SHA, END, SRAM
from test_barrier_protocol import OUT

REGISTER, DISPATCH, UART, PPE, FREE = 0x84003254, 0x840030b2, 0x840047a0, 0x84008f6e, 0x84004d0e


class Irqs(Harness):
    def __init__(self):
        super().__init__(0xfe, hart=0)
        self.cpu.mem_map(0x0c000000, 0x201000)
        self.cpu.mem_map(0x1ec10000, 0x1000)
        self.cpu.mem_map(0x1fb50000, 0x3000)
        self.character = 0
        self.consumed = False
        self.free_arguments = []
        self.cpu.hook_add(UC_HOOK_CODE, self.print_hook, begin=0x8400452a, end=0x8400452a)
        self.cpu.hook_add(UC_HOOK_CODE, self.free_hook, begin=FREE, end=FREE)
        self.cpu.hook_add(UC_HOOK_MEM_READ, self.uart_read, begin=0x1ec10000, end=0x1ec10017)

    def print_hook(self, cpu, address, size, _data):
        cpu.reg_write(UC_RISCV_REG_A0, 0)
        cpu.reg_write(UC_RISCV_REG_PC, cpu.reg_read(UC_RISCV_REG_RA))

    def free_hook(self, cpu, address, size, _data):
        self.free_arguments.append(cpu.reg_read(UC_RISCV_REG_A0))
        cpu.emu_stop()

    def uart_read(self, cpu, access, address, size, value, _data):
        if address == 0x1ec10014:
            self.put32(address, 0x20 if self.consumed else 0x21)
        elif address == 0x1ec10000:
            self.put32(address, self.character)
            self.consumed = True

    def invoke(self, address, args, halt=None):
        self.cpu.reg_write(UC_RISCV_REG_SP, 0x84021e00)
        self.cpu.reg_write(UC_RISCV_REG_RA, END)
        for register, value in zip((UC_RISCV_REG_A0, UC_RISCV_REG_A1, UC_RISCV_REG_A2), args):
            self.cpu.reg_write(register, value)
        self.cpu.emu_start(address, END, timeout=1000000, count=50000)
        assert self.cpu.reg_read(UC_RISCV_REG_PC) == (halt or END)

    def register(self, source, callback):
        self.invoke(REGISTER, (source, callback, 1))
        table_slot = 0x3e9013a8 + 0x4a8 + source * 4
        assert self.get32(table_slot) == callback
        return hex(table_slot)

    def command(self, command):
        for character in command.encode('ascii'):
            self.character, self.consumed = character, False
            self.invoke(DISPATCH, (0x16,))
            assert self.consumed


def main():
    uart = Irqs()
    uart_slot = uart.register(0x16, UART)
    assert uart.stop_and_get() == 0
    assert uart.get32(SRAM + 0x46ec) == 0
    uart.phase = 'after-stop-get-zero'
    uart.command('rd 3e9046ec 00000000\r')
    assert uart.get32(SRAM + 0x46ec) == 0
    uart.command('xx 3e9046ec 00000001\r')
    assert uart.get32(SRAM + 0x46ec) == 0
    uart.command('wt 3e9046ec 00000001\r')
    assert uart.get32(SRAM + 0x46ec) == 1
    assert uart.get32(0x0c200004) == 0x17

    ppe = Irqs()
    ppe_slot = ppe.register(0x5f, PPE)
    assert ppe.stop_and_get() == 0
    ppe.put32(0x1fb50fe4, 0)
    ppe.invoke(DISPATCH, (0x5f,))
    assert not ppe.free_arguments and ppe.get32(0x0c200004) == 0x60
    ppe.put32(0x1fb50fe4, 1)
    ppe.put32(0x1fb50fe0, 0x11234)
    ppe.invoke(DISPATCH, (0x5f,), halt=FREE)
    assert ppe.free_arguments == [0x1234]

    report = {'passed': True, 'firmware_sha256': CODE_SHA, 'data_sha256': DATA_SHA,
              'native_registration_slots': {'uart_0x16': uart_slot, 'ppe_0x5f': ppe_slot},
              'uart_after_stop_get_zero': {'read_no_mutation': True, 'invalid_command_no_mutation': True,
                                          'write_changes_rx_gate_0_to_1': True},
              'ppe_after_stop_get_zero': {'empty_no_free': True, 'bufid_free_argument': 0x1234},
              'scope': 'Original RV32 registration, IRQ table dispatch, UART handler/parser and PPE handler execute in emulation. UART FIFO/PLIC/PPE registers are modeled, printf and hart-ID getter are stubbed, bufid release halts at entry. This proves conditional software reachability after STOP/GET0, not physical IRQ delivery or actual hardware buffer release. No router contact.'}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'irq-stop-counterexamples.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
