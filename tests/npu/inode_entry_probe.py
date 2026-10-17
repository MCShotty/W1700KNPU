#!/usr/bin/env python3
"""Stop before INODE callback instructions; never a successful caller replay."""
import argparse
from collections import deque
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
from unicorn import UC_HOOK_CODE, riscv_const as r
from inode_trace import InodeTrace, SAVED
import restore_native_prefix as captured

ROOT = captured.ROOT


class CallbackEntry(Exception):
    pass


def registers(cpu):
    return dict(pc=cpu.reg_read(r.UC_RISCV_REG_PC),
        ra=cpu.reg_read(r.UC_RISCV_REG_RA), sp=cpu.reg_read(r.UC_RISCV_REG_SP),
        saved=[cpu.reg_read(register) for register in SAVED],
        mstatus=cpu.reg_read(r.UC_RISCV_REG_MSTATUS),
        interrupt=[cpu.reg_read(register) for register in (r.UC_RISCV_REG_MIE, r.UC_RISCV_REG_MTVEC)])


def run(pair, snapshot, output):
    assert output.is_relative_to(ROOT / '.local') and not output.exists()
    stage = (0x12, 0x17).index(json.loads(snapshot.read_bytes())['request'][11])
    h, _, record, inputs = captured.fixture(pair, snapshot,
        origin='actual-provider-allocator-caller-before-INODE-' + str(stage))
    inputs[str(Path(__file__).relative_to(ROOT))] = captured.digest(Path(__file__))
    # Construct the unchanged oracle for its entry preconditions, not its result.
    oracle = InodeTrace(h, record['request'])
    before = registers(h.cpu)
    owner = bytes(h.cpu.mem_read(oracle.owner, 4372))
    callback = h.inode.symbols['npu_emulation_inode_callback']
    instructions = deque(maxlen=128)
    observed = {}

    def instruction(cpu, pc, size, unused):
        row = registers(cpu)
        row.update(size=size, instruction=bytes(cpu.mem_read(pc, size)).hex())
        instructions.append(row)
        if pc != callback:
            return
        observed.update(row)
        pointer = cpu.reg_read(r.UC_RISCV_REG_A0)
        observed['argument'] = pointer
        observed['payload'] = list(struct.unpack('<3I', cpu.mem_read(pointer, 12)))
        observed['owner_unchanged'] = bytes(cpu.mem_read(oracle.owner, 4372)) == owner
        raise CallbackEntry()

    hook = h.cpu.hook_add(UC_HOOK_CODE, instruction)
    try:
        try:
            h.message(record['request'])
        except CallbackEntry:
            pass
        else:
            raise AssertionError('INODE callback was not observed')
    finally:
        h.cpu.hook_del(hook)
    assert observed['pc'] == callback and observed['owner_unchanged']
    assert observed['payload'] == record['request'][11:14]
    assert h.unmodeled is None and observed['mstatus'] & 8 == 0
    assert all(captured.digest(ROOT / name) == expected for name, expected in inputs.items())
    differences = [dict(register=('s' + str(index) if index < 12 else ('gp', 'tp')[index - 12]),
        before=old, callback_entry=new) for index, (old, new) in enumerate(zip(before['saved'], observed['saved']))
        if old != new]
    result = dict(diagnostic_completed=True, stage=stage, before=before, callback_entry=observed,
        saved_register_differences=differences, preceding_instructions=list(instructions), inputs=inputs,
        unchanged_entry_oracle_preconditions=True, original_entry_abi_comparison_would_pass=not differences,
        callback_instruction_executed=False, callback_body_validated=False, original_checker_passed=False,
        diagnostic_restoration_only=True, fresh_loader_allocator_caller_proof=False,
        input_drift_waivers=False, full_setup=False, hardware=False,
        limits=['Stops at callback entry before executing that instruction; not a callback return or full constructor proof.',
            'The unchanged old oracle entry preconditions are checked; its failing ABI assertion is not relabeled.',
            'Only a strictly restored producing prefix is used; no fabricated owner,SETUP or native guard repair.'])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(diagnostic_completed=True, callback_entry=hex(callback),
        differences=differences, callback_instruction_executed=False,
        receipt=str(output.relative_to(ROOT)), sha256=captured.digest(output))), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    for name in ('pair', 'snapshot', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    run(args.pair.resolve(), args.snapshot.resolve(), args.output.resolve())


if __name__ == '__main__':
    main()
