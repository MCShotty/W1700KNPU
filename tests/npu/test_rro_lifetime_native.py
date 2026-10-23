#!/usr/bin/env python3
"""Compose actual caller/framing bytes with stock effects and current denials.

Synthetic RAM/aliases and single-hart mutex state remain explicit. No checked
RRO admission, original cold startup, physical DMA or retained lifetime claim.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess

from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r

from emulation_layout import map_sram
import native_prefix_snapshot
import npu_image as image
import test_inode_rro_original as original
from test_firmware_memory_layout import NativeMemory, STACK_TOPS, SRAM, SRAM_BYTES
from test_firmware_stop_counterexample import PRINTF, HART_ID
from test_rro_lifetime_callers import ROOT, sha, validate_packets

PAIR = ROOT / ('.local/npu-build-scratch/native-c2/world-checked-irq-q6/log-upper/'
    'isolated-world-checked-irq-q6-image/rootfs/lib/firmware/airoha')
CODE_SHA = '4e43de6fd2ba1a163c1e9e8c2aebe28954bc15ed13d8a774749d2e1cb9f1ffe8'
DATA_SHA = 'a282ca7ac0bd9cd262f2250bfe4fa4a7b4a556dc804e54e8463ae381a25d6f16'
MANIFEST = ROOT / '.local/npu-resume-20261021/pair-fix-q1/manifest.json'


class RroWriteObserver:
    """One native callback, retaining only the active call's exact write trace."""
    def __init__(self, cpu):
        self.cpu, self.trace = cpu, None
        self.handle = cpu.hook_add(UC_HOOK_MEM_WRITE, self.write)

    def write(self, cpu, access, address, size, value, unused):
        assert self.trace is not None, 'RRO-write-outside-observed-call'
        self.trace.write(cpu, access, address, size, value, unused)

    def call(self, host, trace, address, *arguments):
        assert self.handle is not None and host.cpu is self.cpu
        assert self.trace is None, 'nested-RRO-write-observer'
        self.trace = trace
        try:
            return host.call(address, *arguments)
        finally:
            self.trace = None

    def close(self):
        assert self.trace is None
        if self.handle is not None:
            self.cpu.hook_del(self.handle)
            self.handle = None


class CurrentRroMemory(NativeMemory):
    """Use the existing call ABI/limits, but load the qualified CURRENT raw pair."""
    def __init__(self):
        self.code = (PAIR / 'en7581_MT7996_npu_rv32.bin').read_bytes()
        data = (PAIR / 'en7581_MT7996_npu_data.bin').read_bytes()
        assert hashlib.sha256(self.code).hexdigest() == CODE_SHA
        assert hashlib.sha256(data).hexdigest() == DATA_SHA
        assert len(self.code) <= 0x201000 and len(data) <= SRAM_BYTES
        self.cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        self.cpu.mem_map(original.CODE, 0x201000)
        self.cpu.mem_write(original.CODE, self.code)
        map_sram(self.cpu)
        self.cpu.mem_write(SRAM, data)
        self.cpu.mem_map(0x1ec0c000, 0x1000)
        self.cpu.mem_map(0x1ec03000, 0x1000)
        self.put32(0x1ec03048, 0x10000)
        self.cpu.reg_write(r.UC_RISCV_REG_GP, SRAM + 0x13a8)


def current_denials(destination, packets):
    manifest = json.loads(MANIFEST.read_bytes())
    assert manifest['code']['sha256'] == CODE_SHA and manifest['data']['sha256'] == DATA_SHA
    components = {name: Path(manifest['components'][name]['path']) for name in ('base', 'cold-inode')}
    for name, path in components.items(): assert sha(path) == manifest['components'][name]['sha256']
    symbols = image.symbols(components['cold-inode'])
    hook = next(row for row in manifest['hooks'] if row['site'] == original.CALLBACK)
    assert hook['symbol'] == 'npu_emulation_inode_callback' and hook['target'] == symbols[hook['symbol']]
    # Derive field offsets from the actual headers rather than inferring a C ABI.
    source = destination / 'fault-offsets.c'
    source.write_text('#include <stddef.h>\n#include <stdio.h>\n#include "cold-inode.h"\n'
        '#include "admission.h"\nint main(void) { printf("[%zu,%zu,%zu,%zu]\\n",'
        'offsetof(struct npu_cold_inode_state,fault),offsetof(struct npu_admission,closed),'
        'offsetof(struct npu_admission,fault),offsetof(struct npu_barrier,fault)); return 0; }\n')
    command = [shutil.which('clang'), '-std=c11', '-Wall', '-Wextra', '-Werror', '-I', str(ROOT / 'firmware/npu'),
               str(source), '-o', str(destination / 'fault-offsets')]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (destination / 'fault-offsets.log').write_text(completed.stdout + completed.stderr)
    assert completed.returncode == 0, completed.stderr
    offsets = json.loads(subprocess.check_output([str(destination / 'fault-offsets')], text=True, timeout=10))
    assert offsets == [8, 0, 8, 16]
    updates = {symbols['npu_emulation_inode_state'] + offsets[0]: 1,
               symbols['npu_emulation_admission_state'] + offsets[1]: 1,
               symbols['npu_emulation_admission_state'] + offsets[2]: 1,
               symbols['npu_emulation_barrier_state'] + offsets[3]: 1,
               symbols['npu_emulation_inode_running']: 0, symbols['phase']: 2}
    allowed = {address + i for address in updates for i in range(4)}
    h = CurrentRroMemory()
    h.cpu.mem_map(original.ALIAS, original.ALIAS_BYTES)
    h.cpu.mem_write(original.ALIAS, b'\xa5' * original.ALIAS_BYTES)
    offset = original.CALLBACK - original.CODE
    assert h.code[offset:offset + 4] == image.jal(original.CALLBACK, hook['target'])
    counts, executed = {}, set()

    def instruction(cpu, pc, size, unused):
        offset = pc - original.CODE
        assert 0 <= offset <= len(h.code) - size
        assert bytes(cpu.mem_read(pc, size)) == h.code[offset:offset + size], ('current-instruction-mutation', hex(pc))
        assert pc not in (original.INNER, original.CLEAR, PRINTF, HART_ID, 0x840048f4, 0x84004212)
        executed.add(pc)
        if pc in (original.CALLBACK, hook['target']): counts[pc] = counts.get(pc, 0) + 1

    h.cpu.hook_add(UC_HOOK_CODE, instruction)
    writes = RroWriteObserver(h.cpu)
    saved = [getattr(r, 'UC_RISCV_REG_S' + str(i)) for i in range(12)] + [r.UC_RISCV_REG_GP, r.UC_RISCV_REG_TP]
    rows = []
    for ordinal, packet in enumerate(packets):
        expected_sram = bytearray(h.cpu.mem_read(SRAM, SRAM_BYTES))
        expected_code = bytearray(h.cpu.mem_read(original.CODE, len(h.code)))
        for address, value in updates.items():
            target, base = (expected_sram, SRAM) if SRAM <= address < SRAM + SRAM_BYTES else (expected_code, original.CODE)
            struct.pack_into('<I', target, address - base, value)
        for index, register in enumerate(saved[:12]): h.cpu.reg_write(register, 0xa1000000 + index * 0x101)
        h.cpu.reg_write(r.UC_RISCV_REG_TP, 0xb1000101)
        h.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 8)
        registers = [h.cpu.reg_read(register) for register in saved]
        h.cpu.mem_write(original.PAYLOAD, struct.pack('<6I', *packet))
        trace = original.Trace(h, allowed)
        previous = dict(counts)
        result = writes.call(h, trace, original.CALLBACK, original.PAYLOAD)
        assert result == 0, 'current-RRO-not-denied'
        assert [h.cpu.reg_read(register) for register in saved] == registers
        assert h.cpu.reg_read(r.UC_RISCV_REG_SP) == STACK_TOPS[0] and h.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) == 8
        assert bytes(h.cpu.mem_read(SRAM, SRAM_BYTES)) == expected_sram
        assert bytes(h.cpu.mem_read(original.ALIAS, original.ALIAS_BYTES)) == b'\xa5' * original.ALIAS_BYTES
        actual_code = bytes(h.cpu.mem_read(original.CODE, len(h.code)))
        lo, hi = STACK_TOPS[0] - 256 - original.CODE, STACK_TOPS[0] - original.CODE
        assert actual_code[:lo] == expected_code[:lo] and actual_code[hi:] == expected_code[hi:]
        assert all(not lo <= pc - original.CODE < hi for pc in executed)
        assert trace.written <= allowed
        assert counts[original.CALLBACK] - previous.get(original.CALLBACK, 0) == 1
        assert counts[hook['target']] - previous.get(hook['target'], 0) == 1
        rows.append(dict(ordinal=ordinal, selector=packet[0] & 15, result=result,
            original_constructor_entered=False, RRO_memory_unchanged=True, exact_fault_projection=True,
            ABI_preserved=True, MSTATUS_preserved=True, writes_sha256=trace.hash.hexdigest()))
    writes.close()
    return dict(passed=True, cases=len(rows), observations=rows, hook=hook, field_offsets=offsets,
        fault_fields={hex(address): value for address, value in updates.items()},
        source_inputs={str(path.relative_to(ROOT)): sha(path) for path in [MANIFEST, *components.values(),
            ROOT / 'tools/npu_image.py', ROOT / 'firmware/npu/cold-inode.h', ROOT / 'firmware/npu/admission.h',
            ROOT / 'firmware/npu/barrier.h', ROOT / 'firmware/npu/cold-inode.c', ROOT / 'firmware/npu/admission.c',
            ROOT / 'tests/npu/cold-inode-native-emulation.c']},
        limitation='Direct rejection probes use absent cold context. They do not qualify admitted RRO or full setup.')


def run(destination, receipt_path):
    assert not receipt_path.is_symlink()
    receipt_path = receipt_path.resolve(strict=True)
    assert receipt_path.is_relative_to(ROOT / '.local/npu-rro-lifetime-callers')
    receipt = json.loads(receipt_path.read_bytes())
    assert receipt['passed'] and receipt['characterization_only']
    if receipt['format'] == 'w1700k-rro-lifetime-characterization-v1':
        assert receipt['cases'] == 1021
    else:
        assert receipt['format'] == 'w1700k-rro-lifetime-characterization-v2' and receipt['cases'] == 1037
        assert receipt['metadata']['selected_complete_teardown'] == [
            'mt76_unregister_device', 'mt76_free_device', 'mt76_npu_deinit']
    assert receipt['target_RRO_lifetime_qualified'] is False
    assert not receipt['hardware'] and not receipt['checked_RRO_admitted']
    # Rehash the original caller inputs/artifacts; no rewritten producer receipt.
    dependencies = {**receipt['metadata']['inputs'], **receipt['artifacts']}
    assert all(sha(ROOT / name) == expected for name, expected in dependencies.items()), 'caller-input-or-artifact-drift'
    capture = receipt_path.parent / 'caller-payloads.bin'
    packets = validate_packets(capture)
    paths = [Path(__file__), receipt_path, capture, original.GHIDRA,
             PAIR / 'en7581_MT7996_npu_rv32.bin', PAIR / 'en7581_MT7996_npu_data.bin',
             original.INPUT / 'en7581_MT7996_npu_rv32.bin', ROOT / 'tests/npu/test_inode_rro_original.py',
             ROOT / 'tests/npu/test_firmware_memory_layout.py', ROOT / 'tests/npu/emulation_layout.py',
             ROOT / 'tests/npu/test_firmware_stop_counterexample.py',
             ROOT / 'tests/npu/test_rro_write_observer.py']
    manifest = json.loads(MANIFEST.read_bytes())
    paths += [MANIFEST, *[Path(manifest['components'][name]['path']) for name in ('base', 'cold-inode')]]
    paths += list((ROOT / 'firmware/npu').glob('*.h'))
    paths += [ROOT / 'firmware/npu/cold-inode.c', ROOT / 'firmware/npu/admission.c',
              ROOT / 'tests/npu/cold-inode-native-emulation.c']
    inputs = native_prefix_snapshot.source_inputs({str(path.relative_to(ROOT)): sha(path) for path in paths})
    assert sha(original.GHIDRA) == original.GHIDRA_SHA
    stock = (original.INPUT / 'en7581_MT7996_npu_rv32.bin').read_bytes()
    assert hashlib.sha256(stock).hexdigest() == original.CODE_SHA
    h = NativeMemory()
    h.cpu.mem_map(original.ALIAS, original.ALIAS_BYTES)
    h.cpu.mem_write(original.ALIAS, b'\xa5' * original.ALIAS_BYTES)
    counts, instructions = {}, {}
    forbidden = (0x840048f4, 0x84004212, PRINTF, HART_ID)

    def instruction(cpu, pc, size, unused):
        offset = pc - original.CODE
        assert 0 <= offset <= len(stock) - size, ('RRO-left-original-code', hex(pc))
        assert bytes(cpu.mem_read(pc, size)) == stock[offset:offset + size], ('RRO-instruction-not-original', hex(pc))
        assert pc not in forbidden, ('RRO-substituted-helper', hex(pc))
        instructions[pc] = instructions.get(pc, 0) + 1
        if pc in (original.CALLBACK, original.INNER, original.CLEAR): counts[pc] = counts.get(pc, 0) + 1

    h.cpu.hook_add(UC_HOOK_CODE, instruction)
    writes = RroWriteObserver(h.cpu)
    saved = [getattr(r, 'UC_RISCV_REG_S' + str(i)) for i in range(12)] + [r.UC_RISCV_REG_GP, r.UC_RISCV_REG_TP]
    rows = []
    for ordinal, packet in enumerate(packets):
        selector, api, argument, physical, output_status, output_count = packet
        selector &= 15
        assert api == 24 and output_status == output_count == 0
        before_sram = bytes(h.cpu.mem_read(SRAM, SRAM_BYTES))
        before_alias = bytes(h.cpu.mem_read(original.ALIAS, original.ALIAS_BYTES))
        expected_sram, expected_alias, allowed, base, extent = original.project(
            selector, argument, physical, before_sram, before_alias)
        for index, register in enumerate(saved[:12]): h.cpu.reg_write(register, 0xa1000000 + index * 0x101)
        h.cpu.reg_write(r.UC_RISCV_REG_TP, 0xb1000101)
        h.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 8)
        registers = [h.cpu.reg_read(register) for register in saved]
        h.cpu.mem_write(original.PAYLOAD, struct.pack('<6I', *packet))
        trace = original.Trace(h, allowed)
        previous = dict(counts)
        result = writes.call(h, trace, original.CALLBACK, original.PAYLOAD)
        assert result == 1 and [h.cpu.reg_read(register) for register in saved] == registers, 'stock-RRO-ABI'
        assert h.cpu.reg_read(r.UC_RISCV_REG_SP) == STACK_TOPS[0]
        assert h.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) == 8
        assert bytes(h.cpu.mem_read(SRAM, SRAM_BYTES)) == expected_sram
        assert bytes(h.cpu.mem_read(original.ALIAS, original.ALIAS_BYTES)) == expected_alias
        assert trace.written == allowed, 'current-RRO-store-footprint'
        actual_code = bytes(h.cpu.mem_read(original.CODE, len(h.code)))
        assert actual_code == h.code
        delta = {hex(pc): counts.get(pc, 0) - previous.get(pc, 0) for pc in counts}
        assert delta.get(hex(original.CALLBACK)) == delta.get(hex(original.INNER)) == 1
        assert delta.get(hex(original.CLEAR), 0) == int(selector == 0)
        rows.append(dict(ordinal=ordinal, frame=list(packet), selector=selector, argument=argument,
            alias_base=hex(base), extent=extent, result=result, exact_bytes_written=len(trace.written),
            stores=trace.count, ordered_writes_sha256=trace.hash.hexdigest(), entries=delta,
            exact_SRAM_and_alias_projection=True, ABI_preserved=True, MSTATUS_preserved=True))
        if selector != 0 or ordinal % 16 == 0:
            print(json.dumps(dict(captured_frame=ordinal, selector=selector, argument=argument, passed=True)), flush=True)
    writes.close()
    current = current_denials(destination, packets)
    inputs.update(current['source_inputs'])
    inputs = native_prefix_snapshot.source_inputs(inputs)
    assert all(sha(ROOT / name) == value for name, value in {**dependencies, **inputs}.items()), 'composition-input-drift'
    shutil.copyfile(__file__, destination / 'driver-at-run.py')
    artifacts = {str(path.relative_to(ROOT)): sha(path) for path in destination.iterdir() if path.is_file()}
    return dict(format='w1700k-rro-caller-stock-current-composition-v1', passed=True,
        stock_effect_cases=len(rows), stock_observations=rows, current_rejection=current,
        caller_receipt=str(receipt_path.relative_to(ROOT)), caller_receipt_sha256=sha(receipt_path),
        capture_sha256=sha(capture), inputs=inputs, artifacts=artifacts,
        current_CODE_sha256=CODE_SHA, current_DATA_sha256=DATA_SHA,
        original_stock_CODE_sha256=original.CODE_SHA, original_stock_DATA_sha256=original.DATA_SHA,
        original_Ghidra_export_sha256=original.GHIDRA_SHA,
        stock_executed_instructions_match_original_stock=True, stock_executed_instructions=sum(instructions.values()),
        stock_distinct_instruction_addresses=len(instructions), helper_substitution=False, synthetic_RAM=True,
        instruction_limit=2000000, timeout_us=3000000, checked_RRO_admitted=False,
        target_RRO_lifetime_qualified=False, fresh_loader_allocator_caller_proof=False, hardware=False,
        limits=['All134 actual C-generated raw mailbox frames execute in order in stock-effect and current-rejection fixtures.',
                'Stock e743/61a7 executes the original RRO byte effects; current qualified4e43/a282 executes checked denials.',
                'Original Ghidra export is reused and hash-verified; no new disassembler analysis is claimed.',
                'Callbacks execute against explicit synthetic RAM/aliases, seeded globals and single-hart mutex state.',
                'Existing NativeMemory.call instruction/time limits and all old live replay jobs are unchanged.',
                'Stock CODE is unchanged. Current CODE changes only the exact fault/phase/running fields and modeled 256-byte stack window.',
                'Callback return1 is not mailbox success, checked admission, physical DMA, concurrency or retained-lifetime proof.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--caller-receipt', type=Path, required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    destination = ROOT / '.local/npu-rro-lifetime-native' / args.name
    destination.mkdir(parents=True, exist_ok=False)
    result = run(destination, args.caller_receipt)
    with (destination / 'result.json').open('x') as stream: stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, stock_frames=result['stock_effect_cases'], current_denials=result['current_rejection']['cases'],
        receipt=str((destination / 'result.json').relative_to(ROOT)),
        sha256=sha(destination / 'result.json'), checked_RRO_admitted=False, hardware=False)), flush=True)


if __name__ == '__main__': main()
