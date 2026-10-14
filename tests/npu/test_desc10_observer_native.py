#!/usr/bin/env python3
"""Observer fixture on actual raw-loaded ELF symbols; no guest execution proof."""
import argparse
from functools import partial
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
from unicorn import riscv_const as r
from cold_wire_native import ColdProviderRequest
from test_boot_irq_installation import TX
import test_npu_raw_pair as raw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists() and args.output.resolve().is_relative_to(raw.ROOT / '.local')
    h, _, _, manifest = raw.load(args.pair.resolve(), factory=partial(ColdProviderRequest, request=0x93000000))
    owner = h.desc10.symbols['npu_emulation_desc10_state']
    running = h.desc10.symbols['npu_emulation_desc10_running']
    guarded = h.allocator_rv.symbols['npu_emulation_callback_guarded']
    assert 'npu_emulation_callback_guarded' not in h.rv.symbols
    h.cold_request = h.cold_desc10 = True
    h.clear_count = 0x7000
    h.put32(running, 1)
    h.put32(guarded, 1)
    h.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 0)
    cases = 0
    for suffix, value in (('4aac_store', 0), ('4ad2_store', 3)):
        words = [0x31445443, 1, 0, 1, 7171, 7171, 7170, 512, 512, 512, 1, 0, 0, value, TX, 2]
        h.cpu.mem_write(owner, struct.pack('<16I', *words))
        pc = h.desc10.symbols['npu_emulation_desc10_' + suffix]
        h.cpu.reg_write(r.UC_RISCV_REG_PC, pc)
        before = bytes(h.cpu.mem_read(owner, 64))
        registers = [h.cpu.reg_read(getattr(r, 'UC_RISCV_REG_X' + str(i))) for i in range(32)]
        h.observe_tx_write(h.cpu, TX, 2, value)
        assert bytes(h.cpu.mem_read(owner, 64)) == before and h.clear_count == 0x7000
        assert registers == [h.cpu.reg_read(getattr(r, 'UC_RISCV_REG_X' + str(i))) for i in range(32)]
        cases += 1
        for index in (*range(11), 13, 14, 15):
            h.put32(owner + 4 * index, words[index] + 1)
            try:
                h.observe_tx_write(h.cpu, TX, 2, value)
            except AssertionError:
                cases += 1
            else:
                raise AssertionError(('dirty native observer fixture accepted', index))
            h.put32(owner + 4 * index, words[index])
    paths = [Path(__file__).resolve(), raw.ROOT / 'tests/npu/cold_wire_native.py',
             raw.ROOT / 'tests/npu/test_npu_raw_pair.py']
    result = dict(passed=True, cases=cases, linked_guard_export='allocator', guest_execution=False,
        inputs=manifest['inputs'] | {str(path.relative_to(raw.ROOT)): raw.composition.sha(path) for path in paths},
        limits=['Real raw-loader and actual linked ELF symbol ownership with synthetic observer states.',
                'Only Python observation is exercised; this is not native DESC10, fresh setup or physical proof.'])
    with args.output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=cases, linked_guard_export='allocator')))


if __name__ == '__main__':
    main()
