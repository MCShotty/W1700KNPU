#!/usr/bin/env python3
"""Cold marker transition through the original reset prelude, then late harts."""
import json
from pathlib import Path
import random

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r

from test_startup_native import Startup, STARTUP, ROOT, CODE, SRAM, STATE, sha
from test_admission_native import build_platform

OUT = ROOT / 'research/checkpoints/2026-09-06-npu-bootstrap'
BUILD = ROOT / '.local/npu-bootstrap'
BINDING = ROOT / 'tests/npu/startup-platform-emulation.c'
MARKER = 0x1ec0c140


class Prelude(Startup):
    def __init__(self, path):
        super().__init__(path)
        self.helper_calls = []
        self.marker_writes = []
        self.cpu.mem_map(0x1ec11000, 0x1000)
        self.cpu.mem_map(0x1ec00000, 0x1000)
        for address in (0x84004352, 0x84004362):
            self.cpu.hook_add(UC_HOOK_CODE, self.hart_csr, begin=address, end=address)
        # This regression ends just after the native store. IRQ-controller setup
        # and timer delays are modeled; the separate IRQ-installation suite runs
        # registration and dispatch. No hardware timing is inferred here.
        for address in (0x840032e2, 0x84004130):
            self.cpu.hook_add(UC_HOOK_CODE, self.helper, begin=address, end=address)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, self.marker, begin=MARKER, end=MARKER+3)

    def helper(self, cpu, address, size, data):
        self.helper_calls.append(hex(address))
        cpu.reg_write(r.UC_RISCV_REG_A0, 0)
        cpu.reg_write(r.UC_RISCV_REG_PC, cpu.reg_read(r.UC_RISCV_REG_RA))

    def marker(self, cpu, access, address, size, value, data):
        self.marker_writes.append({'pc': hex(cpu.reg_read(r.UC_RISCV_REG_PC)),
                                   'value': value, 'size': size, 'hart': self.hart})

    def cold_marker(self, coordinator):
        self.hart = 0
        self.cpu.context_restore(coordinator)
        assert self.cpu.reg_read(r.UC_RISCV_REG_PC) == CODE+0xf4
        assert self.get32(MARKER) == 0 and self.get32(SRAM+0xbb8) == 1
        self.skip_stop = CODE+0xf4
        self.cpu.emu_start(CODE+0xf4, 0x84004400, count=10000, timeout=1000000)
        assert self.cpu.reg_read(r.UC_RISCV_REG_PC) == 0x84004400
        assert self.marker_writes == [{'pc': '0x840043fc', 'value': 0xffffffff,
                                      'size': 4, 'hart': 0}]
        assert self.get32(MARKER) == 0xffffffff and self.get32(SRAM+0xbb8) == 0
        assert self.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
        assert self.helper_calls == ['0x840032e2'] + ['0x84004130']*3
        self.verify_initialized()


def late_workers(path, preimage=False):
    cases = []
    for seed in range(16):
        h = Prelude(path)
        order = list(range(1, 8))
        random.Random(seed).shuffle(order)
        # Exercise first arrivals both before and after core 0 publishes state.
        waiting = {}
        for hart in order[:seed % 8]:
            stop, waiting[hart] = h.execute(hart)
            assert stop == 'npu_emulation_startup_wait'
        stop, c0 = h.execute(0)
        assert stop == 'native-continuation'
        h.cold_marker(c0)
        late = []
        for hart in order:
            stop, _ = h.execute(hart, waiting.get(hart))
            if preimage and hart not in waiting:
                assert stop == 'npu_emulation_startup_fault'
                assert h.get32(STARTUP+12) == 3 and h.get32(STATE+16) == 1
                cases.append({'seed': seed, 'falsely_rejected_late_hart': hart})
                break
            assert stop == 'native-continuation', (seed, hart, stop)
            late.append(hart)
        else:
            h.verify_initialized()
            assert len(h.init_calls) == 2
            assert h.get32(STARTUP+20) == 1
            # Normal marker transition must not permit same-hart reentry.
            assert h.execute(order[-1])[0] == 'npu_emulation_startup_fault'
            cases.append({'seed': seed, 'workers': late, 'preexisting_waiters': len(waiting),
                          'duplicate_rejected': True})
    return cases


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    current = BINDING.read_text()
    old = current.replace('uint32_t warm = !hart && ', 'uint32_t warm = ')
    assert old != current
    preimage = BUILD / 'startup-marker-preimage.c'
    preimage.write_text(old)
    old_path = build_platform(startup=True, startup_binding=preimage)
    negative = late_workers(old_path, preimage=True)
    path = build_platform(startup=True)
    positive = late_workers(path)
    assert sum('falsely_rejected_late_hart' in x for x in negative) == 14
    result = {'passed': True, 'binding_sha256': sha(BINDING.read_bytes()),
              'test_sha256': sha(Path(__file__).read_bytes()),
              'elf_sha256': sha(path.read_bytes()), 'preimage_elf_sha256': sha(old_path.read_bytes()),
              'fixed_cases': positive, 'preimage_cases': negative,
              'native_marker_store': '0x840043fc',
              'modeled_helpers': ['0x840032e2 IRQ setup', '0x84004130 delay'],
              'scope': 'Original reset through cold marker store, with serialized hart contexts. Not complete native bootstrap or hardware proof.'}
    (OUT / 'startup-late-hart.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'passed': True, 'fixed_schedules': len(positive),
                      'preimage_schedules': len(negative), 'false_rejections': 14}))


if __name__ == '__main__':
    main()
