#!/usr/bin/env python3
"""Check the hand-written header adapters' caller ABI on both return paths."""
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from unicorn import riscv_const as r
import test_tunnel_header_bounds as bounds
from test_bridge_startup import input_bindings
from test_firmware_memory_layout import STACK_TOPS


def main():
    inputs = input_bindings()
    paths = [Path(__file__), bounds.SOURCE, bounds.HEADER, bounds.ASM, bounds.LINKER,
             bounds.layout.LINKER, bounds.order.LINKER, bounds.txdone.LINKER]
    inputs.update({str(p.relative_to(bounds.ROOT)): bounds.sha(p.read_bytes()) for p in paths})
    compiled = bounds.build()
    profile, _ = bounds.layout.build()
    reset, _ = bounds.layout.build_reset()
    h = bounds.Headers(profile, reset)
    h.header_rv, _ = bounds.install(h, compiled[1])
    saved = [getattr(r, 'UC_RISCV_REG_S'+str(i)) for i in range(12)]
    fixed = [r.UC_RISCV_REG_GP, r.UC_RISCV_REG_TP]
    cases = [
        ('vxlan-accepted', lambda: bounds.store_case(h, 0, 19, 50, enabled=True)),
        ('vxlan-rejected', lambda: bounds.store_case(h, 0, 20, 50, enabled=True)),
        ('srv6-accepted', lambda: bounds.store_case(h, 1, 7, 128, enabled=True)),
        ('srv6-rejected', lambda: bounds.store_case(h, 1, 7, 129, enabled=True)),
        ('consumer-accepted', lambda: bounds.consumer_case(h, 41, 128, enabled=True)),
        ('consumer-rejected', lambda: bounds.consumer_case(h, 41, 0, enabled=True)),
        ('mailbox-accepted', lambda: bounds.mailbox_case(h, 0, 0, 50, 59)),
        ('mailbox-rejected', lambda: bounds.mailbox_case(h, 1, 7, 129, 139)),
    ]
    rows = []
    for index, (name, test) in enumerate(cases):
        for n, reg in enumerate(saved):
            h.cpu.reg_write(reg, 0x13570000+index*256+n)
        before = [h.cpu.reg_read(reg) for reg in saved+fixed]
        test()
        after = [h.cpu.reg_read(reg) for reg in saved+fixed]
        assert before == after, (name, before, after)
        assert h.cpu.reg_read(r.UC_RISCV_REG_SP) == STACK_TOPS[0], name
        assert h.cpu.reg_read(r.UC_RISCV_REG_PC) == bounds.allocator.END
        rows.append(dict(name=name, callee_saved_gp_tp_unchanged=after, final_sp=hex(STACK_TOPS[0])))
    assert all(bounds.sha((bounds.ROOT/name).read_bytes()) == value for name, value in inputs.items())
    result = dict(schema=1, inputs_before_after=inputs, cases=rows,
                  scope='Actual guarded callbacks, consumer and original ISR; caller-saved scratch registers are not ABI invariants.')
    encoded = (json.dumps(result, indent=2)+'\n').encode()
    (bounds.OUT/'header-abi.json').write_bytes(encoded)
    print(json.dumps(dict(abi_cases=len(rows), evidence_sha256=bounds.sha(encoded))))


if __name__ == '__main__':
    main()
