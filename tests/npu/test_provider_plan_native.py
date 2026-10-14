#!/usr/bin/env python3
"""Raw-native bootstrap using bytes emitted by the actual provider plan builder."""
import argparse
from functools import partial
import json
from pathlib import Path
import re
import struct
import sys

sys.dont_write_bytecode = True
from unicorn import UC_HOOK_MEM_READ
from unicorn import riscv_const as r
import test_npu_raw_pair as raw
import test_cold_txdone_native as tx
from test_bootstrap_native import BOOT, PLAN, ADM
from test_firmware_mailbox_dispatch import MBOX, DISPATCH
from test_firmware_memory_layout import STACK_TOPS
from test_firmware_stop_counterexample import END
from emulation_layout import STATE

ROOT = raw.ROOT


class ProviderRequest(tx.TxPackets):
    def __init__(self, paths, parts, *, request):
        self.request_address = request
        self.request_alias = (request & 0x3fffffff) | 0x40000000
        self.request_reads = []
        self.wire_frames = []
        super().__init__(paths, parts)
        self.cpu.mem_map(self.request_alias & ~0xfff, 0x2000)
        self.cpu.hook_add(UC_HOOK_MEM_READ, self.observe_request,
                         begin=self.request_alias, end=self.request_alias + 255)

    def is_memory(self, address, size):
        if self.request_alias <= address < self.request_alias + 256:
            return address + size <= self.request_alias + 256
        return super().is_memory(address, size)

    def observe_request(self, cpu, access, address, size, value, data):
        self.request_reads.append(dict(offset=address - self.request_alias, size=size))

    def message(self, words, length=None, flags=1, address=None):
        address = self.request_address if address is None else address
        context = self.cpu.context_save()
        encoded = struct.pack('<' + 'I' * len(words), *words)
        assert len(encoded) <= 256
        self.cpu.mem_write(self.request_alias, encoded + bytes(256 - len(encoded)))
        self.put32(MBOX + 0x30, address)
        self.put32(MBOX + 0x34, len(encoded) if length is None else length)
        self.put32(MBOX + 0x3c, flags)
        self.request_reads.clear()
        self.callback_entries.clear()
        for register, value in ((r.UC_RISCV_REG_SP, STACK_TOPS[0] - 0x1000),
                                (r.UC_RISCV_REG_RA, END), (r.UC_RISCV_REG_A0, 8),
                                (r.UC_RISCV_REG_MSTATUS, 0)):
            self.cpu.reg_write(register, value)
        assert self.run(DISPATCH, []) == END
        returned_stack = self.cpu.reg_read(r.UC_RISCV_REG_SP)
        assert returned_stack == STACK_TOPS[0] - 0x1000, ('native-message-stack-unbalanced', hex(returned_stack))
        result = dict(flags=self.get32(MBOX + 0x3c),
                      words=list(struct.unpack('<' + 'I' * len(words), self.cpu.mem_read(self.request_alias, len(encoded)))),
                      callbacks=self.callback_entries.copy(), reads=self.request_reads.copy(),
                      returned_stack=hex(returned_stack))
        assert all(row['offset'] + row['size'] <= (len(encoded) if length is None else length)
                   for row in result['reads'])
        self.wire_frames.append(dict(address=address, request=words, response=result))
        self.cpu.context_restore(context)
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-provider-plan-20261010' / args.name
    assert not dest.exists()
    dest.mkdir(parents=True)
    plan_path = args.plan.resolve()
    plan = plan_path.read_bytes()
    assert len(plan) == 48
    words = struct.unpack('<12I', plan)
    assert words[-1] == 256 and words[-2] != raw.composition.native.REQUEST
    h, paths, _, manifest = raw.load(args.pair.resolve(), factory=partial(ProviderRequest, request=words[-2]))
    # These are explicit modeled loader publications; production SRAM/identity
    # publication is not inferred from the provider's private snapshot.
    h.cpu.mem_write(PLAN, plan)
    identity = raw.composition.control.BOOT
    h.cpu.mem_write(raw.composition.boot.LOADER, struct.pack('<2I', *identity))
    h.hart = 0
    h.cpu.context_restore(h.fresh)
    assert h.reset() == 0x8400420a
    assert bytes(h.cpu.mem_read(BOOT + 32, 48)) == plan
    controls = []
    for address in (raw.composition.native.REQUEST, words[-2] + 4,
                    h.request_alias, words[0], 0, 0xffffffff):
        row = h.message([0x30, 10, 0], address=address)
        assert row['flags'] == 3 and not row['callbacks'] and not row['reads']
        assert bytes(h.cpu.mem_read(BOOT + 32, 48)) == plan
        controls.append(dict(address=address, **row))
    host = raw.composition.control.Host(paths)
    assert raw.composition.control.exchange(host, h)[0] == raw.composition.control.ACCEPTED
    version = h.message([0x30, 10, 0])
    assert version['flags'] == 7 and version['words'][2] == 0x457
    replies = raw.composition.boot.setup(h, run_clear=True)
    raw.composition.control.advance(host, h)
    h.finish_coordinator()
    workers = [h.worker(hart) for hart in range(1, 8)]
    h.on_core0()
    assert raw.composition.control.exchange(host, h)[0] == raw.composition.control.ACCEPTED
    parked = [h.get32(STATE + 20 + 4 * hart) for hart in range(8)]
    assert parked == [1] * 8 and h.get32(ADM + 4) == 0
    strict = [h.message(frame) for frame in ([0x10, 1, 1536], [0x12, 1, 1024], [0x1a, 1, 512])]
    assert all(row['flags'] == 3 and not row['callbacks'] for row in strict)
    assert bytes(h.cpu.mem_read(PLAN, 48)) == bytes(h.cpu.mem_read(BOOT + 32, 48)) == plan
    h.check_hooks()
    inputs = manifest['inputs'] | {str(plan_path.relative_to(ROOT)): raw.composition.sha(plan_path),
                                  str(Path(__file__).relative_to(ROOT)): raw.composition.sha(Path(__file__)),
                                  'tests/npu/test_npu_raw_pair.py': raw.composition.sha(ROOT / 'tests/npu/test_npu_raw_pair.py')}
    assert all(raw.composition.sha(ROOT / path) == digest for path, digest in inputs.items())
    result = dict(passed=True, raw_pair=True, post_load_elf_injection=False,
                  request_base=hex(words[-2]), request_alias=hex(h.request_alias), provider_plan_sha256=raw.composition.sha(plan_path),
                  fixed_fixture_rejected=True, address_controls=controls, version=version, setup=replies,
                  workers=workers, parked=parked, strict_denials=strict, wire_frames=h.wire_frames, inputs=inputs,
                  limits=['Actual provider C emitted plan consumed by raw native initialization and dynamic-address mailbox.',
                          'Provider allocation/OF,SRAM/identity publication,backing/IRQ scheduling remain modeled; strict full setup is still denied.',
                          'No real reset containment,loader publication,physical drains,hardware or clients.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, request_base=hex(words[-2]), fixture_rejected=True, native_harts=8)))


if __name__ == '__main__':
    main()
