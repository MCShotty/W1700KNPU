#!/usr/bin/env python3
"""Execute compiled consumer RX cleanup; kernel APIs and DMA effects are models."""
import argparse
import gc
import io
import json
from pathlib import Path
import struct
import sys

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_PROT_READ, UC_PROT_EXEC
from unicorn import arm64_const as arm

import test_cold_mcu_native as mcu
import test_rxwi_retirement_native as rxwi

PRODUCER_SHA = '92c75156014d8e4a4ed795656bf29d47268ca6b64e5a40544a35acc181d4e31e'
CORE, DRIVER, ENTRIES, DESCRIPTORS, POOL, TASK = (
    0x13000000, 0x44000000, 0x45000000, 0x46000000, 0x47000000, 0x48000000)
NAMES = ('mt76_dma_cleanup', 'mt76_dma_rx_cleanup', 'mt76_npu_queue_cleanup')
Q_RX, Q_SIZE, Q_COUNT, NAPI, NAPI_SIZE = 0x33f8, 0x80, 21, 0x8f0, 0x1f0


class CoreModule(rxwi.Module):
    def __init__(self, path, expected):
        super().__init__(path, CORE, NAMES, expected)
        elf = ELFFile(io.BytesIO(self.raw))
        symbols = list(elf.get_section_by_name('.symtab').iter_symbols())
        index, = {symbol['st_shndx'] for symbol in symbols if symbol.name in NAMES}
        decoder = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
        self.instructions = {}
        for name, (start, size) in self.functions.items():
            rows = list(decoder.disasm(self.text[start-CORE:start-CORE+size], start))
            assert len(rows)*4 == size
            self.instructions[name] = [(row.address, row.mnemonic, row.op_str) for row in rows]
            for row in rows:
                if row.mnemonic != 'bl':
                    continue
                pc = row.address
                if pc in self.calls:
                    target = self.calls[pc]
                    if target in NAMES:
                        delta = self.functions[target][0]-pc
                        assert delta % 4 == 0 and -(1 << 27) <= delta < 1 << 27
                        struct.pack_into('<I', self.text, pc-CORE, 0x94000000 | ((delta >> 2) & 0x3ffffff))
                    continue
                word = struct.unpack_from('<I', self.text, pc-CORE)[0]
                delta = (word & 0x3ffffff) << 2
                if delta & (1 << 27):
                    delta -= 1 << 28
                targets = [symbol.name for symbol in symbols if symbol['st_shndx'] == index and
                    symbol['st_info']['type'] == 'STT_FUNC' and CORE+symbol['st_value'] == pc+delta]
                assert len(targets) == 1, ('unresolved-local-BL', hex(pc), targets)
                self.calls[pc] = targets[0]
        expected_operands = {
            'mt76_dma_cleanup': {('ldr', 'x1, [x0, #0x858]'),
                ('mov', 'x3, #0x33e0'), ('add', 'x19, x19, #0x80'),
                ('ldr', 'x0, [x19, #0x78]'), ('add', 'x21, x21, #0x1f0')},
            'mt76_dma_rx_cleanup': {('ldr', 'w2, [x1, #0x30]'),
                ('ldrh', 'w2, [x1, #0x40]'), ('tbnz', 'w2, #9, #0x13001d98')},
            'mt76_npu_queue_cleanup': {('ldrh', 'w1, [x19, #0x2c]'),
                ('ldr', 'w0, [x19, #0x34]'), ('ldr', 'x27, [x19, #0x10]'),
                ('mov', 'w24, #0x28'), ('ldr', 'x1, [x0, #0x2b8]'),
                ('ldr', 'w3, [x3, #0x20]'), ('ldr', 'x0, [x21, #0x878]'),
                ('ldrh', 'w2, [x2, #0x20]'), ('ldr', 'x1, [x2, #0x10]'),
                ('ldr', 'x2, [x1, #0x28]'), ('ldr', 'x0, [x1, #0x10]')}}
        for name, operands in expected_operands.items():
            actual = {(mnemonic, args) for _, mnemonic, args in self.instructions[name]}
            assert operands <= actual, ('fixture-ABI-operands', name, operands-actual)


class Replay(mcu.Replay):
    def __init__(self, core, radio, case, mutation=None):
        self.core, self.core_entries = core, dict.fromkeys(NAMES, 0)
        self.mutation = mutation
        self.syncs, self.pages_returned, self.pools_destroyed, self.descriptor_accesses = [], [], [], []
        self.dequeues, self.skb_frees = 0, 0
        radio_case = dict(mcu=True, dma=True, hif2=case.get('hif2', False),
            send_error=case.get('send_error', 0), poll=case.get('poll', False))
        super().__init__(radio, radio_case, 'omit-firmware-poll' if mutation == 'omit-firmware-poll' else None)
        self.fixture = case
        self.cpu.mem_map(CORE, 0x100000)
        text = bytearray(core.text)
        self.core_nops = set()
        mutation_target = {'omit-queue-cleanup':'mt76_dma_rx_cleanup',
            'omit-page-return':'page_pool_put_unrefed_netmem',
            'omit-DMA-sync':'__dma_sync_single_for_cpu',
            'omit-pool-destroy':'page_pool_destroy'}.get(mutation)
        if mutation_target:
            self.core_nops = {pc for pc, name in core.calls.items() if name == mutation_target}
            assert self.core_nops
            for pc in self.core_nops:
                struct.pack_into('<I', text, pc-CORE, 0xd503201f)
        if mutation == 'read-descriptor-status':
            pc, = [pc for pc, mnemonic, operands in core.instructions['mt76_npu_queue_cleanup']
                if (mnemonic,operands) == ('mov','w24, #0x28')]
            # Load q->desc and then its first word; the access control must fire.
            struct.pack_into('<II', text, pc-CORE, 0xf9401278, 0xb940031f)
        self.cpu.mem_write(CORE, bytes(text))
        self.cpu.mem_protect(CORE, 0x100000, UC_PROT_READ | UC_PROT_EXEC)
        for address, size in ((DRIVER,0x1000), (ENTRIES,0x10000), (DESCRIPTORS,0x10000),
                (POOL,0x1000), (TASK,0x1000), (rxwi.VMEMMAP,0x10000)):
            self.cpu.mem_map(address, size)
        self.cpu.reg_write(arm.UC_ARM64_REG_SP_EL0, TASK)
        self.put64(mcu.DEV+0x858, DRIVER)
        self.put32(DRIVER, 0x100 if case.get('tracked', True) else 0)
        self.put64(mcu.OPS+0x2b8, (1 << 38) if case.get('coherent', False) else 0)
        for offset in (0x33c0, 0x33d0):
            self.put64(mcu.DEV+offset, mcu.DEV+offset)
            self.put64(mcu.DEV+offset+8, mcu.DEV+offset)
        self.put32(POOL+0x20, 2)
        self.qid = case.get('qid', 19)
        assert self.qid in (19, 20) or (self.qid == 0 and case.get('ordinary', False))
        self.queue = mcu.DEV+Q_RX+self.qid*Q_SIZE
        self.ndesc = case.get('ndesc', 512)
        self.queued = case.get('queued', 3)
        self.tail = case.get('tail', 511) if self.ndesc else 0
        assert (self.ndesc == self.queued == 0) or (0 <= self.queued < self.ndesc and 0 <= self.tail < self.ndesc)
        assert not case.get('ordinary', False) or self.queued == 0
        self.put64(self.queue+0x10, ENTRIES)
        self.put64(self.queue+0x20, DESCRIPTORS)
        self.cpu.mem_write(self.queue+0x2c, struct.pack('<H', self.tail))
        self.put32(self.queue+0x30, self.ndesc)
        self.put32(self.queue+0x34, self.queued)
        self.put32(self.queue+0x38, 2048 if case.get('shared',False) else 2120)
        flags = 0 if case.get('ordinary', False) else 0x208+(self.qid-19)
        self.cpu.mem_write(self.queue+0x40, struct.pack('<H', flags))
        self.put64(self.queue+0x78, POOL)
        self.put64(self.queue+0x58, mcu.DEV)
        self.cpu.mem_write(self.queue+0x2a, struct.pack('<H', (self.tail+self.queued) % self.ndesc if self.ndesc else 0))
        self.put64(mcu.DEV+NAPI+0x30, DRIVER)
        self.put64(mcu.DEV+NAPI+self.qid*NAPI_SIZE+0x30, DRIVER)
        if case.get('rx_head', False):
            self.put64(self.queue+0x70, ENTRIES+0xf000)
        self.expected_syncs, self.pages = [], {}
        for ordinal in range(self.queued):
            slot = (self.tail+ordinal) % self.ndesc
            entry = ENTRIES+slot*40
            shared = case.get('shared', False)
            page_index = ordinal//2 if shared else ordinal
            buffer = rxwi.BUFFER+page_index*4096+(ordinal % 2)*2048 if shared else rxwi.BUFFER+ordinal*4096
            page = rxwi.VMEMMAP+(((buffer+0x8000000000) & rxwi.MASK64) >> 12)*64
            self.put64(entry, buffer)
            dma, length = 0x23400000+ordinal*4096, 1800
            self.put64(entry+0x10, dma)
            self.cpu.mem_write(entry+0x20, struct.pack('<H', length))
            self.put32(DESCRIPTORS+slot*24, int(case.get('done',False)))
            self.put32(DESCRIPTORS+slot*24+12, dma)
            self.expected_syncs.append([mcu.OPS, dma, length, 2])
            self.put64(page+0x10, POOL)
            self.pages[page] = self.pages.get(page, 0)+1
        for page, references in self.pages.items():
            self.put64(page+0x28, references)
        self.descriptor_before = bytes(self.cpu.mem_read(DESCRIPTORS, 0x10000))
        self.cpu.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, self.descriptor,
            begin=DESCRIPTORS, end=DESCRIPTORS+0xffff)

    def descriptor(self, _cpu, access, address, size, _value, _data):
        self.descriptor_accesses.append([access,address,size])
        raise AssertionError('descriptor-status-not-consulted')

    def code(self, cpu, pc, size, data):
        if self.core.contains(pc):
            return self.core_code(cpu, pc, size)
        if pc in self.module.calls and self.module.calls[pc] == 'mt76_dma_cleanup':
            assert cpu.reg_read(arm.UC_ARM64_REG_X0) == mcu.DEV
            self.instructions += 1
            self.events.append(dict(kind='native-call', name='mt76_dma_cleanup'))
            cpu.reg_write(arm.UC_ARM64_REG_X30, pc+4)
            cpu.reg_write(arm.UC_ARM64_REG_PC, self.core.functions['mt76_dma_cleanup'][0])
            return
        return super().code(cpu, pc, size, data)

    def core_code(self, cpu, pc, size):
        assert size == 4
        self.instructions += 1
        for name, (start, _) in self.core.functions.items():
            if pc == start:
                self.core_entries[name] += 1
                self.events.append(dict(kind='native-entry', name=name))
        if pc in self.core_nops or pc not in self.core.calls:
            return
        name = self.core.calls[pc]
        if name in NAMES:
            return
        args = tuple(cpu.reg_read(mcu.REGS[index]) for index in range(4))
        self.events.append(dict(kind='modeled-core-call', name=name, args=list(args)))
        if name == '__dma_sync_single_for_cpu':
            self.syncs.append(list(args))
        elif name == 'page_pool_put_unrefed_netmem':
            assert args[0] == POOL and args[1] in self.pages and args[2:] == (0xffffffff, 0)
            assert args[1] not in self.pages_returned, 'no-duplicate-page-return'
            assert self.value64(args[1]+0x28) == 1, 'page-fragments-exhausted'
            self.pages_returned.append(args[1])
        elif name == 'page_pool_destroy':
            assert args[0] == POOL
            self.check_queue()
            assert not self.pools_destroyed, 'pool-destroyed-once'
            self.pools_destroyed.append(args[0])
        elif name == '__local_bh_enable_ip':
            assert args[1] == 0x200
            depth = struct.unpack('<I', cpu.mem_read(TASK+0x10, 4))[0]
            assert depth >= 0x200
            self.put32(TASK+0x10, depth-0x200)
        elif name == 'mt76_dma_dequeue':
            assert args[:3] == (mcu.DEV, self.queue, 1) and self.queued == 0
            self.dequeues += 1
        elif name == 'sk_skb_reason_drop':
            assert args[:3] == (0, ENTRIES+0xf000, 2)
            self.skb_frees += 1
        elif name == 'mt76_free_pending_rxwi':
            assert args[0] == mcu.DEV and self.value64(mcu.DEV+0x33d0) == mcu.DEV+0x33d0
        else:
            assert name in {'kthread_park','mt76_npu_shutdown_irqs','mt76_napi_cleanup',
                'napi_disable','mutex_lock','mutex_unlock','__netif_napi_del_locked','synchronize_net'}, name
        self.returned(pc)

    def check_queue(self):
        assert struct.unpack('<I', self.cpu.mem_read(self.queue+0x34, 4))[0] == 0, 'queue-drained-before-pool-destroy'
        assert set(self.pages_returned) == set(self.pages), 'all-modeled-pages-returned'
        expected = [] if self.fixture.get('coherent', False) else self.expected_syncs
        assert self.syncs == expected, 'every-noncoherent-entry-synchronized'
        tail = (self.tail+self.queued) % self.ndesc if self.ndesc else 0
        assert struct.unpack('<H', self.cpu.mem_read(self.queue+0x2c, 2))[0] == tail, 'queue-tail-wrap'

    def run(self):
        scope = self.fixture.get('scope', 'core')
        if scope == 'outer':
            self.call()
            assert self.core_entries['mt76_dma_cleanup'] == 1, 'compiled-core-cleanup-count'
            names = [event['name'] for event in self.events if event['kind'] == 'modeled-call']
            assert names.count('____mt76_poll_msec') == 1, 'firmware-state-poll-count'
            assert self.logs == ([] if self.case['poll'] else [
                'Timeout for initializing firmware\n','Failed to exit mcu\n']), 'MCU-failure-log-contract'
            poll = next(index for index, event in enumerate(self.events) if event.get('name') == '____mt76_poll_msec')
            shared = next(index for index, event in enumerate(self.events) if event['kind'] == 'native-entry' and event['name'] == 'mt76_dma_cleanup')
            assert poll < shared, 'MCU-poll-before-compiled-consumer-cleanup'
            before = len(self.events)
            self.call()
            assert len(self.events) == before+1, 'outer-cleanup-idempotent'
        else:
            name = 'mt76_dma_rx_cleanup' if scope == 'rx' else 'mt76_dma_cleanup'
            self.cpu.reg_write(arm.UC_ARM64_REG_SP, mcu.STACK+0xf000)
            self.cpu.reg_write(arm.UC_ARM64_REG_X30, mcu.END)
            self.cpu.reg_write(arm.UC_ARM64_REG_X0, mcu.DEV)
            self.cpu.reg_write(arm.UC_ARM64_REG_X1, self.queue)
            self.cpu.emu_start(self.core.functions[name][0], mcu.END, timeout=5_000_000, count=1_000_000)
            assert self.cpu.reg_read(arm.UC_ARM64_REG_PC) == mcu.END, 'bounded-core-cleanup-return'
        self.check_queue()
        expected_pools = int(scope != 'rx' and self.ndesc != 0)
        assert len(self.pools_destroyed) == expected_pools, 'pool-destroy-boundary'
        assert not self.descriptor_accesses, 'descriptor-status-not-consulted'
        assert bytes(self.cpu.mem_read(DESCRIPTORS,0x10000)) == self.descriptor_before
        assert struct.unpack('<I', self.cpu.mem_read(TASK+0x10,4))[0] == 0, 'balanced-bottom-half-depth'
        npu = bool(self.ndesc and not self.fixture.get('ordinary',False))
        assert self.core_entries['mt76_npu_queue_cleanup'] == int(npu), 'native-NPU-route'
        assert self.dequeues == int(bool(self.ndesc) and self.fixture.get('ordinary',False))
        assert self.skb_frees == int(self.fixture.get('rx_head',False))
        return dict(case=self.fixture, instructions=self.instructions, native_entries={**self.native_entries,**self.core_entries},
            DMA_sync_calls=len(self.syncs), page_return_calls=len(self.pages_returned),
            pool_destroy_calls=len(self.pools_destroyed), descriptor_accesses=self.descriptor_accesses,
            events=self.events, physical_drain_proven=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--producer', type=Path, required=True)
    parser.add_argument('--expected-producer-sha256', default=PRODUCER_SHA)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert mcu.sha(args.producer) == args.expected_producer_sha256
    producer = json.loads(args.producer.read_bytes())
    assert producer['passed'] and producer['originals_unchanged']
    context_path = args.producer.parent/'context.json'
    context = json.loads(context_path.read_bytes())
    core_path = args.producer.parent/'mt76/mt76.ko'
    radio_path = args.producer.parent/'mt76/mt7996/mt7996e.ko'
    inputs = {str(path.resolve()):mcu.sha(path) for path in (
        args.producer,context_path,core_path,radio_path,Path(__file__),Path(mcu.__file__),Path(rxwi.__file__))}
    for module in list(sys.modules.values()):
        filename = getattr(module,'__file__',None)
        if not filename:
            continue
        path = Path(filename).resolve()
        if path.is_file() and any(path.is_relative_to(mcu.ROOT/directory) for directory in ('tests','tools')):
            inputs[str(path)] = mcu.sha(path)
    for name in ('dma.c','npu.c','mt76.h','dma.h','airoha_offload.h','mt7996/init.c','mt7996/mcu.c','mt7996/dma.c','mt7996/mt7996.h'):
        path = args.source/name
        assert mcu.sha(path) == context['mt76_sources'][name]['sha256'], ('source-module-profile-mismatch',name)
        inputs[str(path.resolve())] = mcu.sha(path)
    core = CoreModule(core_path,producer['inner']['modules']['mt76.ko']['sha256'])
    radio = mcu.Module(radio_path,producer['inner']['modules']['mt7996/mt7996e.ko']['sha256'])
    cases = []
    for tracked in (False,True):
        for coherent in (False,True):
            for queued in (0,1,3,511):
                cases.append(dict(tracked=tracked,coherent=coherent,queued=queued,
                    done=coherent,qid=19+int(coherent)))
    for poll in (False,True):
        for error in (0,-5,-110):
            for hif2 in (False,True):
                cases.append(dict(scope='outer',poll=poll,send_error=error,hif2=hif2,
                    coherent=hif2,qid=19+int(hif2),done=hif2))
    for tracked in (False,True):
        cases.append(dict(ordinary=True,qid=0,queued=0,tail=0,tracked=tracked,rx_head=True))
    cases.append(dict(scope='rx',ndesc=0,queued=0))
    cases.append(dict(scope='rx',queued=0))
    cases.append(dict(ndesc=0,queued=0))
    for coherent in (False,True):
        cases.append(dict(queued=2,shared=True,coherent=coherent,
            synthetic_shared_fragment_helper_case=True))
    assert len(cases) == 35
    results = []
    for case in cases:
        replay = Replay(core,radio,case)
        results.append(replay.run())
        del replay
        gc.collect()
    groups = {}
    for row in results:
        case = row['case']
        if case.get('scope') != 'outer':
            continue
        key = (case['poll'],case['hif2'])
        trace = {name:row[name] for name in ('events','instructions','native_entries')}
        if key in groups:
            assert groups[key] == trace, 'send-error-changes-consumer-cleanup-trace'
        else:
            groups[key] = trace
    assert len(groups) == 4
    controls = []
    for mutation, expected in (
        ('omit-queue-cleanup','queue-drained-before-pool-destroy'),
        ('omit-page-return','all-modeled-pages-returned'),
        ('omit-DMA-sync','every-noncoherent-entry-synchronized'),
        ('omit-pool-destroy','pool-destroy-boundary'),
        ('read-descriptor-status','descriptor-status-not-consulted'),
        ('omit-firmware-poll','firmware-state-poll-count')):
        try:
            Replay(core,radio,dict(scope='outer'),mutation).run()
        except AssertionError as error:
            assert str(error) == expected, (mutation,str(error))
            controls.append(dict(mutation=mutation,failed_assertion=expected,emulator_bytes_only=True))
        else:
            raise AssertionError(('mutation-survived',mutation))
    assert all(mcu.sha(Path(path)) == digest for path,digest in inputs.items()), 'input-drift'
    args.output.mkdir(exist_ok=False)
    result = dict(passed=True,cases=len(results),controls=controls,results=results,
        inputs=inputs,producer_receipt_sha256=mcu.sha(args.producer),
        actual_functions=[*mcu.SELECTED,*NAMES],send_error_trace_groups=len(groups),
        core_fixture_ABI='SHA-bound compiled load/store operands; partial DWARF is not a layout source',
        queue_capacity=512,queued_ranges=[0,1,2,3,511],refill_keeps_one_slot_empty=True,
        descriptors_initialized_with_entry_DMA_addresses=True,DONE_states=[False,True],
        shared_fragment_cases_are_helper_models_not_current_allocation_profile=True,
        empty_TX_token_and_RRO_allocations=True,
        kernel_APIs_DMA_sync_page_pool_and_physical_effects_modeled=True,
        actual_Linux_cleanup_executed=False,physical_retirement=False,
        no_compilation=True,module_loaded=False,hardware=False)
    with (args.output/'result.json').open('x') as stream:
        json.dump(result,stream,indent=2)
        stream.write('\n')
    print(json.dumps(dict(passed=True,cases=len(results),controls=len(controls),
        result_sha256=mcu.sha(args.output/'result.json'))))


if __name__ == '__main__':
    main()
