"""Artifact-specific computed code-entry proof,not a general NPU/physical bound."""
from collections import deque

from capstone.riscv import RISCV_OP_REG, RISCV_OP_IMM, RISCV_OP_MEM

from test_npu_direct_stack import decode, transfer
from test_npu_constant_targets import returned
from test_npu_original_body_stack import local_effect
from test_npu_reaching_targets import STORES, merge, reg
from test_npu_switch_targets import reachable

if not __debug__:
    raise RuntimeError('original-entry-proof-requires-assertions')


def r(name):
    return 'reg', name


def imm(value):
    return 'imm', value


def memory(base, offset):
    return 'mem', base, offset


def signature(instruction):
    operands = []
    for operand in instruction.operands:
        if operand.type == RISCV_OP_REG:
            operands.append(r(instruction.reg_name(operand.reg)))
        elif operand.type == RISCV_OP_IMM:
            operands.append(imm(operand.imm))
        else:
            assert operand.type == RISCV_OP_MEM, 'unsupported-operand'
            operands.append(memory(instruction.reg_name(operand.mem.base),operand.mem.disp))
    return instruction.mnemonic, tuple(operands)


def expected_program():
    # This version is deliberately limited to the reviewed RV32 fast-path layout.
    rows = [(0,'c.li',(r('t1'),imm(15))), (2,'c.mv',(r('a4'),r('a0'))),
        (4,'bgeu',(r('t1'),r('a2'),imm(38))), (8,'andi',(r('a5'),r('a4'),imm(15))),
        (12,'c.bnez',(r('a5'),imm(126))), (14,'c.bnez',(r('a1'),imm(106))),
        (16,'andi',(r('a3'),r('a2'),imm(-16))), (20,'c.andi',(r('a2'),imm(15))),
        (22,'c.add',(r('a3'),r('a4'))), (32,'c.addi',(r('a4'),imm(16))),
        (34,'bltu',(r('a4'),r('a3'),imm(-10))), (38,'c.bnez',(r('a2'),imm(4))),
        (40,'c.jr',(r('ra'),)), (42,'sub',(r('a3'),r('t1'),r('a2'))),
        (46,'c.slli',(r('a3'),imm(2))), (48,'auipc',(r('t0'),imm(0))),
        (52,'c.add',(r('a3'),r('t0'))), (54,'jalr',(r('zero'),r('a3'),imm(10))),
        (118,'c.jr',(r('ra'),)), (120,'andi',(r('a1'),r('a1'),imm(255))),
        (124,'slli',(r('a3'),r('a1'),imm(8))), (128,'c.or',(r('a1'),r('a3'))),
        (130,'slli',(r('a3'),r('a1'),imm(16))), (134,'c.or',(r('a1'),r('a3'))),
        (136,'c.j',(imm(-120),)), (138,'slli',(r('a3'),r('a5'),imm(2))),
        (142,'auipc',(r('t0'),imm(0))), (146,'c.add',(r('a3'),r('t0'))),
        (148,'c.mv',(r('t0'),r('ra'))), (150,'jalr',(r('ra'),r('a3'),imm(-88))),
        (154,'c.mv',(r('ra'),r('t0'))), (156,'c.addi',(r('a5'),imm(-16))),
        (158,'c.sub',(r('a4'),r('a5'))), (160,'c.add',(r('a2'),r('a5'))),
        (162,'bgeu',(r('t1'),r('a2'),imm(-120))), (166,'c.j',(imm(-152),))]
    rows += [(24+2*index,'c.sw',(r('a1'),imm(4*index),r('a4'))) for index in range(4)]
    rows += [(58+4*index,'sb',(r('a1'),memory('a4',14-index))) for index in range(15)]
    assert len(rows) == len({row[0] for row in rows}) == 55
    return {offset:(name,operands) for offset,name,operands in rows}


def bitvector_lemmas(address, timeout_ms=10000):
    import z3
    assert type(address) is int and address%2 == 0 and 0 <= address < address+168 <= 1<<32
    assert type(timeout_ms) is int and 0 < timeout_ms <= 10000, 'invalid-solver-timeout'
    value, length = z3.BitVecs('masked_value tail_length',32)
    mask = z3.BitVecVal(0xfffffffe,32)
    tail = (z3.BitVecVal(address+48,32)+((15-length)<<2)+10)&mask
    alignment = (z3.BitVecVal(address+142,32)+((value&15)<<2)-88)&mask
    targets = [address+58+4*index for index in range(16)]
    queries = [('low-mask-range',[],z3.UGT(value&15,15),'unsat'),
        ('tail-target-range',[z3.ULE(length,15)],z3.Not(z3.Or(*[tail == target for target in targets])),'unsat'),
        ('alignment-target-range',[(value&15) != 0],z3.Not(z3.Or(*[alignment == target for target in targets[:-1]])),'unsat'),
        ('weak-tail-bound-counterexample',[z3.ULE(length,16)],z3.Not(z3.Or(*[tail == target for target in targets])),'sat'),
        ('missing-nonzero-counterexample',[],z3.Not(z3.Or(*[alignment == target for target in targets[:-1]])),'sat')]
    results = []
    for name, assumptions, violation, expected in queries:
        solver = z3.Solver()
        solver.set(timeout=timeout_ms)
        solver.add(*assumptions,violation)
        result = str(solver.check())
        assert result == expected, (name,'solver-did-not-establish-required-result',result)
        results.append(dict(name=name,result=result,SMT2=solver.to_smt2(),
            counterexample=str(solver.model()) if result == 'sat' else None))
    return dict(version=z3.get_full_version(),timeout_ms=timeout_ms,queries=results)


def flow(instructions, address):
    positions = {instruction.address:instruction for instruction in instructions}
    targets = [address+58+4*index for index in range(16)]
    successors, edges = {}, {}
    for instruction in instructions:
        pc = instruction.address
        successors[pc] = set()
        if returned(instruction):
            edges[pc] = None
            continue
        if pc == address+54:
            edges[pc] = dict(kind='reviewed-code-tail',target=None)
            successors[pc].update(targets)
            continue
        if pc == address+150:
            # The independently checked SB suffix changes no GPR and returns via RA.
            edges[pc] = dict(kind='reviewed-code-summary',target=None)
            successors[pc].add(pc+instruction.size)
            continue
        edge = transfer(instruction,None)
        if edge is not None:
            assert edge['target'] in positions and 'call' not in edge['kind'], 'other-external-or-unknown-control'
            successors[pc].add(edge['target'])
        if edge is None or edge['kind'] == 'conditional-direct-transfer':
            following = pc+instruction.size
            assert following in positions, 'fallthrough-outside-carrier'
            successors[pc].add(following)
        edges[pc] = edge
    predecessors = {pc:set() for pc in positions}
    for source, targets_at_site in successors.items():
        for target in targets_at_site:
            predecessors[target].add(source)
    return positions,successors,edges,predecessors


def destination(instruction, edge, address):
    if instruction.address == address+150:
        return 1
    if returned(instruction) or edge is not None or instruction.mnemonic in STORES:
        return None
    result = reg(instruction,0)
    return result if result else None


def register_flow(positions, successors, edges, address):
    initial = [0]+[None]*31
    initial[2] = 0
    constants = {address:tuple(initial)}
    definitions = {address:tuple(frozenset({-1}) for _ in range(32))}
    pending,updates = deque([address]),0
    while pending:
        pc = pending.popleft()
        instruction = positions[pc]
        if pc == address+150:
            after = list(constants[pc])
            after[1] = pc+instruction.size
            after = tuple(after)
        else:
            after = local_effect(instruction,constants[pc],edges[pc])
        assert constants[pc][2] == after[2] == 0, 'SP-not-preserved'
        written = destination(instruction,edges[pc],address)
        outgoing = list(definitions[pc])
        if written is not None:
            outgoing[written] = frozenset({pc})
        outgoing = tuple(outgoing)
        for target in successors[pc]:
            state = after if target not in constants else merge(constants[target],after)
            last = outgoing if target not in definitions else tuple(
                left|right for left,right in zip(definitions[target],outgoing))
            if target not in constants or state != constants[target] or last != definitions[target]:
                constants[target],definitions[target] = state,last
                pending.append(target)
                updates += 1
                assert updates <= 66*len(positions), 'register-flow-convergence-bound'
    return constants,definitions,updates


def inspect_entry(data, address=0x840103aa):
    assert isinstance(data,bytes) and len(data) == 168, 'carrier-extent-drift'
    assert type(address) is int and address%2 == 0 and 0 <= address < address+len(data) <= 1<<32
    instructions, expected = decode(data,address), expected_program()
    assert {instruction.address-address for instruction in instructions} == set(expected), 'instruction-boundary-drift'
    for instruction in instructions:
        assert signature(instruction) == expected[instruction.address-address], (
            'instruction-contract-drift',instruction.address,instruction.mnemonic,instruction.op_str)
    positions,successors,edges,predecessors = flow(instructions,address)
    constants,definitions,updates = register_flow(positions,successors,edges,address)
    assert set(constants) == set(positions), 'unreviewed-carrier-instruction'
    tail_start,head_start = address+42,address+138
    tail_guards = {address+4,address+38,address+162}
    assert predecessors[tail_start] == tail_guards, 'unchecked-tail-entry'
    assert predecessors[head_start] == {address+12}, 'unchecked-alignment-entry'
    for offsets in ((42,46,48,52,54),(138,142,146,148,150)):
        for left,right in zip(offsets,offsets[1:]):
            assert predecessors[address+right] == {address+left}, 'computed-prefix-bypass'
    for pc in tail_guards:
        assert constants[pc][6] == 15, 'tail-limit-not-known'
    assert definitions[address+38][12] == frozenset({address+20}), 'tail-mask-not-reaching-definition'
    assert definitions[address+12][15] == frozenset({address+8}), 'alignment-mask-not-reaching-definition'
    tail_cut = {(pc,tail_start) for pc in tail_guards}
    assert not {address+offset for offset in (42,46,48,52,54)}.intersection(
        reachable(successors,address,removed_edges=tail_cut)), 'tail-safe-edges-do-not-dominate'
    assert not {address+offset for offset in (138,142,146,148,150)}.intersection(
        reachable(successors,address,(address+12,head_start))), 'alignment-safe-edge-does-not-dominate'
    assert definitions[address+148][1] == frozenset({-1}), 'incoming-RA-not-preserved-before-save'
    assert definitions[address+154][5] == frozenset({address+148}), 'saved-RA-not-preserved-by-suffix'
    assert definitions[address+154][1] == frozenset({address+150}), 'link-return-not-known'
    assert predecessors[address+154] == {address+150}, 'unreviewed-postcall-entry'
    protected = {0,2,3,4,8,9,*range(18,28)}
    assert all(destination(instruction,edges[instruction.address],address) not in protected
        for instruction in instructions), 'protected-register-write'
    assert {instruction.address for instruction in instructions
        if destination(instruction,edges[instruction.address],address) == 1} == {address+150,address+154}
    solver = bitvector_lemmas(address)
    return dict(passed=True,profile='rv32-newlib-fast-memset-code-entry-v1',entry=address,
        carrier_bytes=168,instructions=55,local_SP_bytes=0,reviewed_SB_suffix_local_SP_bytes=0,
        tail_site=address+54,tail_targets=[address+58+4*index for index in range(16)],
        linked_site=address+150,linked_targets=[address+58+4*index for index in range(15)],
        linked_return=address+154,RA_save_restore_and_suffix_return_checked=True,
        known_bound=15,reaching_definitions_and_safe_edges_checked=True,
        all_carrier_instructions_conservatively_reached=True,register_flow_updates=updates,
        solver=solver,caller_owned_accessible_nonwrapping_data_and_immutable_code_assumed=True,
        exact_entry_ordinary_return_and_no_async_faults_assumed=True,
        arbitrary_memory_fill_semantics_or_termination_proved=False,
        NPU_global_graph_whole_chain_IRQ_per_hart_or_physical_bound_proved=False,hardware=False)
