#!/usr/bin/env python3
"""Native DESC10 negatives from an artifact-bound captured prefix, not fresh boot."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
import unicorn
from unicorn import riscv_const as r
from emulation_layout import STATE
from test_bootstrap_native import ADM
import test_npu_raw_pair as raw
import restore_native_prefix as captured

ROOT = raw.ROOT


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fixture(pair, snapshot):
    h, restore, record, inputs = captured.fixture(pair, snapshot,
        origin='actual-provider-allocator-caller-before-DESC10')
    inputs[str(Path(__file__).relative_to(ROOT))] = captured.digest(Path(__file__))
    return h, restore, record, inputs, {}


def check(h, restore, request):
    cold = h.rv.symbols['npu_emulation_cold_setup_state']
    owner = h.desc10.symbols['npu_emulation_desc10_state']
    packet = h.packet.symbols['npu_emulation_packet_state']
    entry = h.desc10.symbols['npu_emulation_desc10_callback']
    reserve = h.desc10.symbols['npu_emulation_desc10_reserve']
    first_store = h.desc10.symbols['npu_emulation_desc10_b45e_store']
    second_store = h.desc10.symbols['npu_emulation_desc10_b46a_store']
    registers = [getattr(r, 'UC_RISCV_REG_S' + str(i)) for i in range(12)]
    registers += [r.UC_RISCV_REG_GP, r.UC_RISCV_REG_TP]

    def put(address, value):
        return lambda cpu: h.put32(address, value)

    def bump(address):
        return lambda cpu: h.put32(address, h.get32(address) ^ 32)

    def record(type_):
        matches = [0x3e901be4 + 8 * i for i in range(h.get32(0x3e901bd4))
                   if h.get32(0x3e901be4 + 8 * i) & 65535 == type_]
        assert len(matches) == 1
        return matches[0]

    packet_record, queue_record, temporary_record = [record(type_) for type_ in (0x8a, 0x12, 0x1d)]

    cases = [(name, entry, mutate, 0, 0) for name, mutate in (
        ('running-preowned', put(h.desc10.symbols['npu_emulation_desc10_running'], 1)),
        ('callback-slot', put(0x3e90017c, 0)),
        ('static-type107', put(0x8401cfa8, 0x106)),
        ('fixed-L2-pointer', put(0x8401cfac, 0xdead0000)),
        ('static-type108', put(0x8401cfb0, 0x109)),
        ('fixed-L2-extent', bump(0x8401cfb4)),
        ('packet-pool', bump(0x3e901b88)),
        ('temporary-pool', bump(0x3e901bc0)),
        ('skb-queue', bump(0x3e901b84)),
        ('skb-capacity', put(0x3e900bc0, 0)),
        ('packet-lock-ID', put(0x3e901b9c, 29)),
        ('skb-lock-ID', put(0x3e901bb8, 18)),
        ('collector-lock-ID', put(0x3e901bc4, 21)),
        ('RX-order', put(cold + 380, 2)),
        ('prior-RX-order', put(cold + 384, 0)),
        ('allocator-count-bound', put(0x3e901bd4, 101)),
        ('packet-record-type', put(packet_record, 0x8b)),
        ('packet-record-reserved', put(packet_record, 0x1008a)),
        ('queue-record-start', bump(queue_record + 4)),
        ('temporary-record-start', bump(temporary_record + 4)),
        ('packet-definition-size', put(0x8401b228, 32736)),
        ('queue-definition-size', put(0x8401d02c, 16384)),
        ('temporary-definition-size', put(0x8401d04c, 4064)),
        ('queue-definition-flags', put(0x8401d028, 0x10012)),
    )]
    cases += [
        ('computed-unmapped-address', reserve, lambda cpu: cpu.reg_write(r.UC_RISCV_REG_A0, 0xdead0000), 0, 0),
        ('computed-wrong-width', reserve, lambda cpu: cpu.reg_write(r.UC_RISCV_REG_A2, 4), 0, 0),
        ('computed-wrong-value', reserve, lambda cpu: cpu.reg_write(
            r.UC_RISCV_REG_A1, cpu.reg_read(r.UC_RISCV_REG_A1) ^ 1), 0, 0),
        ('late-IRQ-enable', reserve, lambda cpu: cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 8), 0, 0),
        ('after-first-store-held-fault', first_store, put(STATE + 16, 1), 1, 0),
        ('first-store-readback', first_store, lambda cpu: cpu.reg_write(
            r.UC_RISCV_REG_S0, cpu.reg_read(r.UC_RISCV_REG_S0) ^ 1), 1, 0),
        ('second-store-readback', second_store, lambda cpu: cpu.reg_write(
            r.UC_RISCV_REG_A0, cpu.reg_read(r.UC_RISCV_REG_A0) ^ 4), 2, 1),
    ]
    rows = []
    for name, site, mutate, committed, published in cases:
        restore()
        assert h.get32(packet + 16) == 2560 and not any(h.cpu.mem_read(owner, 64))
        spans = ((h.get32(0x3e903964), 8192), (0x3e8adc70, 1024),
                 (h.get32(0x3e901bc0), 4096), (h.get32(0x3e901b84), 16384), (0x50c00000, 16384))
        untouched = {base: bytes(h.cpu.mem_read(base, size)) for base, size in spans}
        packet_before = bytes(h.cpu.mem_read(packet, 2076))
        for i, register in enumerate(registers[:12]):
            h.cpu.reg_write(register, 0xa1000000 + i * 0x101)
        expected_registers = [h.cpu.reg_read(register) for register in registers]
        injected, returned = [], []

        def inject(cpu, pc, size, data):
            if not injected:
                mutate(cpu)
                injected.append(True)

        native_run = h.run

        def observed_run(start, stops):
            pc = native_run(start, stops)
            returned.append([h.cpu.reg_read(register) for register in registers])
            return pc

        hook = h.cpu.hook_add(unicorn.UC_HOOK_CODE, inject, begin=site, end=site)
        try:
            with patch.object(h, 'run', side_effect=observed_run):
                reply = h.message(request)
        finally:
            h.cpu.hook_del(hook)
        assert injected and reply['flags'] == 7 and reply['words'][14] == 7, (name, reply)
        assert h.unmodeled is None, (name, h.unmodeled)
        assert returned == [expected_registers], (name, returned, expected_registers)
        assert h.get32(cold) == h.get32(cold + 4) == h.get32(ADM + 4) == 1
        assert h.get32(ADM + 8) == h.get32(STATE + 16) == 1
        words = list(struct.unpack('<16I', h.cpu.mem_read(owner, 64)))
        assert [words[i] for i in (2, 4, 5, 6)] == [1, committed, committed, published], (name, words)
        assert words[7:11] == [0, 0, 0, 0] and h.get32(cold + 380) == (2 if name == 'RX-order' else 1)
        packet_after = bytes(h.cpu.mem_read(packet, 2076))
        expected_packet = bytearray(packet_before)
        packet_fault = int.from_bytes(packet_after[8:12], 'little')
        assert packet_fault in (0, 1)
        expected_packet[8:12] = packet_after[8:12]
        assert packet_after == expected_packet, (name, words, [
            (i, before, after) for i, (before, after) in enumerate(zip(
                struct.unpack('<519I', packet_before), struct.unpack('<519I', packet_after))) if before != after])
        assert all(bytes(h.cpu.mem_read(base, len(contents))) == contents for base, contents in untouched.items())
        assert h.cpu.mem_read(0x3e9046fa, 1)[0] == 0 and h.clear_count == 0x7000
        if committed:
            count = int.from_bytes(h.cpu.mem_read(0x3e902a7c, 2), 'little')
            assert count == (513 if name == 'first-store-readback' else 512), (name, count)
        if committed == 2:
            assert h.get32(0x3e902cf4) == (0x3e8adc70 ^ 4), name
        rows.append(dict(name=name, committed=committed, published=published, shared_packet_fault=packet_fault,
                         retained_packet_claims=2560, retained_active=1, retained_inflight=1,
                         native_callee_saved_before_context_restore=True, returned_stack=reply['returned_stack']))
        print(json.dumps(dict(desc10_native_control=name, passed=True)), flush=True)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert args.output.resolve().is_relative_to(ROOT / '.local') and not args.output.exists()
    h, restore, record, inputs, drift = fixture(args.pair.resolve(), args.snapshot.resolve())
    controls = check(h, restore, record['request'])
    assert all(raw.composition.sha(ROOT / name) == digest for name, digest in inputs.items())
    result = dict(passed=True, cases=len(controls), controls=controls, inputs=inputs,
        diagnostic_prefix=True, snapshot_observer_input_drift=drift,
        fresh_loader_allocator_caller_proof=False,
        limits=['Original guarded RV32 and authenticated frame start from a hash-bound actual producing-run prefix.',
                'Restoration and fault injection are fixtures, not fresh allocator/caller or physical execution.',
                'Early context/operand rejection and first/second-store retention/ABI are covered; later SKB/readiness negatives remain.',
                'MMIO, backing, DMA and scheduling remain modeled; no drain, hardware or client acceptance.'])
    with args.output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=len(controls), fresh_loader_allocator_caller_proof=False)))


if __name__ == '__main__':
    main()
