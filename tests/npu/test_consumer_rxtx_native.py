#!/usr/bin/env python3
"""Replay retained ordinary RX/TX bodies; kernel and physical effects are models."""
import argparse
import gc
import io
import json
from pathlib import Path
import struct
import sys

from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_PROT_READ,UC_PROT_EXEC
from unicorn import arm64_const as arm

import test_consumer_dma_native as base

mcu,rxwi = base.mcu,base.rxwi
EXTRA = 0x14000000
TQUEUE,TENTRIES,TDESC,TREGS,TXWI,NPU,REGMAP = (
    0x49000000,0x4a000000,0x4b000000,0x4c000000,0x4d000000,0x4e000000,0x4f000000)
TX_COMPLETE = 0x1a000000
TXWI_SIZE = 76
NAMES = ('mt76_dma_dequeue','mt76_dma_tx_cleanup','mt76_dma_tx_cleanup.part.0',
    'mt76_dma_sync_idx','mt76_dma_read_dma_idx','mt76_dma_kick_queue',
    'mt76_queue_tx_complete','mt76_put_txwi.part.0','mt76_npu_txdesc_cleanup')


class Module(rxwi.Module):
    def __init__(self,path,expected):
        super().__init__(path,EXTRA,NAMES,expected)
        elf = ELFFile(io.BytesIO(self.raw))
        symbols = list(elf.get_section_by_name('.symtab').iter_symbols())
        index, = {symbol['st_shndx'] for symbol in symbols if symbol.name in NAMES}
        self.instructions,self.indirect = {},{}
        decoder = Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
        for name,(start,size) in self.functions.items():
            rows = list(decoder.disasm(self.text[start-EXTRA:start-EXTRA+size],start))
            assert len(rows)*4 == size
            self.instructions[name] = [(row.address,row.mnemonic,row.op_str) for row in rows]
            for row in rows:
                pc = row.address
                if row.mnemonic == 'blr':
                    self.indirect[pc] = getattr(arm,'UC_ARM64_REG_'+row.op_str.upper())
                if row.mnemonic != 'bl':
                    continue
                if pc in self.calls:
                    target = self.calls[pc]
                    if target in NAMES:
                        delta = self.functions[target][0]-pc
                        assert delta % 4 == 0 and -(1 << 27) <= delta < 1 << 27
                        struct.pack_into('<I',self.text,pc-EXTRA,0x94000000 | ((delta >> 2) & 0x3ffffff))
                    continue
                word = struct.unpack_from('<I',self.text,pc-EXTRA)[0]
                delta = (word & 0x3ffffff) << 2
                if delta & (1 << 27):
                    delta -= 1 << 28
                targets = [symbol.name for symbol in symbols if symbol['st_shndx'] == index and
                    symbol['st_info']['type'] == 'STT_FUNC' and EXTRA+symbol['st_value'] == pc+delta]
                assert len(targets) == 1, ('unresolved-local-BL',hex(pc),targets)
                self.calls[pc] = targets[0]
        expected_operands = {
            'mt76_dma_dequeue':{('orr','w3, w3, #0x80000000'),('str','w3, [x20, #4]'),
                ('str','xzr, [x26]'),('sub','x2, x2, #0x140')},
            'mt76_dma_tx_cleanup.part.0':{('ldr','x1, [x19, #0x20]'),
                ('tbz','x1, #0x30, #0x14001948'),('tbz','x1, #0x31, #0x14001968'),
                ('stp','xzr, xzr, [x19]')},
            'mt76_queue_tx_complete':{('ldr','x2, [x3, #0x28]'),('blr','x2'),
                ('str','w1, [x19, #0x34]')},
            'mt76_put_txwi.part.0':{('str','x20, [x19, #0x33c0]')}}
        for name,required in expected_operands.items():
            actual = {(mnemonic,operands) for _,mnemonic,operands in self.instructions[name]}
            assert required <= actual, ('fixture-ABI-operands',name,required-actual)


class Replay(base.Replay):
    def __init__(self,core,radio,extra,case,mutation=None):
        self.extra = extra
        self.extra_entries = dict.fromkeys(NAMES,0)
        self.payload_unmaps,self.txwi_unmaps,self.txwi_frees,self.completions = [],[],[],[]
        self.tx_descriptor_accesses,self.regmap_events = [],[]
        self.rcu_depth,self.wakes = 0,0
        initial = dict(ordinary=True,qid=0,queued=0,tail=0,tracked=case.get('tracked',True),
            coherent=case.get('coherent',False),hif2=case.get('hif2',False),
            send_error=case.get('send_error',0),poll=case.get('poll',False))
        super().__init__(core,radio,initial)
        self.fixture = dict(case,ordinary=True)
        self.cpu.mem_map(EXTRA,0x100000)
        text = bytearray(extra.text)
        self.extra_nops = set()
        targets = {'omit-TX-unmaps':'dma_unmap_page_attrs',
            'omit-TXWI-cache':'mt76_put_txwi.part.0',
            'omit-NPU-TX-DONE':'mt76_npu_txdesc_cleanup',
            'omit-TX-index-sync':'mt76_dma_sync_idx'}
        if mutation in targets:
            self.extra_nops = {pc for pc,name in extra.calls.items() if name == targets[mutation]}
        elif mutation == 'omit-TX-callback':
            self.extra_nops = set(extra.indirect)
        elif mutation in ('omit-RX-DONE-write','omit-RX-buffer-clear'):
            target = ('str','w3, [x20, #4]') if mutation == 'omit-RX-DONE-write' else ('str','xzr, [x26]')
            self.extra_nops = {pc for pc,mnemonic,operands in extra.instructions['mt76_dma_dequeue']
                if (mnemonic,operands) == target}
        else:
            assert mutation is None,mutation
        if mutation:
            assert self.extra_nops,mutation
        for pc in self.extra_nops:
            struct.pack_into('<I',text,pc-EXTRA,0xd503201f)
        self.cpu.mem_write(EXTRA,bytes(text))
        self.cpu.mem_protect(EXTRA,0x100000,UC_PROT_READ | UC_PROT_EXEC)
        for address,size in ((TQUEUE,0x1000),(TENTRIES,0x20000),(TDESC,0x40000),
                (TREGS,0x1000),(TXWI,0x80000),(NPU,0x1000),(rxwi.VMEMMAP+0x10000,0x10000)):
            self.cpu.mem_map(address,size)
        self.prepare_rx(case)
        self.prepare_tx(case)
        self.cpu.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE,self.tx_descriptor,
            begin=TDESC,end=TDESC+0x3ffff)

    def prepare_rx(self,case):
        self.ndesc,self.tail,self.queued = 1536,1535,case.get('rx',3)
        assert 0 <= self.queued < self.ndesc
        self.put32(self.queue+0x30,self.ndesc)
        self.put32(self.queue+0x34,self.queued)
        self.cpu.mem_write(self.queue+0x2c,struct.pack('<H',self.tail))
        self.cpu.mem_write(self.queue+0x2a,struct.pack('<H',(self.tail+self.queued) % self.ndesc))
        self.pages,self.expected_syncs,self.rx_slots = {},[],[]
        self.rx_initial_ctrl = {}
        for ordinal in range(self.queued):
            slot = (self.tail+ordinal) % self.ndesc
            self.rx_slots.append(slot)
            entry,descriptor = base.ENTRIES+slot*40,base.DESCRIPTORS+slot*16
            buffer = rxwi.BUFFER+ordinal*4096
            page = rxwi.VMEMMAP+(((buffer+0x8000000000) & rxwi.MASK64) >> 12)*64
            dma = 0x23400000+ordinal*4096
            self.put64(entry,buffer)
            self.put64(entry+0x10,dma)
            self.cpu.mem_write(entry+0x20,struct.pack('<H',1800))
            ctrl = (1800 << 16) | (1 << 30) | (int(case.get('rx_done',False)) << 31)
            self.cpu.mem_write(descriptor,struct.pack('<IIII',dma,ctrl,0,0x55667788+ordinal))
            self.rx_initial_ctrl[slot] = ctrl
            self.put64(page+0x10,base.POOL)
            self.put64(page+0x28,1)
            self.pages[page] = 1
            self.expected_syncs.append([mcu.OPS,dma,1800,2])

    def prepare_tx(self,case):
        self.tx_queued = case.get('tx',3)
        self.tx_owner = case.get('owner','phy0')
        npu = case.get('npu_tx',False)
        assert self.tx_owner in ('phy0','phy2','mcu','fwdl')
        assert not npu or self.tx_owner.startswith('phy')
        self.tx_ndesc = 1024 if npu else 2048
        if self.tx_owner in ('mcu','fwdl'):
            self.tx_ndesc = 256 if self.tx_owner == 'mcu' else 128
            self.put64(mcu.DEV+0x33e0+(0 if self.tx_owner == 'mcu' else 2)*8,TQUEUE)
        else:
            band = int(self.tx_owner[-1])
            self.put64(mcu.DEV+0x790+band*8,mcu.PHYS+0x4000)
            self.put64(mcu.PHYS+0x4040,TQUEUE)
        assert 0 <= self.tx_queued < self.tx_ndesc
        self.tx_tail = self.tx_ndesc-1
        self.tx_end = (self.tx_tail+self.tx_queued) % self.tx_ndesc
        self.put64(TQUEUE,TREGS)
        self.put64(TQUEUE+0x10,TENTRIES)
        self.put64(TQUEUE+0x20,TDESC)
        self.cpu.mem_write(TQUEUE+0x2a,struct.pack('<HH',self.tx_end,self.tx_tail))
        self.put32(TQUEUE+0x30,self.tx_ndesc)
        self.put32(TQUEUE+0x34,self.tx_queued)
        self.cpu.mem_write(TQUEUE+0x40,struct.pack('<H',0x200 if npu else 0))
        self.put64(TQUEUE+0x58,mcu.DEV)
        self.put32(TQUEUE+0x60,0x100)
        self.put64(TQUEUE+0x68,0x34560000)
        self.put32(TREGS+12,7)
        self.put64(base.DRIVER+0x28,TX_COMPLETE)
        self.cpu.mem_write(base.DRIVER+8,struct.pack('<H',TXWI_SIZE))
        kind = case.get('txwi','no-free')
        assert kind in ('none','dummy','cached','no-free')
        flags = (0x100 if case.get('tracked',True) else 0) | int(kind != 'cached')
        self.put32(base.DRIVER,flags)
        if npu:
            self.put64(mcu.DEV+0x68c0,NPU)
            self.put64(NPU+8,REGMAP)
        self.expected_payload,self.expected_cached,self.expected_skbs = [],[],[]
        self.tx_slots,self.tx_initial_ctrl = [],{}
        self.tx_entries_before = {}
        for ordinal in range(self.tx_queued):
            slot = (self.tx_tail+ordinal) % self.tx_ndesc
            self.tx_slots.append(slot)
            entry = TENTRIES+slot*40
            skb = 0x60000000+ordinal*64
            self.expected_skbs.append(skb)
            txwi = 0
            if kind == 'dummy':
                txwi = rxwi.MASK64
            elif kind in ('cached','no-free'):
                allocation = TXWI+ordinal*256
                txwi = allocation+TXWI_SIZE
                metadata_dma = 0x38000000+ordinal*4096
                self.put64(txwi+0x10,metadata_dma)
                if kind == 'cached':
                    self.expected_cached.append((txwi,allocation,metadata_dma))
            dma0,dma1 = 0x30000000+ordinal*4096,0x34000000+ordinal*4096
            skip = case.get('skip',0)
            assert skip in range(4)
            self.cpu.mem_write(entry,struct.pack('<QQQQHHHBB',skb,txwi,dma0,dma1,100,64,0xffff,skip,0))
            self.tx_entries_before[slot] = bytes(self.cpu.mem_read(entry,40))
            if not skip & 1:
                self.expected_payload.append([mcu.OPS,dma0,100,1,0])
            if not skip & 2:
                self.expected_payload.append([mcu.OPS,dma1,64,1,0])
            stride = 208 if npu else 16
            descriptor = TDESC+slot*stride
            ctrl = int(case.get('tx_done',True)) if npu else (int(case.get('tx_done',False)) << 31)
            self.tx_initial_ctrl[slot] = ctrl
            self.put32(descriptor,ctrl if npu else dma0)
            self.put32(descriptor+(4 if not npu else 0),ctrl)
            if npu:
                self.put32(descriptor+4,dma0)

    def descriptor(self,_cpu,access,address,size,_value,_data):
        self.descriptor_accesses.append([access,address,size])

    def tx_descriptor(self,_cpu,access,address,size,_value,_data):
        self.tx_descriptor_accesses.append([access,address,size])

    def transfer(self,pc,name):
        self.events.append(dict(kind='native-extra-call',name=name))
        self.cpu.reg_write(arm.UC_ARM64_REG_X30,pc+4)
        self.cpu.reg_write(arm.UC_ARM64_REG_PC,self.extra.functions[name][0])

    def code(self,cpu,pc,size,data):
        if self.extra.contains(pc):
            return self.extra_code(cpu,pc,size)
        return super().code(cpu,pc,size,data)

    def core_code(self,cpu,pc,size):
        name = self.core.calls.get(pc)
        if name in NAMES:
            self.instructions += 1
            return self.transfer(pc,name)
        if name in ('dma_unmap_page_attrs','kfree'):
            self.instructions += 1
            return self.model_call(pc,name)
        if name == 'page_pool_destroy':
            assert struct.unpack('<I',cpu.mem_read(TQUEUE+0x34,4))[0] == 0,'TX-drained-before-pool-destroy'
        return super().core_code(cpu,pc,size)

    def extra_code(self,cpu,pc,size):
        assert size == 4
        self.instructions += 1
        for name,(start,_) in self.extra.functions.items():
            if pc == start:
                self.extra_entries[name] += 1
                self.events.append(dict(kind='native-entry',name=name))
                if name == 'mt76_dma_sync_idx':
                    assert struct.unpack('<H',cpu.mem_read(TQUEUE+0x2c,2))[0] == self.tx_end,'TX-tail-wrap-before-index-sync'
        if pc in self.extra_nops:
            return
        if pc in self.extra.indirect:
            assert cpu.reg_read(self.extra.indirect[pc]) == TX_COMPLETE,'known-TX-completion-callback'
            dev,entry = (cpu.reg_read(mcu.REGS[index]) for index in range(2))
            assert dev == mcu.DEV
            packet,txwi = struct.unpack('<QQ',cpu.mem_read(entry,16))
            assert packet in self.expected_skbs and packet not in self.completions,'unique-TX-completion'
            expected = self.tx_entries_before[self.tx_slots[len(self.completions)]]
            if self.fixture.get('txwi','no-free') == 'dummy':
                expected = expected[:8]+bytes(8)+expected[16:]
            assert bytes(cpu.mem_read(entry,40)) == expected,'copied-TX-entry-before-callback'
            self.completions.append(packet)
            self.events.append(dict(kind='modeled-SKB-completion',skb=packet,txwi=txwi))
            return self.returned(pc)
        name = self.extra.calls.get(pc)
        if name is None or name in NAMES:
            return
        return self.model_call(pc,name)

    def model_call(self,pc,name):
        args = tuple(self.cpu.reg_read(mcu.REGS[index]) for index in range(5))
        self.events.append(dict(kind='modeled-extra-call',name=name,args=list(args)))
        if name == '__dma_sync_single_for_cpu':
            self.syncs.append(list(args[:4]))
        elif name == 'dma_unmap_page_attrs':
            target = self.txwi_unmaps if 0x38000000 <= args[1] < 0x39000000 else self.payload_unmaps
            target.append(list(args))
        elif name == 'kfree':
            assert args[0] in [item[1] for item in self.expected_cached]
            assert args[0] not in self.txwi_frees,'no-duplicate-TXWI-free'
            self.txwi_frees.append(args[0])
        elif name == '__local_bh_enable_ip':
            assert args[1] == 0x200
            depth = struct.unpack('<I',self.cpu.mem_read(base.TASK+0x10,4))[0]
            assert depth >= 0x200
            self.put32(base.TASK+0x10,depth-0x200)
        elif name == '__wake_up':
            assert args[:4] == (mcu.DEV+0x40f0,3,1,0)
            self.wakes += 1
        elif name in ('__rcu_read_lock','__rcu_read_unlock'):
            self.rcu_depth += 1 if name == '__rcu_read_lock' else -1
            assert self.rcu_depth >= 0
        elif name == 'regmap_read':
            assert args[:2] == (REGMAP,0x10c)
            self.put32(args[2],7)
            self.regmap_events.append([name,*args[:2],7])
        elif name == 'regmap_write':
            assert args[0] == REGMAP and args[1] in (0x100,0x104,0x108)
            self.regmap_events.append([name,*args[:3]])
        else:
            raise AssertionError(('unmodeled-call',name,hex(pc)))
        self.returned(pc)

    def run(self):
        if self.fixture.get('scope') == 'outer':
            self.call()
            names = [event['name'] for event in self.events if event['kind'] == 'modeled-call']
            assert names.count('____mt76_poll_msec') == 1
            assert self.logs == ([] if self.case['poll'] else [
                'Timeout for initializing firmware\n','Failed to exit mcu\n'])
            before = len(self.events)
            self.call()
            assert len(self.events) == before+1,'outer-cleanup-idempotent'
        else:
            self.cpu.reg_write(arm.UC_ARM64_REG_SP,mcu.STACK+0xf000)
            self.cpu.reg_write(arm.UC_ARM64_REG_X30,mcu.END)
            self.cpu.reg_write(arm.UC_ARM64_REG_X0,mcu.DEV)
            self.cpu.emu_start(self.core.functions['mt76_dma_cleanup'][0],mcu.END,timeout=5_000_000,count=1_000_000)
            assert self.cpu.reg_read(arm.UC_ARM64_REG_PC) == mcu.END,'bounded-shared-cleanup-return'
        self.check_queue()
        assert len(self.pools_destroyed) == 1 and self.rcu_depth == 0
        for slot in self.rx_slots:
            ctrl = struct.unpack('<I',self.cpu.mem_read(base.DESCRIPTORS+slot*16+4,4))[0]
            assert ctrl == self.rx_initial_ctrl[slot] | (1 << 31),'ordinary-RX-forces-DONE-on-flush'
            assert self.value64(base.ENTRIES+slot*40) == 0,'ordinary-RX-buffer-cleared'
        assert self.extra_entries['mt76_dma_dequeue'] == self.queued+1,'compiled-ordinary-RX-dequeue-count'
        assert self.payload_unmaps == self.expected_payload,'TX-payload-unmaps'
        assert self.extra_entries['mt76_put_txwi.part.0'] == len(self.expected_cached),'TXWI-cache-retirement-count'
        expected_metadata = [[mcu.OPS,dma,TXWI_SIZE,1,0] for _,_,dma in reversed(self.expected_cached)]
        assert self.txwi_unmaps == expected_metadata,'TXWI-metadata-unmaps'
        assert self.txwi_frees == [allocation for _,allocation,_ in reversed(self.expected_cached)],'TXWI-allocation-frees'
        assert self.completions == self.expected_skbs,'TX-SKB-completion-count'
        assert self.value64(mcu.DEV+0x33c0) == mcu.DEV+0x33c0,'TXWI-cache-empty-after-cleanup'
        assert struct.unpack('<I',self.cpu.mem_read(TQUEUE+0x34,4))[0] == 0
        assert struct.unpack('<HH',self.cpu.mem_read(TQUEUE+0x2a,4)) == (7,7),'TX-hardware-index-resync'
        assert self.wakes == 1,'TX-waiter-wakeup'
        for slot in self.tx_slots:
            assert bytes(self.cpu.mem_read(TENTRIES+slot*40,40)) == bytes(40),'TX-entry-zeroed'
            if self.fixture.get('npu_tx',False):
                ctrl = struct.unpack('<I',self.cpu.mem_read(TDESC+slot*208,4))[0]
                assert ctrl == self.tx_initial_ctrl[slot] & ~1,'NPU-TX-DONE-cleared'
        if not self.fixture.get('npu_tx',False):
            assert not self.tx_descriptor_accesses,'ordinary-TX-descriptor-status-not-consulted'
        assert struct.unpack('<I',self.cpu.mem_read(base.TASK+0x10,4))[0] == 0,'balanced-bottom-half-depth'
        return dict(case=self.fixture,instructions=self.instructions,native_entries={
            **self.native_entries,**self.core_entries,**self.extra_entries},
            RX_pages_returned=len(self.pages_returned),RX_DMA_syncs=len(self.syncs),
            TX_payload_unmaps=len(self.payload_unmaps),TXWI_unmaps=len(self.txwi_unmaps),
            TXWI_frees=len(self.txwi_frees),SKB_completions=len(self.completions),
            regmap_events=self.regmap_events,events=self.events,physical_drain_proven=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--producer',type=Path,required=True)
    parser.add_argument('--expected-producer-sha256',default=base.PRODUCER_SHA)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--probe-only',action='store_true')
    args = parser.parse_args()
    assert mcu.sha(args.producer) == args.expected_producer_sha256
    producer = json.loads(args.producer.read_bytes())
    assert producer['passed'] and producer['originals_unchanged']
    context_path = args.producer.parent/'context.json'
    context = json.loads(context_path.read_bytes())
    core_path = args.producer.parent/'mt76/mt76.ko'
    radio_path = args.producer.parent/'mt76/mt7996/mt7996e.ko'
    inputs = {str(path.resolve()):mcu.sha(path) for path in (args.producer,context_path,core_path,radio_path,Path(__file__))}
    for module in list(sys.modules.values()):
        filename = getattr(module,'__file__',None)
        if filename:
            path = Path(filename).resolve()
            if path.is_file() and any(path.is_relative_to(mcu.ROOT/directory) for directory in ('tests','tools')):
                inputs[str(path)] = mcu.sha(path)
    for name in ('dma.c','npu.c','tx.c','mt76.h','dma.h','airoha_offload.h','mt76_connac.h',
            'mt7996/init.c','mt7996/mcu.c','mt7996/dma.c','mt7996/mt7996.h','mt7996/mmio.c'):
        path = args.source/name
        assert mcu.sha(path) == context['mt76_sources'][name]['sha256'],('source-module-profile-mismatch',name)
        inputs[str(path.resolve())] = mcu.sha(path)
    core = base.CoreModule(core_path,producer['inner']['modules']['mt76.ko']['sha256'])
    radio = mcu.Module(radio_path,producer['inner']['modules']['mt7996/mt7996e.ko']['sha256'])
    extra = Module(core_path,producer['inner']['modules']['mt76.ko']['sha256'])
    cases = []
    for tracked in (False,True):
        for coherent in (False,True):
            for rx in (0,1,3,1535):
                cases.append(dict(tracked=tracked,coherent=coherent,rx=rx,tx=0,rx_done=coherent))
    for npu in (False,True):
        for kind in ('none','dummy','cached','no-free'):
            for skip in range(4):
                cases.append(dict(rx=0,tx=3,npu_tx=npu,txwi=kind,skip=skip,
                    generic_driver_flag_override=kind == 'cached'))
    for poll in (False,True):
        for error in (0,-5,-110):
            for hif2 in (False,True):
                cases.append(dict(scope='outer',poll=poll,send_error=error,hif2=hif2,
                    coherent=hif2,npu_tx=True,rx_done=hif2))
    cases.extend((dict(owner='phy2',tx=2047),dict(owner='phy2',tx=1023,npu_tx=True),
        dict(owner='mcu',tx=255),dict(owner='fwdl',tx=127)))
    assert len(cases) == 64
    if args.probe_only:
        cases = [dict(scope='outer',npu_tx=True)]
    results = []
    for case in cases:
        replay = Replay(core,radio,extra,case)
        results.append(replay.run())
        del replay
        gc.collect()
    selected = [*mcu.SELECTED,*base.NAMES,*NAMES]
    observed = sorted({name for row in results for name,count in row['native_entries'].items() if count})
    trace_groups = {}
    for row in results:
        case = row['case']
        if case.get('scope') != 'outer':
            continue
        key = (case.get('poll',False),case.get('hif2',False))
        trace = {name:row[name] for name in ('events','instructions','native_entries')}
        if key in trace_groups:
            assert trace_groups[key] == trace,'send-error-changes-RX-TX-cleanup-trace'
        else:
            trace_groups[key] = trace
    if not args.probe_only:
        assert set(observed) == set(selected)-{'mt76_dma_tx_cleanup','mt76_npu_queue_cleanup'}
        assert len(trace_groups) == 4
    controls = []
    if not args.probe_only:
        for mutation,expected in (
            ('omit-RX-DONE-write','ordinary-RX-forces-DONE-on-flush'),
            ('omit-RX-buffer-clear','ordinary-RX-buffer-cleared'),
            ('omit-TX-unmaps','TX-payload-unmaps'),
            ('omit-TXWI-cache','TXWI-cache-retirement-count'),
            ('omit-NPU-TX-DONE','NPU-TX-DONE-cleared'),
            ('omit-TX-callback','TX-SKB-completion-count'),
            ('omit-TX-index-sync','TX-hardware-index-resync')):
            try:
                case = dict(scope='outer',npu_tx=True)
                if mutation == 'omit-TXWI-cache':
                    case.update(txwi='cached',generic_driver_flag_override=True)
                Replay(core,radio,extra,case,mutation).run()
            except AssertionError as error:
                assert str(error) == expected,(mutation,str(error))
                controls.append(dict(mutation=mutation,failed_assertion=expected,emulator_bytes_only=True))
            else:
                raise AssertionError(('mutation-survived',mutation))
    assert all(mcu.sha(Path(path)) == digest for path,digest in inputs.items()),'input-drift'
    args.output.mkdir(exist_ok=False)
    result = dict(passed=True,complete_matrix=not args.probe_only,cases=len(results),controls=controls,
        results=results,inputs=inputs,producer_receipt_sha256=mcu.sha(args.producer),
        selected_functions=selected,actual_functions=observed,
        selected_but_unentered=sorted(set(selected)-set(observed)),send_error_trace_groups=len(trace_groups),
        outer_cases_keep_MT7996_TXWI_NO_FREE=True,cached_cases_are_generic_driver_flag_overrides=True,
        TX_token_IDR_and_connac_SKB_completion_not_executed=True,
        kernel_APIs_SKB_callback_registers_and_physical_effects_modeled=True,
        actual_Linux_cleanup_executed=False,physical_retirement=False,
        no_compilation=True,module_loaded=False,hardware=False)
    with (args.output/'result.json').open('x') as stream:
        json.dump(result,stream,indent=2)
        stream.write('\n')
    print(json.dumps(dict(passed=True,complete_matrix=not args.probe_only,cases=len(results),controls=len(controls),
        result_sha256=mcu.sha(args.output/'result.json'))))


if __name__ == '__main__':
    main()
