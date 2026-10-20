#!/usr/bin/env python3
"""Finite original memset guests; no static computed-entry or physical claim."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import traceback

import unicorn
from unicorn import Uc, UcError, UC_ARCH_RISCV, UC_MODE_RISCV32
from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_PROT_READ, UC_PROT_EXEC
from unicorn import riscv_const as registers
from capstone.riscv import RISCV_OP_REG, RISCV_OP_MEM

import native_prefix_snapshot
from test_npu_direct_stack import decode
from test_npu_constant_targets import returned

ROOT = Path(__file__).resolve().parents[2]
CODE, DATA, END = 0x84000000, 0x95000000, 0x84200000
ENTRY, STOP = 0x840103aa, 0x84010452


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_code(pair, original, export_path):
    manifest_path, code_path = pair / 'manifest.json', pair / 'CODE.bin'
    manifest, export = [json.loads(path.read_bytes()) for path in (manifest_path, export_path)]
    code, blob = code_path.read_bytes(), original.read_bytes()
    assert len(code) == manifest['code']['bytes'] and digest(code_path) == manifest['code']['sha256']
    assert manifest['code']['base'] == CODE, 'CODE-base-drift'
    assert export['passed'] and export['language'] == 'RISCV:LE:32:AndeStar_v5'
    function = next(row for row in export['functions'] if int(row['entry'],16) == ENTRY)
    assert [(int(row['start'],16),row['bytes']) for row in function['body_ranges']] == [
        (ENTRY,58),(0x84010422,48)]
    observed = []
    for row in function['body_ranges']:
        address, size = int(row['start'],16), row['bytes']
        assert int(row['inclusive_end'],16)+1 == address+size
        data = code[address-CODE:address-CODE+size]
        assert len(data) == size and hashlib.sha256(data).hexdigest() == row['sha256']
        observed.extend((instruction.address,bytes(instruction.bytes).hex()) for instruction in decode(data,address))
    assert observed == [(int(row['address'],16),row['bytes_hex']) for row in function['instructions']]
    assert len(code) >= STOP-CODE and code[ENTRY-CODE:STOP-CODE] == blob[ENTRY-CODE:STOP-CODE]
    carrier, gap = decode(code[ENTRY-CODE:STOP-CODE],ENTRY), decode(code[0x103e4:0x10422],0x840103e4)
    assert len(carrier) == 55 and len(gap) == 16 and returned(gap[-1])
    for index, instruction in enumerate(gap[:-1]):
        ops = instruction.operands
        assert instruction.mnemonic == 'sb' and len(ops) == 2
        assert ops[0].type == RISCV_OP_REG and instruction.reg_name(ops[0].reg) == 'a1'
        assert ops[1].type == RISCV_OP_MEM and instruction.reg_name(ops[1].mem.base) == 'a4'
        assert ops[1].mem.disp == 14-index and instruction.address == 0x840103e4+4*index
    paths = [Path(__file__),manifest_path,code_path,original,export_path]
    inputs = native_prefix_snapshot.source_inputs({str(path.relative_to(ROOT)):digest(path) for path in paths})
    return code, inputs


def expected_effects(initial, destination, length, value):
    expected = list(initial)
    expected[6], expected[14] = 15, destination
    pointer, remaining, writes = destination, length, []

    def byte_tail(address, count):
        for index in range(count):
            writes.append((0x840103e4+4*(15-count+index),address+count-1-index,1,value&255))

    if length > 15:
        misalignment = destination&15
        expected[15] = misalignment
        if misalignment:
            head = 16-misalignment
            byte_tail(pointer,head)
            pointer += head
            remaining -= head
            expected[5], expected[15] = END, (-head)&0xffffffff
        if remaining > 15:
            word = (value&255)*0x01010101
            expected[11] = word
            bulk = remaining&~15
            remaining &= 15
            stop = pointer+bulk
            while pointer < stop:
                for index in range(4):
                    writes.append((0x840103c2+2*index,pointer+4*index,4,word))
                pointer += 16
            expected[13] = stop
            if remaining == 0:
                expected[12], expected[14] = 0, pointer
                return expected, writes
    byte_tail(pointer,remaining)
    expected[5] = 0x840103da
    expected[12], expected[13], expected[14] = remaining, 0x840103da+4*(15-remaining), pointer
    return expected, writes


class Fixture:
    def __init__(self, code):
        self.mapped = (len(code)+4095)&~4095
        self.cpu = Uc(UC_ARCH_RISCV,UC_MODE_RISCV32)
        self.cpu.mem_map(CODE,self.mapped)
        self.cpu.mem_write(CODE,code)
        self.cpu.mem_protect(CODE,self.mapped,UC_PROT_READ|UC_PROT_EXEC)
        self.cpu.mem_map(END,4096)
        self.cpu.mem_write(END,b'\x01\x00'*2048)
        self.cpu.mem_protect(END,4096,UC_PROT_READ|UC_PROT_EXEC)
        self.cpu.mem_map(DATA,16384)
        self.ids = [getattr(registers,'UC_RISCV_REG_X'+str(index)) for index in range(32)]
        self.protected_code = bytes(self.cpu.mem_read(CODE,self.mapped))
        self.protected_end = bytes(self.cpu.mem_read(END,4096))
        self.seed = bytes((index*37+29)&255 for index in range(16384))
        self.context = {}
        self.cpu.hook_add(UC_HOOK_MEM_READ,self.read)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE,self.write)

    def read(self, engine, access, address, width, value, unused):
        self.context['reads'].append((engine.reg_read(registers.UC_RISCV_REG_PC),address,width))

    def write(self, engine, access, address, width, value, unused):
        assert (self.context['destination'] <= address and
            address+width <= self.context['destination']+self.context['length']), 'write-outside-owned-destination'
        self.context['writes'].append((engine.reg_read(registers.UC_RISCV_REG_PC),address,width,value&((1<<(8*width))-1)))

    def run(self, alignment, length, value):
        destination = DATA+0x100+alignment
        assert 0 <= alignment < 16 and 0 <= length <= 1024 and 0 <= value < 1<<32
        self.context = dict(alignment=alignment,length=length,value=value,destination=destination,reads=[],writes=[])
        self.cpu.mem_write(DATA,self.seed)
        for number, register in enumerate(self.ids[1:],1):
            self.cpu.reg_write(register,0xa0000000+number)
        for register, value_in in ((registers.UC_RISCV_REG_RA,END),(registers.UC_RISCV_REG_SP,0x85001000),
            (registers.UC_RISCV_REG_A0,destination),(registers.UC_RISCV_REG_A1,value),
            (registers.UC_RISCV_REG_A2,length),(registers.UC_RISCV_REG_MSTATUS,0x1880)):
            self.cpu.reg_write(register,value_in)
        before = [self.cpu.reg_read(register) for register in self.ids]
        status = self.cpu.reg_read(registers.UC_RISCV_REG_MSTATUS)
        expected, writes = expected_effects(before,destination,length,value)
        memory = bytearray(self.seed)
        memory[destination-DATA:destination-DATA+length] = bytes([value&255])*length
        self.cpu.emu_start(ENTRY,END,count=50000,timeout=1000000)
        after = [self.cpu.reg_read(register) for register in self.ids]
        assert self.cpu.reg_read(registers.UC_RISCV_REG_PC) == END, 'nonterminal-PC'
        assert after == expected, ('register-drift',[(index,expected[index],after[index]) for index in range(32) if after[index] != expected[index]])
        assert self.cpu.reg_read(registers.UC_RISCV_REG_MSTATUS) == status, 'MSTATUS-drift'
        assert self.context['reads'] == [] and self.context['writes'] == writes, 'ordered-memory-effect-drift'
        assert bytes(self.cpu.mem_read(DATA,16384)) == memory, 'whole-data-memory-drift'
        assert bytes(self.cpu.mem_read(CODE,self.mapped)) == self.protected_code, 'CODE-drift'
        assert bytes(self.cpu.mem_read(END,4096)) == self.protected_end, 'return-sentinel-drift'
        return dict(alignment=alignment,length=length,value=value,destination=destination,PC=END,
            registers=after,MSTATUS=status,ordered_writes=self.context['writes'],reads=[],
            protected_memory_exact=True,observed_before_restoration=True,
            synthetic_owned_buffer_only=True,original_entry_to_return_executed=True)


def negative_controls(code):
    store = int.from_bytes(code[0x1041c:0x10420],'little')
    move = int.from_bytes(code[0x103ac:0x103ae],'little')
    ret = int.from_bytes(code[0x10420:0x10422],'little')
    specs = [('omit-byte-store',0x1041c,b'\x13\x00\x00\x00',(0,1,0x5a),'ordered-memory-effect-drift'),
        ('shift-byte-store',0x1041c,(store|(1<<7)).to_bytes(4,'little'),(0,1,0x5a),'write-outside-owned-destination'),
        ('clobber-s0',0x103ac,((move&~(31<<7))|(8<<7)).to_bytes(2,'little'),(0,0,0),'register-drift'),
        ('wrong-return-register',0x10420,((ret&~(31<<7))|(3<<7)).to_bytes(2,'little'),(0,0,0),'fetch')]
    results = []
    for name, offset, patch, case, reason in specs:
        changed = bytearray(code)
        changed[offset:offset+len(patch)] = patch
        fixture = Fixture(bytes(changed))
        try:
            fixture.run(*case)
        except (AssertionError,UcError) as error:
            message = str(error)
            assert reason in message.lower() if reason == 'fetch' else reason in message, (name,'unexpected-rejection',message)
            results.append(dict(name=name,rejected=True,reason=message,synthetic_mutated_guest_only=True,
                code_sha256=hashlib.sha256(changed).hexdigest(),original_code_not_modified=True))
        else:
            raise AssertionError(('mutant-survived',name))
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair',type=Path,required=True)
    parser.add_argument('--original',type=Path,required=True)
    parser.add_argument('--export',type=Path,required=True)
    parser.add_argument('--name',required=True)
    parser.add_argument('--smoke',action='store_true')
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}',args.name)
    paths = [path.resolve() for path in (args.pair,args.original,args.export)]
    assert all(path.is_relative_to(ROOT / '.local') for path in paths)
    code, inputs = load_code(*paths)
    output = ROOT / '.local/npu-original-memset' / args.name
    output.mkdir(parents=True,exist_ok=False)
    fixture, records = Fixture(code), []
    alignments = (0,1,15) if args.smoke else range(16)
    lengths = (0,1,15,16,17,31,32,33,64,65,1023,1024) if args.smoke else [*range(66),79,80,95,96,127,128,255,256,511,512,1023,1024]
    stage = 'nominal'
    try:
        for alignment in alignments:
            for length in lengths:
                for value in (0,0x5a,0x100,0x123456ff):
                    records.append(fixture.run(alignment,length,value))
        stage = 'negative-controls'
        controls = negative_controls(code)
    except Exception as error:
        preserved = output / 'failed-source.py'
        shutil.copy2(Path(__file__),preserved)
        preserved.chmod(stat.S_IMODE(preserved.stat().st_mode)&~0o222)
        target = output / 'failure.json'
        with target.open('x') as stream:
            stream.write(json.dumps(dict(passed=False,stage=stage,error=str(error),traceback=traceback.format_exc(),
                completed=len(records),records=records,nominal_fixture_state=fixture.context,inputs=inputs,
                exact_failed_source_sha256=digest(preserved),hardware=False),indent=2)+'\n')
        raise
    assert all(digest(ROOT / name) == expected for name,expected in inputs.items())
    target = output / 'result.json'
    record = dict(passed=True,scope='finite-whole-original-memset-guests-not-static-entry-or-physical-proof',
        executions=len(records),records=records,inputs=inputs,smoke=args.smoke,negative_controls=controls,
        unicorn_version=unicorn.__version__,original_code_carrier_bytes=168,recovered_Ghidra_body_bytes=106,
        additional_gap_instructions_decoded=16,instruction_limit_per_guest=50000,timeout_us_per_guest=1000000,
        native_constructor_budgets_changed=False,all32_GPR_PC_MSTATUS_and_ordered_effects_checked=True,
        caller_owned_nonwrapping_synthetic_destination_assumed=True,
        arbitrary_32bit_inputs_or_static_computed_entry_permissions_proved=False,global_graph_extended=False,
        whole_chain_IRQ_per_hart_or_physical_bound_proved=False,cold_constructor_or_device_or_client_test=False,hardware=False)
    with target.open('x') as stream:
        stream.write(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(passed=True,executions=len(records),negative_controls=len(controls),
        smoke=args.smoke,sha256=digest(target))),flush=True)


if __name__ == '__main__':
    main()
