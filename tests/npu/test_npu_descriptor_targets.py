#!/usr/bin/env python3
"""Jointly check descriptor tables and previously withheld literal calls."""
import argparse
from bisect import bisect_right
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import struct

import capstone
from capstone.riscv import RISCV_OP_IMM, RISCV_OP_REG
from elftools.dwarf.callframe import FDE

import npu_image
from npu_stack_usage import ROOT, digest
from test_npu_constant_targets import literal_sequence, returned, verify_inputs
from test_npu_direct_stack import candidates, cfa_table, decode, transfer
from test_npu_resolved_stack_subset import read_record, validate_functions
from test_npu_switch_targets import immediate, metadata_matches, reachable, registers, table_sequence


def setup_sequence(instructions,index):
    if index < 12:
        return None
    prefix = instructions[index-12:index+1]
    limit,setup,guard,zero1,zero2,shift,upper,addition,combine,load,constant,copy,jump = prefix
    if not (immediate(limit,'c.li',2) and immediate(setup,'addi',3)
            and setup.reg_name(setup.operands[1].reg) == 'zero' and immediate(guard,'bltu',3)
            and all(immediate(item,'c.li',2) for item in (zero1,zero2,constant))
            and immediate(shift,'slli',3) and shift.operands[2].imm == 2
            and immediate(upper,'lui',2) and immediate(addition,'addi',3)
            and combine.mnemonic == 'c.add' and registers(combine,2)
            and copy.mnemonic == 'c.mv' and registers(copy,2)
            and jump.mnemonic in ('jr','c.jr') and registers(jump,1) and not returned(jump)):
        return None
    operands = load.operands
    if not (load.mnemonic == 'c.lw' and len(operands) == 3
            and operands[0].type == operands[2].type == RISCV_OP_REG
            and operands[1].type == RISCV_OP_IMM and operands[1].imm == 0):
        return None
    bound,source = guard.operands[0].reg,guard.operands[1].reg
    pointer,base = shift.operands[0].reg,upper.operands[0].reg
    critical = {bound,source,pointer,base}
    if not (len(critical) == 4 and bound == limit.operands[0].reg and source == shift.operands[1].reg
            and base == addition.operands[0].reg == addition.operands[1].reg == combine.operands[0].reg == operands[2].reg
            and pointer == combine.operands[1].reg == operands[0].reg == jump.operands[0].reg
            and all(jump.reg_name(reg) not in ('zero','sp','ra') for reg in critical)):
        return None
    if any(item.operands[0].reg in critical or item.reg_name(item.operands[0].reg) in ('zero','sp','ra')
           for item in (setup,zero1,zero2)):
        return None
    if any(item.operands[0].reg == pointer or item.reg_name(item.operands[0].reg) in ('zero','sp','ra')
           for item in (constant,copy)):
        return None
    maximum = limit.operands[1].imm
    if not (0 <= maximum < 1024 and 0 <= upper.operands[1].imm < 1 << 20
            and -2048 <= addition.operands[2].imm <= 2047):
        return None
    table = ((upper.operands[1].imm << 12)+addition.operands[2].imm) & 0xffffffff
    if table % 4 or table+4*(maximum+1) > 1 << 32:
        return None
    if not all(left.address+left.size == right.address for left,right in zip(prefix,prefix[1:])):
        return None
    return dict(address=jump.address,definition_start=limit.address,guard=guard.address,
        guard_fallthrough=zero1.address,default_target=(guard.address+guard.operands[2].imm)&0xffffffff,
        table_address=table,entry_count=maximum+1,load_address=load.address,
        target_register=jump.reg_name(pointer),index_register=jump.reg_name(source),
        prefix_addresses=[item.address for item in prefix],
        prefix_hex=b''.join(bytes(item.bytes) for item in prefix).hex(),
        pattern='bounded-table-with-independent-setup-and-base-destination-add')


def inspect_function(data,address,read_table,known_literal_targets):
    instructions = decode(data,address)
    assert all(item.mnemonic not in ('unimp','c.unimp') for item in instructions), 'invalid-instruction'
    positions = {item.address:item for item in instructions}
    tables,literals = {},{}
    for index,item in enumerate(instructions):
        literal = literal_sequence(instructions,index)
        if literal is not None:
            assert literal['kind'] == 'literal-register-call', 'unsupported-literal-tail'
            assert literal['target'] in known_literal_targets and literal['target'] not in positions, 'unproved-literal-target'
            literals[item.address] = literal
        row = table_sequence(instructions,index) or setup_sequence(instructions,index)
        if row is None:
            continue
        raw = read_table(row['table_address'],row['entry_count'])
        assert isinstance(raw,bytes) and len(raw) == 4*row['entry_count'], 'table-length-drift'
        targets = list(struct.unpack('<'+'I'*row['entry_count'],raw))
        assert all(target in positions and target != address and target % 2 == 0 for target in targets), 'noninternal-table-target'
        assert row['default_target'] in positions and row['default_target'] != address, 'noninternal-default-target'
        assert not set(targets+[row['default_target']]).intersection(row['prefix_addresses']), 'table-target-enters-prefix'
        row.update(table_targets=targets,table_sha256=hashlib.sha256(raw).hexdigest())
        tables[item.address] = row
    assert tables, 'no-recognized-table'
    successors = {item.address:set() for item in instructions}
    control = {capstone.CS_GRP_JUMP,capstone.CS_GRP_CALL,capstone.CS_GRP_RET,capstone.CS_GRP_INT,capstone.CS_GRP_IRET}
    for index,item in enumerate(instructions):
        if returned(item):
            continue
        edge = transfer(item,instructions[index-1] if index else None)
        if edge is not None and edge['target'] is None:
            if item.address in tables:
                successors[item.address].update(tables[item.address]['table_targets'])
                continue
            assert item.address in literals, 'function-has-other-unresolved-register-flow'
            edge = literals[item.address]
        if edge is None:
            assert not control.intersection(item.groups) and item.mnemonic not in (
                'ecall','ebreak','c.ebreak','uret','sret','mret','wfi'), 'unsupported-control-flow'
        elif 'call' not in edge['kind']:
            target = edge['target']
            if address <= target < address+len(data):
                assert target in positions, 'mid-instruction-direct-target'
                successors[item.address].add(target)
            else:
                assert edge['kind'] != 'conditional-direct-transfer', 'external-conditional-target'
        falls = edge is None or 'call' in edge['kind'] or edge['kind'] == 'conditional-direct-transfer'
        if falls:
            following = item.address+item.size
            assert following in positions, 'fallthrough-outside-function'
            successors[item.address].add(following)
    predecessors = {pc:set() for pc in positions}
    for source,targets in successors.items():
        for target in targets:
            predecessors[target].add(source)
    reached = reachable(successors,address)
    for row in tables.values():
        assert row['definition_start'] in reached, 'unreachable-table-definition'
        assert row['guard_fallthrough'] != row['default_target'], 'guard-has-no-distinct-safe-edge'
        for left,right in zip(row['prefix_addresses'],row['prefix_addresses'][1:]):
            assert predecessors[right] == {left}, 'prefix-can-bypass-definition'
        without_safe = reachable(successors,address,(row['guard'],row['guard_fallthrough']))
        assert row['load_address'] not in without_safe and row['address'] not in without_safe, 'guard-safe-edge-does-not-dominate'
        row.update(control_flow_qualified=True,guard_safe_edge_dominates_load_and_jump=True,
                   same_function_only=True,interfunction_edge=False)
    for row in literals.values():
        assert row['definition_start'] in reached, 'unreachable-literal-definition'
        assert predecessors[row['addition_address']] == {row['definition_start']}, 'literal-addition-can-bypass-definition'
        assert predecessors[row['address']] == {row['addition_address']}, 'literal-call-can-bypass-addition'
        assert address not in (row['addition_address'],row['address']), 'function-entry-bypasses-literal-definition'
        row.update(control_flow_qualified=True,qualified_with_internal_tables=True)
    return dict(tables=list(tables.values()),literals=list(literals.values()),instruction_count=len(instructions),
        reachable_instructions=len(reached),other_unknown_register_flow=False)


def integrate(functions,tables,literals):
    from test_npu_internal_dispatch_subset import integrate as integrate_tables
    result = integrate_tables(functions,tables)
    combined = result['functions']
    used = set()
    for site in literals:
        assert site['control_flow_qualified'] is site['qualified_with_internal_tables'] is True
        assert site['kind'] == 'literal-register-call'
        caller,pc,target = site['caller'],site['address'],site['target']
        assert all(type(value) is int for value in (caller,pc,target)) and caller in combined and target in combined
        assert (caller,pc) not in used, 'duplicate-literal-call'
        used.add((caller,pc))
        function = combined[caller]
        assert site['caller_name'] == function['name'] and site['component'] == function['component']
        assert combined[target]['component'] == 'original-reviewed-body', 'unproved-original-frame'
        assert combined[target]['frame'] == site['target_frame'], 'target-frame-drift'
        matches = [edge for edge in function['transfers'] if edge['address'] == pc]
        assert len(matches) == 1 and matches[0]['target'] is None, 'not-a-prior-unknown-literal'
        edge = matches[0]
        assert edge['kind'].startswith('unresolved-register-')
        assert type(site['caller_CFA']) is int and site['caller_CFA'] == edge['caller_CFA'], 'literal-CFA-drift'
        edge.update(target=target,kind=site['kind'],prior_unknown_kind=edge['kind'])
    validate_functions(combined)
    chains,cycles = candidates(combined)
    result.update(qualified_literal_calls=len(used),cycles=cycles,
        resolved_transfers=sum(edge['target'] in combined for row in combined.values() for edge in row['transfers']),
        unresolved_transfers=[dict(caller=address,**edge) for address,row in combined.items()
            for edge in row['transfers'] if edge['target'] not in combined],
        ranked_subset_candidates=sorted((dict(root=address,**row) for address,row in chains.items() if row is not None),
            key=lambda row:(-row['bytes'],row['root'])))
    return result


def audit(pair,graph_path,export_path):
    graph = read_record(graph_path)
    export = json.loads(export_path.read_bytes())
    assert export['passed'] is True and graph['complete_call_chain_bound_proven'] is False
    manifest_path = pair/'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    code_path = pair/'CODE.bin'
    code = code_path.read_bytes()
    assert len(code) == manifest['code']['bytes'] and digest(code_path) == manifest['code']['sha256']
    assert graph['CODE_identity_sha256'] == export['mapped_CODE_sha256'] == digest(code_path)
    component = 'cold-descriptor'
    binary_path = (ROOT/manifest['symbol_files'][component]).resolve()
    assert binary_path.is_relative_to(pair) and digest(binary_path) == manifest['components'][component]['sha256']
    assert export['imported_ELF_sha256'] == digest(binary_path)
    binary = npu_image.elf(binary_path)
    symbols = {item['st_value']:item for item in binary.get_section_by_name('.symtab').iter_symbols()
        if item['st_info']['type'] == 'STT_FUNC' and item['st_size'] and isinstance(item['st_shndx'],int)}
    entries = {item['initial_location']:item for item in binary.get_dwarf_info().CFI_entries() if isinstance(item,FDE)}
    measured = {item['address']:item for item in graph['functions']}
    known = {0x840064b4:16,0x8400651c:16}
    for address,frame in known.items():
        assert measured[address]['component'] == 'original-reviewed-body' and measured[address]['frame'] == frame
    unknown = {(item['caller'],item['address']):item for item in graph['unresolved_transfers'] if item['target'] is None}
    tables,literals,sections = [],[],[]

    def read_table(address,count):
        end = address+count*4
        matching = [section for section in binary.iter_sections() if section['sh_addr'] <= address < end <= section['sh_addr']+section['sh_size']
            and section['sh_flags'] & 2 and not section['sh_flags'] & 5 and section['sh_type'] == 'SHT_PROGBITS']
        assert len(matching) == 1, 'table-not-file-backed-readonly-data'
        section = matching[0]
        data = section.data()[address-section['sh_addr']:end-section['sh_addr']]
        offset = address-manifest['code']['base']
        assert offset >= 0 and code[offset:offset+len(data)] == data
        sections.append(dict(address=address,bytes=len(data),section=section.name,flags=section['sh_flags']))
        return data

    used = set()
    for function in export['functions']:
        address = int(function['entry'],16)
        assert address not in used and address in measured and address in symbols and address in entries
        used.add(address)
        original,symbol = measured[address],symbols[address]
        assert original['component'] == component and original['name'] == symbol.name == function['function_name']
        assert original['bytes'] == symbol['st_size'] == entries[address]['address_range']
        section = binary.get_section(symbol['st_shndx'])
        offset = address-section['sh_addr']
        data = section.data()[offset:offset+symbol['st_size']]
        code_offset = address-manifest['code']['base']
        assert code_offset >= 0 and code[code_offset:code_offset+len(data)] == data
        assert function['body_ranges'] == [dict(start=hex(address),inclusive_end=hex(address+len(data)-1),
            bytes=len(data),sha256=hashlib.sha256(data).hexdigest())]
        instructions = decode(data,address)
        assert [(int(row['address'],16),row['bytes_hex']) for row in function['instructions']] == [
            (item.address,bytes(item.bytes).hex()) for item in instructions]
        observed = inspect_function(data,address,read_table,known)
        metadata = {int(item['switch_address'],16):item for item in function['recovered_tables']}
        assert len(metadata) == len(function['recovered_tables']) == len(observed['tables'])
        cfas = cfa_table(entries[address])
        points = [pc for pc,_ in cfas]

        def cfa(pc):
            return cfas[bisect_right(points,pc)-1][1]

        for row in observed['tables']+observed['literals']:
            assert (address,row['address']) in unknown, 'not-a-prior-unknown-site'
            assert cfa(row['address']) == unknown[(address,row['address'])]['caller_CFA']
            row.update(caller=address,caller_name=symbol.name,caller_CFA=cfa(row['address']),component=component)
        for row in observed['tables']:
            assert all(cfa(target) == cfa(row['address']) for target in row['table_targets']), 'table-CFA-mismatch'
            assert cfa(row['guard']) == cfa(row['default_target']), 'default-CFA-mismatch'
            row.update(metadata_matches(row,metadata[row['address']]),target_CFA_matches_dispatch=True)
            tables.append(row)
        for row in observed['literals']:
            row['target_frame'] = known[row['target']]
            literals.append(row)
    result = integrate(measured,tables,literals)
    assert set(result['functions']) == set(measured), 'new-callee-invented'
    assert result['resolved_transfers'] == graph['resolved_transfers']+len(literals)
    assert len(result['unresolved_transfers']) == len(graph['unresolved_transfers'])-len(literals)-len(tables)
    prior_internal = sum(len(row.get('internal_dispatches',[])) for row in measured.values())
    total_internal = sum(len(row.get('internal_dispatches',[])) for row in result['functions'].values())
    assert total_internal == prior_internal+len(tables)
    inputs = dict(graph['inputs'])
    for path in (manifest_path,code_path,binary_path,graph_path,export_path,Path(__file__),
        ROOT/'tests/npu/test_npu_descriptor_targets_contract.py',ROOT/'tests/npu/descriptor_target_fixtures.json',
        export_path.parent/'scripts/MapNpuRawCode.java',export_path.parent/'scripts/ExportNpuSwitchTables.java',
        export_path.parent/'preparation.json',export_path.parent/'analysis.log',export_path.parent/'script.log'):
        inputs[str(path.relative_to(ROOT))] = digest(path)
    verify_inputs(inputs)
    result['functions'] = list(result['functions'].values())
    result.update(passed=True,tables=tables,literals=literals,functions_checked=len(used),table_sections=sections,
        prior_internal_dispatches=prior_internal,total_internal_dispatches=total_internal,
        prior_graph_sha256=digest(graph_path),prior_graph_rewritten=False,CODE_identity_sha256=digest(code_path),
        remaining_register_unknown=sum(row['target'] is None for row in result['unresolved_transfers']),
        remaining_known_outside_subset=sum(row['target'] is not None for row in result['unresolved_transfers']),
        complete_call_chain_bound_proven=False,all_frames_CFI_proved=False,original_instructions_executed=False,
        current_main_native_qualified=False,full_setup=False,hardware=False,inputs=inputs,
        limits=['Joint control-flow analysis resolves same-function tables and adjacent fixed original-call sequences together.',
            'The two original targets already have exact-body16-byte frame proofs in the prior graph;no callee is invented.',
            'Definition predecessors,guard-safe-edge dominance,readonly table/CODE bytes,all target boundaries and CFA must match.',
            'Exact function entry,ordinary ABI,immutable tables,no IRQ/external mutation remain assumptions.',
            'This is a partial static view,not whole function/cold constructor/IRQ/per-hart/physical or client proof.'])
    return result


def main():
    parser = argparse.ArgumentParser()
    for name in ('pair','graph','export'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--name',required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}',args.name)
    paths = [getattr(args,name).resolve() for name in ('pair','graph','export')]
    assert all(path.is_relative_to(ROOT/'.local') for path in paths)
    result = audit(*paths)
    output = ROOT/'.local/npu-descriptor-targets'/args.name/'result.json'
    output.parent.mkdir(parents=True,exist_ok=False)
    with output.open('x') as stream:
        stream.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,tables=len(result['tables']),literal_calls=len(result['literals']),
        resolved=result['resolved_transfers'],unresolved=len(result['unresolved_transfers']),sha256=digest(output))),flush=True)


if __name__ == '__main__':
    main()
