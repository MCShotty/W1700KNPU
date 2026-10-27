#!/usr/bin/env python3
"""Execute retained Linux IDR/radix-tree bodies with the retained mt7996 token loop."""
import argparse
import gc
import hashlib
import io
import json
from pathlib import Path
import struct
import sys

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile
from elftools.elf.enums import ENUM_RELOC_TYPE_AARCH64 as RELOC
from unicorn import UC_PROT_READ, UC_PROT_WRITE, UC_PROT_EXEC
from unicorn import arm64_const as arm

import test_tx_token_native as base

ROOT, sha, REGS = base.ROOT, base.sha, base.REGS
NODES, SLAB, GUARD = 0x4a000000, 0x4b000000, 0x4c000000
KERNEL_BASES = dict(idr=0x15000000,radix=0x16000000)
NODE_SIZE, NODE_SLOTS, NODE_TAGS, NODE_RCU = 576, 40, 552, 24
ROOT_IDR_FREE = 0x2000000


class KernelObjects:
    def __init__(self, kernel):
        self.elfs, self.symbols, self.definitions, self.relocations = {}, {}, {}, {}
        self.paths = dict(idr=kernel/'lib/idr.o',radix=kernel/'lib/radix-tree.o')
        for label,path in self.paths.items():
            elf = ELFFile(io.BytesIO(path.read_bytes()))
            assert elf['e_machine'] == 'EM_AARCH64' and elf.little_endian
            symbols = list(elf.get_section_by_name('.symtab').iter_symbols())
            index = elf.get_section_index('.text')
            self.elfs[label], self.symbols[label] = elf, symbols
            self.relocations[label] = []
            for symbol in symbols:
                if symbol['st_info']['type'] == 'STT_FUNC' and symbol['st_shndx'] == index:
                    assert symbol.name not in self.definitions
                    self.definitions[symbol.name] = (label,symbol)
            for section in elf.iter_sections():
                if section['sh_type'] == 'SHT_RELA' and section['sh_info'] == index:
                    table = elf.get_section(section['sh_link'])
                    self.relocations[label] += [(relocation,table.get_symbol(relocation['r_info_sym']))
                                                for relocation in section.iter_relocations()]
        selected = {'idr_get_next','idr_get_next_ul','idr_destroy','radix_tree_node_rcu_free'}
        decoder = Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
        while True:
            before = set(selected)
            for name in before:
                label,symbol = self.definitions[name]
                start,size = symbol['st_value'],symbol['st_size']
                elf = self.elfs[label]
                index = elf.get_section_index('.text')
                code = elf.get_section(index).data()[start:start+size]
                for relocation,target in self.relocations[label]:
                    if not start <= relocation['r_offset'] < start+size:
                        continue
                    if target.name in self.definitions:
                        selected.add(target.name)
                    elif target['st_shndx'] == index:
                        address = target['st_value']+relocation['r_addend']
                        selected.update(candidate for candidate,(component,entry) in self.definitions.items()
                                        if component == label and entry['st_value'] == address)
                relocated = {relocation['r_offset'] for relocation,_ in self.relocations[label]}
                for row in decoder.disasm(code,start):
                    if row.mnemonic not in ('bl','b') or row.address in relocated:
                        continue
                    word = struct.unpack_from('<I',code,row.address-start)[0]
                    delta = (word & 0x3ffffff) << 2
                    if delta & (1 << 27):
                        delta -= 1 << 28
                    target = row.address+delta
                    if row.mnemonic == 'b' and start <= target < start+size:
                        continue
                    matches = {candidate for candidate,(component,entry) in self.definitions.items()
                               if component == label and entry['st_value'] == target}
                    assert len(matches) == 1,('unresolved-kernel-branch',name,hex(row.address),matches)
                    selected.update(matches)
            if selected == before:
                break
        self.selected = selected
        self.modules = {label:KernelModule(self,label) for label in self.paths}


class KernelModule:
    def __init__(self, objects, label):
        self.base, self.path = KERNEL_BASES[label], objects.paths[label]
        self.sha256 = sha(self.path)
        elf = objects.elfs[label]
        index = elf.get_section_index('.text')
        self.text = bytearray(elf.get_section(index).data())
        assert len(self.text) < 0x100000
        self.functions = {name:(self.base+symbol['st_value'],symbol['st_size'])
                          for name,(component,symbol) in objects.definitions.items()
                          if component == label and name in objects.selected}
        self.instructions, self.calls, self.tails, self.data = {}, {}, set(), {}
        self.relocated_data = []
        decoder = Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
        for name,(start,size) in self.functions.items():
            rows = list(decoder.disasm(self.text[start-self.base:start-self.base+size],start))
            assert size > 0 and len(rows)*4 == size
            self.instructions[name] = [(row.address,row.mnemonic,row.op_str) for row in rows]
        for relocation,target in objects.relocations[label]:
            offset,kind = relocation['r_offset'],relocation['r_info_type']
            pc = self.base+offset
            if not self.contains(pc):
                continue
            word = struct.unpack_from('<I',self.text,offset)[0]
            if kind in (RELOC['R_AARCH64_CALL26'],RELOC['R_AARCH64_JUMP26']):
                assert word & 0xfc000000 == (0x94000000 if kind == RELOC['R_AARCH64_CALL26'] else 0x14000000)
                self.calls[pc] = target.name
                if kind == RELOC['R_AARCH64_JUMP26']:
                    self.tails.add(pc)
                continue
            if target['st_shndx'] == index:
                address = self.base+target['st_value']+relocation['r_addend']
            elif target['st_shndx'] == 'SHN_UNDEF':
                assert target.name == '__stack_chk_guard',('undefined-kernel-data',target.name)
                address = GUARD+relocation['r_addend']
            else:
                target_index = target['st_shndx']
                assert isinstance(target_index,int)
                if target_index not in self.data:
                    section = elf.get_section(target_index)
                    assert not section['sh_flags'] & 4 and section['sh_size'] < 0x10000
                    payload = bytearray(section.data())
                    for symbol in objects.symbols[label]:
                        if symbol.name == 'radix_tree_node_cachep' and symbol['st_shndx'] == target_index:
                            struct.pack_into('<Q',payload,symbol['st_value'],SLAB)
                    address = 0x1a000000+list(KERNEL_BASES).index(label)*0x200000+len(self.data)*0x10000
                    self.data[target_index] = (address,bytes(payload))
                address = self.data[target_index][0]+target['st_value']+relocation['r_addend']
            if kind == RELOC['R_AARCH64_ADR_PREL_PG_HI21']:
                assert word & 0x9f000000 == 0x90000000
                pages = (address >> 12)-(pc >> 12)
                assert -(1 << 20) <= pages < 1 << 20
                immediate = pages & 0x1fffff
                word = (word & ~0x60ffffe0) | ((immediate & 3) << 29) | ((immediate >> 2) << 5)
            elif kind == RELOC['R_AARCH64_ADD_ABS_LO12_NC']:
                assert word & 0x7f000000 == 0x11000000 and not word & (1 << 22)
                word = (word & ~0x003ffc00) | ((address & 4095) << 10)
            else:
                kinds = {RELOC['R_AARCH64_LDST8_ABS_LO12_NC']:1,RELOC['R_AARCH64_LDST16_ABS_LO12_NC']:2,
                         RELOC['R_AARCH64_LDST32_ABS_LO12_NC']:4,RELOC['R_AARCH64_LDST64_ABS_LO12_NC']:8}
                assert kind in kinds,('kernel-data-relocation',kind)
                scale = kinds[kind]
                assert address % scale == 0 and word & 0x3b000000 == 0x39000000
                word = (word & ~0x003ffc00) | (((address & 4095)//scale) << 10)
            struct.pack_into('<I',self.text,offset,word)
            self.relocated_data.append(dict(pc=pc,target=target.name,address=address,kind=kind))
        for name,rows in self.instructions.items():
            start,size = self.functions[name]
            for pc,mnemonic,_ in rows:
                if mnemonic not in ('bl','b') or pc in self.calls:
                    continue
                delta = (struct.unpack_from('<I',self.text,pc-self.base)[0] & 0x3ffffff) << 2
                if delta & (1 << 27):
                    delta -= 1 << 28
                address = pc+delta
                if mnemonic == 'b' and start <= address < start+size:
                    continue
                target, = {candidate for candidate,(where,_) in self.functions.items() if where == address}
                self.calls[pc] = target
                if mnemonic == 'b':
                    self.tails.add(pc)
        required = {
            'idr_get_next': {('ldrsw','x2, [x19]'),('str','w1, [x19]')},
            'idr_get_next_ul': {('ldr','w21, [x0, #0x10]'),('add','x22, x0, #8')},
            'idr_destroy': {('ldr','x23, [x0, #8]'),('ldr','x0, [x0, #0x28]'),
                            ('str','xzr, [x22, #8]'),('orr','w0, w0, #0x2000000')},
            'radix_tree_next_chunk': {('and','x5, x2, #0x3f'),('ldr','x0, [x4, #0x28]')},
            'radix_tree_node_rcu_free': {('sub','x20, x0, #0x18'),('mov','x2, #0x200'),
                                       ('str','xzr, [x19, #0x220]')},
        }
        for name,operands in required.items():
            if name in self.instructions:
                actual = {(mnemonic,operand) for _,mnemonic,operand in self.instructions[name]}
                assert operands <= actual,('kernel-fixture-ABI',name,operands-actual)

    def contains(self,pc):
        return any(start <= pc < start+size for start,size in self.functions.values())


def link(modules):
    functions = {name:address for module in modules.values() for name,(address,_) in module.functions.items()}
    for module in modules.values():
        for pc,name in module.calls.items():
            if name not in functions:
                continue
            delta = functions[name]-pc
            assert delta % 4 == 0 and -(1 << 27) <= delta < 1 << 27
            opcode = 0x14000000 if pc in getattr(module,'tails',()) else 0x94000000
            struct.pack_into('<I',module.text,pc-module.base,opcode | ((delta >> 2) & 0x3ffffff))


def verify_linked_bodies(objects,path):
    wanted = objects.selected
    found = {}
    with path.open('rb') as stream:
        elf = ELFFile(stream)
        assert elf['e_machine'] == 'EM_AARCH64' and elf.little_endian
        for symbol in elf.get_section_by_name('.symtab').iter_symbols():
            if symbol.name not in wanted or symbol['st_info']['type'] != 'STT_FUNC':
                continue
            assert symbol.name not in found
            label,original = objects.definitions[symbol.name]
            assert symbol['st_size'] == original['st_size'],('linked-kernel-size',symbol.name)
            section = elf.get_section(symbol['st_shndx'])
            position = section['sh_offset']+symbol['st_value']-section['sh_addr']
            stream.seek(position)
            linked = bytearray(stream.read(symbol['st_size']))
            start,size = original['st_value'],original['st_size']
            source_elf = objects.elfs[label]
            raw = bytearray(source_elf.get_section(source_elf.get_section_index('.text')).data()[start:start+size])
            original_digest,linked_digest = hashlib.sha256(raw).hexdigest(),hashlib.sha256(linked).hexdigest()
            relocations = 0
            for relocation,_ in objects.relocations[label]:
                if not start <= relocation['r_offset'] < start+size:
                    continue
                offset,kind = relocation['r_offset']-start,relocation['r_info_type']
                if kind in (RELOC['R_AARCH64_CALL26'],RELOC['R_AARCH64_JUMP26']):
                    mask = 0x03ffffff
                elif kind == RELOC['R_AARCH64_ADR_PREL_PG_HI21']:
                    mask = 0x60ffffe0
                else:
                    assert kind in {RELOC['R_AARCH64_ADD_ABS_LO12_NC'],RELOC['R_AARCH64_LDST8_ABS_LO12_NC'],
                                    RELOC['R_AARCH64_LDST16_ABS_LO12_NC'],RELOC['R_AARCH64_LDST32_ABS_LO12_NC'],
                                    RELOC['R_AARCH64_LDST64_ABS_LO12_NC']},('linked-relocation',kind)
                    mask = 0x003ffc00
                for payload in (raw,linked):
                    word = struct.unpack_from('<I',payload,offset)[0]
                    struct.pack_into('<I',payload,offset,word & ~mask)
                relocations += 1
            assert raw == linked,('linked-kernel-code-mismatch',symbol.name)
            found[symbol.name] = dict(bytes=size,object_sha256=original_digest,linked_sha256=linked_digest,
                                     relocation_immediates_normalized=relocations,
                                     opcode_register_and_nonrelocated_bytes_identical=True)
        assert set(found) == wanted,('missing-linked-kernel-symbols',wanted-set(found))
    return found


class Replay(base.Replay):
    def __init__(self,modules,case,mutation=None):
        super().__init__(modules,case)
        self.cpu.mem_map(NODES,0x100000)
        self.cpu.mem_map(GUARD,0x1000)
        self.kernel_modules = [modules[name] for name in KERNEL_BASES]
        self.tails = {pc for module in self.kernel_modules for pc in module.tails}
        self.kernel_returns, self.pending_rcu, self.freed_nodes, self.nodes = {}, [], set(), set()
        self.callback_active = False
        self.idr = base.DEV+base.TOKEN_IDR
        self.put32(self.idr+4,4)
        self.put32(self.idr+16,0)
        self.put32(self.idr+20,0)
        if self.tokens:
            highest = max(self.tokens)
            shift = max(0,((highest.bit_length()-1)//6)*6)
            root = self.build_node(self.tokens,shift,0,0)
            self.put64(self.idr+8,root+2)
            self.put32(self.idr+4,4 | (ROOT_IDR_FREE if self.get64(root+NODE_TAGS) else 0))
        else:
            self.put32(self.idr+4,4 | ROOT_IDR_FREE)
        self.kernel_nops = set()
        if mutation:
            targets = {'omit-kernel-destroy':'idr_destroy','omit-RCU-enqueue':'call_rcu',
                       'omit-node-zero':'memset','omit-slab-free':'kmem_cache_free'}
            writes = {
                'omit-next-index-store':('idr_get_next',('str','w1, [x19]')),
                'omit-IDR-head-clear':('idr_destroy',('str','xzr, [x22, #8]')),
                'omit-IDR-free-mark':('idr_destroy',('orr','w0, w0, #0x2000000')),
            }
            assert mutation in targets or mutation in writes
            for module in modules.values():
                selected = {pc for pc,name in module.calls.items() if name == targets.get(mutation)
                            and (mutation != 'omit-node-zero' or module in self.kernel_modules)}
                if mutation in writes:
                    name,operand = writes[mutation]
                    selected.update(pc for pc,mnemonic,text in module.instructions.get(name,())
                                    if (mnemonic,text) == operand)
                for pc in selected:
                    self.kernel_nops.add(pc)
                    self.cpu.mem_protect(module.base,0x100000,UC_PROT_READ | UC_PROT_EXEC | UC_PROT_WRITE)
                    word = 0xd65f03c0 if pc in self.tails else 0xd503201f
                    self.cpu.mem_write(pc,struct.pack('<I',word))
                    self.cpu.mem_protect(module.base,0x100000,UC_PROT_READ | UC_PROT_EXEC)
            assert self.kernel_nops,('missing-kernel-mutation',mutation)

    def build_node(self,entries,shift,parent,offset):
        node = NODES+len(self.nodes)*NODE_SIZE
        self.nodes.add(node)
        groups = {}
        for token,value in entries.items():
            groups.setdefault((token >> shift) & 63,{})[token] = value
        self.cpu.mem_write(node,bytes([shift,offset,len(groups),0]))
        self.put64(node+8,parent)
        self.put64(node+16,self.idr)
        self.put64(node+NODE_RCU,node+NODE_RCU)
        self.put64(node+NODE_RCU+8,node+NODE_RCU)
        free = (1 << 64)-1
        for slot,values in groups.items():
            if shift:
                child = self.build_node(values,shift-6,node,slot)
                value = child+2
                if not self.get64(child+NODE_TAGS):
                    free &= ~(1 << slot)
            else:
                value, = values.values()
                free &= ~(1 << slot)
            self.put64(node+NODE_SLOTS+8*slot,value)
        self.put64(node+NODE_TAGS,free)
        return node

    def returned(self,pc,value=0):
        if pc not in self.tails:
            return super().returned(pc,value)
        target = self.cpu.reg_read(arm.UC_ARM64_REG_X30)
        for index in range(18):
            self.cpu.reg_write(REGS[index],value if index == 0 else 0xbad00000+index)
        self.cpu.reg_write(arm.UC_ARM64_REG_NZCV,0xa0000000)
        self.cpu.reg_write(arm.UC_ARM64_REG_PC,target)

    def code(self,cpu,pc,size,data):
        if pc in self.kernel_nops:
            self.instructions += 1
            return
        if pc in self.kernel_returns:
            name,args,expected = self.kernel_returns.pop(pc)
            if name == 'idr_get_next':
                token,txwi = expected
                assert cpu.reg_read(REGS[0]) == txwi,'kernel-IDR-next-value'
                assert self.get32(args[1]) == (args[2] if token is None else token),'kernel-IDR-next-index'
                self.queries.append([args[2],token])
            else:
                assert self.get64(self.idr+8) == 0,'kernel-IDR-head-cleared'
                assert self.get32(self.idr+4) == 4 | ROOT_IDR_FREE,'kernel-IDR-free-mark'
                self.destroyed += 1
                self.tokens.clear()
        for name in ('idr_get_next','idr_destroy'):
            if pc != self.functions[name]:
                continue
            args = tuple(cpu.reg_read(REGS[index]) for index in range(2))
            assert args[0] == self.idr,'kernel-IDR-owner'
            if name == 'idr_get_next':
                assert self.get32(base.DEV+base.TOKEN_LOCK) == 1
                completed = len(self.queries)
                remaining = struct.unpack('<H',cpu.mem_read(base.DEV+base.TOKEN_COUNT,2))[0]
                assert remaining == len(self.initial_tokens)-completed,'token-count-progress'
                assert self.cache() == list(reversed(list(self.initial_tokens.values())[:completed])),'TXWI-cache-membership'
                start = self.get32(args[1])
                token = next((token for token in sorted(self.tokens) if token >= start),None)
                expected = (token,0 if token is None else self.tokens[token])
                args += (start,)
            else:
                assert self.get32(base.DEV+base.TOKEN_LOCK) == 0
                expected = None
            target = cpu.reg_read(arm.UC_ARM64_REG_X30)
            assert target not in self.kernel_returns,'nonrecursive-IDR-outer-call'
            self.kernel_returns[target] = (name,args,expected)
        name = self.calls.get(pc)
        if any(module.contains(pc) for module in self.kernel_modules) and name not in self.functions:
            if name in ('call_rcu','kmem_cache_free','memset'):
                self.instructions += 1
                args = tuple(cpu.reg_read(REGS[index]) for index in range(3))
                self.events.append(dict(kind='modeled-kernel-service',name=name,arguments=list(args)))
                result = 0
                if name == 'call_rcu':
                    node = args[0]-NODE_RCU
                    assert node in self.nodes and node not in {head-NODE_RCU for head,_ in self.pending_rcu},'RCU-node-once'
                    assert args[1] == self.functions['radix_tree_node_rcu_free'],'compiled-RCU-callback'
                    self.pending_rcu.append(args[:2])
                elif name == 'memset':
                    assert NODES <= args[0] < NODES+0x100000 and args[1] == 0
                    assert args[2] in (512,24),'kernel-node-zero-length'
                    cpu.mem_write(args[0],bytes(args[2]))
                    result = args[0]
                else:
                    assert self.callback_active and args[0] == SLAB and args[1] in self.nodes,'modeled-slab-node'
                    node = args[1]
                    assert node not in self.freed_nodes,'slab-free-once'
                    assert bytes(cpu.mem_read(node+NODE_SLOTS,512+24)) == bytes(512+24),'kernel-node-zero-before-free'
                    assert self.get64(node+NODE_RCU) == self.get64(node+NODE_RCU+8) == node+NODE_RCU,'kernel-node-list-reinitialized'
                    self.freed_nodes.add(node)
                return self.returned(pc,result)
        return super().code(cpu,pc,size,data)

    def run(self):
        result = super().run()
        assert not self.kernel_returns,'all-IDR-returns-observed'
        assert {head-NODE_RCU for head,_ in self.pending_rcu} == self.nodes,'all-kernel-nodes-RCU-enqueued'
        assert not self.freed_nodes,'no-node-free-before-modeled-grace'
        self.callback_active = True
        for head,address in self.pending_rcu:
            self.cpu.reg_write(REGS[0],head)
            self.cpu.reg_write(arm.UC_ARM64_REG_SP,base.STACK+0xf000)
            self.cpu.reg_write(arm.UC_ARM64_REG_X30,base.END)
            self.cpu.emu_start(address,base.END,timeout=3_000_000,count=500000)
            assert self.cpu.reg_read(arm.UC_ARM64_REG_PC) == base.END,'bounded-RCU-callback-return'
        self.callback_active = False
        assert self.freed_nodes == self.nodes,'all-kernel-nodes-slab-returned'
        result.update(kernel_nodes=len(self.nodes),RCU_enqueued=len(self.pending_rcu),
                      modeled_slab_returns=len(self.freed_nodes),kernel_instructions_total=self.instructions)
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--producer',type=Path,required=True)
    parser.add_argument('--expected-producer-sha256',default=base.PRODUCER_SHA)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--mac-source',type=Path)
    parser.add_argument('--kernel',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--inspect-only',action='store_true')
    args = parser.parse_args()
    assert sha(args.producer) == args.expected_producer_sha256
    producer = json.loads(args.producer.read_bytes())
    assert producer['passed'] and producer['originals_unchanged']
    context_path = args.producer.parent/'context.json'
    context = json.loads(context_path.read_bytes())
    assert args.kernel.resolve() == Path(context['kernel']).resolve()
    inputs = {str(path.resolve()):sha(path) for path in (args.producer,context_path,Path(__file__))}
    for name,digest in context['kernel_configs'].items():
        assert sha(args.kernel/name) == digest
        inputs[str((args.kernel/name).resolve())] = digest
    manifest_path = args.producer.parent/'kernel-before.json'
    manifest = json.loads(manifest_path.read_bytes())
    inputs[str(manifest_path.resolve())] = sha(manifest_path)
    kernel_files = ('vmlinux','lib/idr.o','lib/radix-tree.o','lib/idr.c','lib/radix-tree.c',
                    'include/linux/idr.h','include/linux/radix-tree.h','include/linux/xarray.h')
    for name in kernel_files:
        path = args.kernel/name
        assert sha(path) == manifest[name]['sha256'],('kernel-original-manifest',name)
        inputs[str(path.resolve())] = sha(path)
    del manifest
    gc.collect()
    filenames = dict(core='mt76.ko',radio='mt7996/mt7996e.ko',connac='mt76-connac-lib.ko')
    paths = {label:args.producer.parent/'mt76'/name for label,name in filenames.items()}
    for path in paths.values():
        inputs[str(path.resolve())] = sha(path)
    for name in ('mt7996/mac.c','mt7996/mmio.c','mt7996/mt7996.h','mt76_connac_mac.c','tx.c','dma.c','mt76.h'):
        path = args.mac_source if name == 'mt7996/mac.c' and args.mac_source else args.source/name
        assert sha(path) == context['mt76_sources'][name]['sha256'],('source-module-profile',name)
        inputs[str(path.resolve())] = sha(path)
    modules = {label:base.Module(path,label,producer['inner']['modules'][filenames[label]]['sha256'])
               for label,path in paths.items()}
    objects = KernelObjects(args.kernel)
    linked = verify_linked_bodies(objects,args.kernel/'vmlinux')
    modules.update(objects.modules)
    link(modules)
    for module in list(sys.modules.values()):
        filename = getattr(module,'__file__',None)
        if filename:
            path = Path(filename).resolve()
            if path.is_file() and any(path.is_relative_to(ROOT/name) for name in ('tests','tools')):
                inputs[str(path)] = sha(path)
    inspection = {label:dict(functions=module.functions,calls=module.calls,instructions=module.instructions,
                            tails=sorted(getattr(module,'tails',()))) for label,module in modules.items()}
    args.output.mkdir(parents=True)
    if args.inspect_only:
        result = dict(passed=True,inspection_only=True,inputs=inputs,modules=inspection,kernel_linked_functions=linked)
    else:
        cases = [dict(mode='tokens',tokens=[],phys=phys,skbs='none',format='FW') for phys in (0,1,5,7)]
        for tokens in ((0,),(7,),(0,3,8191),(0,8192,16383)):
            for skbs in ('none','all','mixed'):
                for format_ in ('FW','MAC'):
                    for phys in (0,5):
                        cases.append(dict(mode='tokens',tokens=list(tokens),skbs=skbs,format=format_,phys=phys))
        for status in ('pending','ready'):
            cases.append(dict(mode='tokens',tokens=[0,3,8191],skbs='all',format='FW',phys=5,status=status))
        full_leaf = dict(mode='tokens',tokens=list(range(64)),phys=0,skbs='none',format='FW')
        cases.append(full_leaf)
        cases.append(dict(mode='tokens',tokens=[0,63,64,65,4095,4096,16383],phys=5,skbs='all',format='MAC'))
        rows = []
        for case in cases:
            replay = Replay(modules,case)
            try:
                rows.append(replay.run())
            except Exception as error:
                with (args.output/'failure.json').open('x') as stream:
                    json.dump(dict(case=case,error=str(error),events=replay.events,
                                   entries=replay.entries,kernel_returns=replay.kernel_returns,inputs=inputs),stream,indent=2)
                raise
            del replay
            gc.collect()
        probe = dict(mode='tokens',tokens=[0,8192,16383],phys=5,skbs='all',format='MAC')
        controls = []
        for mutation,expected in (('omit-kernel-destroy','IDR-destroy-once'),
                                  ('omit-RCU-enqueue','all-kernel-nodes-RCU-enqueued'),
                                  ('omit-node-zero','kernel-node-zero-before-free'),
                                  ('omit-slab-free','all-kernel-nodes-slab-returned'),
                                  ('omit-next-index-store','kernel-IDR-next-index'),
                                  ('omit-IDR-head-clear','kernel-IDR-head-cleared'),
                                  ('omit-IDR-free-mark','kernel-IDR-free-mark')):
            try:
                Replay(modules,full_leaf if mutation == 'omit-IDR-free-mark' else probe,mutation).run()
            except AssertionError as error:
                assert str(error) == expected,(mutation,str(error),expected)
                controls.append(dict(mutation=mutation,failed_assertion=expected,emulator_bytes_only=True))
            else:
                raise AssertionError(('kernel-mutation-survived',mutation))
        entered = {name:sum(row['native_entries'][name] for row in rows)
                   for name in rows[0]['native_entries']}
        assert all(entered[name] for name in objects.selected),'each-selected-kernel-body-entered'
        assert not any(event.get('name') in ('idr_get_next','idr_destroy') and event['kind'].startswith('modeled')
                       for row in rows for event in row['events']),'no-modeled-IDR-service'
        result = dict(passed=True,cases=len(rows),controls=controls,rows=rows,inputs=inputs,modules=inspection,
            producer_sha256=sha(args.producer),kernel_version='6.18.52',
            kernel_linked_functions=linked,native_entry_totals=entered,
            selected_but_unentered=[name for name,count in entered.items() if not count],
            kernel_fixture_allocation_is_modeled=True,
            actual_compiled_IDR_and_radix_tree_execution=True,
            RCU_grace_scheduling_SLAB_mac80211_and_DMA_effects_are_models=True,
            complete_kernel_SMP_and_physical_lifetime=False,current_FW_high_DMA_fix_acceptance=False,hardware=False)
    for filename,digest in inputs.items():
        assert sha(Path(filename)) == digest,('input-changed',filename)
    with (args.output/'result.json').open('x') as stream:
        json.dump(result,stream,indent=2)
        stream.write('\n')
    print(json.dumps(dict(passed=True,inspection_only=args.inspect_only,cases=result.get('cases'),
                         controls=len(result.get('controls',())),inputs=len(inputs))))


if __name__ == '__main__':
    main()
