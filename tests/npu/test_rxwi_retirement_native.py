#!/usr/bin/env python3
"""Characterize retained AArch64 RXWI helpers; kernel and outer cleanup are modeled."""
import argparse
import ctypes
import hashlib
import io
import json
from pathlib import Path
import struct
import sys

from elftools.elf.elffile import ELFFile
from elftools.elf.enums import ENUM_RELOC_TYPE_AARCH64 as RELOC
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_BLOCK
from unicorn import arm64_const as arm

import test_cold_probe_lifetime as extraction

ROOT = Path(__file__).resolve().parents[2]
PRODUCER_SHA = 'a840d3cccb1d0bd8cc60a856d1a1bb9723dfc05af73484d955a33978a458d22f'
CORE, RADIO = 0x10000000, 0x11000000
DEV, STACK, TASK, OBJECTS = 0x40000000, 0x41000000, 0x42000000, 0x43000000
HW, DRIVER, POOL, END = 0x44000000, 0x45000000, 0x46000000, 0x1f000000
VMEMMAP, BUFFER = 0xfffffffec0000000, 0xffffff8000100000
MASK64 = (1 << 64) - 1
REGS = [getattr(arm, 'UC_ARM64_REG_X' + str(i)) for i in range(29)] + [arm.UC_ARM64_REG_X29, arm.UC_ARM64_REG_X30]

# These offsets are specific to the SHA-bound modules, not a general mt76 ABI.
# They are checked against the actual loads/stores in the retained inspection.
RXWI_HEAD, WED_LOCK, RX_TOKEN_SIZE = 0x33d0, 0x7e0, 0x40e8
RRO_MAP, RRO_MAP_END, RRO_CACHE, RRO_LOCK = 0xa9f0, 0xb1e0, 0xa9e0, 0xa9c8
RXWI_DMA, RXWI_PTR = 0x10, 0x18


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class Module:
    def __init__(self, path, base, names, expected):
        assert sha(path) == expected
        self.path, self.base, self.sha256 = path, base, expected
        self.raw = path.read_bytes()
        elf = ELFFile(io.BytesIO(self.raw))
        assert elf['e_machine'] == 'EM_AARCH64' and elf.little_endian
        symbols = elf.get_section_by_name('.symtab')
        table = {symbol.name:symbol for symbol in symbols.iter_symbols() if symbol.name}
        selected = {name:table[name] for name in names}
        indices = {symbol['st_shndx'] for symbol in selected.values()}
        assert len(indices) == 1
        index, = indices
        section = elf.get_section(index)
        self.text = bytearray(section.data())
        assert len(self.text) <= 0x100000
        self.functions = {name:(base + symbol['st_value'], symbol['st_size'])
            for name, symbol in selected.items()}
        assert all(size > 0 and size % 4 == 0 for _, size in self.functions.values())
        self.calls = {}
        self.applied_relocations = []
        for relocations in elf.iter_sections():
            if relocations['sh_type'] != 'SHT_RELA' or relocations['sh_info'] != index:
                continue
            targets = elf.get_section(relocations['sh_link'])
            for relocation in relocations.iter_relocations():
                offset = relocation['r_offset']
                pc = base + offset
                if not self.contains(pc):
                    continue
                target = targets.get_symbol(relocation['r_info_sym'])
                kind = relocation['r_info_type']
                word = struct.unpack_from('<I', self.text, offset)[0]
                if kind == RELOC['R_AARCH64_CALL26']:
                    assert word & 0xfc000000 == 0x94000000
                    self.calls[pc] = target.name
                    continue
                assert target['st_shndx'] == index
                address = base + target['st_value'] + relocation['r_addend']
                if kind == RELOC['R_AARCH64_ADR_PREL_PG_HI21']:
                    assert word & 0x9f000000 == 0x90000000
                    pages = (address >> 12) - (pc >> 12)
                    assert -(1 << 20) <= pages < 1 << 20
                    immediate = pages & 0x1fffff
                    word = (word & ~0x60ffffe0) | ((immediate & 3) << 29) | ((immediate >> 2) << 5)
                else:
                    assert kind == RELOC['R_AARCH64_ADD_ABS_LO12_NC']
                    assert word & 0x7f000000 == 0x11000000 and not word & (1 << 22)
                    word = (word & ~0x003ffc00) | ((address & 4095) << 10)
                struct.pack_into('<I', self.text, offset, word)
                self.applied_relocations.append(dict(offset=offset, kind=kind, target=address))

    def contains(self, pc):
        return any(start <= pc < start + size for start, size in self.functions.values())


class RegisterTransport:
    """Reuse fixed AArch64 buffers with the installed SDK's batch primitives."""
    def __init__(self, cpu):
        self.cpu = cpu
        self.read_ids = (ctypes.c_int * 4)(*REGS[:4])
        self.read_values = (ctypes.c_uint64 * 4)()
        self.read_pointers = (ctypes.c_void_p * 4)(
            *(ctypes.addressof(self.read_values) + index * 8 for index in range(4)))
        ids = REGS[:18] + [arm.UC_ARM64_REG_X30, arm.UC_ARM64_REG_PC]
        self.write_ids = (ctypes.c_int * 20)(*ids)
        self.write_values = (ctypes.c_uint64 * 20)(0,
            *(0xbad00000 + index for index in range(1, 18)), 0, 0)
        self.write_pointers = (ctypes.c_void_p * 20)(
            *(ctypes.addressof(self.write_values) + index * 8 for index in range(20)))

    def arguments(self):
        assert self.cpu._do_reg_read_batch(self.read_ids, self.read_pointers, 4) == 0
        return tuple(self.read_values)

    def result(self, pc, value, batch_pc):
        self.write_values[0] = value
        self.write_values[18] = self.write_values[19] = pc + 4
        assert self.cpu._do_reg_write_batch(self.write_ids, self.write_pointers, 20 if batch_pc else 19) == 0
        if not batch_pc:
            # A scalar PC write also exits the current translated block.
            self.cpu.reg_write(arm.UC_ARM64_REG_PC, pc + 4)


class Replay:
    def __init__(self, modules, *, active, cached, shared_page=False, late_drain=False, source_drain=False,
                 drop_enqueue=False, drop_free=False, batch_pc=False):
        self.modules = modules
        self.cpu = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        for module in modules.values():
            self.cpu.mem_map(module.base, 0x100000)
            self.cpu.mem_write(module.base, bytes(module.text))
        for base, size in ((DEV,0x20000),(STACK,0x10000),(TASK,0x1000),
                (OBJECTS,0x10000),(HW,0x1000),(DRIVER,0x1000),(POOL,0x1000),
                (END,0x1000),(VMEMMAP,0x10000)):
            self.cpu.mem_map(base, size)
        self.cpu.reg_write(arm.UC_ARM64_REG_SP_EL0, TASK)
        self.registers = RegisterTransport(self.cpu)
        self.events = []
        self.live = set()
        self.freed = set()
        self.active = {}
        self.pages = {}
        self.returned_pages = set()
        self.drop_enqueue, self.drop_free = drop_enqueue, drop_free
        self.batch_pc = batch_pc
        self.token_queries = 0
        self.context_frees = 0
        self.native_put_entries = 0
        self.instructions = 0
        self.calls = {pc:name for module in modules.values() for pc,name in module.calls.items()}
        self.head(DEV + RXWI_HEAD)
        self.head(DEV + RRO_CACHE)
        for address in range(DEV + RRO_MAP, DEV + RRO_MAP_END, 16):
            self.head(address)
        self.put64(DEV + 0x858, DRIVER)
        self.put64(DEV + 0x7d8, HW)
        self.put32(DRIVER, 1 << 8)
        self.cpu.mem_write(DEV + RX_TOKEN_SIZE, struct.pack('<H', 32768))
        for index in range(cached + len(active)):
            address = OBJECTS + index * 64
            self.live.add(address)
            if index < cached:
                self.enqueue(address)
                continue
            item = index - cached
            token = active[item]
            buffer = BUFFER + (0 if shared_page else item * 4096) + (item * 2048 if shared_page else 0)
            page = VMEMMAP + (((buffer + 0x8000000000) & MASK64) >> 12) * 64
            self.put64(address + RXWI_PTR, buffer)
            self.put64(address + RXWI_DMA, 0x100000 + item * 4096)
            self.put64(page + 8, 0)
            self.put64(page + 0x10, POOL)
            self.pages[page] = self.pages.get(page, 0) + 1
            self.active[token] = address
        for page, fragments in self.pages.items():
            self.put64(page + 0x28, fragments)
        self.initial_active = dict(self.active)
        self.cpu.hook_add(UC_HOOK_BLOCK, self.block)
        for pc in set(self.calls) | {self.modules['core'].functions['mt76_put_rxwi'][0]}:
            self.cpu.hook_add(UC_HOOK_CODE, self.code, begin=pc, end=pc)
        self.call('core', 'mt76_free_pending_rxwi')
        assert len(self.freed) == cached and len(self.live) == len(active), 'initial-cache-drain'
        self.call('radio', 'mt7996_rro_msdu_page_map_free')
        assert not self.active and self.token_queries == 32768, 'complete-modeled-IDR-sweep'
        if source_drain:
            assert not self.cache() and not self.live, 'source-RXWI-cache-drain'
        else:
            assert self.cache() == set(self.initial_active.values()), 'late-RXWI-cache-transfer'
        assert self.returned_pages == set(self.pages), 'every-modeled-page-returned-once'
        for address in self.initial_active.values():
            assert self.get64(address + RXWI_DMA) == self.get64(address + RXWI_PTR) == 0
        if late_drain:
            self.call('core', 'mt76_free_pending_rxwi')
            self.call('core', 'mt76_free_pending_rxwi')
            assert not self.cache() and not self.live, 'late-cache-drain-before-context-free'
            assert len(self.freed) == cached + len(active), 'RXWI-freed-exactly-once'
        self.call('core', 'mt76_free_device')
        assert self.context_frees == 1
        assert len(self.live_at_context_free) == (0 if late_drain or source_drain else len(active))
        assert self.get32(TASK + 0x10) == 0, 'balanced-modeled-bottom-half-depth'
        self.result = dict(active_tokens=list(active), initial_cached=cached, shared_page=shared_page,
            modeled_late_drain=late_drain, actual_RRO_source_drain=source_drain,
            RXWI_live_at_context_free=len(self.live_at_context_free),
            RXWI_frees=len(self.freed), page_returns=len(self.returned_pages), token_queries=self.token_queries,
            instructions=self.instructions, native_put_rxwi_entries=self.native_put_entries,
            events=self.events)

    def put64(self, address, value):
        self.cpu.mem_write(address, struct.pack('<Q', value & MASK64))

    def get64(self, address):
        return struct.unpack('<Q', self.cpu.mem_read(address, 8))[0]

    def put32(self, address, value):
        self.cpu.mem_write(address, struct.pack('<I', value))

    def get32(self, address):
        return struct.unpack('<I', self.cpu.mem_read(address, 4))[0]

    def head(self, address):
        self.put64(address, address)
        self.put64(address + 8, address)

    def enqueue(self, address):
        head = DEV + RXWI_HEAD
        first = self.get64(head)
        self.put64(address, first)
        self.put64(address + 8, head)
        self.put64(first + 8, address)
        self.put64(head, address)

    def cache(self):
        head = DEV + RXWI_HEAD
        address = self.get64(head)
        output = set()
        previous = head
        while address != head:
            assert address in self.live and address not in output, 'valid-live-cache-list'
            assert self.get64(address + 8) == previous
            output.add(address)
            previous, address = address, self.get64(address)
        assert self.get64(head + 8) == previous
        return output

    def result_at_call(self, pc, value=0):
        self.registers.result(pc, value, self.batch_pc)

    def block(self, cpu, pc, size, _data):
        assert size > 0 and size % 4 == 0 and pc % 4 == 0
        assert any(start <= pc and pc + size <= start + length
            for module in self.modules.values() for start, length in module.functions.values()), ('unexpected-block', hex(pc), size)
        self.instructions += size // 4

    def code(self, cpu, pc, size, _data):
        assert size == 4 and any(module.contains(pc) for module in self.modules.values()), ('unexpected-PC', hex(pc))
        if pc == self.modules['core'].functions['mt76_put_rxwi'][0]:
            self.native_put_entries += 1
        if pc not in self.calls:
            return
        name = self.calls[pc]
        x0, x1, x2, x3 = self.registers.arguments()
        if name in ('mt76_put_rxwi','mt76_free_pending_rxwi'):
            assert x0 == DEV
            if name == 'mt76_put_rxwi':
                assert x1 in self.live
            if name == 'mt76_put_rxwi' and self.drop_enqueue:
                self.result_at_call(pc)
            else:
                cpu.reg_write(arm.UC_ARM64_REG_X30, pc + 4)
                cpu.reg_write(arm.UC_ARM64_REG_PC, self.modules['core'].functions[name][0])
            return
        if name == 'mt76_rx_token_release':
            assert x0 == DEV and 0 <= x1 < 32768
            self.token_queries += 1
            result = self.active.pop(x1, 0)
            if result:
                self.events.append(dict(kind='modeled-IDR-remove', token=x1, RXWI=result))
            self.result_at_call(pc, result)
            return
        if name == 'page_pool_put_unrefed_netmem':
            assert x0 == POOL and x1 in self.pages and x1 not in self.returned_pages
            assert x2 == 0xffffffff and x3 == 0 and self.get64(x1 + 0x28) == 1
            self.returned_pages.add(x1)
            self.put64(x1 + 0x28, 0)
            self.events.append(dict(kind='modeled-page-pool-return', page=x1))
        elif name == 'kfree':
            assert x0 in self.live and x0 not in self.freed, 'no-double-RXWI-free'
            if not self.drop_free:
                self.live.remove(x0)
                self.freed.add(x0)
            self.events.append(dict(kind='modeled-kfree', RXWI=x0))
        elif name == '__local_bh_enable_ip':
            assert x1 == 0x200 and self.get32(TASK + 0x10) >= 0x200, 'balanced-modeled-bottom-half-depth'
            self.put32(TASK + 0x10, self.get32(TASK + 0x10) - 0x200)
        elif name in ('mt76_npu_shutdown_irqs', 'mt76_napi_cleanup', 'mt76_npu_deinit'):
            assert x0 == DEV
            self.events.append(dict(kind='modeled-CPU-lifecycle', function=name))
        elif name == 'ieee80211_free_hw':
            assert x0 == HW and not self.context_frees
            self.context_frees += 1
            self.live_at_context_free = set(self.live)
            self.events.append(dict(kind='modeled-context-free', live_RXWI=len(self.live)))
        else:
            raise AssertionError(('unexpected-modeled-call', name, hex(pc)))
        self.result_at_call(pc)

    def call(self, module_name, function):
        module = self.modules[module_name]
        for index, register in enumerate(REGS):
            self.cpu.reg_write(register, 0x51000000 + index)
        self.cpu.reg_write(REGS[0], DEV)
        self.cpu.reg_write(arm.UC_ARM64_REG_SP, STACK + 0x8000)
        self.cpu.reg_write(arm.UC_ARM64_REG_X30, END)
        self.cpu.emu_start(module.functions[function][0], END, count=1000000, timeout=5000000)
        assert self.cpu.reg_read(arm.UC_ARM64_REG_PC) == END, ('bounded-helper-did-not-return', function)
        assert self.cpu.reg_read(arm.UC_ARM64_REG_SP) == STACK + 0x8000
        assert all(self.cpu.reg_read(REGS[index]) == 0x51000000 + index for index in range(19, 30)), function


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--producer', type=Path, required=True)
    parser.add_argument('--expected-producer-sha256', default=PRODUCER_SHA)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.producer = args.producer.resolve()
    assert sha(args.producer) == args.expected_producer_sha256
    producer = json.loads(args.producer.read_bytes())
    assert producer['passed'] and not producer['hardware'] and not producer['module_loaded']
    out = args.output.resolve()
    assert out.is_relative_to(ROOT / '.local')
    out.mkdir(exist_ok=False)
    source = args.source.resolve()
    source_bindings = {}
    for name in ('dma.c','mac80211.c','npu.c','mt76.h','mt7996/mac.c','mt7996/init.c','mt7996/dma.c'):
        expected = producer['inputs']['.local/merge-nonoc-20260923/mt76-merged/' + name]
        assert sha(source / name) == expected, name
        source_bindings[name] = expected
    cleanup = extraction.function((source / 'mt7996/init.c').read_text(), 'mt7996_cleanup_device')
    assert cleanup.index('mt7996_dma_cleanup(dev);') < cleanup.index('mt7996_rro_msdu_page_map_free(dev);')
    assert 'mt76_free_pending_rxwi' not in cleanup
    rro_release = extraction.function((source / 'mt7996/mac.c').read_text(), 'mt7996_rro_msdu_page_map_free')
    source_drain = 'mt76_free_pending_rxwi(&dev->mt76);' in rro_release
    if source_drain:
        assert rro_release.index('mt7996_rx_token_put(dev);') < rro_release.index('mt76_free_pending_rxwi(&dev->mt76);')
    dma = extraction.function((source / 'dma.c').read_text(), 'mt76_dma_cleanup')
    assert 'mt76_free_pending_rxwi(dev);' in dma
    free = extraction.function((source / 'mac80211.c').read_text(), 'mt76_free_device')
    deinit = extraction.function((source / 'npu.c').read_text(), 'mt76_npu_deinit')
    assert 'mt76_free_pending_rxwi' not in free and 'mt76_free_pending_rxwi' not in deinit
    assert 'mt76_put_rxwi' not in deinit
    module_root = args.producer.parent
    modules = {
        'core':Module(module_root / 'mt76/mt76.ko', CORE,
            ('mt76_put_rxwi','mt76_put_rxwi.part.0','mt76_free_pending_rxwi','mt76_free_device'),
            producer['inner']['modules']['mt76.ko']['sha256']),
        'radio':Module(module_root / 'mt76/mt7996/mt7996e.ko', RADIO,
            ('mt7996_rro_msdu_page_map_free',), producer['inner']['modules']['mt7996/mt7996e.ko']['sha256'])}
    assert ('mt76_free_pending_rxwi' in modules['radio'].calls.values()) == source_drain, 'source-and-compiled-RRO-drain-disagree'
    results = []
    configurations = [((),0,False), ((),2,False), ((0,),0,False), ((0,16,32767),2,False), ((0,32767),1,True)]
    for active, cached, shared in configurations:
        for late in (False, True):
            replay = Replay(modules, active=active, cached=cached, shared_page=shared, late_drain=late, source_drain=source_drain)
            results.append(replay.result)
    controls = []
    for name, kwargs, assertion in (
        ('missing-native-cache-enqueue', dict(drop_enqueue=True), 'source-RXWI-cache-drain' if source_drain else 'late-RXWI-cache-transfer'),
        ('missing-modeled-free', dict(drop_free=True), 'initial-cache-drain'),
        ('batched-PC-control-transfer', dict(batch_pc=True), 'balanced-modeled-bottom-half-depth')):
        try:
            Replay(modules, active=(0,), cached=1, late_drain=True, source_drain=source_drain, **kwargs)
        except AssertionError as error:
            assert error.args == (assertion,), (name, error.args)
            controls.append(dict(name=name, intended_assertion=assertion, rejected=True))
        else:
            raise AssertionError(('control-not-detected', name))
    metadata = dict(passed=True, scope='Finite retained AArch64 helper execution with modeled outer order and kernel boundaries',
        cases=len(results), results=results, controls=controls,
        producer_path=str(args.producer.relative_to(ROOT)), producer_sha256=sha(args.producer),
        module_bindings={str(module.path.relative_to(ROOT)):module.sha256 for module in modules.values()},
        test_source_sha256=sha(Path(__file__)),
        source_bindings=source_bindings,
        source_order_selected=True, actual_RRO_helper_contains_source_drain=source_drain,
        full_cold_cleanup_executed=False, actual_kernel_IDR_or_page_pool=False,
        actual_retained_RRO_cache_and_free_helper_instructions=True,
        modeled_late_drain_is_not_a_compiled_source_fix=True,
        limits=dict(instructions_per_helper=1000000, timeout_us_per_helper=5000000),
        new_compilation=False, hardware=False, physical_retirement=False, full_npu_goal_complete=False)
    with (out / 'result.json').open('x') as stream:
        json.dump(metadata, stream, indent=2)
        stream.write('\n')
    assert all(sha(module.path) == module.sha256 for module in modules.values())
    print(json.dumps(dict(passed=True, cases=len(results), controls=len(controls),
        conditional_live_RXWI=[row['RXWI_live_at_context_free'] for row in results if not row['modeled_late_drain']],
        new_compilation=False, physical_retirement=False)))


if __name__ == '__main__':
    main()
