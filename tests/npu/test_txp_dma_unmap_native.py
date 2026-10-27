#!/usr/bin/env python3
"""Check actual MT7996 TXP unmap arguments; DMA and completion effects are models."""
import argparse
import gc
import io
import json
from pathlib import Path
import struct
import sys

from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE,UC_PROT_READ,UC_PROT_EXEC
from unicorn import arm64_const as arm

import test_rxwi_retirement_native as native

ROOT = native.ROOT
RADIO,CONNAC,DEV,STACK,OPS,DMA_DEV,END,BUFFER = (
    0x10000000,0x11000000,0x40000000,0x41000000,0x42000000,0x43000000,0x1f000000,0x44000000)
DEVICE = 0x45000000
TXWI_SIZE = 76
PRODUCER_SHA = '92c75156014d8e4a4ed795656bf29d47268ca6b64e5a40544a35acc181d4e31e'
FUNCTIONS = {'radio':('mt7996_txwi_free',),'connac':('mt76_connac_txp_skb_unmap',)}


class Module(native.Module):
    def __init__(self,path,base,label,expected):
        elf = ELFFile(io.BytesIO(path.read_bytes()))
        symbols = list(elf.get_section_by_name('.symtab').iter_symbols())
        names = list(FUNCTIONS[label])
        if label == 'radio':
            names += [symbol.name for symbol in symbols if symbol['st_info']['type'] == 'STT_FUNC' and
                symbol.name.startswith('mt7996_txp_skb_unmap')]
        super().__init__(path,base,names,expected)
        decoder = Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
        for start,size in self.functions.values():
            for row in decoder.disasm(self.text[start-base:start-base+size],start):
                if row.mnemonic != 'bl':
                    continue
                pc = row.address
                if pc in self.calls:
                    name = self.calls[pc]
                    if name in self.functions:
                        delta = self.functions[name][0]-pc
                        assert delta % 4 == 0 and -(1 << 27) <= delta < 1 << 27
                        struct.pack_into('<I',self.text,pc-base,0x94000000 | ((delta >> 2) & 0x3ffffff))
                    continue
                word = struct.unpack_from('<I',self.text,pc-base)[0]
                delta = (word & 0x3ffffff) << 2
                if delta & (1 << 27):
                    delta -= 1 << 28
                targets = [name for name,(address,_) in self.functions.items() if address == pc+delta]
                assert len(targets) == 1,('unresolved-local-BL',hex(pc),targets)
                self.calls[pc] = targets[0]


class Replay:
    def __init__(self,modules,case,mutation=None):
        self.modules,self.case = modules,case
        self.cpu = Uc(UC_ARCH_ARM64,UC_MODE_ARM)
        self.calls = {pc:name for module in modules.values() for pc,name in module.calls.items()}
        self.entries = dict.fromkeys([name for module in modules.values() for name in module.functions],0)
        self.instructions,self.cached,self.completed = 0,0,0
        self.unmaps = []
        self.nops = set()
        decoder = Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
        for label,module in modules.items():
            text = bytearray(module.text)
            if mutation in ('omit-FW-unmaps','omit-MAC-unmap','omit-cache-put'):
                target = 'mt76_put_txwi' if mutation == 'omit-cache-put' else 'dma_unmap_page_attrs'
                selected = mutation == 'omit-FW-unmaps' or label == 'radio'
                if selected:
                    for pc,name in module.calls.items():
                        if name == target:
                            self.nops.add(pc)
                            struct.pack_into('<I',text,pc-module.base,0xd503201f)
            if mutation == 'invert-TXP-format' and label == 'radio':
                rows = [row for start,size in module.functions.values()
                    for row in decoder.disasm(text[start-module.base:start-module.base+size],start)]
                pc, = [row.address for row in rows if row.mnemonic in ('tbz','tbnz') and ', #0x1b,' in row.op_str]
                word = struct.unpack_from('<I',text,pc-module.base)[0]
                struct.pack_into('<I',text,pc-module.base,word ^ 0x01000000)
            self.cpu.mem_map(module.base,0x100000)
            self.cpu.mem_write(module.base,bytes(text))
            self.cpu.mem_protect(module.base,0x100000,UC_PROT_READ | UC_PROT_EXEC)
        for address,size in ((DEV,0x10000),(STACK,0x10000),(OPS,0x1000),(BUFFER,0x1000),(END,0x1000)):
            self.cpu.mem_map(address,size)
        self.put64(DEV+0x858,OPS)
        self.cpu.mem_write(OPS+8,struct.pack('<H',TXWI_SIZE))
        self.put64(DEV+0x870,DEVICE)
        self.put64(DEV+0x878,DMA_DEV)
        self.put32(DEV+0x66ec,0x79900000)
        self.txwi = BUFFER+TXWI_SIZE
        self.skb = 0x46000000 if case['skb'] else 0
        self.put64(self.txwi+0x18,self.skb)
        self.expected = []
        if case['format'] == 'FW':
            self.cpu.mem_write(BUFFER+37,struct.pack('<H',0x4aa))
            self.cpu.mem_write(BUFFER+39,bytes([case['nbuf']]))
            for index in range(case['nbuf']):
                low = 0x23400000+index*4096
                self.put32(BUFFER+40+index*4,low)
                self.cpu.mem_write(BUFFER+64+index*2,struct.pack('<H',(case['high'] << 12) | case['length']))
                self.expected.append([DMA_DEV,low | (case['high'] << 32),case['length'],1,0])
        else:
            self.put32(BUFFER+28,1 << 27)
            self.cpu.mem_write(BUFFER+37,struct.pack('<H',0x4aa))
            self.put32(BUFFER+40,0x23400000)
            self.put32(BUFFER+44,(case['high'] << 12) | case['length'])
            self.expected.append([DMA_DEV,0x23400000 | (case['high'] << 32),case['length'],1,0])
        self.cpu.hook_add(UC_HOOK_CODE,self.code)

    def put64(self,address,value):
        self.cpu.mem_write(address,struct.pack('<Q',value))

    def put32(self,address,value):
        self.cpu.mem_write(address,struct.pack('<I',value))

    def returned(self,pc,value=0):
        for index in range(18):
            self.cpu.reg_write(native.REGS[index],value if index == 0 else 0xbad00000+index)
        self.cpu.reg_write(arm.UC_ARM64_REG_NZCV,0xa0000000)
        self.cpu.reg_write(arm.UC_ARM64_REG_X30,pc+4)
        self.cpu.reg_write(arm.UC_ARM64_REG_PC,pc+4)

    def code(self,cpu,pc,size,_data):
        assert size == 4 and any(module.contains(pc) for module in self.modules.values()),('unexpected-execution',hex(pc))
        self.instructions += 1
        for module in self.modules.values():
            for name,(start,_) in module.functions.items():
                if pc == start:
                    self.entries[name] += 1
        if pc in self.nops or pc not in self.calls:
            return
        name = self.calls[pc]
        args = tuple(cpu.reg_read(native.REGS[index]) for index in range(5))
        if name == 'mt76_connac_txp_skb_unmap':
            assert args[:2] == (DEV,self.txwi)
            cpu.reg_write(arm.UC_ARM64_REG_X30,pc+4)
            cpu.reg_write(arm.UC_ARM64_REG_PC,self.modules['connac'].functions[name][0])
            return
        if any(name in module.functions for module in self.modules.values()):
            return
        if name == 'dma_unmap_page_attrs':
            self.unmaps.append(list(args))
        elif name == '__mt76_tx_complete_skb':
            assert args[:4] == (DEV,0x4aa,self.skb,0) and self.skb
            self.completed += 1
        elif name == 'mt76_put_txwi':
            assert args[:2] == (DEV,self.txwi)
            assert bytes(cpu.mem_read(self.txwi+0x18,8)) == bytes(8),'SKB-cleared-before-cache-put'
            self.cached += 1
        else:
            raise AssertionError(('unmodeled-call',name))
        self.returned(pc)

    def run(self,contract):
        for index in range(5):
            self.cpu.reg_write(native.REGS[index],DEV if index == 0 else self.txwi if index == 1 else 0)
        self.cpu.reg_write(arm.UC_ARM64_REG_SP,STACK+0xf000)
        self.cpu.reg_write(arm.UC_ARM64_REG_X30,END)
        self.cpu.emu_start(self.modules['radio'].functions['mt7996_txwi_free'][0],END,
            timeout=5_000_000,count=1_000_000)
        assert self.cpu.reg_read(arm.UC_ARM64_REG_PC) == END,'bounded-unmap-return'
        assert self.cached == 1,'cache-put-count'
        assert self.completed == int(self.case['skb']),'modeled-SKB-completion-count'
        correct = self.unmaps == self.expected
        known_bug = self.case['format'] == 'FW' and self.case['nbuf'] > 0 and self.case['high'] > 0
        if contract == 'baseline-bug' and known_bug:
            malformed = [[dev,address & 0xffffffff,length | (self.case['high'] << 12),direction,attrs]
                for dev,address,length,direction,attrs in self.expected]
            assert self.unmaps == malformed and not correct,'native-unmap-arguments'
        else:
            assert correct,'native-unmap-arguments'
        return dict(case=self.case,instructions=self.instructions,native_entries=self.entries,
            expected_DMA_arguments=self.expected,observed_DMA_arguments=self.unmaps,
            DMA_arguments_correct=correct,known_baseline_bug_reproduced=known_bug and not correct,
            modeled_completion_calls=self.completed,modeled_cache_puts=self.cached)


def sha(path):
    return native.sha(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--producer',type=Path,required=True)
    parser.add_argument('--expected-producer-sha256',default=PRODUCER_SHA)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--contract',choices=('correct','baseline-bug'),default='correct')
    args = parser.parse_args()
    assert sha(args.producer) == args.expected_producer_sha256
    producer = json.loads(args.producer.read_bytes())
    assert producer['passed'] and producer['originals_unchanged']
    context_path = args.producer.parent/'context.json'
    context = json.loads(context_path.read_bytes())
    paths = dict(radio=args.producer.parent/'mt76/mt7996/mt7996e.ko',
        connac=args.producer.parent/'mt76/mt76-connac-lib.ko')
    expected = dict(radio=producer['inner']['modules']['mt7996/mt7996e.ko']['sha256'],
        connac=producer['inner']['modules']['mt76-connac-lib.ko']['sha256'])
    inputs = {str(path.resolve()):sha(path) for path in (args.producer,context_path,*paths.values(),Path(__file__))}
    for module in list(sys.modules.values()):
        filename = getattr(module,'__file__',None)
        if filename:
            path = Path(filename).resolve()
            if path.is_file() and any(path.is_relative_to(ROOT/directory) for directory in ('tests','tools')):
                inputs[str(path)] = sha(path)
    for name in ('mt7996/mac.c','mt7996/pci.c','mt76_connac_mac.c','mt76_connac.h','mt76_connac3_mac.h','mt76.h'):
        path = args.source/name
        assert sha(path) == context['mt76_sources'][name]['sha256'],('source-module-profile-mismatch',name)
        inputs[str(path.resolve())] = sha(path)
    modules = {label:Module(path,RADIO if label == 'radio' else CONNAC,label,expected[label])
        for label,path in paths.items()}
    cases = []
    for skb in (False,True):
        for nbuf in (0,1,2,6):
            for high in (0,1,15):
                for length in (1,64,4095):
                    cases.append(dict(format='FW',skb=skb,nbuf=nbuf,high=high,length=length))
        for high in (0,1,3):
            for length in (1,64,4095):
                cases.append(dict(format='MAC',skb=skb,nbuf=1,high=high,length=length))
    assert len(cases) == 90
    rows = []
    for case in cases:
        replay = Replay(modules,case)
        rows.append(replay.run(args.contract))
        del replay
        gc.collect()
    controls = []
    for mutation,case,assertion in (
        ('omit-FW-unmaps',dict(format='FW',skb=False,nbuf=1,high=0,length=64),'native-unmap-arguments'),
        ('omit-MAC-unmap',dict(format='MAC',skb=False,nbuf=1,high=1,length=64),'native-unmap-arguments'),
        ('omit-cache-put',dict(format='FW',skb=False,nbuf=1,high=0,length=64),'cache-put-count'),
        ('invert-TXP-format',dict(format='MAC',skb=False,nbuf=1,high=1,length=64),'native-unmap-arguments')):
        try:
            Replay(modules,case,mutation).run(args.contract)
        except AssertionError as error:
            assert str(error) == assertion,(mutation,str(error))
            controls.append(dict(mutation=mutation,failed_assertion=assertion,emulator_bytes_only=True))
        else:
            raise AssertionError(('mutation-survived',mutation))
    wrong = sum(not row['DMA_arguments_correct'] for row in rows)
    assert wrong == (36 if args.contract == 'baseline-bug' else 0)
    assert all(sha(Path(path)) == digest for path,digest in inputs.items()),'input-drift'
    args.output.mkdir(exist_ok=False)
    result = dict(passed=True,contract=args.contract,behavioral_contract_pass=wrong == 0,
        known_bug_reproduced=wrong == 36,cases=len(rows),incorrect_argument_cases=wrong,
        controls=controls,results=rows,inputs=inputs,producer_receipt_sha256=sha(args.producer),
        selected_functions=[name for module in modules.values() for name in module.functions],
        actual_functions=sorted({name for row in rows for name,count in row['native_entries'].items() if count}),
        DMA_completion_and_cache_effects_modeled=True,token_IDR_not_executed=True,
        no_compilation=True,module_loaded=False,physical_failure_proven=False,hardware=False)
    with (args.output/'result.json').open('x') as stream:
        json.dump(result,stream,indent=2)
        stream.write('\n')
    print(json.dumps(dict(passed=True,contract=args.contract,behavioral_contract_pass=wrong == 0,
        cases=len(rows),incorrect_argument_cases=wrong,controls=len(controls),
        result_sha256=sha(args.output/'result.json'))))


if __name__ == '__main__':
    main()
