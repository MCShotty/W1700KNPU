#!/usr/bin/env python3
"""Replay exact normal RV32 RRO objects against complete host journal bytes."""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_BLOCK, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r

import test_inode_rro_original as original
from emulation_layout import CODE, SRAM, SRAM_BYTES, map_sram
from test_firmware_memory_layout import STACK_TOPS
from test_rro_native import ROOT, SOURCE, sha, run

END = CODE + 0x200000
CALL_INSTRUCTIONS = 10000000
CALL_MICROSECONDS = 60000000


def layout(destination):
    fields = {
        'state_bytes':'sizeof(struct npu_rro_lifetime)', 'plan_bytes':'sizeof(struct npu_rro_plan)',
        'plan':'offsetof(struct npu_rro_lifetime,plan)', 'error':'offsetof(struct npu_rro_lifetime,error)',
        'last_ticket':'offsetof(struct npu_rro_lifetime,last_ticket)',
        'exposure':'offsetof(struct npu_rro_lifetime,exposure)',
        'publication':'offsetof(struct npu_rro_lifetime,publication)',
        'resets':'offsetof(struct npu_rro_lifetime,resets)',
        'publication_bytes':'sizeof(struct npu_rro_publication)', 'reset_bytes':'sizeof(struct npu_rro_reset)',
        'HELD':'NPU_RRO_HELD', 'PUBLICATION_FAILED':'NPU_RRO_PUBLICATION_FAILED',
        'RESET_FAILED':'NPU_RRO_NPU_RESET_FAILED', 'NPU_POSSIBLE':'NPU_RRO_RESET_NPU_POSSIBLE',
        'NPU_CONFIRMED':'NPU_RRO_RESET_NPU_CONFIRMED', 'RESET_COMPLETE':'NPU_RRO_RESET_COMPLETE',
    }
    source = destination / 'layout.c'
    formats = ','.join('\\"' + name + '\\":%zu' for name in fields)
    source.write_text('#include <stddef.h>\n#include <stdio.h>\n#include "rro-native.h"\nint main(void){'
        'printf("{' + formats + '}\\n",' + ','.join('(size_t)(' + value + ')' for value in fields.values()) + ');return 0;}\n')
    run([shutil.which('clang'),'-std=c11','-Wall','-Wextra','-Werror','-I',SOURCE,source,'-o',destination / 'layout'],
        destination / 'layout-build.log')
    return json.loads(run([destination / 'layout'],destination / 'layout.log').stdout)


class Machine:
    def __init__(self, program, sizes):
        self.cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        self.cpu.mem_map(CODE,0x201000)
        map_sram(self.cpu)
        self.cpu.mem_map(original.ALIAS,original.ALIAS_BYTES)
        self.cpu.mem_write(SRAM,b'\xa5' * SRAM_BYTES)
        self.cpu.mem_write(original.ALIAS,b'\xa5' * original.ALIAS_BYTES)
        self.symbols, self.text, self.writable = {}, [], []
        with program.open('rb') as stream:
            elf = ELFFile(stream)
            assert elf.elfclass == 32 and elf.little_endian and elf.header.e_machine == 'EM_RISCV'
            for segment in elf.iter_segments():
                if segment['p_type'] != 'PT_LOAD' or not segment['p_memsz']: continue
                address, count = segment['p_vaddr'],segment['p_memsz']
                assert CODE <= address and address + count <= END
                self.cpu.mem_write(address,segment.data() + bytes(count-segment['p_filesz']))
            for section in elf.iter_sections():
                if not section['sh_flags'] & 2 or not section['sh_size']: continue
                if section['sh_flags'] & 4: self.text.append((section['sh_addr'],section.data()))
                if section['sh_flags'] & 1: self.writable.append((section['sh_addr'],section['sh_size']))
            for symbol in elf.get_section_by_name('.symtab').iter_symbols():
                self.symbols[symbol.name] = (symbol['st_value'],symbol['st_size'])
        self.owner,self.owner_bytes = self.symbols['rro_emulation_state']
        self.plan,self.plan_bytes = self.symbols['rro_emulation_plan']
        assert self.owner_bytes == sizes['state_bytes'] and self.plan_bytes == sizes['plan_bytes']
        self.scope, self.seen, self.blocks, self.calls, self.max_stack = None,set(),0,0,0
        self.handles = [self.cpu.hook_add(UC_HOOK_BLOCK,self.block),self.cpu.hook_add(UC_HOOK_MEM_WRITE,self.write)]

    def block(self,cpu,address,size,unused):
        self.blocks += 1
        key = (address,size)
        if key in self.seen: return
        for base,data in self.text:
            if base <= address and address + size <= base + len(data):
                assert bytes(cpu.mem_read(address,size)) == data[address-base:address-base+size]
                self.seen.add(key)
                return
        raise AssertionError(('execution-outside-exact-RRO-ELF',hex(address),size))

    def write(self,cpu,access,address,size,value,unused):
        assert self.scope is not None,'write-outside-declared-call'
        if STACK_TOPS[0]-4096 <= address and address+size <= STACK_TOPS[0]:
            self.max_stack = max(self.max_stack,STACK_TOPS[0]-address)
            return
        if any(base <= address and address+size <= base+count for base,count in self.writable):
            if self.scope['kind'] != 0:
                assert address+size <= self.plan or address >= self.plan+self.plan_bytes,'immutable-plan-write'
            return
        span = set(range(address,address+size))
        assert span <= self.scope['allowed'],('unexpected-native-RRO-store',hex(address),size)
        self.scope['written'].update(span)
        self.scope['hash'].update(struct.pack('<IIIQ',cpu.reg_read(r.UC_RISCV_REG_PC),address,size,value & 0xffffffffffffffff))
        self.scope['stores'] += 1

    def call(self,name,*arguments,kind=-1,allowed=None):
        assert self.scope is None
        registers = [getattr(r,'UC_RISCV_REG_S'+str(i)) for i in range(12)] + [r.UC_RISCV_REG_GP,r.UC_RISCV_REG_TP]
        values = [0xa1000000+i*0x101 for i in range(12)] + [SRAM+0x13a8,0xb1000101]
        for register,value in zip(registers,values): self.cpu.reg_write(register,value)
        self.cpu.reg_write(r.UC_RISCV_REG_SP,STACK_TOPS[0]);self.cpu.reg_write(r.UC_RISCV_REG_RA,END)
        self.cpu.reg_write(r.UC_RISCV_REG_MSTATUS,8)
        for i in range(8): self.cpu.reg_write(getattr(r,'UC_RISCV_REG_A'+str(i)),arguments[i] if i<len(arguments) else 0)
        trace = dict(kind=kind,allowed=allowed or set(),written=set(),hash=hashlib.sha256(),stores=0)
        self.scope = trace
        try:
            self.cpu.emu_start(self.symbols[name][0],END,count=CALL_INSTRUCTIONS,timeout=CALL_MICROSECONDS)
            assert self.cpu.reg_read(r.UC_RISCV_REG_PC) == END,('native-call-not-terminal',name,hex(self.cpu.reg_read(r.UC_RISCV_REG_PC)))
            assert [self.cpu.reg_read(register) for register in registers] == values,'native-RRO-callee-saved'
            assert self.cpu.reg_read(r.UC_RISCV_REG_SP) == STACK_TOPS[0] and self.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) == 8
            for base,data in self.text: assert bytes(self.cpu.mem_read(base,len(data))) == data,'ELF-instruction-mutation'
            self.calls += 1
            return self.cpu.reg_read(r.UC_RISCV_REG_A0),trace
        finally:
            self.scope = None

    def state(self): return bytes(self.cpu.mem_read(self.owner,self.owner_bytes))

    def snapshot(self):
        return dict(writable=[(base,bytes(self.cpu.mem_read(base,count))) for base,count in self.writable],
            sram=bytes(self.cpu.mem_read(SRAM,SRAM_BYTES)),alias=bytes(self.cpu.mem_read(original.ALIAS,original.ALIAS_BYTES)),
            state=self.state())

    def restore(self,snapshot):
        assert self.scope is None
        for base,data in snapshot['writable']: self.cpu.mem_write(base,data)
        self.cpu.mem_write(SRAM,snapshot['sram']);self.cpu.mem_write(original.ALIAS,snapshot['alias'])

    def close(self):
        for handle in self.handles: self.cpu.hook_del(handle)
        self.handles = []; self.cpu = None


def expected_projection(machine,selector,argument,physical):
    return original.project(selector,argument,physical,bytes(machine.cpu.mem_read(SRAM,SRAM_BYTES)),
        bytes(machine.cpu.mem_read(original.ALIAS,original.ALIAS_BYTES)))


def replay(machine,stream,profile,sizes,rows):
    publication_prefix = reset_prefix = None
    expected_plan = None
    count = 1 + (137 if profile==2 else 139) + 129 + 1 + 1025*2
    for index in range(count):
        header = stream.read(16)
        assert len(header)==16
        kind,mode,ordinal,bytes_ = struct.unpack('<4I',header)
        expected = stream.read(bytes_)
        assert mode==profile and bytes_==sizes['state_bytes'] and len(expected)==bytes_
        allowed = set(); projection = None
        if kind==0:
            name,arguments = 'rro_emulation_init',(profile,)
        elif kind==1:
            name,arguments = 'rro_emulation_enroll',(ordinal,)
        elif kind==2:
            if ordinal==0: publication_prefix=machine.snapshot()
            physical = 0x88801000 if ordinal==128 else 0x88000000+ordinal*65536
            projection = expected_projection(machine,int(ordinal==128),0 if ordinal==128 else ordinal,physical)
            allowed = projection[2]; name,arguments = 'rro_emulation_publish',(ordinal,)
        elif kind==3:
            name,arguments = 'rro_emulation_hardware',()
        elif kind==4:
            start = original.SESSION if ordinal==1024 else original.ALIAS+(ordinal//8)*65536+(ordinal%8)*8192
            machine.cpu.mem_write(start,b'\x35'*8192)
            if ordinal==0: reset_prefix=machine.snapshot()
            projection = expected_projection(machine,3,ordinal,0)
            allowed = projection[2]; name,arguments = 'rro_emulation_reset',(ordinal,1)
        elif kind==5:
            name,arguments = 'rro_emulation_mcu',(ordinal,1)
        else: raise AssertionError(('unknown-state-record',kind))
        result,trace = machine.call(name,*arguments,kind=kind,allowed=allowed)
        assert result==0,(profile,kind,ordinal,result)
        assert machine.state()==expected,('whole-RV32-journal-versus-host',profile,kind,ordinal)
        if kind==0: expected_plan=expected[sizes['plan']:sizes['plan']+sizes['plan_bytes']]
        assert bytes(machine.cpu.mem_read(machine.plan,machine.plan_bytes))==expected_plan
        if projection:
            assert bytes(machine.cpu.mem_read(SRAM,SRAM_BYTES))==projection[0]
            assert bytes(machine.cpu.mem_read(original.ALIAS,original.ALIAS_BYTES))==projection[1]
            assert trace['written']==allowed,'native-RRO-complete-store-footprint'
        rows.write(json.dumps(dict(profile=profile,kind=kind,ordinal=ordinal,result=result,
            state_sha256=hashlib.sha256(expected).hexdigest(),stores=trace['stores'],write_sha256=trace['hash'].hexdigest()))+'\n')
        if (kind==2 and ordinal%16==0) or (kind==4 and ordinal%128==0):
            print(json.dumps(dict(profile=profile,kind=kind,ordinal=ordinal,verified_records=index+1)),flush=True)
    return publication_prefix,reset_prefix,count


def second_generation(machine,profile,sizes,rows):
    for session in range(1025):
        before=bytearray(machine.state());ticket=struct.unpack_from('<I',before,sizes['last_ticket'])[0]+1
        struct.pack_into('<I',before,sizes['last_ticket'],ticket)
        offset=sizes['resets']+session*sizes['reset_bytes']
        struct.pack_into('<6I',before,offset,2,2,ticket,sizes['NPU_CONFIRMED'],0,0)
        start=original.SESSION if session==1024 else original.ALIAS+(session//8)*65536+(session%8)*8192
        machine.cpu.mem_write(start,b'\x35'*8192)
        projection=expected_projection(machine,3,session,0)
        result,trace=machine.call('rro_emulation_reset',session,2,kind=4,allowed=projection[2])
        assert result==0 and machine.state()==before
        assert bytes(machine.cpu.mem_read(SRAM,SRAM_BYTES))==projection[0]
        assert bytes(machine.cpu.mem_read(original.ALIAS,original.ALIAS_BYTES))==projection[1] and trace['written']==projection[2]
        struct.pack_into('<6I',before,offset,3,2,ticket,sizes['RESET_COMPLETE'],0,0)
        result,_=machine.call('rro_emulation_mcu',session,2,kind=5)
        assert result==0 and machine.state()==before
        rows.write(json.dumps(dict(profile=profile,generation=2,session=session,state_sha256=hashlib.sha256(before).hexdigest()))+'\n')
        if session%128==0: print(json.dumps(dict(profile=profile,generation=2,session=session)),flush=True)


def fault_cases(machine,profile,sizes,pub,reset,rows):
    count=0
    for reset_mode,snapshot in ((False,pub),(True,reset)):
        write_points=(0,512,1023) if reset_mode else (0,1,16384,24576)
        read_points=(0,513,1025) if reset_mode else (0,8193,24577)
        cases=[(kind,index) for kind in (2,3) for index in write_points]
        cases += [(kind,index) for kind in (1,4) for index in read_points]
        for kind,index in cases:
            machine.restore(snapshot)
            result,_=machine.call('rro_emulation_fault',kind,index)
            assert result==0
            before=bytearray(snapshot['state']);ticket=struct.unpack_from('<I',before,sizes['last_ticket'])[0]+1
            struct.pack_into('<I',before,sizes['last_ticket'],ticket)
            struct.pack_into('<I',before,sizes['error'],sizes['RESET_FAILED'] if reset_mode else sizes['PUBLICATION_FAILED'])
            if reset_mode:
                struct.pack_into('<6I',before,sizes['resets'],1,1,ticket,sizes['NPU_POSSIBLE'],0xffffffff,0)
                selector,argument,physical=3,0,0
            else:
                slot=2 if profile==0 else 0
                struct.pack_into('<I',before,sizes['exposure']+slot*4,3)
                struct.pack_into('<2I',before,sizes['publication'],ticket,0xffffffff)
                selector,argument,physical=0,0,0x88000000
            projection=original.project(selector,argument,physical,snapshot['sram'],snapshot['alias'])
            result,trace=machine.call('rro_emulation_reset' if reset_mode else 'rro_emulation_publish',
                *((0,1) if reset_mode else (0,)),kind=4 if reset_mode else 2,allowed=projection[2])
            assert result==sizes['HELD'] and machine.state()==before,('native-error-journal',profile,reset_mode,kind,index,result)
            expected_sram=bytearray(snapshot['sram']);expected_alias=bytearray(snapshot['alias'])
            written=(index+int(kind==3)) if kind in (2,3) else ((1024 if reset_mode else 24577) if index else (0 if reset_mode else 1))
            if not reset_mode and written:
                struct.pack_into('<I',expected_sram,0x1fdc,original.ALIAS);written-=1
                clear=min(written,16384);expected_alias[:clear*4]=bytes(clear*4);written-=clear
            for i in range(written): expected_alias[i*8+7]=0xff
            assert bytes(machine.cpu.mem_read(SRAM,SRAM_BYTES))==expected_sram
            assert bytes(machine.cpu.mem_read(original.ALIAS,original.ALIAS_BYTES))==expected_alias
            after=machine.state()
            result,again=machine.call('rro_emulation_reset' if reset_mode else 'rro_emulation_publish',
                *((0,1) if reset_mode else (0,)),kind=4 if reset_mode else 2)
            assert result==sizes['HELD'] and machine.state()==after and not again['written']
            rows.write(json.dumps(dict(profile=profile,reset=reset_mode,failure_kind=kind,index=index,
                result=result,partial_state_retained=True,write_sha256=trace['hash'].hexdigest()))+'\n')
            count+=1
    return count


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--name',required=True)
    parser.add_argument('--host-receipt',type=Path,required=True)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--compile-only',action='store_true')
    args=parser.parse_args();assert re.fullmatch('[a-z][a-z0-9-]{0,39}',args.name)
    destination=ROOT / '.local/npu-rro-native-execution-20261023' / args.name
    destination.mkdir(parents=True,exist_ok=False)
    host_path=args.host_receipt.resolve(strict=True);archive=args.archive.resolve(strict=True)
    assert host_path.is_relative_to(ROOT / '.local/npu-rro-native-host-20261023') and archive.is_relative_to(ROOT / '.local')
    host=json.loads(host_path.read_bytes());assert host['passed'] and len(host['mutants'])==4
    inputs={str(host_path.relative_to(ROOT)):sha(host_path),**host['inputs'],**host['artifacts'],str(archive.relative_to(ROOT)):sha(archive)}
    dependencies=[Path(__file__),ROOT / 'tests/npu/rro-native-emulation.c',ROOT / 'tests/npu/rro-native-emulation.ld',
        ROOT / 'tests/npu/test_rro_native.py',ROOT / 'tests/npu/rro-native-fixture.h',Path(original.__file__),
        ROOT / 'tests/npu/emulation_layout.py',ROOT / 'tests/npu/test_firmware_memory_layout.py',original.GHIDRA,
        original.INPUT / 'en7581_MT7996_npu_rv32.bin',original.INPUT / 'en7581_MT7996_npu_data.bin']
    for path in dependencies: inputs[str(path.relative_to(ROOT))]=sha(path)
    for module in list(sys.modules.values()):
        path=getattr(module,'__file__',None)
        if path and Path(path).resolve().is_relative_to(ROOT / 'tests/npu'):
            path=Path(path).resolve();inputs[str(path.relative_to(ROOT))]=sha(path)
    assert sha(original.GHIDRA)==original.GHIDRA_SHA
    assert sha(dependencies[-2])==original.CODE_SHA and sha(dependencies[-1])==original.DATA_SHA
    assert all(sha(ROOT / name)==expected for name,expected in inputs.items()),'initial-source-drift'
    members=subprocess.check_output(['ar','t',str(archive)],text=True).splitlines();assert len(members)==24
    objects=[]
    for name in ('rro-lifetime.o','rro-native.o'):
        assert members.count(name)==1
        data=subprocess.check_output(['ar','p',str(archive),name]);path=destination / name
        path.write_bytes(data);assert data==(archive.parent / name).read_bytes();objects.append(path)
        inputs[str((archive.parent / name).relative_to(ROOT))]=sha(path)
    lld=Path(shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld')
    assert lld.is_file();inputs[str(lld.relative_to(ROOT))]=sha(lld)
    for path in dependencies[:3]: shutil.copyfile(path,destination / path.name)
    shutil.copyfile(__file__,destination / 'driver-at-run.py')
    shutil.copyfile(ROOT / 'tests/npu/rro-native-fixture.h',destination / 'rro-native-fixture.h')
    program=destination / 'rro-native.elf'
    command=[shutil.which('clang'),'--target=riscv32','-march=rv32imac_zicsr','-mabi=ilp32','-std=c11',
        '-Os','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-fno-stack-protector',
        '-msmall-data-limit=0','-mno-relax','-nostdlib','--ld-path='+str(lld),'-Wl,--no-relax',
        '-Wl,-T,'+str(destination / 'rro-native-emulation.ld'),'-I'+str(SOURCE),'-I'+str(destination),
        str(destination / 'rro-native-emulation.c'),*[str(path) for path in objects],'-o',str(program)]
    run(command,destination / 'build.log');sizes=layout(destination)
    if args.compile_only:
        with (destination / 'compile-preflight.json').open('x') as stream:
            json.dump(dict(compiled=True,full_execution=False,inputs=inputs,command=command,layout=sizes,
                program_sha256=sha(program),exact_normal_archive_objects=True),stream,indent=2)
        print(json.dumps(dict(compiled=True,full_execution=False,program_sha256=sha(program))),flush=True)
        return
    record_count=fault_count=call_count=block_count=0;seen=stack=0
    with (host_path.parent / 'states.bin').open('rb') as stream,(destination / 'observations.jsonl').open('x') as rows:
        for profile in range(3):
            machine=Machine(program,sizes)
            pub,reset,count=replay(machine,stream,profile,sizes,rows)
            record_count+=count
            second_generation(machine,profile,sizes,rows)
            fault_count+=fault_cases(machine,profile,sizes,pub,reset,rows)
            call_count+=machine.calls;block_count+=machine.blocks;seen+=len(machine.seen);stack=max(stack,machine.max_stack)
            machine.close();del machine,pub,reset;gc.collect()
        assert stream.read()==b''
    assert record_count==host['matrix']['state_records']==6958 and fault_count==78
    assert call_count==6958+1025*2*3+fault_count*3
    assert all(sha(ROOT / name)==expected for name,expected in inputs.items()),'final-source-drift'
    artifacts={str(path.relative_to(ROOT)):sha(path) for path in destination.rglob('*') if path.is_file()}
    result=dict(passed=True,inputs=inputs,artifacts=artifacts,command=command,layout=sizes,
        exact_normal_archive_objects=True,profiles=3,publication_calls=129*3,reset_calls=1025*2*3,
        whole_host_state_records_equal=record_count,native_IO_fault_cases=fault_count,total_fixture_calls=call_count,
        executed_basic_block_entries=block_count,distinct_block_views=seen,maximum_observed_stack_bytes=stack,
        ELF_instruction_bytes_verified=True,full_SRAM_and_alias_projections=True,callee_saved_and_MSTATUS_preserved=True,
        original_instruction_replay=False,current_native_transport_admitted=False,hardware=False,
        limits=['Actual extracted normal RV32 members execute,with direct freestanding function-entry fixtures and synthetic mappings.',
            'Every host journal byte matches for6958 first-generation states; second-generation states are independently projected.',
            'Stock byte projection was independently verified by prior original-instruction work,not freshly replayed here.',
            'All CPU/hart exclusion,backing/device references and MCU success remain models; no current raw pair or physical admission is inferred.',
            'Fault-prefix restoration is fixture-only copying of previously executed prefix memory,not production rollback or retirement.'])
    with (destination / 'result.json').open('x') as stream:
        json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(passed=True,profiles=3,host_state_records=record_count,fault_cases=fault_count,fixture_calls=call_count)),flush=True)


if __name__=='__main__': main()
