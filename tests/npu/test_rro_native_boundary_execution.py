#!/usr/bin/env python3
"""Targeted, host-seeded RV32 RRO boundary execution; not a native prefix replay."""
import argparse
from collections import Counter
import gc
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess

import test_inode_rro_original as original
from emulation_layout import SRAM, SRAM_BYTES
from test_rro_native import ROOT, sha
from test_rro_native_execution import Machine, expected_projection


HOST_ROOT = ROOT / '.local/npu-rro-native-host-20261023/host-q3'
PREFLIGHT_ROOT = ROOT / '.local/npu-rro-native-execution-20261023'
OUTPUT_ROOT = ROOT / '.local/npu-rro-native-boundary-20261023'
SESSION_TABLE_OFFSET = 0x458c
SESSION = 1024
PUBLICATION = 128
SIGNATURES = 1024


def relative(path):
    path = path.resolve(strict=True)
    assert path.is_relative_to(ROOT), ('outside-canonical-workspace', path)
    return path.relative_to(ROOT).as_posix()


def verified(path, expected, inputs):
    digest = sha(path)
    assert digest == expected, ('input-drift', relative(path), expected, digest)
    inputs[relative(path)] = digest
    return digest


def bind_inputs(host_path, preflight_path, program):
    assert host_path == HOST_ROOT / 'result.json'
    assert preflight_path.is_relative_to(PREFLIGHT_ROOT)
    assert preflight_path.name == 'compile-preflight.json'
    assert program == preflight_path.parent / 'rro-native.elf'
    host = json.loads(host_path.read_bytes())
    preflight = json.loads(preflight_path.read_bytes())
    assert host['passed'] and len(host['mutants']) == 4
    assert preflight['compiled'] and preflight['full_execution'] is False
    assert preflight['exact_normal_archive_objects'] is True
    sizes = preflight['layout']
    assert sizes['state_bytes'] == host['matrix']['state_bytes'] == 30356
    assert sizes['publication_bytes'] == 8 and sizes['reset_bytes'] == 24
    assert sizes['publication'] + 129 * sizes['publication_bytes'] == sizes['resets']
    assert sizes['resets'] + 1025 * sizes['reset_bytes'] == sizes['state_bytes']
    assert host['matrix']['state_records'] == 6958

    inputs = {}
    verified(preflight_path, sha(preflight_path), inputs)
    verified(host_path, preflight['inputs'][relative(host_path)], inputs)
    verified(program, preflight['program_sha256'], inputs)
    assert preflight['command'][-2:] == ['-o', str(program)]
    for name in host['inputs']:
        assert preflight['inputs'][name] == host['inputs'][name]
        verified(ROOT / name, host['inputs'][name], inputs)
    source_files = (
        'firmware/npu/rro-native.c', 'firmware/npu/rro-native.h',
        'firmware/npu/rro-lifetime.c', 'firmware/npu/rro-lifetime.h',
        'tests/npu/test_rro_native.py', 'tests/npu/test_rro_native_execution.py',
        'tests/npu/test_inode_rro_original.py', 'tests/npu/emulation_layout.py',
        'tests/npu/test_firmware_memory_layout.py',
        'tests/npu/rro-native-fixture.h', 'tests/npu/rro-native-emulation.c',
        'tests/npu/rro-native-emulation.ld',
    )
    for name in source_files:
        verified(ROOT / name, preflight['inputs'][name], inputs)
    inputs[relative(Path(__file__))] = sha(Path(__file__))

    archives = [name for name in preflight['inputs'] if name.endswith('/libw1700k-npu.a')]
    assert len(archives) == 1
    archive = ROOT / archives[0]
    verified(archive, preflight['inputs'][archives[0]], inputs)
    members = subprocess.check_output(['ar', 't', str(archive)], text=True).splitlines()
    assert len(members) == 24
    for name in ('rro-lifetime.o', 'rro-native.o'):
        assert members.count(name) == 1
        normal = archive.parent / name
        compiled = preflight_path.parent / name
        expected = preflight['inputs'][relative(normal)]
        verified(normal, expected, inputs)
        verified(compiled, expected, inputs)
        extracted = subprocess.check_output(['ar', 'p', str(archive), name])
        assert hashlib.sha256(extracted).hexdigest() == expected, ('archive-member-drift', name)
        assert str(compiled) in preflight['command'], ('ELF-object-command-mismatch', name)
    return host, preflight, sizes, inputs


def host_boundaries(host_path, host, sizes, inputs):
    states = host_path.parent / 'states.bin'
    key = relative(states)
    assert key in host['artifacts']
    assert states.stat().st_size == host['matrix']['state_records'] * (16 + sizes['state_bytes'])
    digest = hashlib.sha256()
    boundaries, initial = {profile: {} for profile in range(3)}, {}
    counts = {profile: Counter() for profile in range(3)}
    previous, active, records = None, -1, 0
    with states.open('rb') as stream:
        while header := stream.read(16):
            assert len(header) == 16, 'truncated-host-state-header'
            digest.update(header)
            kind, profile, ordinal, length = struct.unpack('<4I', header)
            assert length == sizes['state_bytes'] and 0 <= profile < 3
            if profile != active:
                assert profile == active + 1 and kind == 0 and ordinal == 0
                previous, active = None, profile
            state = stream.read(length)
            assert len(state) == length, 'truncated-host-journal'
            digest.update(state)
            counts[profile][kind] += 1
            records += 1
            if kind == 0:
                assert previous is None and profile not in initial
                initial[profile] = state
            if kind == 2 and ordinal == PUBLICATION:
                assert previous is not None
                assert previous[:2] == (1, (137 if profile == 2 else 139) - 1)
                assert 'publication' not in boundaries[profile]
                boundaries[profile]['publication'] = (previous[2], state)
            if kind == 4 and ordinal == SESSION:
                assert previous is not None and previous[:2] == (5, SESSION - 1)
                assert 'reset' not in boundaries[profile]
                boundaries[profile]['reset'] = (previous[2], state)
            previous = kind, ordinal, state
    assert active == 2 and records == host['matrix']['state_records'] == 6958
    assert digest.hexdigest() == host['artifacts'][key], 'host-state-stream-drift'
    inputs[key] = digest.hexdigest()
    for profile in range(3):
        assert counts[profile] == Counter({
            0: 1, 1: 137 if profile == 2 else 139, 2: 129, 3: 1, 4: 1025, 5: 1025})
        assert set(boundaries[profile]) == {'publication', 'reset'}
    return initial, boundaries


def failed_journal(prefix, profile, branch, sizes):
    result = bytearray(prefix)
    phase_offset = sizes['error'] + 4
    assert sizes['error'] == 4 and sizes['last_ticket'] == 20
    assert struct.unpack_from('<I', result, sizes['error'])[0] == 0
    assert struct.unpack_from('<I', result, phase_offset)[0] == (1 if branch == 'publication' else 2)
    ticket = struct.unpack_from('<I', result, sizes['last_ticket'])[0] + 1
    struct.pack_into('<I', result, sizes['last_ticket'], ticket)
    if branch == 'publication':
        slot = (137 if profile == 2 else 139) - 1
        exposure = sizes['exposure'] + slot * 4
        entry = sizes['publication'] + PUBLICATION * sizes['publication_bytes']
        assert struct.unpack_from('<I', result, exposure)[0] == 1
        assert struct.unpack_from('<2I', result, entry) == (0, 0)
        struct.pack_into('<I', result, exposure, 3)
        struct.pack_into('<2I', result, entry, ticket, 0xffffffff)
        error = sizes['PUBLICATION_FAILED']
    else:
        entry = sizes['resets'] + SESSION * sizes['reset_bytes']
        assert struct.unpack_from('<6I', result, entry) == (1, 0, 0, 0, 0, 0)
        struct.pack_into('<6I', result, entry, 1, 1, ticket, sizes['NPU_POSSIBLE'], 0xffffffff, 0)
        error = sizes['RESET_FAILED']
    struct.pack_into('<I', result, sizes['error'], error)
    assert struct.unpack_from('<I', result, phase_offset)[0] == (1 if branch == 'publication' else 2)
    return bytes(result), ticket, error


def partial_memory(prefix, branch, base, successful_stores):
    sram, alias = bytearray(prefix['sram']), bytearray(prefix['alias'])
    written = set()
    signatures = successful_stores
    if branch == 'publication' and successful_stores:
        struct.pack_into('<I', sram, SESSION_TABLE_OFFSET, base)
        written.update(range(SRAM + SESSION_TABLE_OFFSET, SRAM + SESSION_TABLE_OFFSET + 4))
        signatures -= 1
    assert 0 <= signatures <= SIGNATURES
    start = base - original.ALIAS
    for index in range(signatures):
        offset = start + 7 + 8 * index
        alias[offset] = 0xff
        written.add(base + 7 + 8 * index)
    return bytes(sram), bytes(alias), written


def mapped_memory(machine):
    return (bytes(machine.cpu.mem_read(SRAM, SRAM_BYTES)),
            bytes(machine.cpu.mem_read(original.ALIAS, original.ALIAS_BYTES)))


def execute_boundary(machine, profile, branch, before, after, initial, sizes, rows):
    result, _ = machine.call('rro_emulation_init', profile, kind=0)
    assert result == 0 and machine.state() == initial, ('host-init-mismatch', profile)
    assert bytes(machine.cpu.mem_read(machine.plan, machine.plan_bytes)) == before[
        sizes['plan']:sizes['plan'] + sizes['plan_bytes']]
    machine.cpu.mem_write(machine.owner, before)
    if branch == 'reset':
        machine.cpu.mem_write(SRAM + SESSION_TABLE_OFFSET, struct.pack('<I', original.SESSION))
    assert machine.state() == before
    assert bytes(machine.cpu.mem_read(original.ALIAS, original.ALIAS_BYTES)) == b'\xa5' * original.ALIAS_BYTES
    prefix = machine.snapshot()
    selector = 1 if branch == 'publication' else 3
    projection = expected_projection(machine, selector, 0 if branch == 'publication' else SESSION,
                                     0x88801000 if branch == 'publication' else 0)
    expected_sram, expected_alias, allowed, base, length = projection
    assert base == original.SESSION and length == 8192
    assert len(allowed) == SIGNATURES + (4 if branch == 'publication' else 0)
    name = 'rro_emulation_publish' if branch == 'publication' else 'rro_emulation_reset'
    arguments = (PUBLICATION,) if branch == 'publication' else (SESSION, 1)
    call_kind = 2 if branch == 'publication' else 4
    result, trace = machine.call(name, *arguments, kind=call_kind, allowed=allowed)
    assert result == 0 and machine.state() == after, ('host-after-mismatch', profile, branch, result)
    assert mapped_memory(machine) == (bytes(expected_sram), bytes(expected_alias))
    assert trace['written'] == allowed and trace['stores'] == (
        SIGNATURES + (1 if branch == 'publication' else 0))
    rows.write(json.dumps(dict(profile=profile, branch=branch, positive=True,
        before_sha256=hashlib.sha256(before).hexdigest(), after_sha256=hashlib.sha256(after).hexdigest(),
        stores=trace['stores'], write_sha256=trace['hash'].hexdigest())) + '\n')

    expected_state, ticket, error = failed_journal(before, profile, branch, sizes)
    write_points = (0, 1, 512, 1024) if branch == 'publication' else (0, 512, 1023)
    cases = [(kind, index) for kind in (2, 3) for index in write_points]
    cases += [(kind, index) for kind in (1, 4) for index in (0, 513, 1025)]
    total_stores = SIGNATURES + (branch == 'publication')
    for kind, index in cases:
        machine.restore(prefix)
        assert machine.state() == before and mapped_memory(machine) == (prefix['sram'], prefix['alias'])
        armed, _ = machine.call('rro_emulation_fault', kind, index)
        assert armed == 0 and machine.state() == before
        result, trace = machine.call(name, *arguments, kind=call_kind, allowed=allowed)
        assert result == sizes['HELD'] and machine.state() == expected_state, (
            'failed-journal', profile, branch, kind, index, result)
        assert struct.unpack_from('<I', machine.state(), sizes['last_ticket'])[0] == ticket
        assert struct.unpack_from('<I', machine.state(), sizes['error'])[0] == error
        assert struct.unpack_from('<I', machine.state(), sizes['error'] + 4)[0] == (
            1 if branch == 'publication' else 2)
        slot = (137 if profile == 2 else 139) - 1
        assert struct.unpack_from('<I', machine.state(), sizes['exposure'] + slot * 4)[0] == (
            3 if branch == 'publication' else 15)
        successful = (index + int(kind == 3) if kind in (2, 3) else
                      (int(branch == 'publication') if index == 0 else total_stores))
        partial_sram, partial_alias, footprint = partial_memory(prefix, branch, base, successful)
        assert mapped_memory(machine) == (partial_sram, partial_alias), (
            'partial-memory', profile, branch, kind, index)
        assert trace['written'] == footprint and trace['stores'] == successful, (
            'partial-store-footprint', profile, branch, kind, index)
        retry, again = machine.call(name, *arguments, kind=call_kind)
        assert retry == sizes['HELD'] and machine.state() == expected_state
        assert not again['written'] and again['stores'] == 0
        assert mapped_memory(machine) == (partial_sram, partial_alias), (
            'retry-mapped-memory', profile, branch, kind, index)
        rows.write(json.dumps(dict(profile=profile, branch=branch, positive=False,
            failure_kind=kind, index=index, held=retry, ticket=ticket, error=error,
            successful_stores=successful, write_sha256=trace['hash'].hexdigest(),
            state_sha256=hashlib.sha256(expected_state).hexdigest(), retry_without_stores=True)) + '\n')
    return len(cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--host-receipt', required=True, type=Path)
    parser.add_argument('--program', required=True, type=Path)
    parser.add_argument('--preflight', required=True, type=Path)
    args = parser.parse_args()
    assert re.fullmatch(r'[a-z][a-z0-9-]{0,39}', args.name)
    host_path = args.host_receipt.resolve(strict=True)
    program = args.program.resolve(strict=True)
    preflight_path = args.preflight.resolve(strict=True)
    host, preflight, sizes, inputs = bind_inputs(host_path, preflight_path, program)
    initial, boundaries = host_boundaries(host_path, host, sizes, inputs)
    states_name = relative(host_path.parent / 'states.bin')
    assert preflight['inputs'][states_name] == inputs[states_name], 'preflight-host-stream-mismatch'
    destination = OUTPUT_ROOT / args.name
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, destination / 'driver-at-run.py')
    positives = faults = calls = blocks = 0
    distinct_blocks = maximum_stack = 0
    with (destination / 'observations.jsonl').open('x') as rows:
        for profile in range(3):
            for branch in ('publication', 'reset'):
                machine = Machine(program, sizes)
                try:
                    before, after = boundaries[profile][branch]
                    faults += execute_boundary(machine, profile, branch, before, after,
                                               initial[profile], sizes, rows)
                    positives += 1
                    calls += machine.calls
                    blocks += machine.blocks
                    distinct_blocks += len(machine.seen)
                    maximum_stack = max(maximum_stack, machine.max_stack)
                finally:
                    machine.close()
                    del machine
                    gc.collect()
    assert positives == 6 and faults == 78 and calls == 6 * 2 + 78 * 3
    for name, digest in inputs.items():
        assert sha(ROOT / name) == digest, ('final-input-drift', name)
    artifacts = {relative(path): sha(path) for path in (
        destination / 'driver-at-run.py', destination / 'observations.jsonl')}
    result = dict(passed=True, profiles=3, positive_boundary_cases=positives,
        injected_fault_cases=faults, total_fixture_calls=calls,
        host_seeded_prefixes=True, native_prefix_replay=False,
        complements_full_exact_object_replay=True, hardware=False,
        current_native_transport_admitted=False, hardware_transport_admission=False,
        exact_normal_archive_objects=True, ELF_instruction_bytes_verified=True,
        full_SRAM_and_alias_projections=True, full_host_after_journal_bytes=True,
        callee_saved_and_MSTATUS_preserved=True, partial_store_footprints_verified=True,
        retry_HELD_without_stores=True, executed_basic_block_entries=blocks,
        distinct_block_views=distinct_blocks, maximum_observed_stack_bytes=maximum_stack,
        inputs=inputs, artifacts=artifacts, compile_preflight_layout=sizes,
        compile_preflight_declared_inputs=preflight['inputs'],
        host_declared_inputs=host['inputs'], host_declared_artifacts=host['artifacts'],
        limits=['HOST-SEEDED synthetic journal prefixes; no previously executed native prefix or full startup.',
            'Only publication ordinal128 and NPU reset session1024 execute here; the live full exact-object replay is independent.',
            'Mapped SRAM/alias are synthetic A5 bytes, with only the reset1024 session-table binding seeded.',
            'Fixture backing, exclusion and MCU success remain models; neither hardware nor current transport is admitted.'])
    output = destination / 'result.json'
    with output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(passed=True, profiles=3, positive_boundary_cases=positives,
        injected_fault_cases=faults, host_seeded_prefixes=True, native_prefix_replay=False,
        result=relative(output), result_sha256=sha(output))), flush=True)


if __name__ == '__main__':
    main()
