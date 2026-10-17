#!/usr/bin/env python3
"""Local SP paths in exact original bodies, never a complete callee-chain bound."""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import re

import capstone
from capstone.riscv import RISCV_OP_IMM, RISCV_OP_MEM, RISCV_OP_REG, RISCV_REG_RA, RISCV_REG_SP
import native_prefix_snapshot
from test_npu_constant_targets import returned
from test_npu_direct_stack import decode, transfer
from test_npu_reaching_targets import STORES, effects, merge, reg, signed

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stack_memory(instruction, delta):
    name, ops = instruction.mnemonic, instruction.operands
    if name not in ('lb', 'lbu', 'lh', 'lhu', 'lw', 'sb', 'sh', 'sw',
                    'c.lw', 'c.sw', 'c.lwsp', 'c.swsp'):
        return None
    if name.startswith('c.'):
        assert len(ops) == 3 and ops[1].type == RISCV_OP_IMM and ops[2].type == RISCV_OP_REG
        base, offset = ops[2].reg, ops[1].imm
    else:
        assert len(ops) == 2 and ops[1].type == RISCV_OP_MEM
        base, offset = ops[1].mem.base, ops[1].mem.disp
    if base != RISCV_REG_SP:
        return None
    width = 1 if name in ('lb', 'lbu', 'sb') else 2 if name in ('lh', 'lhu', 'sh') else 4
    start = delta + offset
    assert delta <= start and start + width <= 0 and start % width == 0, 'stack-access-outside-local-reservation'
    return dict(address=instruction.address, entry_SP_offset=start, bytes=width, instruction=name)


def local_effect(instruction, state, edge):
    ops = instruction.operands
    if edge is None and not returned(instruction) and instruction.mnemonic not in STORES and ops and ops[0].type == RISCV_OP_REG and ops[0].reg == RISCV_REG_SP:
        # SP=0 represents an entry-relative offset, never an absolute constant.
        assert instruction.mnemonic in ('addi', 'c.addi', 'c.addi16sp'), 'non-relative-SP-write'
        if instruction.mnemonic == 'addi':
            assert len(ops) == 3 and ops[1].type == RISCV_OP_REG and ops[1].reg == RISCV_REG_SP
        else:
            assert len(ops) == 2
        assert ops[-1].type == RISCV_OP_IMM
    if instruction.mnemonic in ('mul', 'mulh', 'mulhsu', 'mulhu', 'div', 'divu', 'rem', 'remu'):
        assert len(ops) == 3 and all(operand.type == RISCV_OP_REG for operand in ops)
        result = list(state)
        result[reg(instruction, 0)] = None
        result[0] = 0
        return tuple(result)
    if instruction.mnemonic in ('c.lui', 'neg', 'seqz', 'snez'):
        assert len(ops) == 2 and ops[0].type == RISCV_OP_REG
        assert ops[1].type == (RISCV_OP_IMM if instruction.mnemonic == 'c.lui' else RISCV_OP_REG)
        result = list(state)
        # These non-SP writes need no constant value for the local SP contract.
        result[reg(instruction, 0)] = None
        result[0] = 0
        return tuple(result)
    if instruction.mnemonic in ('csrr', 'csrrci', 'csrrsi'):
        assert instruction.operands and instruction.operands[0].type == RISCV_OP_REG
        destination = reg(instruction, 0)
        assert destination != 2, 'CSR-write-to-SP'
        result = list(state)
        result[destination] = None
        result[0] = 0
        return tuple(result)
    return effects(instruction, state, edge)


def local_body(data, address, max_frame=4096):
    assert address % 2 == 0 and 0 <= address < address + len(data) <= 0x100000000
    assert 0 < max_frame <= 0x100000 and max_frame % 16 == 0
    instructions = decode(data, address)
    positions = {i.address:i for i in instructions}
    edges, successors, tails = {}, {}, {}
    controls = {capstone.CS_GRP_JUMP, capstone.CS_GRP_CALL, capstone.CS_GRP_RET,
                capstone.CS_GRP_INT, capstone.CS_GRP_IRET}
    for instruction in instructions:
        pc, name = instruction.address, instruction.mnemonic
        successors[pc] = set()
        if returned(instruction):
            edges[pc] = None
            continue
        # No adjacent-AUIPC target inference: indirect calls remain opaque ABI calls.
        edge = transfer(instruction, None)
        if name == 'jal' and len(instruction.operands) == 2:
            assert instruction.operands[0].type == RISCV_OP_REG and instruction.operands[0].reg == RISCV_REG_RA, 'non-ABI-direct-link-register'
        if name in ('c.jalr', 'jalr'):
            if name == 'jalr':
                assert instruction.operands[0].type == RISCV_OP_REG and instruction.operands[0].reg == RISCV_REG_RA, 'unknown-noncall-register-flow'
            edge = dict(target=None, kind='ordinary-ABI-unresolved-call')
        elif edge is not None and edge['target'] is None:
            raise AssertionError('unknown-noncall-register-flow')
        if edge is None:
            assert not controls.intersection(instruction.groups) and name not in (
                'ecall', 'ebreak', 'c.ebreak', 'uret', 'sret', 'mret', 'wfi', 'unimp', 'c.unimp'), 'unsupported-control-flow'
        elif 'call' not in edge['kind']:
            target = edge['target']
            if address <= target < address + len(data):
                assert target in positions, 'mid-instruction-target'
                successors[pc].add(target)
            else:
                assert edge['kind'] == 'direct-tail', 'conditional-exit-outside-body'
                tails[pc] = target
        falls = edge is None or 'call' in edge['kind'] or edge['kind'] == 'conditional-direct-transfer'
        if falls:
            following = pc + instruction.size
            assert following in positions, 'fallthrough-outside-body'
            successors[pc].add(following)
        edges[pc] = edge
    initial = [0] + [None] * 31
    initial[2] = 0
    states, pending, updates = {address:tuple(initial)}, deque([address]), 0
    peak, returns, transfers, memory = 0, set(), {}, {}
    while pending:
        pc = pending.popleft()
        instruction, state = positions[pc], states[pc]
        assert state[2] is not None, 'unknown-SP'
        delta = signed(state[2])
        assert -max_frame <= delta <= 0 and delta % 16 == 0, 'SP-outside-local-bound'
        access = stack_memory(instruction, delta)
        if access is not None:
            memory[pc] = access
        after = local_effect(instruction, state, edges[pc])
        assert after[2] is not None, 'unknown-SP'
        new_delta = signed(after[2])
        assert -max_frame <= new_delta <= 0 and new_delta % 16 == 0, 'SP-outside-local-bound'
        peak = max(peak, -delta, -new_delta)
        if returned(instruction):
            assert delta == 0, 'unbalanced-return-SP'
            returns.add(pc)
        edge = edges[pc]
        if edge is not None and ('call' in edge['kind'] or pc in tails):
            if pc in tails:
                assert delta == 0, 'unbalanced-tail-SP'
            transfers[pc] = dict(address=pc, target=edge['target'], kind=edge['kind'],
                                 caller_CFA=-delta, child_frame_proved=False)
        for target in successors[pc]:
            if target in states:
                assert states[target][2] == after[2], 'inconsistent-SP-merge-or-loop'
                value = merge(states[target], after)
            else:
                value = after
            if target not in states or states[target] != value:
                states[target] = value
                pending.append(target)
                updates += 1
                assert updates <= 66 * len(instructions), 'local-state-convergence-bound'
    assert set(states) == set(positions), 'unreachable-or-unreviewed-body-instruction'
    assert returns or tails, 'no-reviewed-return-or-tail'
    return dict(entry=address, bytes=len(data), instructions=len(instructions),
        local_max_stack_bytes=peak, returns=sorted(returns),
        external_transfers=[transfers[pc] for pc in sorted(transfers)],
        stack_memory=[memory[pc] for pc in sorted(memory)],
        entry_SP_deltas={str(pc):signed(states[pc][2]) for pc in sorted(states)},
        all_body_instructions_reached_by_conservative_CFG=True,
        reviewed_returns_and_tail_SP_balanced=True, child_frames_proved=False,
        termination_proved=False, complete_call_chain_bound_proven=False)


def audit(original, paired, export_path):
    export = json.loads(export_path.read_bytes())
    assert export['passed'] and export['language'] == 'RISCV:LE:32:AndeStar_v5'
    code, pair = original.read_bytes(), paired.read_bytes()
    assert hashlib.sha256(pair).hexdigest() == export['mapped_CODE_sha256']
    results = []
    for function in export['functions']:
        assert len(function['body_ranges']) == 1, 'noncontiguous-body-not-supported'
        body = function['body_ranges'][0]
        start, stop = int(body['start'], 16), int(body['inclusive_end'], 16) + 1
        assert start == int(function['entry'], 16) and body['bytes'] == stop-start
        offset = start - 0x84000000
        assert 0 <= offset < offset + stop-start <= min(len(code), len(pair))
        data = code[offset:offset+stop-start]
        assert data == pair[offset:offset+stop-start] and hashlib.sha256(data).hexdigest() == body['sha256']
        decoded = decode(data, start)
        assert [(i.address, bytes(i.bytes).hex()) for i in decoded] == [
            (int(i['address'], 16), i['bytes_hex']) for i in function['instructions']]
        results.append(local_body(data, start))
    paths = (original, paired, export_path, Path(__file__))
    inputs = native_prefix_snapshot.source_inputs({str(p.relative_to(ROOT)):digest(p) for p in paths})
    assert all(digest(ROOT / name) == expected for name, expected in inputs.items())
    return dict(passed=True, functions=results, inputs=inputs, capstone_version=capstone.__version__,
        original_CODE_sha256=hashlib.sha256(code).hexdigest(),
        paired_CODE_sha256=hashlib.sha256(pair).hexdigest(),
        complete_call_chain_bound_proven=False, graph_extended=False,
        native_firmware_executed=False, hardware=False,
        limits=['Exact contiguous analyzed bodies/bytes only;analyst-seeded Ghidra names are not original symbols.',
                'Exact entry,ordinary calls/returns with restored SP and no asynchronous IRQ/external mutation are assumptions.',
                'Every external call/tail keeps an unproved child cost;local depth is not a whole function-chain bound.',
                'Non-SP-based memory aliases/escaped stack pointers,termination,register save correctness and physical placement are not proved.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--paired', type=Path, required=True)
    parser.add_argument('--export', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    paths = [p.resolve() for p in (args.original, args.paired, args.export)]
    assert all(p.is_relative_to(ROOT / '.local') for p in paths)
    result = audit(*paths)
    target = ROOT / '.local/npu-original-body-stack' / args.name / 'result.json'
    target.parent.mkdir(parents=True, exist_ok=False)
    with target.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, functions=len(result['functions']),
        local_frames=[f['local_max_stack_bytes'] for f in result['functions']],
        sha256=digest(target))), flush=True)


if __name__ == '__main__':
    main()
