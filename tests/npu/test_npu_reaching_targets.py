#!/usr/bin/env python3
"""Conservative constant register flow under explicit ordinary-ABI assumptions."""
import argparse
from collections import deque
import json
from pathlib import Path
import re

import capstone
from capstone.riscv import RISCV_OP_IMM, RISCV_OP_REG

from npu_stack_usage import ROOT,digest
from test_npu_constant_targets import returned,verify_inputs
from test_npu_direct_stack import decode,transfer
from test_npu_resolved_stack_subset import read_record

NAMES = ('zero','ra','sp','gp','tp','t0','t1','t2','s0','s1',
         *('a'+str(index) for index in range(8)),*('s'+str(index) for index in range(2,12)),
         *('t'+str(index) for index in range(3,7)))
REGISTERS = {name:index for index,name in enumerate(NAMES)}
REGISTERS['fp'] = 8
CALLER_SAVED = (1,5,6,7,*range(10,18),*range(28,32))
LOADS = {'lb','lbu','lh','lhu','lw','c.lw','c.lwsp'}
STORES = {'sb','sh','sw','c.sw','c.swsp'}
BINARY = {'add','sub','and','or','xor','sll','srl','sra','slt','sltu'}
COMPRESSED_BINARY = {'c.add','c.sub','c.and','c.or','c.xor'}
IMMEDIATE = {'addi','andi','ori','xori','slli','srli','srai','slti','sltiu'}
COMPRESSED_IMMEDIATE = {'c.addi','c.addi16sp','c.addi4spn','c.andi','c.slli','c.srli','c.srai'}


def reg(instruction,index):
    operand = instruction.operands[index]
    assert operand.type == RISCV_OP_REG
    return REGISTERS[instruction.reg_name(operand.reg)]


def signed(value):
    return value-(1<<32) if value & (1<<31) else value


def operation(name,left,right):
    if left is None or right is None:
        return None
    if name == 'add': value = left+right
    elif name == 'sub': value = left-right
    elif name == 'and': value = left & right
    elif name == 'or': value = left | right
    elif name == 'xor': value = left ^ right
    elif name == 'sll': value = left << (right & 31)
    elif name == 'srl': value = left >> (right & 31)
    elif name == 'sra': value = signed(left) >> (right & 31)
    elif name == 'slt': value = int(signed(left) < signed(right & 0xffffffff))
    elif name == 'sltu': value = int(left < (right & 0xffffffff))
    else: raise AssertionError(('unsupported-operation',name))
    return value & 0xffffffff


def effects(instruction,state,edge):
    result = list(state)
    name,operands = instruction.mnemonic,instruction.operands
    if edge is not None:
        if 'call' in edge['kind'] or name == 'c.jalr':
            for index in CALLER_SAVED:
                result[index] = None
            result[1] = (instruction.address+instruction.size)&0xffffffff
        result[0] = 0
        return tuple(result)
    if returned(instruction) or name in STORES or name in ('fence','fence.i','nop','c.nop'):
        return state
    assert operands and operands[0].type == RISCV_OP_REG, 'unsupported-register-effects'
    destination = reg(instruction,0)
    if name in ('lui','auipc'):
        assert len(operands) == 2 and operands[1].type == RISCV_OP_IMM
        value = (operands[1].imm << 12)+(instruction.address if name == 'auipc' else 0)
    elif name in ('li','c.li'):
        assert len(operands) == 2 and operands[1].type == RISCV_OP_IMM
        value = operands[1].imm
    elif name in ('mv','c.mv','not'):
        assert len(operands) == 2
        value = state[reg(instruction,1)]
        if name == 'not' and value is not None: value = ~value
    elif name in BINARY:
        assert len(operands) == 3
        value = operation(name,state[reg(instruction,1)],state[reg(instruction,2)])
    elif name in COMPRESSED_BINARY:
        assert len(operands) == 2
        value = operation(name[2:],state[destination],state[reg(instruction,1)])
    elif name in IMMEDIATE:
        assert len(operands) == 3 and operands[2].type == RISCV_OP_IMM
        op = dict(addi='add',andi='and',ori='or',xori='xor',slli='sll',srli='srl',srai='sra',slti='slt',sltiu='sltu')[name]
        value = operation(op,state[reg(instruction,1)],operands[2].imm)
    elif name in COMPRESSED_IMMEDIATE:
        assert operands[-1].type == RISCV_OP_IMM
        source = state[2] if name == 'c.addi4spn' else state[destination]
        op = dict(**{'c.addi':'add','c.addi16sp':'add','c.addi4spn':'add','c.andi':'and',
                     'c.slli':'sll','c.srli':'srl','c.srai':'sra'})[name]
        value = operation(op,source,operands[-1].imm)
    elif name in LOADS:
        value = None
    else:
        raise AssertionError(('unsupported-register-effects',name))
    result[destination] = None if value is None else value & 0xffffffff
    result[0] = 0
    return tuple(result)


def merge(left,right):
    assert len(left) == len(right) == 32 and left[0] == right[0] == 0
    return tuple(a if a == b else None for a,b in zip(left,right))


def inspect_function(data,address):
    instructions = decode(data,address)
    positions = {row.address:row for row in instructions}
    successors = {pc:set() for pc in positions}
    edges,unknown = {},{}
    control = {capstone.CS_GRP_JUMP,capstone.CS_GRP_CALL,capstone.CS_GRP_RET,capstone.CS_GRP_INT,capstone.CS_GRP_IRET}
    for index,item in enumerate(instructions):
        if returned(item):
            edges[item.address] = None
            continue
        edge = transfer(item,instructions[index-1] if index else None)
        if edge is not None and edge['target'] is None:
            assert item.mnemonic == 'c.jalr' and len(item.operands) == 1, 'unknown-noncall-register-flow'
            unknown[item.address] = reg(item,0)
            edge = dict(target=None,kind='ordinary-ABI-unresolved-call')
        if edge is None:
            assert not control.intersection(item.groups) and item.mnemonic not in (
                'ecall','ebreak','c.ebreak','uret','sret','mret','wfi','unimp','c.unimp'), 'unsupported-control-flow'
        elif 'call' not in edge['kind']:
            target = edge['target']
            if address <= target < address+len(data):
                assert target in positions, 'mid-instruction-target'
                successors[item.address].add(target)
            else:
                assert edge['kind'] != 'conditional-direct-transfer', 'external-conditional-target'
        falls = edge is None or 'call' in edge['kind'] or edge['kind'] == 'conditional-direct-transfer'
        if falls:
            following = item.address+item.size
            assert following in positions, 'fallthrough-outside-function'
            successors[item.address].add(following)
        edges[item.address] = edge
    assert unknown, 'no-register-calls'
    # Each register's flat lattice is unreachable -> one constant -> unknown.
    # Different constants or any unknown input join to unknown,never to a guess.
    states = {address:tuple([0]+[None]*31)}
    pending,updates = deque([address]),0
    while pending:
        pc = pending.popleft()
        after = effects(positions[pc],states[pc],edges[pc])
        for target in successors[pc]:
            value = after if target not in states else merge(states[target],after)
            if target not in states or states[target] != value:
                states[target] = value
                pending.append(target)
                updates += 1
                assert updates <= 66*len(instructions), 'constant-flow-convergence-bound'
    rows = []
    for pc,register in unknown.items():
        assert pc in states, 'unreachable-register-call'
        target = states[pc][register]
        assert target is not None, ('register-call-not-singleton',hex(pc))
        rows.append(dict(address=pc,target=target & ~1,raw_target=target,target_register=NAMES[register],
            control_flow_qualified=True,proof='reaching-register-singleton-under-ordinary-ABI',
            all_reachable_predecessors_joined=True))
    return dict(calls=rows,instruction_count=len(instructions),reachable_instruction_count=len(states),
        state_updates=updates,unknown_register_calls_remaining=0,
        ordinary_ABI_call_return_assumed=True,callee_saved_registers_assumed_preserved=True)


def audit(pair,graph_path,export_path):
    graph = read_record(graph_path)
    export = json.loads(export_path.read_bytes())
    assert export['passed'] is True and graph['complete_call_chain_bound_proven'] is False
    manifest_path = pair/'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    code_path = pair/'CODE.bin'
    code = code_path.read_bytes()
    assert digest(code_path) == graph['CODE_identity_sha256'] == export['mapped_CODE_sha256'] == manifest['code']['sha256']
    assert len(code) == manifest['code']['bytes']
    binary_path = (ROOT/manifest['symbol_files']['base']).resolve()
    assert binary_path.is_relative_to(pair) and digest(binary_path) == export['imported_ELF_sha256'] == manifest['components']['base']['sha256']
    functions = {row['address']:row for row in graph['functions']}
    unknown = {(row['caller'],row['address']):row for row in graph['unresolved_transfers'] if row['target'] is None}
    rows,used = [],set()
    for function in export['functions']:
        if function['function_name'] not in ('npu_emulation_open','npu_emulation_irq_dispatch'):
            continue
        address = int(function['entry'],16)
        assert address in functions and address not in used
        used.add(address)
        original = functions[address]
        assert original['component'] == 'base' and original['name'] == function['function_name']
        offset = address-manifest['code']['base']
        data = code[offset:offset+original['bytes']]
        instructions = decode(data,address)
        assert [(int(row['address'],16),row['bytes_hex']) for row in function['instructions']] == [
            (row.address,bytes(row.bytes).hex()) for row in instructions]
        result = inspect_function(data,address)
        for row in result['calls']:
            assert (address,row['address']) in unknown
            assert manifest['code']['base'] <= row['target'] < manifest['code']['base']+len(code)
            instruction = next(item for item in function['instructions'] if int(item['address'],16) == row['address'])
            assert instruction['flow_targets'] == [hex(row['target'])], 'Ghidra-singleton-reference-drift'
            row.update(caller=address,caller_name=original['name'],caller_CFA=unknown[(address,row['address'])]['caller_CFA'],
                target_frame_proved_here=False,target_already_in_graph=row['target'] in functions)
            rows.append(row)
    inputs = dict(graph['inputs'])
    for path in (manifest_path,code_path,binary_path,graph_path,export_path,Path(__file__),
        ROOT/'tests/npu/test_npu_reaching_targets_contract.py',ROOT/'tests/npu/reaching_target_fixtures.json',
        export_path.parent/'preparation.json',export_path.parent/'analysis.log',export_path.parent/'script.log',
        export_path.parent/'scripts/ExportNpuSwitchTables.java'):
        inputs[str(path.relative_to(ROOT))] = digest(path)
    verify_inputs(inputs)
    return dict(passed=True,functions_checked=len(used),singleton_calls=len(rows),calls=rows,
        CODE_identity_sha256=digest(code_path),prior_graph_sha256=digest(graph_path),graph_extended=False,
        prior_graph_rewritten=False,complete_call_chain_bound_proven=False,original_instructions_executed=False,
        hardware=False,full_setup=False,inputs=inputs,limits=[
            'All unknown register controls in selected functions must be ordinary C.JALR calls and resolve to singleton targets.',
            'Both branch paths and loop backedges join;conflicting or unknown values fail qualification.',
            'Exact function entry,ordinary ABI calls/returns and preserved callee-saved registers are explicit assumptions.',
            'Asynchronous IRQ or external register/CODE mutation is not qualified by this analysis.',
            'Loads are unknown;caller-saved registers are clobbered at every call;unsupported control/register effects fail closed.',
            'This identifies call targets only;original callee frames/IRQ/per-hart/physical bounds remain required.'])


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
    output = ROOT/'.local/npu-reaching-targets'/args.name/'result.json'
    output.parent.mkdir(parents=True,exist_ok=False)
    with output.open('x') as stream:
        stream.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,singleton_calls=result['singleton_calls'],graph_extended=False,sha256=digest(output))),flush=True)


if __name__ == '__main__':
    main()
