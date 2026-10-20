#!/usr/bin/env python3
"""Check bounded intra-function tables without inventing inter-function edges."""
import argparse
from bisect import bisect_right
from collections import deque
import hashlib
import json
from pathlib import Path
import re
import struct

import capstone
from capstone.riscv import RISCV_OP_IMM, RISCV_OP_REG, RISCV_REG_RA
from elftools.dwarf.callframe import FDE

import npu_image
from npu_stack_usage import ROOT, digest
from test_npu_constant_targets import returned, verify_inputs
from test_npu_direct_stack import cfa_table, decode, transfer


def registers(instruction, count):
    operands = instruction.operands
    return len(operands) == count and all(item.type == RISCV_OP_REG for item in operands)


def immediate(instruction, name, count):
    operands = instruction.operands
    return (instruction.mnemonic == name and len(operands) == count
            and all(item.type == RISCV_OP_REG for item in operands[:-1])
            and operands[-1].type == RISCV_OP_IMM)


def relative_table_sequence(instructions, index, guard_setup=False):
    if index < 8:
        return None
    jump = instructions[index]
    if jump.mnemonic not in ('jr', 'c.jr') or not registers(jump, 1) or returned(jump):
        return None
    target = jump.operands[0].reg
    guard, upper, addition, shift, combine, load, target_add = instructions[index-7:index]
    if not (immediate(guard, 'bltu', 3) and immediate(upper, 'auipc', 2)
            and immediate(addition, 'addi', 3) and immediate(shift, 'c.slli', 2)
            and shift.operands[1].imm == 2 and combine.mnemonic == target_add.mnemonic == 'c.add'
            and registers(combine, 2) and registers(target_add, 2)):
        return None
    operands = load.operands
    if not (load.mnemonic == 'c.lw' and len(operands) == 3
            and operands[0].type == operands[2].type == RISCV_OP_REG
            and operands[1].type == RISCV_OP_IMM and operands[1].imm == 0):
        return None
    bound, pointer, base = guard.operands[0].reg, guard.operands[1].reg, upper.operands[0].reg
    if not (target == pointer == shift.operands[0].reg == combine.operands[0].reg
            == operands[0].reg == operands[2].reg == target_add.operands[0].reg
            and base == addition.operands[0].reg == addition.operands[1].reg
            == combine.operands[1].reg == target_add.operands[1].reg
            and base != pointer and bound != pointer
            and all(jump.reg_name(reg) not in ('zero', 'ra', 'sp') for reg in (bound, pointer, base))):
        return None

    def is_limit(item):
        return ((immediate(item, 'c.li', 2) or (immediate(item, 'addi', 3)
            and item.reg_name(item.operands[1].reg) == 'zero'))
            and item.operands[0].reg == bound)

    start = index - 8
    limit = instructions[start]
    setup = []
    if guard_setup:
        biased = False
        while not is_limit(limit):
            destination = limit.operands[0].reg if limit.operands and limit.operands[0].type == RISCV_OP_REG else None
            bias = ((immediate(limit, 'addi', 3) or immediate(limit, 'c.addi', 2))
                and destination == pointer and not biased)
            harmless = ((immediate(limit, 'addi', 3) or (limit.mnemonic == 'xor' and registers(limit, 3)))
                and destination not in (None, bound, pointer, base)
                and limit.reg_name(destination) not in ('zero', 'ra', 'sp') and len(setup) < 2)
            if start == 0 or not (bias or harmless):
                return None
            if bias:
                biased = True
            else:
                setup.append(limit.address)
            start -= 1
            limit = instructions[start]
    elif not is_limit(limit):
        # Some compilers materialize the biased index between limit and guard.
        bias = limit
        if not ((immediate(bias, 'addi', 3) or immediate(bias, 'c.addi', 2))
                and bias.operands[0].reg == pointer and start > 0):
            return None
        start -= 1
        limit = instructions[start]
        if not is_limit(limit):
            return None
    maximum = limit.operands[-1].imm
    if not (0 <= maximum < 1024 and 0 <= upper.operands[1].imm < 1 << 20
            and -2048 <= addition.operands[2].imm <= 2047):
        return None
    prefix = instructions[start:index+1]
    if not all(left.address + left.size == right.address for left, right in zip(prefix, prefix[1:])):
        return None
    table = (upper.address + (upper.operands[1].imm << 12) + addition.operands[2].imm) & 0xffffffff
    if table % 4 or table + 4 * (maximum + 1) > 1 << 32:
        return None
    result = dict(address=jump.address, definition_start=limit.address, guard=guard.address,
        guard_fallthrough=upper.address, default_target=(guard.address + guard.operands[2].imm) & 0xffffffff,
        table_address=table, entry_count=maximum+1, load_address=load.address,
        target_register=jump.reg_name(target), index_register=jump.reg_name(pointer),
        table_entry_encoding='base-relative-u32',
        prefix_addresses=[item.address for item in prefix],
        prefix_hex=b''.join(bytes(item.bytes) for item in prefix).hex())
    if setup:
        result['pre_guard_setup_instructions'] = sorted(setup)
    return result


def table_sequence(instructions, index, guard_setup=False):
    relative = relative_table_sequence(instructions, index, guard_setup=guard_setup)
    if relative is not None:
        return relative
    jump = instructions[index]
    if jump.mnemonic not in ('jr', 'c.jr') or not registers(jump, 1) or returned(jump):
        return None
    target_register = jump.operands[0].reg
    if jump.reg_name(target_register) in ('zero', 'ra', 'sp'):
        return None
    load_index = index - 1
    while load_index >= 0 and index - load_index <= 9:
        item = instructions[load_index]
        benign = (immediate(item, 'c.li', 2) or (item.mnemonic == 'c.mv' and registers(item, 2)))
        if (not benign or item.operands[0].reg == target_register
                or item.reg_name(item.operands[0].reg) in ('zero', 'ra', 'sp')):
            break
        load_index -= 1
    if load_index < 6 or index - load_index > 9:
        return None
    load = instructions[load_index]
    operands = load.operands
    # Capstone 5 represents C.LW as REG,IMM,REG, unlike ordinary LW's REG,MEM.
    if not (load.mnemonic == 'c.lw' and len(operands) == 3
            and operands[0].type == operands[2].type == RISCV_OP_REG
            and operands[1].type == RISCV_OP_IMM and operands[1].imm == 0
            and operands[0].reg == target_register):
        return None
    limit, guard, shift, upper, addition, combine = instructions[load_index-6:load_index]
    if not (immediate(limit, 'c.li', 2) or (immediate(limit, 'addi', 3)
            and limit.reg_name(limit.operands[1].reg) == 'zero')):
        return None
    maximum = limit.operands[-1].imm
    if not 0 <= maximum < 1024:
        return None
    if not (immediate(guard, 'bltu', 3) and immediate(shift, 'slli', 3)
            and shift.operands[2].imm == 2 and immediate(upper, 'lui', 2)
            and immediate(addition, 'addi', 3) and combine.mnemonic == 'c.add'
            and registers(combine, 2)):
        return None
    bound, source = guard.operands[0].reg, guard.operands[1].reg
    pointer, base = shift.operands[0].reg, upper.operands[0].reg
    if not (bound == limit.operands[0].reg and source == shift.operands[1].reg
            and pointer == operands[2].reg == combine.operands[0].reg
            and base == addition.operands[0].reg == addition.operands[1].reg == combine.operands[1].reg
            and len({source, pointer, base}) == 3 and bound != source
            and all(jump.reg_name(reg) not in ('zero', 'ra', 'sp')
                    for reg in (source, pointer, base, bound))):
        return None
    if not (0 <= upper.operands[1].imm < 1 << 20 and -2048 <= addition.operands[2].imm <= 2047):
        return None
    prefix = instructions[load_index-6:index+1]
    if not all(left.address + left.size == right.address for left, right in zip(prefix, prefix[1:])):
        return None
    table = ((upper.operands[1].imm << 12) + addition.operands[2].imm) & 0xffffffff
    if table % 4 or table + 4 * (maximum + 1) > 1 << 32:
        return None
    return dict(address=jump.address, definition_start=limit.address, guard=guard.address,
        guard_fallthrough=shift.address, default_target=(guard.address + guard.operands[2].imm) & 0xffffffff,
        table_address=table, entry_count=maximum+1, load_address=load.address,
        target_register=jump.reg_name(target_register), index_register=jump.reg_name(source),
        prefix_addresses=[item.address for item in prefix],
        prefix_hex=b''.join(bytes(item.bytes) for item in prefix).hex())


def reachable(successors, start, removed_edge=None, removed_edges=()):
    visited, pending = set(), [start]
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        pending.extend(target for target in successors[current] if target not in visited
                       and (current, target) != removed_edge and (current, target) not in removed_edges)
    return visited


def reaching_constants(instructions, successors, edges, address):
    from test_npu_original_body_stack import local_effect
    from test_npu_reaching_targets import merge
    positions = {instruction.address:instruction for instruction in instructions}
    states, pending, updates = {address:tuple([0]+[None]*31)}, deque([address]), 0
    while pending:
        pc = pending.popleft()
        instruction = positions[pc]
        if instruction.mnemonic == 'jal' and len(instruction.operands) == 2:
            assert instruction.operands[0].type == RISCV_OP_REG and instruction.operands[0].reg == RISCV_REG_RA, 'non-ABI-direct-link-register'
        after = local_effect(instruction, states[pc], edges[pc])
        for target in successors[pc]:
            state = after if target not in states else merge(states[target], after)
            if target not in states or state != states[target]:
                states[target] = state
                pending.append(target)
                updates += 1
                assert updates <= 66 * len(instructions), 'constant-state-convergence-bound'
    return states, updates


def relative_guard_set(row, positions, successors, predecessors, states, address):
    from test_npu_reaching_targets import reg
    guard, safe = positions[row['guard']], row['guard_fallthrough']
    bound, index = guard.operands[0].reg, guard.operands[1].reg
    guards = {guard.address}
    for pc in predecessors[safe] - guards:
        candidate = positions[pc]
        assert (immediate(candidate, 'bgeu', 3) and candidate.operands[0].reg == bound
            and candidate.operands[1].reg == index and pc + candidate.size == row['default_target']
            and (pc + candidate.operands[2].imm) & 0xffffffff == safe), 'unqualified-alternate-safe-entry'
        guards.add(pc)
    assert predecessors[safe] == guards, 'incomplete-safe-edge-set'
    for pc in guards:
        assert pc in states and states[pc][reg(positions[pc], 0)] == row['entry_count']-1, 'guard-bound-not-proved-constant'
    # Entries before a guard are safe only because its actual bound is proved.
    after_safe = row['prefix_addresses'][row['prefix_addresses'].index(safe):]
    for left, right in zip(after_safe, after_safe[1:]):
        assert predecessors[right] == {left}, 'prefix-can-bypass-safe-edge-set'
    safe_edges = {(pc, safe) for pc in guards}
    without_safe = reachable(successors, address, removed_edges=safe_edges)
    assert not set(after_safe).intersection(without_safe), 'safe-edge-set-does-not-dominate'
    primary_only = reachable(successors, address, (guard.address, safe))
    row.update(control_flow_qualified=True, same_function_only=True, interfunction_edge=False,
        guard_safe_edge_dominates_load_and_jump=not set(after_safe).intersection(primary_only),
        guard_safe_edge_set_dominates_load_and_jump=True,
        guard_bound_register=guard.reg_name(bound), guard_bound_constant=row['entry_count']-1,
        qualified_safe_edges=[dict(source=pc, target=safe) for pc in sorted(guards)],
        qualification_profile='relative-unsigned-safe-edge-set-v1')


def inspect_function(data, address, read_table, relative_guard_sets=False):
    instructions = decode(data, address)
    assert all(item.mnemonic not in ('unimp', 'c.unimp') for item in instructions), 'invalid-instruction'
    positions = {item.address:item for item in instructions}
    tables = {}
    for index, item in enumerate(instructions):
        row = table_sequence(instructions, index, guard_setup=relative_guard_sets)
        if row is None:
            continue
        raw = read_table(row['table_address'], row['entry_count'])
        assert isinstance(raw, bytes) and len(raw) == 4 * row['entry_count'], 'table-length-drift'
        targets = list(struct.unpack('<' + 'I' * row['entry_count'], raw))
        if row.get('table_entry_encoding') == 'base-relative-u32':
            targets = [(row['table_address'] + value) & 0xffffffff for value in targets]
        assert all(target in positions and target != address and target % 2 == 0 for target in targets), 'noninternal-table-target'
        assert row['default_target'] in positions and row['default_target'] != address, 'noninternal-default-target'
        assert not set(targets + [row['default_target']]).intersection(row['prefix_addresses']), 'table-target-enters-prefix'
        row.update(table_targets=targets, table_sha256=hashlib.sha256(raw).hexdigest())
        tables[item.address] = row
    assert tables, 'no-recognized-table'
    successors = {item.address:set() for item in instructions}
    edges = {}
    control = {capstone.CS_GRP_JUMP, capstone.CS_GRP_CALL, capstone.CS_GRP_RET,
               capstone.CS_GRP_INT, capstone.CS_GRP_IRET}
    for index, item in enumerate(instructions):
        if returned(item):
            edges[item.address] = None
            continue
        edge = transfer(item, instructions[index-1] if index else None)
        edges[item.address] = edge
        if edge is not None and edge['target'] is None:
            assert item.address in tables, 'function-has-other-unresolved-register-flow'
            successors[item.address].update(tables[item.address]['table_targets'])
            continue
        if edge is None:
            assert not control.intersection(item.groups) and item.mnemonic not in (
                'ecall', 'ebreak', 'c.ebreak', 'uret', 'sret', 'mret', 'wfi'), 'unsupported-control-flow'
        elif 'call' not in edge['kind']:
            target = edge['target']
            if address <= target < address + len(data):
                assert target in positions, 'mid-instruction-direct-target'
                successors[item.address].add(target)
            else:
                assert edge['kind'] != 'conditional-direct-transfer', 'external-conditional-target'
        falls = edge is None or 'call' in edge['kind'] or edge['kind'] == 'conditional-direct-transfer'
        if falls:
            following = item.address + item.size
            assert following in positions, 'fallthrough-outside-function'
            successors[item.address].add(following)
    predecessors = {item.address:set() for item in instructions}
    for source, targets in successors.items():
        for target in targets:
            predecessors[target].add(source)
    reached = reachable(successors, address)
    states, updates = reaching_constants(instructions, successors, edges, address) if relative_guard_sets else ({}, 0)
    for row in tables.values():
        assert row['definition_start'] in reached, 'unreachable-table-definition'
        assert row['guard_fallthrough'] != row['default_target'], 'guard-has-no-distinct-safe-edge'
        if relative_guard_sets and row.get('table_entry_encoding') == 'base-relative-u32':
            relative_guard_set(row, positions, successors, predecessors, states, address)
            continue
        for left, right in zip(row['prefix_addresses'], row['prefix_addresses'][1:]):
            assert predecessors[right] == {left}, 'prefix-can-bypass-definition'
        without_safe = reachable(successors, address, (row['guard'], row['guard_fallthrough']))
        protected_prefix = row['prefix_addresses'][row['prefix_addresses'].index(row['guard']) + 1:]
        assert not set(protected_prefix).intersection(without_safe), 'guard-safe-edge-does-not-dominate'
        row.update(control_flow_qualified=True, guard_safe_edge_dominates_load_and_jump=True,
                   same_function_only=True, interfunction_edge=False)
    result = dict(tables=list(tables.values()), instruction_count=len(instructions),
                reachable_instructions=len(reached), other_unknown_register_flow=False)
    if relative_guard_sets:
        result.update(relative_guard_sets=True, reaching_constant_updates=updates,
            entry_registers_unknown_except_zero=True, calls_clobber_caller_saved=True)
    return result


def metadata_matches(row, metadata):
    assert int(metadata['switch_address'], 16) == row['address'], 'metadata-switch-address-drift'
    assert metadata['label_values'] == list(range(row['entry_count'])), 'metadata-label-drift'
    cases = [int(value, 16) for value in metadata['case_targets']]
    assert cases[:row['entry_count']] == row['table_targets'], 'metadata-table-order-drift'
    extra = cases[row['entry_count']:]
    assert extra in ([], [row['default_target']]), 'unexplained-metadata-case'
    return dict(metadata_case_count=len(cases), metadata_unlabelled_default_count=len(extra),
                metadata_load_tables_available=bool(metadata['load_tables']))


def audit(pair, graph_path, export_path):
    graph = json.loads(graph_path.read_bytes())
    export = json.loads(export_path.read_bytes())
    assert graph['passed'] is export['passed'] is True and graph['complete_call_chain_bound_proven'] is False
    verify_inputs(graph['inputs'])
    manifest_path = pair / 'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    code_path = pair / 'CODE.bin'
    code = code_path.read_bytes()
    code_hash = digest(code_path)
    assert len(code) == manifest['code']['bytes'] and code_hash == manifest['code']['sha256']
    assert graph['CODE_identity_sha256'] == export['mapped_CODE_sha256'] == code_hash, 'mixed-CODE-cohorts'
    component = 'base'
    binary_path = (ROOT / manifest['symbol_files'][component]).resolve()
    assert binary_path.is_relative_to(pair) and digest(binary_path) == manifest['components'][component]['sha256']
    assert export['imported_ELF_sha256'] == digest(binary_path)
    binary = npu_image.elf(binary_path)
    symbols = {item['st_value']:item for item in binary.get_section_by_name('.symtab').iter_symbols()
               if item['st_info']['type'] == 'STT_FUNC' and item['st_size'] and isinstance(item['st_shndx'], int)}
    entries = {item['initial_location']:item for item in binary.get_dwarf_info().CFI_entries() if isinstance(item, FDE)}
    measured = {item['address']:item for item in graph['functions']}
    old_unknown = {(item['caller'],item['address']):item for item in graph['unresolved_transfers'] if item['target'] is None}
    inputs, outputs, table_sections = dict(graph['inputs']), [], []

    def read_table(address, count):
        end = address + count * 4
        sections = [section for section in binary.iter_sections()
                    if section['sh_addr'] <= address < end <= section['sh_addr'] + section['sh_size']
                    and section['sh_flags'] & 2 and not section['sh_flags'] & 5
                    and section['sh_type'] == 'SHT_PROGBITS']
        assert len(sections) == 1, 'table-not-file-backed-readonly-data'
        section = sections[0]
        data = section.data()[address-section['sh_addr']:end-section['sh_addr']]
        offset = address - manifest['code']['base']
        assert offset >= 0 and offset + len(data) <= len(code) and code[offset:offset+len(data)] == data
        table_sections.append(dict(address=address, bytes=len(data), section=section.name, flags=section['sh_flags']))
        return data

    used = set()
    for function in export['functions']:
        address = int(function['entry'], 16)
        assert address not in used and address in measured and address in symbols and address in entries
        used.add(address)
        original, symbol = measured[address], symbols[address]
        assert original['component'] == component and original['name'] == symbol.name == function['function_name']
        assert original['bytes'] == symbol['st_size'] == entries[address]['address_range']
        section = binary.get_section(symbol['st_shndx'])
        offset = address - section['sh_addr']
        data = section.data()[offset:offset+symbol['st_size']]
        code_offset = address - manifest['code']['base']
        assert code_offset >= 0 and code[code_offset:code_offset+len(data)] == data
        assert function['body_ranges'] == [dict(start=hex(address), inclusive_end=hex(address+len(data)-1),
            bytes=len(data), sha256=hashlib.sha256(data).hexdigest())], 'Ghidra-function-extent-drift'
        instructions = decode(data, address)
        assert [(int(row['address'],16),row['bytes_hex']) for row in function['instructions']] == [
            (item.address,bytes(item.bytes).hex()) for item in instructions], 'Ghidra-instruction-byte-drift'
        observed = inspect_function(data, address, read_table)
        metadata = {int(item['switch_address'],16):item for item in function['recovered_tables']}
        assert len(metadata) == len(function['recovered_tables']) == len(observed['tables'])
        table = cfa_table(entries[address])
        points = [pc for pc,_ in table]

        def cfa(pc):
            return table[bisect_right(points, pc)-1][1]

        for row in observed['tables']:
            assert (address,row['address']) in old_unknown, 'not-a-prior-unknown-site'
            assert cfa(row['address']) == old_unknown[(address,row['address'])]['caller_CFA']
            assert all(cfa(target) == cfa(row['address']) for target in row['table_targets']), 'table-CFA-mismatch'
            assert cfa(row['guard']) == cfa(row['default_target']), 'default-CFA-mismatch'
            row.update(metadata_matches(row,metadata[row['address']]), caller=address, caller_name=symbol.name,
                caller_CFA=cfa(row['address']), component=component, target_CFA_matches_dispatch=True)
            outputs.append(row)
    for path in (manifest_path,code_path,binary_path,graph_path,export_path,Path(__file__),
                 ROOT / 'tests/npu/test_npu_switch_targets_contract.py',
                 ROOT / 'tests/npu/switch_target_fixtures.json',
                 export_path.parent / 'scripts/ExportNpuSwitchTables.java',
                 export_path.parent / 'scripts/MapNpuRawCode.java',
                 export_path.parent / 'analysis.log',export_path.parent / 'script.log'):
        inputs[str(path.relative_to(ROOT))] = digest(path)
    verify_inputs(inputs)
    return dict(passed=True, functions_checked=len(used), qualified_internal_dispatches=len(outputs), tables=outputs,
        total_indexed_entries=sum(row['entry_count'] for row in outputs), table_sections=table_sections,
        CODE_identity_sha256=code_hash, prior_graph_sha256=digest(graph_path), prior_graph_rewritten=False,
        interfunction_edges_added=0, graph_extended=False, complete_call_chain_bound_proven=False,
        original_instructions_executed=False, hardware=False, inputs=inputs,
        limits=['Exact linked function entry and ordinary ABI calls/returns are assumptions.',
            'The table bytes must remain immutable;no IRQ,external mutation or interior-entry qualification follows.',
            'Only this narrow unsigned-bounded,absolute-word,C.LW/C.JR compiler pattern is accepted.',
            'Every loaded word/default is a same-function instruction start with matching CFI CFA.',
            'Ghidra metadata corroborates exact bytes/order;missing load-table provenance is supplied by ELF/CODE,not inferred as empty.',
            'These are internal control-flow sites,not new zero-frame callees or a whole permitted-path stack bound.'])


def main():
    parser = argparse.ArgumentParser()
    for name in ('pair', 'graph', 'export'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}',args.name)
    paths = [getattr(args,name).resolve() for name in ('pair','graph','export')]
    assert all(path.is_relative_to(ROOT / '.local') for path in paths)
    result = audit(*paths)
    output = ROOT / '.local/npu-switch-targets' / args.name / 'result.json'
    output.parent.mkdir(parents=True,exist_ok=False)
    with output.open('x') as stream:
        stream.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,functions=result['functions_checked'],
        internal_dispatches=result['qualified_internal_dispatches'],entries=result['total_indexed_entries'],
        graph_extended=False,sha256=digest(output))),flush=True)


if __name__ == '__main__':
    main()
