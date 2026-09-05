#!/usr/bin/env python3
"""Execute original mailbox registration/IRQ/Wi-Fi dispatch in modeled memory."""
import json
from pathlib import Path
import struct

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r

from test_firmware_stop_irqs import Irqs, DISPATCH
from test_firmware_stop_counterexample import CODE_SHA, DATA_SHA, SRAM

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/checkpoints/2026-09-05-npu-admission'
MBOX, INIT, ISR, WIFI = 0x1ec0c000, 0x84003f00, 0x84003cd6, 0x84003a9c
PHYSICAL, PAYLOAD, CAPACITY = 0x02000000, 0x42000000, 256
from emulation_layout import ICV

CALLBACK = 0x3e900d2c


class Mailbox(Irqs):
    def __init__(self):
        super().__init__()
        self.cpu.mem_map(MBOX, 0x1000)
        self.cpu.mem_map(PAYLOAD, 0x1000)
        self.entries = []
        self.events = []
        self.trace = False
        self.halt = None
        self.cpu.hook_add(UC_HOOK_MEM_READ, self.mbox_read, begin=MBOX, end=MBOX)
        self.cpu.hook_add(UC_HOOK_MEM_READ, self.payload_read, begin=PAYLOAD, end=PAYLOAD + CAPACITY - 1)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, self.flags_write, begin=MBOX + 0x3c, end=MBOX + 0x3f)
        for address in (DISPATCH, ISR, WIFI, 0x8400fc2c, 0x8400e084, 0x8400ff9c, 0x8400d7ca, 0x84003c28):
            self.cpu.hook_add(UC_HOOK_CODE, self.entry_hook, begin=address, end=address)
        self.invoke(INIT, ())
        assert self.get32(CALLBACK) == WIFI
        assert self.get32(CALLBACK + 4) == 0x84003a86
        assert self.get32(CALLBACK + 16) == 0x84001060
        assert self.get32(CALLBACK + 20) == 0x840060a8
        assert self.get32(SRAM + 0x1850 + 8 * 4) == ISR
        self.put32(SRAM + 0x2ac0, ICV)
        self.trace = True

    def mbox_read(self, cpu, access, address, size, value, data):
        # Modeled successful W1C of the inbound mailbox interrupt status.
        self.put32(MBOX, 0)

    def entry_hook(self, cpu, address, size, data):
        if self.trace:
            self.entries.append(hex(address))
        if address == self.halt:
            cpu.emu_stop()

    def payload_read(self, cpu, access, address, size, value, data):
        if self.trace:
            self.events.append({'kind': 'payload-read', 'offset': address - PAYLOAD, 'size': size})

    def flags_write(self, cpu, access, address, size, value, data):
        if self.trace:
            self.events.append({'kind': 'mailbox-flags-write', 'value': value})

    def message(self, words, length=None, function=0, wait=True, static=False, halt=None, address=PHYSICAL):
        data = struct.pack('<' + 'I' * len(words), *words)
        assert len(data) <= CAPACITY
        self.cpu.mem_write(PAYLOAD, data + bytes(CAPACITY - len(data)))
        self.put32(MBOX + 0x30, address)
        self.put32(MBOX + 0x34, len(data) if length is None else length)
        self.put32(MBOX + 0x3c, function << 11 | int(wait) | (0x20 if static else 0))
        self.entries.clear()
        self.events.clear()
        self.halt = halt
        self.invoke(DISPATCH, (8,), halt=halt)
        return {'flags': self.get32(MBOX + 0x3c),
                'words': list(struct.unpack('<' + 'I' * len(words), self.cpu.mem_read(PAYLOAD, len(data)))),
                'trace': self.entries.copy(), 'events': self.events.copy()}


def main():
    mbox = Mailbox()
    stopped = mbox.message([0x14, 24, 0, 0, 0, 0])
    assert stopped['flags'] == 7 and mbox.get32(SRAM + 0x46ec) == 0
    assert stopped['trace'] == [hex(address) for address in (DISPATCH, ISR, WIFI, 0x8400fc2c, 0x8400e084)]
    mbox.put32(SRAM + 0x46e8, 0)
    mbox.cpu.mem_write(SRAM + 0x46f6, b'\x01\x01')
    idle = mbox.message([0x33, 0, 0x76543210])
    assert idle['flags'] == 7 and idle['words'][2] == 0
    restarted = mbox.message([0x12, 24, 0, 0, 0, 0])
    assert restarted['flags'] == 7 and mbox.get32(SRAM + 0x46ec) == 1

    discovery = Mailbox().message([0x3f, 0, 0x3143514e, 1, 64, *([0] * 11)])
    assert discovery['flags'] == 7 and discovery['words'][2] == 0
    assert discovery['words'][3:] == [1, 64, *([0] * 11)]

    short = Mailbox().message([0x14, 24, 0, 0, 0, 0], length=0)
    assert short['flags'] == 7
    assert any(event['kind'] == 'payload-read' and event['offset'] >= 8 for event in short['events'])
    asynchronous = Mailbox().message([0x14, 24, 0, 0, 0, 0], wait=False, halt=0x84003c28)
    assert asynchronous['events'][0] == {'kind': 'mailbox-flags-write', 'value': 6}
    assert any(event['kind'] == 'payload-read' for event in asynchronous['events'][1:])

    registration = Mailbox()
    before = registration.get32(CALLBACK)
    static = registration.message([0], function=12, static=True)
    assert before == WIFI and registration.get32(CALLBACK) == PHYSICAL
    assert not static['events'] and static['trace'] == [hex(DISPATCH), hex(ISR)]

    report = {'passed': True, 'firmware_sha256': CODE_SHA, 'data_sha256': DATA_SHA,
              'registration': {'wifi': hex(WIFI), 'tunnel': '0x84003a86',
                               'tr471': '0x84001060', 'ppe': '0x840060a8'},
              'native_stop': stopped, 'native_idle_query': idle, 'native_restart': restarted,
              'unsupported_info_selector15': discovery, 'zero_length_still_dispatches': short,
              'nowait_done_precedes_payload_read': asynchronous,
              'static_function12_overwrites_wifi_callback': {'before': hex(before), 'after': hex(PHYSICAL)},
              'scope': 'Original common mailbox initialization, IRQ registration, ISR, Wi-Fi dispatcher and SET/GET callbacks. Modeled PLIC/mailbox W1C and coherent payload memory, stubbed printf/hart ID, modeled other-worker idle flags. The nowait case halts at host-notifier entry after callback. Demonstrates software paths, not physical mailbox/DMA timing or hardware exploitation.'}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'native-mailbox-dispatch.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'native_mailbox_route': stopped['trace'],
                      'unsupported_probe_safe': True, 'length_and_static_index_unchecked': True}))


if __name__ == '__main__':
    main()
