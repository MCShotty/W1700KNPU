#!/usr/bin/env python3
"""Original trap-prefix routing,not delivery,ECALL service or whole IRQ proof."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import traceback

import unicorn
from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_CODE
from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_PROT_EXEC, UC_PROT_READ
from unicorn import riscv_const as registers
import z3

import native_prefix_snapshot
from original_memset_entry import signature, r, imm
from test_npu_direct_stack import decode, transfer
from test_npu_constant_targets import returned
from test_npu_original_body_stack import local_body
from test_npu_switch_targets import reachable
from test_original_memset_entry import solver_inputs
from test_original_memset_native import ROOT, CODE, END, digest

DISPATCH, UNKNOWN, IRQ = 0x84004230,0x84004258,0x8400431a
VECTOR, CALL = 0x84006894,0x840068e0
STACK, STACK_TOP = 0x85000000,0x85001000


def route(cause):
    assert type(cause) is int and 0 <= cause < 1<<32
    return IRQ if cause == 0x8000000b else UNKNOWN


def routing_lemmas():
    cause = z3.BitVec('mcause',32)
    decoded = z3.And(cause < 0,z3.LShR(cause << 1,1) == 11)
    queries = [('only-machine-external-interrupt',z3.Xor(decoded,cause == 0x8000000b),'unsat'),
        ('no-synchronous-exception-uses-IRQ-branch',z3.And(z3.UGE(cause,0),z3.ULT(cause,1<<31),decoded),'unsat'),
        ('omitted-interrupt-bit-counterexample',z3.Xor(z3.LShR(cause << 1,1) == 11,cause == 0x8000000b),'sat')]
    records = []
    for name,violation,expected in queries:
        solver = z3.Solver()
        solver.set(timeout=10000)
        solver.add(violation)
        result = str(solver.check())
        assert result == expected, ('routing-solver-did-not-establish-result',name,result)
        records.append(dict(name=name,result=result,SMT2=solver.to_smt2(),
            counterexample=str(solver.model()) if result == 'sat' else None))
    return records


def prefix_contract(data):
    expected = [(0,'c.addi',(r('sp'),imm(-32))),
        *[(2+2*index,'c.swsp',(r(name),imm(offset),r('sp'))) for index,(name,offset) in enumerate(
            (('s0',24),('s1',20),('ra',28),('s2',16),('s3',12),('s4',8),('s5',4),('s6',0)))],
        (18,'c.mv',(r('s0'),r('a2'))),(20,'c.mv',(r('s1'),r('a1'))),
        (22,'c.mv',(r('a2'),r('a3'))),(24,'bgez',(r('a0'),imm(16))),
        (28,'slli',(r('a5'),r('a0'),imm(1))),(32,'c.srli',(r('a5'),imm(1))),
        (34,'c.li',(r('a4'),imm(11))),(36,'beq',(r('a5'),r('a4'),imm(198)))]
    instructions = decode(data,DISPATCH)
    assert len(data) == UNKNOWN-DISPATCH and len(instructions) == len(expected), 'trap-routing-prefix-drift'
    assert [(i.address-DISPATCH,*signature(i)) for i in instructions] == expected, 'trap-routing-prefix-drift'
    return instructions


def diagnostic_cfg(data):
    positions = {i.address:i for i in decode(data,DISPATCH)}
    successors,external = {},[]
    for pc,instruction in positions.items():
        successors[pc] = set()
        if returned(instruction):
            continue
        edge = transfer(instruction,None)
        if edge is not None:
            assert edge['target'] is not None, 'unreviewed-indirect-trap-flow'
            if 'call' in edge['kind']:
                assert edge['target'] in (0x840048f4,0x840030b2), 'unexpected-trap-child'
                external.append(dict(site=pc,target=edge['target'],child_contract_qualified=False))
            else:
                assert edge['target'] in positions, 'trap-branch-outside-body'
                successors[pc].add(edge['target'])
        if edge is None or 'call' in edge['kind'] or edge['kind'] == 'conditional-direct-transfer':
            assert pc+instruction.size in positions, 'trap-fallthrough-outside-body'
            successors[pc].add(pc+instruction.size)
    unknown_reached = reachable(successors,UNKNOWN)
    returns = {pc for pc,instruction in positions.items() if returned(instruction)}
    assert returns == {0x8400433a} and not returns.intersection(unknown_reached)
    assert IRQ not in unknown_reached and 0x84004318 in unknown_reached
    assert successors[0x84004318] == {0x84004318}
    assert all(row['target'] == 0x840048f4 for row in external if row['site'] in unknown_reached)
    return dict(diagnostic_reaches_no_in_body_return_or_IRQ_branch=True,self_loop=0x84004318,
        external_children=external,ordinary_child_return_edges_only_for_CFG=True,
        child_completion_or_memory_safety_or_termination_proved=False)


def bound_export(path,original,code):
    record = json.loads(path.read_bytes())
    assert record['passed'] and record['language'] == 'RISCV:LE:32:AndeStar_v5'
    results = {}
    for function in record['functions']:
        assert len(function['body_ranges']) == 1
        body = function['body_ranges'][0]
        address,size = int(body['start'],16),body['bytes']
        assert address == int(function['entry'],16) and int(body['inclusive_end'],16)+1 == address+size
        offset = address-CODE
        assert 0 <= offset < offset+size <= min(len(original),len(code))
        data = code[offset:offset+size]
        assert data == original[offset:offset+size] and hashlib.sha256(data).hexdigest() == body['sha256']
        assert [(i.address,bytes(i.bytes).hex()) for i in decode(data,address)] == [
            (int(i['address'],16),i['bytes_hex']) for i in function['instructions']]
        assert address not in results
        results[address] = data
    return results


class PrefixFixture:
    def __init__(self,code):
        self.cpu = Uc(UC_ARCH_RISCV,UC_MODE_RISCV32)
        self.mapped = (len(code)+4095)&~4095
        self.cpu.mem_map(CODE,self.mapped)
        self.cpu.mem_write(CODE,code)
        self.cpu.mem_protect(CODE,self.mapped,UC_PROT_READ|UC_PROT_EXEC)
        self.code = bytes(self.cpu.mem_read(CODE,self.mapped))
        self.cpu.mem_map(STACK,8192)
        self.seed = bytes((index*43+7)&255 for index in range(8192))
        self.ids = [getattr(registers,'UC_RISCV_REG_X'+str(index)) for index in range(32)]
        self.cpu.hook_add(UC_HOOK_CODE,self.stop)
        self.cpu.hook_add(UC_HOOK_MEM_READ,self.read)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE,self.write)

    def stop(self,cpu,pc,size,unused):
        if pc in self.stops:
            cpu.emu_stop()

    def read(self,cpu,access,address,width,value,unused):
        self.reads.append((cpu.reg_read(registers.UC_RISCV_REG_PC),address,width))

    def write(self,cpu,access,address,width,value,unused):
        assert width == 4 and self.low <= address < address+width <= STACK_TOP
        self.writes.append((cpu.reg_read(registers.UC_RISCV_REG_PC),address,width,value&0xffffffff))

    def run(self,cause,syscall_id,*,vector=False):
        assert type(cause) is int and 0 <= cause < 1<<32
        assert type(syscall_id) is int and 0 <= syscall_id < 1<<32
        assert type(vector) is bool
        self.cpu.mem_write(STACK,self.seed)
        for index,register in enumerate(self.ids[1:],1):
            self.cpu.reg_write(register,0x90000000+index)
        for register,value in ((registers.UC_RISCV_REG_SP,STACK_TOP),(registers.UC_RISCV_REG_RA,END),
            (registers.UC_RISCV_REG_A0,cause),(registers.UC_RISCV_REG_A1,0x840170a8),
            (registers.UC_RISCV_REG_A2,STACK_TOP+128),(registers.UC_RISCV_REG_A3,0x84017086),
            (registers.UC_RISCV_REG_A7,syscall_id),(registers.UC_RISCV_REG_MSTATUS,0x1880),
            (registers.UC_RISCV_REG_MCAUSE,cause),(registers.UC_RISCV_REG_MEPC,0x840170a8)):
            self.cpu.reg_write(register,value)
        before = [self.cpu.reg_read(register) for register in self.ids]
        status = self.cpu.reg_read(registers.UC_RISCV_REG_MSTATUS)
        expected = list(before)
        expected[2] -= 128 if vector else 32
        self.low,self.reads,self.writes = expected[2],[],[]
        if vector:
            start,self.stops,stop = VECTOR,{CALL},CALL
            expected[10:14] = [cause,0x840170a8,expected[2],before[1]]
            writes = [(VECTOR+2*index,expected[2]+4*index,4,expected[2] if index == 2 else before[index])
                      for index in range(1,32)]
        else:
            start,self.stops,stop = DISPATCH,{UNKNOWN,IRQ},route(cause)
            expected[8],expected[9],expected[12] = before[12],before[11],before[13]
            if cause&0x80000000:
                expected[14],expected[15] = 11,cause&0x7fffffff
            writes = [(DISPATCH+2+2*index,expected[2]+offset,4,before[register])
                for index,(register,offset) in enumerate(((8,24),(9,20),(1,28),(18,16),(19,12),(20,8),(21,4),(22,0)))]
        memory = bytearray(self.seed)
        for pc,address,width,value in writes:
            memory[address-STACK:address-STACK+width] = value.to_bytes(width,'little')
        self.cpu.emu_start(start,END,count=500,timeout=1000000)
        after = [self.cpu.reg_read(register) for register in self.ids]
        assert self.cpu.reg_read(registers.UC_RISCV_REG_PC) == stop, 'trap-prefix-route-drift'
        assert after == expected, 'trap-prefix-GPR-drift'
        assert self.cpu.reg_read(registers.UC_RISCV_REG_MSTATUS) == status, 'trap-prefix-MSTATUS-drift'
        assert self.writes == writes and self.reads == [], 'trap-prefix-memory-effect-drift'
        assert bytes(self.cpu.mem_read(STACK,8192)) == memory, 'trap-prefix-stack-memory-drift'
        assert bytes(self.cpu.mem_read(CODE,self.mapped)) == self.code, 'trap-prefix-CODE-drift'
        return dict(cause=cause,syscall_id=syscall_id,vector_prefix=vector,PC=stop,GPR=after,MSTATUS=status,
            ordered_writes=writes,no_data_reads=True,protected_bytes_exact=True,observed_before_reset=True,
            isolated_prefix_stopped_before_child=True,actual_ECALL_or_interrupt_delivery_executed=False)


def negative_controls(code):
    specifications = [('inverted-interrupt-test',0x4248,1<<12,11),
                      ('wrong-external-interrupt-number',0x4252,1<<2,0x8000000b)]
    records = []
    for name,offset,mask,cause in specifications:
        changed = bytearray(code)
        width = 4 if offset == 0x4248 else 2
        word = int.from_bytes(changed[offset:offset+width],'little')^mask
        changed[offset:offset+width] = word.to_bytes(width,'little')
        instruction = decode(bytes(changed[offset:offset+width]),CODE+offset)[0]
        expected = ('bltz',(r('a0'),imm(16))) if offset == 0x4248 else ('c.li',(r('a4'),imm(10)))
        assert signature(instruction) == expected, 'negative-control-encoding-drift'
        fixture = PrefixFixture(bytes(changed))
        try:
            fixture.run(cause,214)
        except AssertionError as error:
            assert str(error) == 'trap-prefix-route-drift', ('unexpected-mutated-route-rejection',name,str(error))
            records.append(dict(name=name,rejected=True,reason=str(error),
                changed_in_memory_guest_sha256=hashlib.sha256(changed).hexdigest(),
                separately_mutated_guest_not_original_coverage=True,original_file_not_modified=True))
        else:
            raise AssertionError(('mutated-route-survived',name))
    return records


def main():
    parser = argparse.ArgumentParser()
    for name in ('pair','original','bodies','dispatcher','solver-receipt'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--name',required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}',args.name)
    paths = [path.resolve() for path in (args.pair,args.original,args.bodies,args.dispatcher,args.solver_receipt)]
    assert all(path.is_relative_to(ROOT / '.local') for path in paths)
    manifest = json.loads((paths[0] / 'manifest.json').read_bytes())
    code_path = paths[0] / 'CODE.bin'
    assert manifest['code']['base'] == CODE and manifest['code']['sha256'] == digest(code_path)
    code,original = code_path.read_bytes(),paths[1].read_bytes()
    assert len(code) == manifest['code']['bytes']
    bodies = bound_export(paths[2],original,code)
    assert set(bodies) == {VECTOR,0x840170fa}
    dispatcher = bound_export(paths[3],original,code)
    assert set(dispatcher) == {DISPATCH} and len(dispatcher[DISPATCH]) == 268
    prefix_contract(dispatcher[DISPATCH][:UNKNOWN-DISPATCH])
    graph,lemmas = diagnostic_cfg(dispatcher[DISPATCH]),routing_lemmas()
    child = local_body(bodies[0x840170fa],0x840170fa)
    assert child['local_max_stack_bytes'] == 0 and not child['external_transfers']
    try:
        local_body(bodies[VECTOR],VECTOR)
    except AssertionError as error:
        assert str(error) == 'unsupported-control-flow'
    else:
        raise AssertionError('trap-veneer-must-not-be-admitted-as-ordinary-return')
    inputs = solver_inputs(paths[4])
    for path in (Path(__file__),paths[0] / 'manifest.json',code_path,*paths[1:4]):
        inputs[str(path.relative_to(ROOT))] = digest(path)
    inputs = native_prefix_snapshot.source_inputs(inputs)
    output = ROOT / '.local/npu-original-trap-routing' / args.name
    output.mkdir(parents=True,exist_ok=False)
    fixture = PrefixFixture(code)
    causes = [*range(14),15,0x7fffffff,0x80000000,0x80000003,0x80000007,0x8000000b,0x8000000c,0xffffffff]
    records,vectors,stage = [],[],'dispatcher-prefixes'
    try:
        for cause in causes:
            for syscall_id in (0,214,0xffffffff):
                records.append(fixture.run(cause,syscall_id))
        stage = 'vector-prefixes'
        for cause in (8,9,11,0x8000000b):
            vectors.append(fixture.run(cause,214,vector=True))
        stage = 'mutated-route-controls'
        controls = negative_controls(code)
        stage = 'input-recheck'
        assert all(digest(ROOT / name) == expected for name,expected in inputs.items())
    except Exception as error:
        source = output / 'failed-source.py'
        shutil.copy2(Path(__file__),source)
        source.chmod(stat.S_IMODE(source.stat().st_mode)&~0o222)
        with (output / 'failure.json').open('x') as stream:
            stream.write(json.dumps(dict(passed=False,stage=stage,error=str(error),traceback=traceback.format_exc(),
                dispatcher_prefix_guests=records,vector_prefix_guests=vectors,inputs=inputs,
                exact_failed_source_sha256=digest(source),hardware=False),indent=2)+'\n')
        raise
    record = dict(passed=True,scope='conditional-original-trap-branch-and-isolated-prefix-evidence-not-ECALL-service',
        routing_bitvector_lemmas=lemmas,diagnostic_CFG=graph,dispatcher_prefix_guests=records,vector_prefix_guests=vectors,
        separately_mutated_guest_controls=controls,
        error_child_conditional_local=child,strict_trap_veneer_denial_retained=True,
        whole_dispatcher_or_vector_or_child_call_executed=False,ECALL_service_or_return_contract_qualified=False,
        exact_entry_and_synthetic_accessible_stack_no_async_faults_assumed=True,
        actual_trap_delivery_privilege_delegation_or_all_hart_vector_installation_proved=False,
        NPU_global_graph_whole_chain_IRQ_per_hart_or_physical_bound_proved=False,
        instruction_limit_per_guest=500,timeout_us_per_guest=1000000,inputs=inputs,
        unicorn_version=unicorn.__version__,Z3_version=z3.get_full_version(),hardware=False)
    target = output / 'result.json'
    with target.open('x') as stream:
        stream.write(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(passed=True,dispatcher_prefixes=len(records),vector_prefixes=len(vectors),
                         negative_controls=len(controls),error_child_local=0,sha256=digest(target))),flush=True)


if __name__ == '__main__':
    main()
