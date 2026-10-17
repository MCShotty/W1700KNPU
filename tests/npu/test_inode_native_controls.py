#!/usr/bin/env python3
"""Strict real-prefix INODE fault replay,not a fresh caller or physical proof."""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
from unicorn import UC_HOOK_CODE, riscv_const as r
from emulation_layout import CODE, STATE
from test_bootstrap_native import ADM
from inode_trace import InodeTrace, LOCKS, END, STACK_TOPS, ICV
import native_prefix_snapshot
import restore_native_prefix as captured

ROOT = captured.ROOT


@dataclass(frozen=True)
class Case:
    name: str
    boundary: str
    stores: int
    published: int


CASES = (
    Case('callback-slot', 'entry', 0, 0),
    Case('prior-tail-fault', 'entry', 0, 0),
    Case('wrong-address', 'reserve', 0, 0),
    Case('wrong-width', 'reserve', 0, 0),
    Case('wrong-value', 'reserve', 0, 0),
    Case('late-IRQ', 'reserve', 0, 0),
    Case('late-nonce', 'reserve', 0, 0),
    Case('late-neighbor', 'reserve', 0, 0),
    Case('store-readback', 'publish', 1, 0),
    Case('late-packet-fault', 'publish', 1, 0),
    Case('release-fault', 'release', -1, -1),
    Case('unlock-neighbor', 'release', -1, -1),
)


def put(images, address, width, value):
    base = next(base for base, data in images.items() if base <= address and address + width <= base + len(data))
    images[base][address - base:address - base + width] = value.to_bytes(width, 'little')


def counts(trace, case):
    return (len(trace.events), len(trace.events)) if case.boundary == 'release' else (case.stores, case.published)


def expected_owner(trace, before, case):
    if case.boundary == 'entry':
        result = bytearray(before)
        struct.pack_into('<I', result, 8, 1)
        return result
    result = bytearray(trace.owner_expected)
    committed, published = counts(trace, case)
    struct.pack_into('<I', result, 8, 1)
    if case.boundary != 'release':
        struct.pack_into('<I', result, 12, 1)
        struct.pack_into('<I', result, 24, (1 << trace.stage) - 1)
        struct.pack_into('<2I', result, 28, trace.first + committed, trace.first + published)
    return result


def expected_setup(trace, injections):
    result = bytearray(trace.setup_expected)
    struct.pack_into('<2I', result, 0, 1, 1)
    struct.pack_into('<I', result, 404, trace.stage)
    for item in injections:
        address = int(item['address'], 16)
        if trace.setup <= address and address + item['bytes'] <= trace.setup + len(result):
            result[address - trace.setup:address - trace.setup + item['bytes']] = bytes.fromhex(item['after'])
    return result


def expected_memory(trace, before, case, injections):
    result = {base: bytearray(data) for base, data in before.items()}
    count, _ = counts(trace, case)
    for _, address, width, value in trace.events[:count]: put(result, address, width, value)
    put(result, trace.h.rv.symbols['npu_emulation_control_v2_state'] + 16, 4, trace.request[6])
    for address in (ADM, ADM + 4, ADM + 8, STATE + 16): put(result, address, 4, 1)
    for item in injections:
        address = int(item['address'], 16)
        if any(base <= address and address + item['bytes'] <= base + len(data) for base, data in result.items()):
            put(result, address, item['bytes'], int.from_bytes(bytes.fromhex(item['after']), 'little'))
    return result


def expected_code(trace, before, owner, setup, case, injections):
    result = bytearray(trace.code_expected[CODE])
    result[trace.owner - CODE:trace.owner - CODE + len(owner)] = owner
    result[trace.setup - CODE:trace.setup - CODE + len(setup)] = setup
    if case.boundary == 'entry':
        table = trace.h.inode.elf.get_section_by_name('.symtab')
        for name in ('neighbors_captured', 'flag_neighbors', 'icv_neighbors.0', 'icv_neighbors.1'):
            entries = [entry for entry in table.get_symbol_by_name(name) or ()
                       if any(base <= entry['st_value'] and entry['st_value'] + entry['st_size'] <= base + len(data)
                              for base, data in trace.private.items())]
            assert len(entries) == 1
            offset, size = entries[0]['st_value'] - CODE, entries[0]['st_size']
            result[offset:offset + size] = before[offset:offset + size]
    for item in injections:
        address = int(item['address'], 16)
        if CODE <= address and address + item['bytes'] <= CODE + len(result):
            result[address - CODE:address - CODE + item['bytes']] = bytes.fromhex(item['after'])
    return result


class FaultTrace(InodeTrace):
    def __init__(self, h, request, case):
        super().__init__(h, request)
        self.case, self.release_interrupts = case, []

    def code(self, cpu, pc, size, unused):
        if self.entry_sites[pc] == 'release':
            # A deliberately faulted owner is checked exactly after cleanup.
            status = cpu.reg_read(r.UC_RISCV_REG_MSTATUS)
            interrupt = tuple(cpu.reg_read(register) for register in (r.UC_RISCV_REG_MIE, r.UC_RISCV_REG_MTVEC))
            assert status == (8 if self.case.name == 'late-IRQ' else 0), 'INODE-fault-release-MSTATUS'
            assert interrupt == self.interrupt_before, 'INODE-fault-release-interrupt-CSRs'
            self.release_interrupts.append(dict(mstatus=status, interrupt=interrupt))
            self.entries.append('release')
        else:
            super().code(cpu, pc, size, unused)


class Injection:
    def __init__(self, h, trace, case):
        self.h, self.trace, self.case = h, trace, case
        self.memory, self.registers, self.injected, self.hook = [], [], False, None

    def instruction(self, cpu, pc, size, unused):
        if self.injected: return
        self.injected = True
        name = self.case.name
        address = register = None
        if name == 'callback-slot': address, value = 0x3e9001d8, 0
        elif name == 'prior-tail-fault': address, value = self.h.pcie_tail.symbols['npu_emulation_pcie_tail_state'] + 8, 1
        elif name == 'wrong-address': register, value = r.UC_RISCV_REG_A0, cpu.reg_read(r.UC_RISCV_REG_A0) + 4
        elif name == 'wrong-width': register, value = r.UC_RISCV_REG_A2, 2
        elif name == 'wrong-value': register, value = r.UC_RISCV_REG_A1, cpu.reg_read(r.UC_RISCV_REG_A1) ^ 1
        elif name == 'late-IRQ': register, value = r.UC_RISCV_REG_MSTATUS, cpu.reg_read(r.UC_RISCV_REG_MSTATUS) | 8
        elif name == 'late-nonce': address = self.trace.setup + 24
        elif name in ('late-neighbor', 'unlock-neighbor'): address = ICV - 4
        elif name == 'store-readback': address = self.trace.events[0][1]
        elif name == 'late-packet-fault': address, value = self.h.packet.symbols['npu_emulation_packet_state'] + 8, 1
        elif name == 'release-fault': address, value = STATE + 16, 1
        else: raise AssertionError(name)
        if register is not None:
            self.registers.append(dict(register=register, before=cpu.reg_read(register), after=value))
            cpu.reg_write(register, value)
        else:
            before = bytes(cpu.mem_read(address, 4))
            if name in ('late-nonce', 'late-neighbor', 'unlock-neighbor', 'store-readback'):
                value = int.from_bytes(before, 'little') ^ 1
            after = struct.pack('<I', value)
            cpu.mem_write(address, after)
            self.memory.append(dict(address=hex(address), bytes=4, before=before.hex(), after=after.hex()))

    def __enter__(self):
        site = 0x8400651c if self.case.boundary == 'release' else self.h.inode.symbols['npu_emulation_inode_' +
            dict(entry='callback', reserve='reserve', publish='publish')[self.case.boundary]]
        self.hook = self.h.cpu.hook_add(UC_HOOK_CODE, self.instruction, begin=site, end=site)
        return self

    def __exit__(self, *error): self.h.cpu.hook_del(self.hook)


def run(pair, snapshot, destination, case):
    consumer = native_prefix_snapshot.source_inputs({})
    record = json.loads(snapshot.read_bytes())
    stage = (0x12, 0x17).index(record['request'][11])
    h, _, record, inputs = captured.fixture(pair, snapshot, origin='actual-provider-allocator-caller-before-INODE-' + str(stage))
    for name, expected in consumer.items():
        assert name not in inputs or inputs[name] == expected, ('INODE-consumer-input-conflict', name)
        inputs[name] = expected
    assert destination.is_relative_to(ROOT / '.local') and not destination.exists()
    destination.mkdir(parents=True)
    trace = FaultTrace(h, record['request'], case)
    before = {base: bytes(h.cpu.mem_read(base, len(data))) for base, data in trace.memory.items()}
    owner_before = bytes(h.cpu.mem_read(trace.owner, 4372))
    code_before = bytes(h.cpu.mem_read(CODE, 0x200000))
    injection = Injection(h, trace, case)
    try:
        with trace, injection: reply = h.message(record['request'])
    finally:
        trace_record = trace.save(destination / 'trace')
    assert injection.injected and len(injection.memory) + len(injection.registers) == 1
    assert reply['flags'] == 7 and reply['words'][14] == 7, ('INODE-fault-reply', case.name, reply)
    assert h.unmodeled is None and trace.returns == [dict(pc=END, saved=trace.saved_before,
        sp=STACK_TOPS[0] - 0x1000, mstatus=0, interrupt=trace.interrupt_before)], ('INODE-fault-ABI', trace.returns)
    trace.validate_callback_abi()
    assert reply['returned_stack'] == hex(STACK_TOPS[0] - 0x1000)
    count, published = counts(trace, case)
    assert trace.stores == list(trace.events[:count]), ('INODE-fault-store-prefix', len(trace.stores), count)
    assert trace.locks == ([] if case.boundary == 'entry' else [(LOCKS[0], 4, 0x40), (LOCKS[1], 4, 0)])
    assert trace.entries == (['callback'] if case.boundary == 'entry' else ['callback', 'wrapper', 'helper', 'release'])
    assert len(trace.release_interrupts) == int(case.boundary != 'entry')
    wanted = expected_memory(trace, before, case, injection.memory)
    directory = destination / 'fault-memory'
    directory.mkdir()
    from test_desc10_native_replay import compare
    memory = compare(h, wanted, directory)
    assert all(row['differing_bytes'] == 0 for row in memory), 'INODE-fault-protected-memory'
    owner = expected_owner(trace, owner_before, case)
    setup = expected_setup(trace, injection.memory)
    assert bytes(h.cpu.mem_read(trace.owner, 4372)) == owner, 'INODE-fault-exact-owner'
    assert bytes(h.cpu.mem_read(trace.setup, 412)) == setup, 'INODE-fault-exact-SETUP'
    wanted_code = expected_code(trace, code_before, owner, setup, case, injection.memory)
    actual_code = bytearray(h.cpu.mem_read(CODE, 0x200000))
    first, last = STACK_TOPS[0] - 0x4000 - CODE, STACK_TOPS[0] - CODE
    actual_code[first:last] = wanted_code[first:last]
    assert actual_code == wanted_code, 'INODE-fault-code-or-private-mutation'
    assert h.get32(h.inode.symbols['npu_emulation_inode_running']) == 0
    assert h.get32(h.packet.symbols['npu_emulation_packet_state'] + 16) == 3072
    for name, contents in (('fault-owner-expected.bin', bytes(owner)), ('fault-setup-expected.bin', bytes(setup)),
                           ('fault-code-private-expected.bin', bytes(wanted_code))):
        with (destination / name).open('xb') as stream: stream.write(contents)
    inputs = native_prefix_snapshot.source_inputs(inputs)
    for path in destination.rglob('*'):
        if path.is_file(): inputs[str(path.relative_to(ROOT))] = captured.digest(path)
    assert all(captured.digest(ROOT / name) == expected for name, expected in inputs.items())
    result = dict(passed=True, stage=stage, case=case.name, original_stores=count,
        committed=trace.first + count, published=trace.first + published,
        protected_memory=memory, owner_words=list(struct.unpack_from('<10I', owner)), trace=trace_record,
        exact_owner_bytes=4372, exact_setup_bytes=412, exact_code_private_bytes=0x200000,
        exact_prior_private_and_code=True,
        release_irq_checked=True, release_interrupts=trace.release_interrupts,
        packet_claims=3072, inputs=inputs, injections=injection.memory, register_injections=injection.registers,
        actual_native_guards=True, diagnostic_prefix=True, input_drift_waivers=False,
        fresh_loader_allocator_caller_proof=False, full_setup=False, hardware=False,
        limits=['Strictly restored real producing caller prefix,no forged earlier SETUP or direct owner initialization.',
                'Exactly one explicit fixture fault and its original store prefix;not a physical bus/IRQ fault.',
                'Release retains an exact case-specific CSR check;the clean-owner assertion is replaced by exact retained-fault checks.',
                'Native guards,original instructions,full prior owners and instruction/state bounds are unchanged.',
                'DMA/MMIO/lock/backing/scheduling remain modeled;no drain,reclaim,worker or physical acceptance.'])
    (destination / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, stage=stage, inode_fault=case.name, original_stores=count)), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', choices=[case.name for case in CASES], required=True)
    args = parser.parse_args()
    run(args.pair.resolve(), args.snapshot.resolve(), args.output.resolve(), next(case for case in CASES if case.name == args.case))


if __name__ == '__main__': main()
