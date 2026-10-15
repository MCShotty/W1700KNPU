#!/usr/bin/env python3
"""Full-size original DESC10 fault cases from a strictly bound actual prefix."""
import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import sys
from unittest.mock import patch

from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r

from desc10_store_trace import Desc10Trace, original_sites
from desc10_effect_oracle import IDS, STORES
from emulation_layout import CODE, SRAM, STATE
from test_bootstrap_native import ADM
from test_firmware_memory_layout import STACK_TOPS
import restore_native_prefix as captured
import native_prefix_snapshot

ROOT = captured.ROOT


@dataclass(frozen=True)
class Case:
    name: str
    stores: int
    claims_reserved: int
    claims: int
    published: int
    allocation_errors: int = 0
    skb: int = 0


CASES = (
    Case('denied', 2, 0, 0, 0),
    Case('partial-pool', 2 + 17 * 6, 18, 17, 17, 1),
    Case('claim-fault', 2, 1, 1, 1, 1),
    Case('head-changed', 2, 1, 1, 0, 1),
    Case('release-fault', 2, 1, 1, 1),
    Case('denied-skb19', 2 + IDS * 6, IDS, IDS, IDS),
    Case('before-ready-bitmap', STORES - 2, IDS, IDS, IDS, skb=1),
    Case('before-ready-plan', STORES - 2, IDS, IDS, IDS, skb=1),
)


def expected_locks(case):
    locks = Desc10Trace.LOCKS
    if case.name == 'denied':
        return [(locks[0], 4, 0x40)]
    takes = case.claims_reserved
    result = [(locks[0], 4, 0x40), (locks[1], 4, 0)] * takes
    if case.name == 'denied-skb19':
        result += [(locks[2], 4, 0x40)]
    elif case.skb:
        result += [(locks[2], 4, 0x40), (locks[3], 4, 0x40),
                   (locks[4], 4, 0), (locks[5], 4, 0)]
    return result


def expected_memory(trace, case):
    # The authenticated failed transaction retains its lease after the callback.
    mutations = [(ADM + 4, 4, 1)]
    if case.name == 'partial-pool':
        mutations.append((SRAM + 0x1b80, 2, (trace.oracle.head + 18) % 16384))
    if case.name == 'head-changed':
        mutations.append((SRAM + 0x1ba4, 2, 37))
    images = trace.oracle.memory_prefix(case.stores, case.published,
        allocation_errors=case.allocation_errors, fault=True, mutations=mutations)
    packet = bytearray(trace.oracle.packet_prefix(trace.packet_before, case.claims, fault=True))
    if case.name == 'before-ready-bitmap':
        position = 28 + 511 * 4
        old = int.from_bytes(packet[position:position + 4], 'little')
        struct.pack_into('<I', packet, position, old ^ 1)
    return images, packet


def validate_trace(trace, case):
    assert len(trace.stores) == case.stores, ('retained-original-store-count', case.name, len(trace.stores))
    choices = original_sites()
    for index, ((site, address, width, value), expected) in enumerate(zip(trace.stores, trace.oracle.events)):
        assert site in choices[index], ('retained-original-store-site', case.name, index, hex(site))
        assert (address, width, value) == expected, ('retained-original-store-effect', case.name, index)
    assert trace.locks == expected_locks(case), ('retained-original-lock-order', case.name, trace.locks)


class Injection:
    def __init__(self, h, trace, case):
        self.h, self.trace, self.case = h, trace, case
        self.injected, self.takes, self.hooks = [], 0, []

    def mark(self, address, width, value):
        assert not self.injected
        before = bytes(self.h.cpu.mem_read(address, width))
        self.h.cpu.mem_write(address, value.to_bytes(width, 'little'))
        self.injected.append(dict(address=hex(address), bytes=width,
                                  before=before.hex(), after=value.to_bytes(width, 'little').hex()))

    def read(self, cpu, access, address, width, value, unused):
        if not self.injected:
            self.mark(address, 4, 0x10100)

    def count(self, cpu, access, address, width, value, unused):
        if not self.injected and width == 4 and value == 2561:
            target = self.trace.packet + 8 if self.case.name == 'claim-fault' else SRAM + 0x1ba4
            self.mark(target, 4 if self.case.name == 'claim-fault' else 2,
                      1 if self.case.name == 'claim-fault' else 37)

    def instruction(self, cpu, pc, size, unused):
        if self.injected:
            return
        if self.case.name == 'partial-pool':
            self.takes += 1
            if self.takes == 18:
                self.mark(SRAM + 0x1b80, 2, (self.trace.oracle.head + 18) % 16384)
        elif self.case.name == 'release-fault':
            if self.h.get32(self.trace.packet + 16) == 2561:
                self.mark(STATE + 16, 4, 1)
        elif self.case.name == 'before-ready-bitmap':
            address = self.trace.packet + 28 + 511 * 4
            self.mark(address, 4, self.h.get32(address) ^ 1)
        else:
            address = self.h.packet.symbols['npu_emulation_packet_plan']
            self.mark(address, 4, self.h.get32(address) + 2048)

    def __enter__(self):
        cpu, name = self.h.cpu, self.case.name
        if name in ('denied', 'denied-skb19'):
            address = 0x1ec03070 if name == 'denied' else 0x1ec0304c
            self.hooks.append(cpu.hook_add(UC_HOOK_MEM_READ, self.read, begin=address, end=address + 3))
        elif name in ('claim-fault', 'head-changed'):
            address = self.trace.packet + 16
            self.hooks.append(cpu.hook_add(UC_HOOK_MEM_WRITE, self.count, begin=address, end=address + 3))
        else:
            if name == 'partial-pool':
                pc = self.h.desc10.symbols['npu_emulation_desc10_take']
            elif name == 'release-fault':
                pc = 0x8400651c
            else:
                pc = self.h.desc10.symbols['npu_emulation_desc10_ready']
            self.hooks.append(cpu.hook_add(UC_HOOK_CODE, self.instruction, begin=pc, end=pc))
        return self

    def __exit__(self, *error):
        for hook in self.hooks:
            self.h.cpu.hook_del(hook)


def symbol_bytes(h, binary, name):
    matches = [s for s in binary.elf.get_section_by_name('.symtab').get_symbol_by_name(name)
               if s['st_size'] and isinstance(s['st_shndx'], int)]
    assert len(matches) == 1, name
    symbol = matches[0]
    return symbol['st_value'], bytes(h.cpu.mem_read(symbol['st_value'], symbol['st_size']))


def run(pair, snapshot, destination, case):
    consumer_inputs = native_prefix_snapshot.source_inputs({})
    h, restore, record, inputs = captured.fixture(pair, snapshot,
        origin='actual-provider-allocator-caller-before-DESC10')
    for name, expected in consumer_inputs.items():
        assert name not in inputs or inputs[name] == expected, ('consumer-input-conflict', name)
        inputs[name] = expected
    assert destination.is_relative_to(ROOT / '.local') and not destination.exists()
    destination.mkdir(parents=True)
    trace = Desc10Trace(h, record['request'])
    wanted, packet_wanted = expected_memory(trace, case)
    cold = h.rv.symbols['npu_emulation_cold_setup_state']
    owner = h.desc10.symbols['npu_emulation_desc10_state']
    assert h.get32(trace.packet + 16) == 2560 and not any(h.cpu.mem_read(owner, 13512))
    prior = [symbol_bytes(h, getattr(h, component), name) for component, name in (
        ('rx_event', 'npu_emulation_rx_event_state'), ('txbuf', 'npu_emulation_txbuf_state'),
        ('tx', 'npu_emulation_tx_state'), ('descriptor', 'npu_emulation_descriptor_state'),
        ('binding', 'npu_emulation_page_state'), ('binding', 'npu_emulation_indication_state'))]
    packet_plan, plan_before = symbol_bytes(h, h.packet, 'npu_emulation_packet_plan')
    plan_wanted = bytearray(plan_before)
    if case.name == 'before-ready-plan':
        struct.pack_into('<I', plan_wanted, 0, int.from_bytes(plan_before[:4], 'little') + 2048)
    code_before = bytes(h.cpu.mem_read(CODE, 0x200000))
    writable = [(STACK_TOPS[0] - 0x4000, STACK_TOPS[0])]
    manifest = json.loads((pair / 'manifest.json').read_bytes())
    for filename in manifest['symbol_files'].values():
        with (ROOT / filename).open('rb') as stream:
            binary = ELFFile(stream)
            writable += [(s['sh_addr'], s['sh_addr'] + s['sh_size']) for s in binary.iter_sections()
                         if s['sh_flags'] & 3 == 3 and s['sh_size'] and CODE <= s['sh_addr'] < CODE + len(code_before)]
    saved = [getattr(r, 'UC_RISCV_REG_S' + str(i)) for i in range(12)]
    for index, register in enumerate(saved):
        h.cpu.reg_write(register, 0xa1000000 + index * 0x101)
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
    assert len(injection.injected) == 1, ('fault-injection-not-reached', case.name)
    assert reply['flags'] == 7 and reply['words'][14] == 7, ('retained-fault-reply', case.name, reply)
    assert h.unmodeled is None and returns == [dict(registers=expected_registers, irq=0)], (
        'retained-native-ABI', case.name, returns)
    assert reply['returned_stack'] == hex(STACK_TOPS[0] - 0x1000)
    validate_trace(trace, case)
    memory = []
    for base, expected in wanted.items():
        actual = bytes(h.cpu.mem_read(base, len(expected)))
        differences = [i for i, (left, right) in enumerate(zip(actual, expected)) if left != right]
        row = dict(address=hex(base), bytes=len(expected), differing_bytes=len(differences),
                   actual_sha256=hashlib.sha256(actual).hexdigest(),
                   expected_sha256=hashlib.sha256(expected).hexdigest(), first_differences=differences[:16])
        memory.append(row)
        (destination / f'memory-{base:x}.bin').write_bytes(actual)
        (destination / f'expected-{base:x}.bin').write_bytes(expected)
    (destination / 'memory-comparison.json').write_text(json.dumps(memory, indent=2) + '\n')
    assert all(not row['differing_bytes'] for row in memory), ('retained-protected-memory', case.name, memory)
    packet_after = bytes(h.cpu.mem_read(trace.packet, 2076))
    (destination / 'packet.bin').write_bytes(packet_after)
    assert packet_after == packet_wanted, ('retained-private-packet-state', case.name)
    assert bytes(h.cpu.mem_read(packet_plan, len(plan_wanted))) == plan_wanted
    assert all(bytes(h.cpu.mem_read(address, len(contents))) == contents for address, contents in prior), (
        'retained-prior-owner-bytes', case.name)
    words = list(struct.unpack('<16I', h.cpu.mem_read(owner, 64)))
    assert words[:11] == [0x31445443, 1, 1, 1, case.stores, case.stores, case.stores,
                         case.claims_reserved, case.claims, case.published, case.skb], (case.name, words)
    assert h.get32(cold) == h.get32(cold + 4) == h.get32(ADM + 4) == 1
    assert h.get32(ADM + 8) == h.get32(STATE + 16) == 1
    assert h.get32(cold + 380) == h.get32(cold + 384) == 1
    assert h.cpu.mem_read(SRAM + 0x46fa, 1)[0] == 0 and h.clear_count == 0x7000
    after = bytearray(h.cpu.mem_read(CODE, len(code_before)))
    for begin, end in writable:
        assert CODE <= begin <= end <= CODE + len(after)
        after[begin - CODE:end - CODE] = code_before[begin - CODE:end - CODE]
    assert after == code_before, ('retained-executable-code-changed', case.name)
    inputs = native_prefix_snapshot.source_inputs(inputs)
    assert all(captured.digest(ROOT / name) == expected for name, expected in inputs.items())
    result = dict(passed=True, case=case.name, request=record['request'], owner=words,
        original_store_trace=trace_record, original_stores=case.stores, original_lock_writes=len(trace.locks),
        private_claims=case.claims, queue_publications=case.published,
        packet_claims=2560 + case.claims, exact_packet_bytes=2076,
        protected_memory=memory, injections=injection.injected, inputs=inputs,
        actual_native_guards=True, full_request_count=512, input_drift_waivers=False,
        diagnostic_prefix=True, fresh_loader_allocator_caller_proof=False,
        full_setup=False, hardware=False,
        limits=['The restored pre-DESC10 state is strictly bound to the actual producing caller and current inputs.',
                'Faults are explicit fixture writes at the named original lock/claim/release/readiness boundary.',
                'All25606 possible original stores remain in the oracle; this case checks the exact retained prefix.',
                'Memory, MMIO, DMA backing and scheduling remain modeled. Restoration is not fresh initialization.',
                'No physical containment, drain, retirement, reset, device, traffic or client acceptance.'])
    (destination / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, retained_desc10=case.name, original_stores=case.stores,
                          packet_claims=2560 + case.claims)), flush=True)
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


if __name__ == '__main__':
    main()
