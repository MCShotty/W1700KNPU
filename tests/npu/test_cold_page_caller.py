#!/usr/bin/env python3
"""Trace native host statistics allocator routing in the current 50-hook boot."""
import argparse
import json
from pathlib import Path
import re
import struct
import sys

sys.dont_write_bytecode = True
from unicorn import riscv_const as r
import test_bootstrap_v2_composition as composition
from test_bootstrap_native import Bootstrap, ADM, BOOT
from test_firmware_mailbox_dispatch import PAYLOAD
from test_firmware_memory_layout import STACK_TOPS
from test_firmware_stop_counterexample import END
from emulation_layout import STATE
from test_attach_rx_callbacks import REGISTERS

ROOT = Path(__file__).resolve().parents[2]


class Caller(composition.Composed):
    def __init__(self, paths, parts):
        self.probing = False
        self.getters = []
        self.fallbacks = []
        super().__init__(paths, parts)
        self.put32(0x1ec03070, 0x10000)

    def register_model(self, address, write):
        if address in REGISTERS:
            kind, _, description = REGISTERS[address]
            return description if write == (kind == 'write') else None
        return super().register_model(address, write)

    def code_hook(self, cpu, pc, size, data):
        if self.probing and pc == 0x84005200:
            self.getters.append(dict(type=cpu.reg_read(r.UC_RISCV_REG_A0),
                                     caller=hex(cpu.reg_read(r.UC_RISCV_REG_RA)),
                                     mstatus=cpu.reg_read(r.UC_RISCV_REG_MSTATUS),
                                     active=self.get32(ADM + 4)))
        if self.probing and pc == 0x84005204:
            self.fallbacks.append(dict(type=cpu.reg_read(r.UC_RISCV_REG_A0),
                                       caller=hex(cpu.reg_read(r.UC_RISCV_REG_RA))))
        if self.probing and pc == 0x8400dd82:
            assert cpu.reg_read(r.UC_RISCV_REG_A1) in (0, 2)
            # Remove the fixture's no-DESC observation assertion for this one
            # direct RX0/RX2 probe. Native instructions and strict IRQ gate stay put.
            self.executions[pc] += 1
            super(composition.Composed, self).code_hook(cpu, pc, size, data)
            return
        super().code_hook(cpu, pc, size, data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-cold-page-20261001' / args.name
    assert not dest.exists(), 'Choose a fresh result name'
    dest.mkdir(parents=True)
    paths, parts = composition.build()
    layout = composition.memory_layout(parts)
    h = Caller(paths, parts)
    h.hart = 0
    h.cpu.context_restore(h.fresh)
    assert h.reset() == 0x8400420a
    host = composition.control.Host(paths)
    assert composition.control.exchange(host, h)[0] == composition.control.ACCEPTED
    composition.boot.setup(h, run_clear=True)
    composition.control.advance(host, h)
    footprint = h.finish_coordinator()
    workers = [h.worker(hart) for hart in range(1, 8)]
    assert [h.get32(STATE + 20 + 4 * i) for i in range(8)] == [1] * 8
    assert h.get32(BOOT + 8) == 6 and h.get32(ADM + 4) == 0
    h.on_core0()
    denied = Bootstrap.message(h, [0x10, 1, 1536])
    assert denied['flags'] == 3 and not denied['callbacks']
    # Model the direct caller's already-held callback lease, not IRQ delivery.
    h.put32(ADM + 4, 1)
    before_count = h.get32(0x3e901bd4)
    hold = h.allocator_rv.symbols['npu_emulation_allocator_startup_hold']
    callbacks = []
    for selector, count, flag in ((0, 1536, 0x3e902a84), (2, 1024, 0x3e904588)):
        h.cpu.mem_write(PAYLOAD, struct.pack('<3I', 0x10 | selector, 1, count))
        for register, value in ((r.UC_RISCV_REG_SP, STACK_TOPS[0]),
                                (r.UC_RISCV_REG_RA, END), (r.UC_RISCV_REG_A0, PAYLOAD),
                                (r.UC_RISCV_REG_MSTATUS, 0)):
            h.cpu.reg_write(register, value)
        h.probing = True
        stopped = h.run(0x8400fe34, [hold])
        h.probing = False
        assert stopped == END and h.cpu.reg_read(r.UC_RISCV_REG_A0) == 1
        assert h.get32(flag) == 1
        callbacks.append(dict(selector=selector, count=count, result=1, ready=hex(flag)))
    assert h.get32(STATE + 16) == h.get32(ADM + 8) == 0
    assert h.get32(ADM + 4) == 1
    assert all(any(row['type'] == kind and row['caller'] == caller for row in h.getters)
               for kind, caller in ((10, '0x8400a3ae'), (9, '0x8400a39a'))), h.getters
    assert all(any(row['type'] == kind and row['caller'] == caller for row in h.fallbacks)
               for kind, caller in ((10, '0x8400a3ae'), (9, '0x8400a39a'))), h.fallbacks
    assert h.get32(0x3e901bd4) == before_count + 2
    h.check_hooks()
    assert len(h.patches) == 50
    sources = [ROOT / 'tests/npu/allocator-startup-emulation.c',
               ROOT / 'tests/npu/allocator-startup-emulation.S',
               ROOT / 'tests/npu/test_bootstrap_v2_composition.py', Path(__file__)]
    result = dict(passed=True, unreviewed_allocator_fallback_observed=True, hooks=50,
                  all_harts_parked=[h.get32(STATE + 20 + 4 * i) for i in range(8)],
                  workers=workers, getter_entries=h.getters, fallback_entries=h.fallbacks,
                  callbacks=callbacks, active_lease_retained=True,
                  allocator_records_added=2,
                  strict_denial=denied, boot_footprint=footprint, composition_layout=layout,
                  inputs={str(p.relative_to(ROOT)): composition.sha(p) for p in sources},
                  binaries={str(p.relative_to(ROOT)): composition.sha(p) for p in [*paths, *parts.values()]},
                  scope='Actual current 50-hook native cold boot,explicit direct RX0/RX2 caller lease;not complete host transport.',
                  limits=['No native helper return substitution;later statistics allocations use the original unchecked fallback.',
                          'All-hart parking is native-code evidence with modeled platform inputs,not physical containment.',
                          'New cold ownership core is not substituted into this native caller probe.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, hooks=50, callbacks=callbacks, allocator_records_added=2,
                          statistics_fallback=True, receipt=str((dest / 'result.json').relative_to(ROOT)))))


if __name__ == '__main__':
    main()
