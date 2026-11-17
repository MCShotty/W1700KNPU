"""Locate the cache->skb field in an AArch64 mt7996_txwi_free body."""
from collections import deque

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN, CS_GRP_CALL, CS_GRP_JUMP, CS_GRP_RET
from capstone.arm64 import ARM64_OP_IMM, ARM64_OP_MEM, ARM64_OP_REG


def skb_binding(code, address, calls):
    decoder = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    decoder.detail = True
    rows = list(decoder.disasm(code, address))
    assert rows and len(rows) * 4 == len(code), 'incomplete-txwi-body'

    def field(row, state):
        ops = row.operands
        if len(ops) != 2 or ops[0].type != ARM64_OP_REG or ops[1].type != ARM64_OP_MEM:
            return None
        mem = ops[1].mem
        base = row.reg_name(mem.base)
        if mem.index or row.writeback or mem.disp != 24 or state.get(base) != 'cache':
            return None
        return base, row.reg_name(ops[0].reg)

    # Track only the incoming cache pointer, its SKB field, and the null store.
    # At a control-flow join, retain facts established on every incoming path.
    by_pc = {r.address: r for r in rows}
    states = {address: {'x1': 'cache'}}
    queue = deque([address])
    while queue:
        pc = queue.popleft()
        row, state = by_pc[pc], states[pc]
        after = state.copy()
        for reg in row.regs_access()[1]:
            name = row.reg_name(reg)
            after.pop('x' + name[1:] if name.startswith('w') else name, None)
        ops = row.operands
        if row.mnemonic == 'mov' and len(ops) == 2 and all(op.type == ARM64_OP_REG for op in ops):
            dst, src = (row.reg_name(op.reg) for op in ops)
            if dst.startswith('x') and src in state:
                after[dst] = state[src]
        access = field(row, state)
        if access and row.mnemonic == 'ldr' and access[1].startswith('x'):
            after[access[1]] = 'skb'
        if row.mnemonic.startswith('st') and any(
                op.type == ARM64_OP_MEM and state.get(row.reg_name(op.mem.base)) == 'cache' for op in ops):
            # An unrecognized write through the cache cannot certify a null field.
            after.pop('cleared', None)
            if row.mnemonic == 'str' and access and access[1] == 'xzr':
                after['cleared'] = 'zero'
        after.pop('xzr', None)  # A discarded load never supplies a later argument.
        next_pcs = [pc + row.size]
        if row.group(CS_GRP_CALL):
            for i in (*range(19), 30):
                after.pop(f'x{i}', None)
            if calls.get(pc) == '__mt76_tx_complete_skb':
                after.pop('cleared', None)
        elif row.group(CS_GRP_RET):
            next_pcs = []
        elif row.group(CS_GRP_JUMP):
            assert ops[-1].type == ARM64_OP_IMM, 'unresolved-txwi-branch'
            next_pcs = [ops[-1].imm] + ([] if row.mnemonic == 'b' else next_pcs)
        for successor in next_pcs:
            assert successor in by_pc, 'txwi-branch-leaves-body'
            old = states.get(successor)
            merged = after if old is None else {k:v for k,v in old.items() if after.get(k) == v}
            if old != merged:
                states[successor] = merged
                queue.append(successor)

    complete = [pc for pc in states if calls.get(pc) == '__mt76_tx_complete_skb' and by_pc[pc].group(CS_GRP_CALL)]
    put = [pc for pc in states if calls.get(pc) == 'mt76_put_txwi' and by_pc[pc].group(CS_GRP_CALL)]
    assert complete and all(states[pc].get('x2') == 'skb' for pc in complete), 'completion-must-load-cache-skb'
    assert len(put) == 1 and states[put[0]].get('x1') == 'cache', 'wrong-returned-cache'
    assert states[put[0]].get('cleared') == 'zero', 'clear-must-precede-cache-return'
    clear = [(pc, args[0]) for pc, state in states.items() if by_pc[pc].mnemonic == 'str'
             and (args := field(by_pc[pc], state)) and args[1] == 'xzr']
    assert len(clear) == 1, 'missing-unique-cache-skb-clear'
    return dict(cache_register=clear[0][1], skb_offset=24, clear_pc=clear[0][0],
                complete_pcs=sorted(complete), put_pc=put[0])
