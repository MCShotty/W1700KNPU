#!/usr/bin/env python3
"""Replay retained packet-status registration and retirement with compiled IDRs."""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys

from unicorn import UC_PROT_READ, UC_PROT_WRITE, UC_PROT_EXEC
from unicorn import arm64_const as arm

import test_tx_token_kernel_native as kernel

base = kernel.base
ROOT, sha = kernel.ROOT, kernel.sha
EXTRA_CORE = ('mt76_tx_status_skb_add','mt76_tx_status_skb_get',
              'mt76_tx_status_skb_done','mt76_tx_status_check')
WCID, QUEUE, ID_POINTER = 0x4d000000, 0x4e000000, 0x4f000000
WCID_LIST, PACKET_IDR, DEV_WCID_LIST, STATUS_LOCK = 0x170, 0x180, 0x66c8, 0x4108
FLOWS = ('dma-txs','txs-dma','dma-flush','flush-dma','dma-expiry','pre-dma-expiry')


class Replay(base.Replay):
    def __init__(self,modules,case,mutation=None):
        fixture = dict(mode='tokens',tokens=list(range(case['count'])),skbs='all',
                       status='pending',format=case['format'],phys=case['phys'])
        super().__init__(modules,fixture)
        self.scenario = case
        self.clock_seed = case.get('clock_seed',123456)
        self.clock(self.clock_seed)
        self.current = 'initialization'
        self.cpu.mem_map(kernel.NODES,0x100000)
        self.cpu.mem_map(kernel.GUARD,0x1000)
        for address in (WCID,QUEUE,ID_POINTER):
            self.cpu.mem_map(address,0x1000)
        self.cpu.reg_write(arm.UC_ARM64_REG_TPIDR_EL1,0)
        for module in modules.values():
            for address,payload in module.data.values():
                if address in getattr(module,'data_writable',()):
                    size = (len(payload)+4095) & ~4095
                    self.cpu.mem_protect(address,size,UC_PROT_READ | UC_PROT_WRITE)
        self.tails = {pc for module in modules.values() for pc in getattr(module,'tails',())}
        self.pool = [kernel.NODES+index*kernel.NODE_SIZE for index in range(32)]
        self.allocated, self.deferred, self.freed = set(), [], set()
        self.grace_active, self.fail_alloc = False, False
        self.allocation_failures = 0
        self.txs_expected, self.get_return_guards = None, {}
        self.kernel_nops = set()
        calls = {'omit-registration':'idr_alloc','omit-remove':'idr_remove',
                 'omit-DMA-completion':'__mt76_tx_complete_skb',
                 'omit-status-return':'ieee80211_tx_status_ext','omit-RCU-enqueue':'call_rcu'}
        operands = {
            'omit-wcid-link':('mt76_tx_status_skb_add',('str','x3, [x1]')),
            'omit-TXS-flag':('mt76_tx_status_skb_done',('strb','w5, [x1, #0x53]')),
            'omit-flush-selector':('mt76_tx_status_check',('neg','w22, w22')),
            'omit-wcid-unlink':('mt76_tx_status_skb_get',('str','x1, [x0]')),
        }
        assert mutation is None or mutation in calls or mutation in operands
        for label,module in modules.items():
            selected = set()
            if mutation in calls:
                target = calls[mutation]
                selected = {pc for pc,name in module.calls.items() if name == target and
                    (mutation not in ('omit-registration','omit-remove','omit-status-return') or label == 'core') and
                    (mutation != 'omit-DMA-completion' or label == 'radio')}
            elif mutation in operands:
                name,operand = operands[mutation]
                selected = {pc for pc,mnemonic,text in module.instructions.get(name,()) if (mnemonic,text) == operand}
            for pc in selected:
                self.kernel_nops.add(pc)
                self.cpu.mem_protect(module.base,0x100000,UC_PROT_READ | UC_PROT_WRITE | UC_PROT_EXEC)
                word = 0xd65f03c0 if pc in self.tails else 0xd503201f
                self.cpu.mem_write(pc,struct.pack('<I',word))
                self.cpu.mem_protect(module.base,0x100000,UC_PROT_READ | UC_PROT_EXEC)
        assert mutation is None or self.kernel_nops,('missing-status-mutation',mutation)
        self.head(base.DEV+DEV_WCID_LIST)
        self.head(WCID+WCID_LIST)
        self.init_idr(base.DEV+base.TOKEN_IDR)
        self.init_idr(WCID+PACKET_IDR)
        self.put64(base.DEV+0x44c8,WCID)
        self.cpu.mem_write(WCID+0xb8,struct.pack('<H',0))
        self.put32(WCID+0x80,case['count'])
        for ordinal,txwi in enumerate(self.initial_tokens.values()):
            buffer = txwi-76
            self.cpu.mem_write(buffer+37,struct.pack('<H',0))
            skb = self.buffers[txwi]
            self.put64(skb+0x28,(ordinal % 3) << 51 | 1)
            self.put64(skb+0xc8,skb+256)
            self.cpu.mem_write(skb+256,b'\x88\x00')

    def head(self,address):
        self.put64(address,address)
        self.put64(address+8,address)

    def clock(self,value):
        self.put64(base.JIFFIES,value & ((1 << 64)-1))

    def init_idr(self,address):
        self.cpu.mem_write(address,bytes(24))
        self.put32(address+4,4 | kernel.ROOT_IDR_FREE)

    def returned(self,pc,value=0):
        if pc not in self.tails:
            return super().returned(pc,value)
        target = self.cpu.reg_read(arm.UC_ARM64_REG_X30)
        for index in range(18):
            self.cpu.reg_write(base.REGS[index],value if index == 0 else 0xbad00000+index)
        self.cpu.reg_write(arm.UC_ARM64_REG_NZCV,0xa0000000)
        self.cpu.reg_write(arm.UC_ARM64_REG_PC,target)

    def code(self,cpu,pc,size,data):
        if pc in self.kernel_nops:
            self.instructions += 1
            return
        if pc in self.get_return_guards:
            expected = self.get_return_guards.pop(pc)
            assert cpu.reg_read(base.REGS[0]) == expected,'TXS-SKB-lookup'
        if pc == self.functions['mt76_tx_status_skb_get'] and self.txs_expected is not None:
            pid,expected = self.txs_expected
            assert cpu.reg_read(base.REGS[1]) == WCID
            assert cpu.reg_read(base.REGS[2]) & 0xffffffff == pid
            target = cpu.reg_read(arm.UC_ARM64_REG_X30)
            assert target not in self.get_return_guards
            self.get_return_guards[target] = expected
        name = self.calls.get(pc)
        if name in ('kmem_cache_alloc_noprof','call_rcu','kmem_cache_free','memset') and name not in self.functions:
            args = tuple(cpu.reg_read(base.REGS[index]) for index in range(3))
            if name == 'memset' and not kernel.NODES <= args[0] < kernel.NODES+0x100000:
                return super().code(cpu,pc,size,data)
            self.instructions += 1
            self.events.append(dict(kind='modeled-kernel-service',name=name,phase=self.current,arguments=list(args)))
            result = 0
            if name == 'kmem_cache_alloc_noprof':
                assert args[0] == kernel.SLAB,'status-kernel-slab-owner'
                if self.fail_alloc:
                    self.allocation_failures += 1
                else:
                    assert self.pool,'bounded-node-pool'
                    result = self.pool.pop(0)
                    assert result not in self.allocated
                    self.allocated.add(result)
            elif name == 'call_rcu':
                node = args[0]-kernel.NODE_RCU
                assert node in self.allocated and node not in {head-kernel.NODE_RCU for head,_ in self.deferred},'node-deferred-once'
                assert args[1] == self.functions['radix_tree_node_rcu_free'],'compiled-node-callback'
                self.deferred.append(args[:2])
            elif name == 'memset':
                assert args[1] == 0 and args[2] in (24,512,576),'status-node-zero-length'
                cpu.mem_write(args[0],bytes(args[2]))
                result = args[0]
            else:
                node = args[1]
                assert self.grace_active and args[0] == kernel.SLAB and node in self.allocated,'slab-only-after-modeled-grace'
                assert node not in self.freed,'node-slab-returned-once'
                assert bytes(cpu.mem_read(node+kernel.NODE_SLOTS,536)) == bytes(536),'node-zero-before-slab'
                assert self.get64(node+kernel.NODE_RCU) == self.get64(node+kernel.NODE_RCU+8) == node+kernel.NODE_RCU
                self.freed.add(node)
            return self.returned(pc,result)
        return super().code(cpu,pc,size,data)

    def call(self,name,*args):
        for index in range(8):
            self.cpu.reg_write(base.REGS[index],args[index] if index < len(args) else 0)
        self.cpu.reg_write(arm.UC_ARM64_REG_SP,base.STACK+0xf000)
        self.cpu.reg_write(arm.UC_ARM64_REG_X30,base.END)
        self.cpu.emu_start(self.functions[name],base.END,timeout=3_000_000,count=500000)
        assert self.cpu.reg_read(arm.UC_ARM64_REG_PC) == base.END,('bounded-status-call',self.current,name)
        return self.cpu.reg_read(base.REGS[0])

    def balanced(self):
        assert self.get32(base.DEV+STATUS_LOCK) == self.get32(base.TASK+0x10) == 0,'status-lock-balanced'

    def packet_ids(self):
        result = {}
        start = 0
        while True:
            self.put32(ID_POINTER,start)
            skb = self.call('idr_get_next',WCID+PACKET_IDR,ID_POINTER)
            if not skb:
                return result
            pid = self.get32(ID_POINTER)
            assert pid >= start and pid not in result,'packet-IDR-monotonic'
            result[pid] = skb
            start = pid+1

    def txs_frame(self,pid,wcid=0):
        ack_error = (1 << 16) if self.scenario.get('ack_error',False) else 0
        self.cpu.mem_write(QUEUE+256,struct.pack('<8I',(2 << 6) | ack_error,0,wcid << 16,pid << 24,0,0,0,0))

    def rejected_txs(self,pid,wcid):
        self.current = 'compiled-TXS-header-drop'
        self.balanced()
        before = self.entries['mt76_tx_status_skb_get'],len(self.statuses)
        self.txs_frame(pid,wcid)
        self.call('mt7996_mac_add_txs',base.DEV,QUEUE+256)
        assert before == (self.entries['mt76_tx_status_skb_get'],len(self.statuses)),'TXS-header-drop'
        self.balanced()

    def txs(self,pid,expected):
        self.current = 'compiled-MT7996-TXS-delivery'
        self.balanced()
        before = len(self.statuses)
        dma_done = bool(expected and self.cpu.mem_read(expected+0x53,1)[0] & 1)
        self.txs_expected = (pid,expected)
        self.txs_frame(pid)
        self.call('mt7996_mac_add_txs',base.DEV,QUEUE+256)
        self.txs_expected = None
        assert not self.get_return_guards,'TXS-get-return-observed'
        if expected:
            assert self.call('idr_find',WCID+PACKET_IDR,pid) == 0,'TXS-IDR-retired'
            assert self.cpu.mem_read(expected+0x53,1)[0] & 2,'TXS-flag-written'
            ack = bool(self.get32(expected+0x28) & (1 << 9))
            assert ack != self.scenario.get('ack_error',False),'TXS-ACK-result'
        assert len(self.statuses) == before+int(dma_done),'TXS-status-once'
        self.balanced()

    def check(self,flush):
        self.current = 'forced-flush' if flush else 'stale-status-check'
        self.call('mt76_tx_status_check',base.DEV,int(flush))
        self.balanced()

    def dma(self):
        self.current = 'DMA-token-retirement'
        if self.scenario['flow'] in ('txs-dma','flush-dma','allocation-failure'):
            self.expected_pending = []
            self.expected_status = list(self.buffers.values())
        self.call('mt7996_tx_token_put',base.DEV)
        assert self.get64(base.DEV+base.TOKEN_IDR+8) == 0,'token-IDR-empty'
        assert struct.unpack('<H',self.cpu.mem_read(base.DEV+base.TOKEN_COUNT,2))[0] == 0,'token-count-zero'
        assert self.cache() == list(reversed(self.initial_tokens.values())),'status-TXWI-cache'
        assert all(self.get64(txwi+0x18) == 0 for txwi in self.buffers),'token-SKB-cleared'
        assert self.unmaps == self.expected_unmaps,'status-DMA-arguments'
        self.balanced()

    def run(self):
        self.current = 'compiled-slab-constructors'
        for node in self.pool:
            self.call('radix_tree_node_ctor',node)
        self.current = 'token-fixture-allocation'
        for token,txwi in self.initial_tokens.items():
            self.put32(ID_POINTER,token)
            assert self.call('idr_alloc_u32',base.DEV+base.TOKEN_IDR,txwi,ID_POINTER,token,0x820) == 0,'token-fixture-IDR-allocated'
            assert self.get32(ID_POINTER) == token
        self.fail_alloc = self.scenario['flow'] == 'allocation-failure'
        self.current = 'compiled-status-registration'
        registered = {}
        for ordinal,skb in enumerate(self.buffers.values()):
            pid = self.call('mt76_tx_status_skb_add',base.DEV,WCID,skb)
            if self.fail_alloc:
                assert pid == 1 and self.cpu.mem_read(skb+0x52,1) == b'\x00','allocation-failure-fallback'
                continue
            assert pid == ordinal+3 and self.cpu.mem_read(skb+0x52,1)[0] == pid,'status-packet-ID-allocated'
            assert struct.unpack('<H',self.cpu.mem_read(skb+0x50,2))[0] == 0
            assert self.get64(base.DEV+DEV_WCID_LIST) == self.get64(base.DEV+DEV_WCID_LIST+8) == WCID+WCID_LIST,'wcid-registration-list'
            assert self.call('idr_find',WCID+PACKET_IDR,pid) == skb,'registered-packet-IDR-value'
            registered[pid] = skb
            self.balanced()
        assert self.packet_ids() == registered,'full-registered-packet-IDR'
        for pid,wcid in ((0,0),(3,0x440),(3,1)):
            self.rejected_txs(pid,wcid)
        assert self.packet_ids() == registered,'rejected-TXS-keeps-IDR'
        flow = self.scenario['flow']
        if flow == 'dma-txs':
            self.dma()
            assert not self.statuses and self.packet_ids() == registered,'DMA-keeps-packet-status-owner'
            self.txs(126,0)
            assert self.packet_ids() == registered,'fresh-unknown-TXS-keeps-owner'
            for pid,skb in registered.items():
                self.txs(pid,skb)
            self.txs(3,0)
        elif flow == 'txs-dma':
            for pid,skb in registered.items():
                self.txs(pid,skb)
            assert not self.packet_ids() and not self.statuses,'TXS-before-DMA-keeps-SKB'
            assert all(self.get64(txwi+0x18) == skb for txwi,skb in self.buffers.items()),'TXWI-still-owns-SKB'
            self.dma()
        elif flow == 'dma-flush':
            self.dma()
            assert not self.statuses and self.packet_ids() == registered
            self.check(True)
        elif flow == 'flush-dma':
            self.check(True)
            assert not self.packet_ids(),'flush-before-DMA-IDR-retired'
            assert not self.statuses and all(self.get64(txwi+0x18) == skb for txwi,skb in self.buffers.items()),'flush-keeps-DMA-owned-SKB'
            self.dma()
        elif flow == 'dma-expiry':
            self.dma()
            self.clock(self.clock_seed+24)
            self.check(False)
            assert not self.statuses and self.packet_ids() == registered,'fresh-DMA-not-expired'
            self.clock(self.clock_seed+25)
            self.check(False)
        elif flow == 'pre-dma-expiry':
            self.clock(self.clock_seed+1000000)
            self.check(False)
            assert not self.statuses and self.packet_ids() == registered,'inflight-DMA-not-expired'
            self.dma()
            self.clock(self.clock_seed+1000000+25)
            self.check(False)
        else:
            assert flow == 'allocation-failure' and not self.get64(WCID+PACKET_IDR+8)
            self.dma()
        assert self.statuses == list(self.buffers.values()) and len(set(self.statuses)) == len(self.buffers),'all-SKB-status-once'
        assert not self.packet_ids() and self.get64(WCID+PACKET_IDR+8) == 0,'status-IDR-empty'
        assert self.get64(base.DEV+DEV_WCID_LIST) == self.get64(base.DEV+DEV_WCID_LIST+8) == base.DEV+DEV_WCID_LIST,'wcid-empty-list'
        assert self.get64(WCID+WCID_LIST) == self.get64(WCID+WCID_LIST+8) == WCID+WCID_LIST,'wcid-node-self-linked'
        assert self.get32(WCID+0x80) == 0,'non-AQL-count-retired'
        assert {head-kernel.NODE_RCU for head,_ in self.deferred} == self.allocated,'all-owned-nodes-deferred'
        assert not self.freed,'no-node-free-before-grace'
        self.grace_active = True
        self.current = 'declared-modeled-RCU-grace'
        for head,address in self.deferred:
            assert address == self.functions['radix_tree_node_rcu_free']
            self.call('radix_tree_node_rcu_free',head)
        self.grace_active = False
        assert self.freed == self.allocated,'all-owned-nodes-returned'
        self.balanced()
        return dict(case=self.scenario,instructions=self.instructions,native_entries=self.entries,
                    registered_packet_IDs=list(registered),modeled_status_completions=self.statuses,
                    allocated_kernel_nodes=len(self.allocated),deferred_kernel_nodes=len(self.deferred),
                    modeled_slab_returns=len(self.freed),allocation_failures=self.allocation_failures,
                    final_packet_IDR_empty=True,final_token_IDR_empty=True,events=self.events)


def prepare(args):
    args.output.mkdir(parents=True)
    consumed = {}
    for module in list(sys.modules.values()):
        filename = getattr(module,'__file__',None)
        if not filename:
            continue
        path = Path(filename).resolve()
        if path.is_file() and any(path.is_relative_to(ROOT/name) for name in ('tests','tools')):
            target = args.output/'consumed'/path.relative_to(ROOT)
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as stream:
                stream.write(path.read_bytes())
            target.chmod(0o444)
            consumed[str(path)] = dict(path=str(target),sha256=sha(target))
    with (args.output/'consumed.json').open('x') as stream:
        json.dump(consumed,stream,indent=2)
    assert sha(args.producer) == args.expected_producer_sha256
    producer = json.loads(args.producer.read_bytes())
    assert producer['passed'] and producer['originals_unchanged']
    context_path = args.producer.parent/'context.json'
    context = json.loads(context_path.read_bytes())
    assert args.kernel.resolve() == Path(context['kernel']).resolve()
    inputs = {str(path.resolve()):sha(path) for path in (args.producer,context_path,Path(__file__))}
    inputs.update({filename:row['sha256'] for filename,row in consumed.items()})
    for name,digest in context['kernel_configs'].items():
        assert sha(args.kernel/name) == digest
        inputs[str((args.kernel/name).resolve())] = digest
    manifest_path = args.producer.parent/'kernel-before.json'
    manifest = json.loads(manifest_path.read_bytes())
    inputs[str(manifest_path.resolve())] = sha(manifest_path)
    for name in ('vmlinux','lib/idr.o','lib/radix-tree.o','lib/idr.c','lib/radix-tree.c',
                 'include/linux/idr.h','include/linux/radix-tree.h','include/linux/xarray.h','include/net/mac80211.h'):
        path = args.kernel/name
        assert sha(path) == manifest[name]['sha256'],('kernel-original-manifest',name)
        inputs[str(path.resolve())] = sha(path)
    del manifest
    gc.collect()
    filenames = dict(core='mt76.ko',radio='mt7996/mt7996e.ko',connac='mt76-connac-lib.ko')
    paths = {label:args.producer.parent/'mt76'/name for label,name in filenames.items()}
    for label,path in paths.items():
        assert sha(path) == producer['inner']['modules'][filenames[label]]['sha256']
        inputs[str(path.resolve())] = sha(path)
    for name in ('mt7996/mac.c','mt7996/mac.h','mt7996/mmio.c','mt7996/mt7996.h',
                 'mt76_connac_mac.c','mt76_connac3_mac.h','tx.c','dma.c','mt76.h'):
        path = args.mac_source if name == 'mt7996/mac.c' and args.mac_source else args.source/name
        assert sha(path) == context['mt76_sources'][name]['sha256'],('source-module-profile',name)
        inputs[str(path.resolve())] = sha(path)
    objects = kernel.KernelObjects(args.kernel,
        paths=dict(idr=args.kernel/'lib/idr.o',radix=args.kernel/'lib/radix-tree.o',core=paths['core'],radio=paths['radio']),
        bases=dict(**kernel.KERNEL_BASES,core=base.BASES['core'],radio=base.BASES['radio']),
        roots={'idr_get_next','idr_get_next_ul','idr_destroy','radix_tree_node_rcu_free',
               'radix_tree_node_ctor','idr_alloc_u32','idr_remove','idr_find',
               *base.SELECTED['core'],*base.SELECTED['radio'],*EXTRA_CORE,'mt7996_mac_add_txs'})
    linked = kernel.verify_linked_bodies(objects,args.kernel/'vmlinux')
    modules = dict(objects.modules)
    for label in ('connac',):
        modules[label] = base.Module(paths[label],label,producer['inner']['modules'][filenames[label]]['sha256'])
    kernel.link(modules)
    required = {
        'mt76_tx_status_skb_add': {('add','x0, x19, #0x180'),('mov','w2, #3'),('mov','w3, #0x7f'),
                                  ('strb','w20, [x21, #0x52]'),('add','x3, x19, #0x170')},
        'mt76_tx_status_skb_get': {('sub','x1, x1, #0x19'),('ldr','x0, [x23, #0x188]'),
                                  ('str','x19, [x23, #0x178]')},
        'mt76_tx_status_skb_done': {('strb','w5, [x1, #0x53]')},
        'mt76_tx_status_check': {('mov','x0, #0x66c8'),('neg','w22, w22')},
    }
    for name,operands in required.items():
        actual = {(mnemonic,operand) for _,mnemonic,operand in modules['core'].instructions[name]}
        assert operands <= actual,('status-fixture-ABI',name,operands-actual)
    inspection = {label:dict(functions=module.functions,calls=module.calls,instructions=module.instructions,
                            tails=sorted(getattr(module,'tails',())),
                            relocated_data=getattr(module,'relocated_data',()),
                            data_relocations=getattr(module,'data_relocations',()),
                            data_writable=sorted(getattr(module,'data_writable',())))
                  for label,module in modules.items()}
    return modules,inputs,linked,inspection


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--producer',type=Path,required=True)
    parser.add_argument('--expected-producer-sha256',default=base.PRODUCER_SHA)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--mac-source',type=Path)
    parser.add_argument('--kernel',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--inspect-only',action='store_true')
    parser.add_argument('--probe-flow',choices=(*FLOWS,'allocation-failure'))
    parser.add_argument('--probe-count',type=int,default=3,choices=(1,3,64))
    args = parser.parse_args()
    modules,inputs,linked,inspection = prepare(args)
    if args.inspect_only:
        result = dict(passed=True,inspection_only=True,inputs=inputs,modules=inspection,
                      kernel_linked_functions=linked,hardware=False)
    else:
        if args.probe_flow:
            cases = [dict(flow=args.probe_flow,count=args.probe_count,phys=5,format='FW')]
        else:
            cases = [dict(flow=flow,count=count,phys=phys,format=format_) for flow in FLOWS
                     for count in (1,3) for phys in (0,5) for format_ in ('FW','MAC')]
            cases += [dict(flow=flow,count=64,phys=0,format='FW') for flow in FLOWS]
            cases += [dict(flow='allocation-failure',count=3,phys=phys,format=format_)
                      for phys in (0,5) for format_ in ('FW','MAC')]
            cases += [dict(flow=flow,count=3,phys=5,format='MAC',clock_seed=(1 << 64)-16)
                      for flow in ('dma-expiry','pre-dma-expiry')]
            cases += [dict(flow=flow,count=3,phys=5,format=format_,ack_error=True)
                      for flow in ('dma-txs','txs-dma') for format_ in ('FW','MAC')]
            assert len(cases) == 64
        rows = []
        for case in cases:
            replay = Replay(modules,case)
            try:
                rows.append(replay.run())
            except Exception as error:
                with (args.output/'failure.json').open('x') as stream:
                    json.dump(dict(case=case,phase=replay.current,error=str(error),events=replay.events,
                                   PC=replay.cpu.reg_read(arm.UC_ARM64_REG_PC),entries=replay.entries,
                                   inputs=inputs),stream,indent=2)
                raise
            del replay
            gc.collect()
        with (args.output/'positive-cases.json').open('x') as stream:
            json.dump(dict(passed=True,complete_suite=False,cases=len(rows),rows=rows,inputs=inputs,
                           probe_only=bool(args.probe_flow),hardware=False),stream,indent=2)
        controls = []
        if not args.probe_flow:
            for mutation,flow,expected in (
                    ('omit-registration','dma-txs','status-packet-ID-allocated'),
                    ('omit-wcid-link','dma-txs','wcid-registration-list'),
                    ('omit-remove','dma-txs','TXS-SKB-lookup'),
                    ('omit-TXS-flag','txs-dma','TXS-flag-written'),
                    ('omit-DMA-completion','dma-txs','pending-SKB-before-cache'),
                    ('omit-flush-selector','flush-dma','flush-before-DMA-IDR-retired'),
                    ('omit-status-return','dma-txs','TXS-status-once'),
                    ('omit-wcid-unlink','dma-txs','wcid-empty-list'),
                    ('omit-RCU-enqueue','dma-txs','all-owned-nodes-deferred')):
                replay = Replay(modules,dict(flow=flow,count=3,phys=5,format='MAC'),mutation)
                try:
                    replay.run()
                except Exception as error:
                    if not isinstance(error,AssertionError) or str(error) != expected:
                        with (args.output/'control-failure.json').open('x') as stream:
                            json.dump(dict(mutation=mutation,flow=flow,observed=str(error),expected=expected,
                                           phase=replay.current,events=replay.events,inputs=inputs),stream,indent=2)
                        raise AssertionError((mutation,str(error),expected)) from error
                    controls.append(dict(mutation=mutation,failed_assertion=expected,emulator_bytes_only=True))
                else:
                    raise AssertionError(('status-mutation-survived',mutation))
                del replay
                gc.collect()
        entered = {name:sum(row['native_entries'][name] for row in rows) for name in rows[0]['native_entries']}
        if not args.probe_flow:
            assert all(entered[name] for name in EXTRA_CORE),'status-compiled-bodies-entered'
        assert entered['mt7996_mac_add_txs'],'MT7996-TXS-parser-entered'
        assert not any(event.get('name','').startswith('idr_') and event['kind'].startswith('modeled')
                       for row in rows for event in row['events']),'no-modeled-IDR-logic'
        result = dict(passed=True,probe_only=bool(args.probe_flow),cases=len(rows),controls=controls,
                      rows=rows,inputs=inputs,modules=inspection,kernel_linked_functions=linked,
                      native_entry_totals=entered,producer_sha256=sha(args.producer),
                      actual_MT7996_TXS_parser_and_status_locking_body_execution=True,
                      RCU_SLAB_mac80211_DMA_and_RX_delivery_are_models=True,
                      complete_Linux_SMP_IRQ_parser_and_physical_acceptance=False,
                      current_FW_high_DMA_fix_acceptance=False,hardware=False)
    for filename,digest in inputs.items():
        assert sha(Path(filename)) == digest,('input-changed',filename)
    with (args.output/'result.json').open('x') as stream:
        json.dump(result,stream,indent=2)
        stream.write('\n')
    print(json.dumps(dict(passed=True,inspection_only=args.inspect_only,probe_only=bool(args.probe_flow),
                         cases=result.get('cases'),controls=len(result.get('controls',())),inputs=len(inputs),
                         kernel_functions=len(linked))))


if __name__ == '__main__':
    main()
