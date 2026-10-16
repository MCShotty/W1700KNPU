#!/usr/bin/env python3
"""Tail fault diagnostics from a strictly bound actual caller prefix."""
import argparse
from dataclasses import dataclass
import io
import json
from pathlib import Path
import struct
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_CODE
from unicorn import riscv_const as r
from emulation_layout import CODE, STATE
from test_bootstrap_native import ADM
from test_firmware_memory_layout import STACK_TOPS
from pcie_tail_trace import PcieTailTrace, SITES, LOCKS
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
    Case('prior-tx-fault', 'entry', 0, 0),
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


def expected_images(trace, before, case, injections):
    result = {base: bytearray(data) for base, data in before.items()}
    count, _ = counts(trace, case)
    for address, width, value in trace.events[:count]:
        put(result, address, width, value)
    # The accepted transaction advances its sequence even when its callback fails.
    change = trace.changes[-1]
    put(result, int(change['address'], 16), change['bytes'], change['expected'])
    for address in (ADM, ADM + 4, ADM + 8, STATE + 16):
        put(result, address, 4, 1)
    for injection in injections:
        address = int(injection['address'], 16)
        if any(base <= address and address + injection['bytes'] <= base + len(data) for base, data in result.items()):
            put(result, address, injection['bytes'], int.from_bytes(bytes.fromhex(injection['after']), 'little'))
    return result


class Injection:
    def __init__(self, h, trace, case):
        self.h, self.trace, self.case = h, trace, case
        self.memory, self.registers, self.hook, self.injected = [], [], None, False

    def instruction(self, cpu, pc, size, unused):
        if self.injected:
            return
        self.injected = True
        name = self.case.name
        address = register = None
        if name == 'callback-slot': address, value = 0x3e900178, 0
        elif name == 'prior-tx-fault': address, value = self.h.tx.symbols['npu_emulation_tx_state'] + 8, 1
        elif name == 'wrong-address': register, value = r.UC_RISCV_REG_A0, cpu.reg_read(r.UC_RISCV_REG_A0) + 4
        elif name == 'wrong-width': register, value = r.UC_RISCV_REG_A2, 2
        elif name == 'wrong-value': register, value = r.UC_RISCV_REG_A1, cpu.reg_read(r.UC_RISCV_REG_A1) ^ 1
        elif name == 'late-IRQ': register, value = r.UC_RISCV_REG_MSTATUS, cpu.reg_read(r.UC_RISCV_REG_MSTATUS) | 8
        elif name == 'late-nonce': address = self.trace.setup + 24
        elif name in ('late-neighbor', 'unlock-neighbor'): address = self.trace.events[0][0] + 4
        elif name == 'store-readback': address = self.trace.events[0][0]
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
        symbols = self.h.pcie_tail.symbols
        site = 0x8400651c if self.case.boundary == 'release' else symbols['npu_emulation_pcie_tail_' +
            dict(entry='callback', reserve='reserve', publish='publish')[self.case.boundary]]
        self.hook = self.h.cpu.hook_add(UC_HOOK_CODE, self.instruction, begin=site, end=site)
        return self

    def __exit__(self, *error):
        self.h.cpu.hook_del(self.hook)


def run(pair, snapshot, destination, case):
    consumer_inputs = native_prefix_snapshot.source_inputs({})
    record_ = json.loads(snapshot.read_bytes())
    stage = (0x10, 0x12, 0x1f).index(record_['request'][11])
    h, _, record, inputs = captured.fixture(pair, snapshot,
        origin='actual-provider-allocator-caller-before-PCIE-tail-' + str(stage))
    for name, digest in consumer_inputs.items():
        assert name not in inputs or inputs[name] == digest, ('consumer-input-conflict', name)
        inputs[name] = digest
    assert destination.is_relative_to(ROOT / '.local') and not destination.exists()
    destination.mkdir(parents=True)
    trace = PcieTailTrace(h, record['request'])
    before = {base: bytes(h.cpu.mem_read(base, len(data))) for base, data in trace.memory.items()}
    owner_before = bytes(h.cpu.mem_read(trace.owner, 256))
    code_before = bytearray(h.cpu.mem_read(CODE, 0x200000))
    manifest = json.loads((pair / 'manifest.json').read_bytes())
    path = ROOT / manifest['symbol_files']['cold-pcie-tail']
    binary = ELFFile(io.BytesIO(path.read_bytes()))
    writable = [(section['sh_addr'], section['sh_addr'] + section['sh_size']) for section in binary.iter_sections()
                if section['sh_flags'] & 3 == 3 and section['sh_size']]
    writable += [(trace.setup, trace.setup + 404), (STACK_TOPS[0] - 0x4000, STACK_TOPS[0])]
    saved = [getattr(r, 'UC_RISCV_REG_S' + str(i)) for i in range(12)]
    for index, register in enumerate(saved): h.cpu.reg_write(register, 0xa1000000 + index * 0x101)
    saved += [r.UC_RISCV_REG_GP, r.UC_RISCV_REG_TP]
    expected_registers = [h.cpu.reg_read(register) for register in saved]
    returns, native_run = [], h.run

    def observe_return(start, stops):
        result = native_run(start, stops)
        returns.append(dict(registers=[h.cpu.reg_read(register) for register in saved],
                            irq=h.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8))
        return result

    injection = Injection(h, trace, case)
    try:
        with patch.object(h, 'run', side_effect=observe_return), trace, injection:
            reply = h.message(record['request'])
    finally:
        trace_record = trace.save(destination / 'trace')
    assert injection.injected and len(injection.memory) + len(injection.registers) == 1
    assert reply['flags'] == 7 and reply['words'][14] == 7, ('tail-fault-reply', case.name, reply)
    assert h.unmodeled is None and returns == [dict(registers=expected_registers, irq=0)], ('tail-fault-ABI', returns)
    assert reply['returned_stack'] == hex(STACK_TOPS[0] - 0x1000)
    count, published = counts(trace, case)
    expected_stores = [(0x84000000 + site, *event) for site, event in
                       zip(SITES[trace.first:trace.first + count], trace.events[:count])]
    assert trace.stores == expected_stores, ('tail-fault-stores', trace.stores, expected_stores)
    locks = [] if case.boundary == 'entry' else [(LOCKS[0], 4, 0x40), (LOCKS[1], 4, 0)]
    assert trace.locks == locks, ('tail-fault-locks', trace.locks, locks)
    wanted = expected_images(trace, before, case, injection.memory)
    memory_directory = destination / 'fault-memory'
    memory_directory.mkdir()
    from test_desc10_native_replay import compare
    memory = compare(h, wanted, memory_directory)
    assert all(row['differing_bytes'] == 0 for row in memory), ('tail-fault-memory', memory)
    owner_wanted = expected_owner(trace, owner_before, case)
    owner_actual = bytes(h.cpu.mem_read(trace.owner, 256))
    assert owner_actual == owner_wanted, ('tail-fault-owner', list(struct.unpack('<10I', owner_actual)),
                                          list(struct.unpack_from('<10I', owner_wanted)))
    setup_wanted = bytearray(trace.setup_expected)
    struct.pack_into('<2I', setup_wanted, 0, 1, 1)
    struct.pack_into('<I', setup_wanted, 396, stage)
    for item in injection.memory:
        address = int(item['address'], 16)
        if trace.setup <= address < trace.setup + 404:
            setup_wanted[address - trace.setup:address - trace.setup + 4] = bytes.fromhex(item['after'])
        if CODE <= address < CODE + len(code_before):
            code_before[address - CODE:address - CODE + 4] = bytes.fromhex(item['after'])
    assert bytes(h.cpu.mem_read(trace.setup, 404)) == setup_wanted, 'tail-fault-setup'
    code_after = bytearray(h.cpu.mem_read(CODE, len(code_before)))
    for begin, end in writable:
        assert CODE <= begin <= end <= CODE + len(code_before)
        code_after[begin - CODE:end - CODE] = code_before[begin - CODE:end - CODE]
    assert code_after == code_before, 'tail-fault-unrelated-code-or-private-write'
    assert h.get32(h.pcie_tail.symbols['npu_emulation_pcie_tail_running']) == 0
    assert h.get32(h.packet.symbols['npu_emulation_packet_state'] + 16) == 3072
    inputs = native_prefix_snapshot.source_inputs(inputs)
    for file in destination.rglob('*'):
        if file.is_file(): inputs[str(file.relative_to(ROOT))] = captured.digest(file)
    assert all(captured.digest(ROOT / name) == digest for name, digest in inputs.items())
    result = dict(passed=True, case=case.name, stage=stage, original_stores=count,
        committed=trace.first + count, published=trace.first + published,
        owner_words=list(struct.unpack_from('<10I', owner_actual)), protected_memory=memory,
        exact_owner_bytes=256, exact_setup_bytes=404, packet_claims=3072,
        exact_prior_private_and_code=True, trace=trace_record, injections=injection.memory,
        register_injections=injection.registers, inputs=inputs, actual_native_guards=True,
        diagnostic_prefix=True, input_drift_waivers=False, fresh_loader_allocator_caller_proof=False,
        full_setup=False, hardware=False,
        limits=['Strictly restored actual producing caller prefix; no earlier SETUP or owners are fabricated.',
                'One explicit fixture mutation at the named native boundary, not a physical fault.',
                'Exact original prefix, ordered lock writes, retained owner/SETUP/protected bytes and ABI are checked.',
                'Tail scratch/stack may change; all other CODE/private bytes match except the explicit injection.',
                'MMIO, backing and scheduling remain modeled. No physical/drain/reclamation or client acceptance.'])
    (destination / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, tail_fault=case.name, stage=stage, original_stores=count)), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', choices=[case.name for case in CASES], required=True)
    args = parser.parse_args()
    run(args.pair.resolve(), args.snapshot.resolve(), args.output.resolve(),
        next(case for case in CASES if case.name == args.case))


if __name__ == '__main__': main()
