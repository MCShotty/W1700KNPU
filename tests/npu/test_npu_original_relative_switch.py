#!/usr/bin/env python3
"""Original relative switches: exact snapshots, local CFG results, bounded prefixes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

import native_prefix_snapshot
from test_npu_direct_stack import decode, transfer
from test_npu_original_body_stack import local_body
from test_npu_switch_targets import inspect_function, table_sequence

ROOT = Path(__file__).resolve().parents[2]
BASE = 0x84000000
SITES = {0x840107ca:0x840108e2, 0x840183b2:0x840184c6}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prefix_guests(code, entry, row):
    from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
    from unicorn import UC_PROT_READ, UC_PROT_EXEC
    from unicorn import riscv_const as registers
    ids = [getattr(registers, 'UC_RISCV_REG_X'+str(i)) for i in range(32)]
    mapped = (len(code) + 4095) & ~4095
    observations = []
    for index in [*range(row['entry_count']), row['entry_count'], 0xffffffff]:
        cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        cpu.mem_map(BASE, mapped)
        cpu.mem_write(BASE, code)
        cpu.mem_protect(BASE, mapped, UC_PROT_READ | UC_PROT_EXEC)
        for number, register in enumerate(ids[1:], 1):
            cpu.reg_write(register, 0xa0000000+number)
        cpu.reg_write(registers.UC_RISCV_REG_SP, 0x85001000)
        cpu.reg_write(registers.UC_RISCV_REG_MSTATUS, 0x1880)
        cpu.reg_write(registers.UC_RISCV_REG_A5, index)
        if entry == 0x840107ca:
            cpu.reg_write(registers.UC_RISCV_REG_S5, (index+32) & 0xffffffff)
        allowed = index < row['entry_count']
        target = row['table_targets'][index] if allowed else row['default_target']
        expected = [cpu.reg_read(register) for register in ids]
        expected[15] = target if allowed else index
        if entry == 0x840107ca:
            expected[14] = row['entry_count']-1
            if allowed:
                expected[13] = row['table_address']
        else:
            expected[13] = row['table_address'] if allowed else row['entry_count']-1
        status = cpu.reg_read(registers.UC_RISCV_REG_MSTATUS)
        before = bytes(cpu.mem_read(BASE, mapped))
        reads, writes = [], []
        cpu.hook_add(UC_HOOK_MEM_READ, lambda engine, access, address, width, value, unused:
            reads.append((address, width)))
        cpu.hook_add(UC_HOOK_MEM_WRITE, lambda engine, access, address, width, value, unused:
            writes.append((address, width, value)))
        cpu.emu_start(row['definition_start'], target, count=50)
        actual = [cpu.reg_read(register) for register in ids]
        assert actual == expected and cpu.reg_read(registers.UC_RISCV_REG_PC) == target
        assert cpu.reg_read(registers.UC_RISCV_REG_MSTATUS) == status
        assert reads == ([(row['table_address']+4*index, 4)] if allowed else []) and writes == []
        assert bytes(cpu.mem_read(BASE, mapped)) == before
        observations.append(dict(index=index, in_range=allowed, start=row['definition_start'], PC=target,
            registers=actual, MSTATUS=status, reads=reads, writes=writes,
            whole_protected_memory_unchanged=True, observed_before_restoration=True,
            stopped_before_case_body=True, original_prefix_bytes_executed=True,
            synthetic_registers_and_memory_permissions=True, full_original_function_executed=False))
    return observations


def audit(original, paired, exports, execute_prefixes=False):
    blob, code = original.read_bytes(), paired.read_bytes()
    paths, rows, seen = [original, paired, Path(__file__)], [], set()
    for path in exports:
        export = json.loads(path.read_bytes())
        assert export['passed'] and export['language'] == 'RISCV:LE:32:AndeStar_v5'
        paths.append(path)
        for function in export['functions']:
            entry = int(function['entry'], 16)
            if entry not in SITES:
                continue
            assert entry not in seen and len(function['body_ranges']) == 1
            seen.add(entry)
            body = function['body_ranges'][0]
            size, offset = body['bytes'], entry-BASE
            assert int(body['start'], 16) == entry and int(body['inclusive_end'], 16)+1 == entry+size
            assert 0 <= offset < offset+size <= min(len(blob), len(code))
            data = blob[offset:offset+size]
            assert data == code[offset:offset+size] and hashlib.sha256(data).hexdigest() == body['sha256']
            instructions = decode(data, entry)
            assert [(i.address, bytes(i.bytes).hex()) for i in instructions] == [
                (int(i['address'], 16), i['bytes_hex']) for i in function['instructions']]
            tables_read = []

            def read_table(address, count):
                start, length = address-BASE, 4*count
                assert 0 <= start < start+length <= min(len(blob), len(code))
                raw = blob[start:start+length]
                assert raw == code[start:start+length]
                tables_read.append(dict(address=address, bytes=length,
                    sha256=hashlib.sha256(raw).hexdigest(), exact_original_and_paired_bytes=True,
                    carrier='original-executable-CODE-blob', physical_readonly_permission_proved=False))
                return raw

            dispatches = [row for index in range(len(instructions))
                if (row := table_sequence(instructions, index)) is not None]
            assert len(dispatches) == 1 and dispatches[0]['address'] == SITES[entry]
            row = dispatches[0]
            assert row['table_entry_encoding'] == 'base-relative-u32'
            raw = read_table(row['table_address'], row['entry_count'])
            row['table_targets'] = [(row['table_address']+word) & 0xffffffff
                for word in struct.unpack('<'+'I'*row['entry_count'], raw)]
            prefix = set(row['prefix_addresses'])
            entries = []
            for index, instruction in enumerate(instructions):
                edge = transfer(instruction, instructions[index-1] if index else None)
                if edge is not None and edge['target'] in prefix and instruction.address not in prefix:
                    entries.append(dict(source=instruction.address, target=edge['target'], kind=edge['kind']))
            result = dict(entry=entry, bytes=size, instructions=len(instructions), body_sha256=body['sha256'],
                older_Ghidra_CODE_sha256=export['mapped_CODE_sha256'], exact_body_and_instruction_bytes=True,
                prefix=row, direct_entries_from_outside_prefix=entries)
            try:
                result['CFG'] = dict(qualified=True, result=inspect_function(data, entry, read_table))
            except AssertionError as error:
                result['CFG'] = dict(qualified=False, error=str(error))
            try:
                result['local_stack'] = dict(qualified=True,
                    result=local_body(data, entry, read_table=read_table))
            except AssertionError as error:
                result['local_stack'] = dict(qualified=False, error=str(error))
            result['table_snapshot_reads'] = tables_read
            recovered = function['recovered_tables']
            assert len(recovered) == 1 and int(recovered[0]['switch_address'], 16) == row['address']
            ghidra = {int(value, 16) for value in recovered[0]['case_targets']}
            result['Ghidra_unique_targets_match_table_and_default'] = ghidra == set(row['table_targets']+[row['default_target']])
            result['Ghidra_labels_used_as_table_indices'] = False
            if execute_prefixes:
                result['prefix_guests'] = prefix_guests(code, entry, row)
            rows.append(result)
    assert seen == set(SITES)
    inputs = native_prefix_snapshot.source_inputs({str(path.relative_to(ROOT)):digest(path) for path in paths})
    assert all(digest(ROOT / name) == expected for name, expected in inputs.items())
    return dict(observations_verified=True, scope='two-original-relative-switches-local-CFG-and-isolated-prefixes',
        rows=rows, inputs=inputs, original_CODE_sha256=digest(original), paired_CODE_sha256=digest(paired),
        table_snapshot_immutability_assumed=True, physical_table_permissions_proved=False,
        guest_scope='Original isolated dispatch prefixes with synthetic state,not complete functions.' if execute_prefixes else 'No guest executed.',
        global_graph_extended=False, earlier_graph_requalified=False,
        complete_call_chain_or_physical_stack_bound_proven=False, hardware=False,
        limits=['A denied CFG or local stack remains denied; a successful isolated prefix does not override it.',
                'Executable-blob table snapshots are not compiled-ELF read-only data or physical permissions.',
                'All external child costs,entry ABI,termination,aliases,asynchronous mutation and physical placement remain unproved.',
                'Byte-equal original bodies do not requalify the older imported ELF or whole current CODE graph.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--paired', type=Path, required=True)
    parser.add_argument('--export', type=Path, action='append', required=True)
    parser.add_argument('--execute-prefixes', action='store_true')
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    original, paired, *exports = [path.resolve() for path in [args.original, args.paired, *args.export]]
    assert all(path.is_relative_to(ROOT / '.local') for path in [original, paired, *exports])
    result = audit(original, paired, exports, args.execute_prefixes)
    target = ROOT / '.local/npu-original-relative-switch' / args.name / 'result.json'
    target.parent.mkdir(parents=True, exist_ok=False)
    with target.open('x') as stream:
        stream.write(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(observations_verified=True, rows=[dict(entry=hex(row['entry']),
        CFG=row['CFG']['qualified'], local_stack=row['local_stack']['qualified'],
        local_frame=row['local_stack'].get('result', {}).get('local_max_stack_bytes'),
        prefix_guests=len(row.get('prefix_guests', []))) for row in result['rows']],
        sha256=digest(target))), flush=True)


if __name__ == '__main__':
    main()
