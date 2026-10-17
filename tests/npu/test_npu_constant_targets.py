#!/usr/bin/env python3
"""Identify guarded literal register targets without extending the stack graph."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

import capstone
from capstone.riscv import RISCV_OP_IMM, RISCV_OP_REG, RISCV_REG_ZERO

import npu_image
from npu_stack_usage import ROOT, digest
from test_npu_assembly_stack_usage import match_code
from test_npu_direct_stack import decode, transfer


def returned(instruction):
    return instruction.mnemonic == 'ret' or (
        instruction.mnemonic in ('jr', 'c.jr') and len(instruction.operands) == 1
        and instruction.operands[0].type == RISCV_OP_REG
        and instruction.reg_name(instruction.operands[0].reg) == 'ra')


def literal_sequence(instructions, index):
    if index < 2:
        return None
    upper, addition, jump = instructions[index-2:index+1]
    if jump.mnemonic not in ('jr', 'c.jr', 'c.jalr'):
        return None
    if upper.mnemonic != 'lui' or addition.mnemonic != 'addi':
        return None
    if upper.address + upper.size != addition.address or addition.address + addition.size != jump.address:
        return None
    first, second, final = upper.operands, addition.operands, jump.operands
    if not (len(first) == 2 and first[0].type == RISCV_OP_REG and first[1].type == RISCV_OP_IMM
            and len(second) == 3 and all(item.type == RISCV_OP_REG for item in second[:2])
            and second[2].type == RISCV_OP_IMM and len(final) == 1 and final[0].type == RISCV_OP_REG):
        return None
    if first[0].reg == RISCV_REG_ZERO or second[0].reg == RISCV_REG_ZERO:
        return None
    if second[1].reg != first[0].reg or final[0].reg != second[0].reg:
        return None
    if not 0 <= first[1].imm < 1 << 20 or not -2048 <= second[2].imm <= 2047:
        return None
    return dict(address=jump.address, definition_start=upper.address,
        addition_address=addition.address,
        target=(((first[1].imm << 12) + second[2].imm) & 0xffffffff) & ~1,
        kind='literal-register-call' if jump.mnemonic == 'c.jalr' else 'literal-register-tail',
        target_register=jump.reg_name(final[0].reg),
        sequence_hex=b''.join(bytes(item.bytes) for item in (upper, addition, jump)).hex())


def inspect_function(data, address):
    instructions = decode(data, address)
    assert all(item.mnemonic not in ('unimp','c.unimp') for item in instructions), 'invalid-instruction'
    positions = {item.address:index for index, item in enumerate(instructions)}
    assert len(positions) == len(instructions)
    sequences = {item.address:row for index,item in enumerate(instructions)
                 if (row := literal_sequence(instructions,index)) is not None}
    successors = {item.address:set() for item in instructions}
    unknown, invalid = [], []
    control_groups = {capstone.CS_GRP_JUMP, capstone.CS_GRP_CALL, capstone.CS_GRP_RET,
                      capstone.CS_GRP_INT, capstone.CS_GRP_IRET}
    for index, instruction in enumerate(instructions):
        if returned(instruction):
            continue
        edge = transfer(instruction,instructions[index-1] if index else None)
        if edge is not None and edge['target'] is None:
            if instruction.address in sequences:
                edge = sequences[instruction.address]
            else:
                unknown.append(instruction.address)
                continue
        if edge is None and (control_groups.intersection(instruction.groups) or
                instruction.mnemonic in ('ecall','ebreak','c.ebreak','uret','sret','mret','wfi')):
            invalid.append(dict(address=instruction.address,reason='unsupported-control-flow'))
            continue
        if edge is not None:
            target = edge['target']
            if address <= target < address + len(data):
                if target not in positions:
                    invalid.append(dict(address=instruction.address,reason='mid-instruction-target',target=target))
                else:
                    successors[instruction.address].add(target)
        falls_through = edge is None or 'call' in edge['kind'] or edge['kind'] == 'conditional-direct-transfer'
        following = instruction.address + instruction.size
        if falls_through and following in positions:
            successors[instruction.address].add(following)
    predecessors = {item.address:set() for item in instructions}
    for source, targets in successors.items():
        for target in targets:
            predecessors[target].add(source)
    reachable, pending = set(), [address]
    while pending:
        current = pending.pop()
        if current in reachable:
            continue
        reachable.add(current)
        pending.extend(successors[current] - reachable)
    rows = []
    for row in sequences.values():
        reasons = []
        if unknown:
            reasons.append('function-has-unresolved-register-flow')
        if invalid:
            reasons.append('function-has-unsupported-control-flow')
        if row['definition_start'] not in reachable:
            reasons.append('definition-not-reachable-from-function-entry')
        if predecessors[row['addition_address']] != {row['definition_start']}:
            reasons.append('addition-can-bypass-upper-definition')
        if predecessors[row['address']] != {row['addition_address']}:
            reasons.append('transfer-can-bypass-addition')
        if address in (row['addition_address'],row['address']):
            reasons.append('function-entry-bypasses-definition')
        rows.append(dict(row,control_flow_qualified=not reasons,rejection_reasons=reasons))
    return dict(sequences=rows,unresolved_register_sites=unknown,invalid_control_flow=invalid,
                reachable_instruction_count=len(reachable),instruction_count=len(instructions))


def verify_inputs(inputs):
    assert isinstance(inputs,dict) and inputs
    for name, expected in inputs.items():
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT) and path.is_file() and digest(path) == expected, name


def audit(pair, graph_path):
    graph = json.loads(graph_path.read_bytes())
    assert graph['passed'] is True and graph['complete_call_chain_bound_proven'] is False
    verify_inputs(graph['inputs'])
    manifest_path = pair / 'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    inputs = dict(graph['inputs'])
    for name in ('CODE','DATA'):
        path = pair / (name + '.bin')
        assert digest(path) == manifest[name.lower()]['sha256']
        assert path.stat().st_size == manifest[name.lower()]['bytes']
        assert inputs.get(str(path.relative_to(ROOT))) == digest(path)
    code = (pair / 'CODE.bin').read_bytes()
    symbols = {}
    names = {}
    for component,relative in manifest['symbol_files'].items():
        path = (ROOT / relative).resolve()
        assert path.is_relative_to(pair) and digest(path) == manifest['components'][component]['sha256']
        binary = npu_image.elf(path)
        for symbol in binary.get_section_by_name('.symtab').iter_symbols():
            if not isinstance(symbol['st_shndx'],int):
                continue
            if symbol.name:
                names.setdefault(symbol['st_value'],set()).add(symbol.name)
            if symbol['st_info']['type'] == 'STT_FUNC' and symbol['st_size']:
                section = binary.get_section(symbol['st_shndx'])
                offset = symbol['st_value'] - section['sh_addr']
                assert section['sh_flags'] & 4 and offset >= 0
                body = section.data()[offset:offset+symbol['st_size']]
                assert len(body) == symbol['st_size']
                key = (component,symbol.name,symbol['st_value'],symbol['st_size'])
                assert key not in symbols or symbols[key] == body
                symbols[key] = body
    by_address = {row['address']:row for row in graph['functions']}
    assert len(by_address) == graph['CFI_compiler_frames_matched']
    unknown = {(edge['caller'],edge['address']):edge for edge in graph['unresolved_transfers']
               if edge['target'] is None}
    assert len(unknown) == sum(edge['target'] is None for edge in graph['unresolved_transfers'])
    results, qualified = [], []
    for function in graph['functions']:
        address, size = function['address'],function['bytes']
        assert (function['component'],function['name'],address,size) in symbols
        offset = address - manifest['code']['base']
        assert offset >= 0 and offset + size <= len(code)
        data = symbols[(function['component'],function['name'],address,size)]
        match_code(data,address,code,manifest['code']['base'])
        observed = inspect_function(data,address)
        for row in observed['sequences']:
            key = (address,row['address'])
            assert key in unknown, ('sequence-not-an-original-unknown',key)
            target = row['target']
            row = dict(row,caller=address,caller_name=function['name'],component=function['component'],
                caller_CFA=unknown[key]['caller_CFA'],target_linked_names=sorted(names.get(target,())),
                target_is_measured_C_entry=target in by_address,
                target_is_within_CODE=manifest['code']['base'] <= target < manifest['code']['base'] + len(code))
            results.append(row)
            if row['control_flow_qualified']:
                assert row['target_is_within_CODE'], ('qualified-target-outside-CODE',row)
                qualified.append(row)
    for path in (manifest_path,graph_path,Path(__file__),
                 ROOT / 'tests/npu/test_npu_constant_targets_contract.py',
                 ROOT / 'tests/npu/constant_target_fixtures.json'):
        inputs[str(path.relative_to(ROOT))] = digest(path)
    verify_inputs(inputs)
    return dict(passed=True,component_count=len(manifest['components']),
        measured_C_functions=len(by_address),original_unknown_register_sites=len(unknown),
        literal_sequence_candidates=len(results),control_flow_qualified_literal_sites=len(qualified),
        qualified_target_counts=dict(Counter(hex(row['target']) for row in qualified)),
        remaining_unidentified_register_sites=len(unknown)-len(qualified),sequences=results,
        original_graph_unresolved_transfers=len(graph['unresolved_transfers']),
        original_graph_sha256=digest(graph_path),original_graph_rewritten=False,
        graph_extended=False,complete_call_chain_bound_proven=False,
        original_continuations_executed=False,hardware=False,
        capstone_version=capstone.__version__,inputs=inputs,
        limits=['This static supplement identifies literal targets,not permitted callbacks or complete callee frames.',
            'Qualification assumes entry at the exact linked function start and ordinary ABI call/return control flow.',
            'Unknown register flow or unsupported control flow anywhere in a function prevents local qualification.',
            'Direct targets into either later instruction reject a sequence;unreachable definitions are rejected.',
            'The original C-stack graph is neither rewritten nor extended;its unresolved callee/IRQ/per-hart/physical limits remain.',
            'No guest firmware or hardware is executed.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair',type=Path,required=True)
    parser.add_argument('--graph',type=Path,required=True)
    parser.add_argument('--name',required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}',args.name)
    pair, graph = args.pair.resolve(),args.graph.resolve()
    assert pair.is_relative_to(ROOT / '.local') and graph.is_relative_to(ROOT / '.local')
    result = audit(pair,graph)
    output = ROOT / '.local/npu-constant-targets' / args.name / 'result.json'
    output.parent.mkdir(parents=True,exist_ok=False)
    with output.open('x') as stream:
        stream.write(json.dumps(result,indent=2) + '\n')
    print(json.dumps(dict(passed=True,unknown_register_sites=result['original_unknown_register_sites'],
        qualified_literal_sites=result['control_flow_qualified_literal_sites'],
        target_counts=result['qualified_target_counts'],graph_extended=False,sha256=digest(output))),flush=True)


if __name__ == '__main__':
    main()
