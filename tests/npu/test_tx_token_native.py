#!/usr/bin/env python3
"""Execute retained TX token/SKB bodies; IDR, mac80211 and DMA effects are models."""
import argparse
import gc
import io
import json
from pathlib import Path
import struct
import sys

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile
from elftools.elf.enums import ENUM_RELOC_TYPE_AARCH64 as RELOC
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE, UC_PROT_READ, UC_PROT_EXEC
from unicorn import arm64_const as arm

import test_rxwi_retirement_native as native

ROOT, sha, REGS = native.ROOT, native.sha, native.REGS
DEV, STACK, TASK, DRIVER, OBJECTS, SKBS, PHYS, HW, DMA_DEV, ENTRY, END = (
    0x40000000, 0x41000000, 0x42000000, 0x43000000, 0x44000000,
    0x45000000, 0x46000000, 0x47000000, 0x48000000, 0x49000000, 0x1f000000)
JIFFIES = 0x17000000
PRODUCER_SHA = '92c75156014d8e4a4ed795656bf29d47268ca6b64e5a40544a35acc181d4e31e'
SELECTED = {
    'core': ('__mt76_tx_complete_skb', 'mt76_tx_status_unlock', 'mt76_put_txwi', 'mt76_put_txwi.part.0'),
    'radio': ('mt7996_tx_token_put', 'mt7996_txwi_free'),
    'connac': ('mt76_connac_tx_complete_skb', 'mt76_connac_txp_skb_unmap'),
}
BASES = dict(core=0x10000000, radio=0x11000000, connac=0x12000000)
TOKEN_LOCK, TOKEN_IDR, TOKEN_COUNT, CACHE_HEAD = 0x40a0, 0x40a8, 0x40c2, 0x33c0
DRIVER_FLAGS = (1 << 0) | (1 << 4) | (1 << 5) | (1 << 7) | (1 << 8)


class Module:
    def __init__(self, path, label, expected):
        assert sha(path) == expected, ('module-hash', label)
        self.base, self.path, self.sha256 = BASES[label], path, expected
        elf = ELFFile(io.BytesIO(path.read_bytes()))
        assert elf['e_machine'] == 'EM_AARCH64' and elf.little_endian
        symbols = list(elf.get_section_by_name('.symtab').iter_symbols())
        table = {symbol.name: symbol for symbol in symbols if symbol.name}
        names = list(SELECTED[label])
        if label == 'radio':
            names += [symbol.name for symbol in symbols if symbol['st_info']['type'] == 'STT_FUNC'
                      and symbol.name.startswith('mt7996_txp_skb_unmap')]
        index, = {table[name]['st_shndx'] for name in names}
        self.text = bytearray(elf.get_section(index).data())
        assert len(self.text) < 0x100000
        self.functions = {name: (self.base + table[name]['st_value'], table[name]['st_size'])
                          for name in names}
        self.calls, self.instructions, self.data = {}, {}, {}
        decoder = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
        for name, (start, size) in self.functions.items():
            rows = list(decoder.disasm(self.text[start-self.base:start-self.base+size], start))
            assert size > 0 and len(rows) * 4 == size
            self.instructions[name] = [(row.address, row.mnemonic, row.op_str) for row in rows]
        for section in elf.iter_sections():
            if section['sh_type'] != 'SHT_RELA' or section['sh_info'] != index:
                continue
            targets = elf.get_section(section['sh_link'])
            for relocation in section.iter_relocations():
                offset, kind = relocation['r_offset'], relocation['r_info_type']
                pc = self.base + offset
                if not self.contains(pc):
                    continue
                target = targets.get_symbol(relocation['r_info_sym'])
                word = struct.unpack_from('<I', self.text, offset)[0]
                if kind == RELOC['R_AARCH64_CALL26']:
                    assert word & 0xfc000000 == 0x94000000
                    self.calls[pc] = target.name
                    continue
                if target['st_shndx'] == 'SHN_UNDEF':
                    assert target.name == 'jiffies', ('undefined-data', target.name)
                    address = JIFFIES + relocation['r_addend']
                elif target['st_shndx'] == index:
                    address = self.base + target['st_value'] + relocation['r_addend']
                else:
                    target_index = target['st_shndx']
                    assert isinstance(target_index, int)
                    if target_index not in self.data:
                        data = elf.get_section(target_index)
                        assert not data['sh_flags'] & 4 and len(data.data()) < 0x100000
                        address = 0x18000000 + list(BASES).index(label)*0x200000 + len(self.data)*0x100000
                        self.data[target_index] = (address, data.data())
                    address = self.data[target_index][0] + target['st_value'] + relocation['r_addend']
                if kind == RELOC['R_AARCH64_ADR_PREL_PG_HI21']:
                    assert word & 0x9f000000 == 0x90000000
                    pages = (address >> 12) - (pc >> 12)
                    assert -(1 << 20) <= pages < 1 << 20
                    immediate = pages & 0x1fffff
                    word = (word & ~0x60ffffe0) | ((immediate & 3) << 29) | ((immediate >> 2) << 5)
                elif kind == RELOC['R_AARCH64_LDST64_ABS_LO12_NC']:
                    assert word & 0xffc00000 == 0xf9400000 and address % 8 == 0
                    word = (word & ~0x003ffc00) | (((address & 4095) >> 3) << 10)
                else:
                    assert kind == RELOC['R_AARCH64_ADD_ABS_LO12_NC'], ('data-relocation', kind)
                    assert word & 0x7f000000 == 0x11000000 and not word & (1 << 22)
                    word = (word & ~0x003ffc00) | ((address & 4095) << 10)
                struct.pack_into('<I', self.text, offset, word)
        for rows in self.instructions.values():
            for pc, mnemonic, _ in rows:
                if mnemonic != 'bl' or pc in self.calls:
                    continue
                delta = (struct.unpack_from('<I', self.text, pc-self.base)[0] & 0x3ffffff) << 2
                if delta & (1 << 27):
                    delta -= 1 << 28
                name, = {symbol.name for symbol in symbols if symbol['st_shndx'] == index
                         and symbol['st_info']['type'] == 'STT_FUNC'
                         and self.base + symbol['st_value'] == pc + delta}
                self.calls[pc] = name
        required = {
            'mt7996_tx_token_put': {('mov','x1, #0x40a0'), ('mov','x0, #0x40a8'),
                                    ('strh','w1, [x20, #0xc2]'), ('str','wzr, [x0, #0x78]')},
            'mt7996_txwi_free': {('ldr','x2, [x19, #0x18]'), ('str','xzr, [x19, #0x18]')},
            '__mt76_tx_complete_skb': {('ldrb','w0, [x21, #0x52]'), ('ldrb','w1, [x21, #0x53]'),
                                        ('str','x3, [x21, #0x48]'), ('add','x0, x20, #0x8e8')},
            'mt76_put_txwi.part.0': {('add','x0, x0, #0x7e4'), ('str','x20, [x19, #0x33c0]')},
            'mt76_connac_tx_complete_skb': {('ldr','x2, [x1, #8]'), ('ldrh','w1, [x1, #0x24]')},
        }
        for name, operands in required.items():
            if name in self.instructions:
                actual = {(mnemonic, operand) for _, mnemonic, operand in self.instructions[name]}
                assert operands <= actual, ('fixture-ABI-operands',name,operands-actual)

    def contains(self, pc):
        return any(start <= pc < start + size for start, size in self.functions.values())


def link(modules):
    functions = {name: address for module in modules.values()
                 for name, (address, _) in module.functions.items()}
    for module in modules.values():
        for pc, name in module.calls.items():
            if name in functions:
                delta = functions[name] - pc
                assert delta % 4 == 0 and -(1 << 27) <= delta < 1 << 27
                struct.pack_into('<I', module.text, pc-module.base, 0x94000000 | ((delta >> 2) & 0x3ffffff))


class Replay:
    def __init__(self, modules, case, mutation=None):
        self.modules, self.case = modules, case
        self.cpu = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.functions = {name: address for module in modules.values()
                          for name, (address, _) in module.functions.items()}
        self.entries = dict.fromkeys(self.functions, 0)
        self.calls = {pc: name for module in modules.values() for pc, name in module.calls.items()}
        self.events, self.unmaps, self.statuses, self.frees, self.queries = [], [], [], [], []
        self.instructions, self.destroyed = 0, 0
        self.nops = set()
        targets = {'omit-token-release': 'mt7996_txwi_free', 'omit-IDR-destroy': 'idr_destroy',
                   'omit-SKB-completion': '__mt76_tx_complete_skb', 'omit-cache-put': 'mt76_put_txwi',
                   'omit-DMA-unmaps': 'dma_unmap_page_attrs', 'omit-SKB-free': 'dev_kfree_skb_any_reason'}
        for label, module in modules.items():
            text = bytearray(module.text)
            if mutation in targets:
                self.nops.update(pc for pc, name in module.calls.items() if name == targets[mutation])
            elif mutation in ('omit-token-decrement', 'omit-mgmt-reset', 'omit-SKB-clear') and label == 'radio':
                name = 'mt7996_txwi_free' if mutation == 'omit-SKB-clear' else 'mt7996_tx_token_put'
                operands = {'omit-token-decrement': {('strh', 'w1, [x20, #0xc2]')},
                            'omit-mgmt-reset': {('str', 'wzr, [x0, #0x78]')},
                            'omit-SKB-clear': {('str', 'xzr, [x19, #0x18]')}}[mutation]
                self.nops.update(pc for pc, mnemonic, operand in module.instructions[name]
                                 if (mnemonic, operand) in operands)
            for pc in self.nops:
                if module.base <= pc < module.base + len(text):
                    struct.pack_into('<I', text, pc-module.base, 0xd503201f)
            self.cpu.mem_map(module.base, 0x100000)
            self.cpu.mem_write(module.base, bytes(text))
            self.cpu.mem_protect(module.base, 0x100000, UC_PROT_READ | UC_PROT_EXEC)
            for address, payload in module.data.values():
                size = (len(payload)+4095) & ~4095
                self.cpu.mem_map(address, size)
                self.cpu.mem_write(address, payload)
                self.cpu.mem_protect(address, size, UC_PROT_READ)
        assert mutation is None or self.nops, ('missing-mutation', mutation)
        for address, size in ((DEV,0x10000),(STACK,0x10000),(TASK,0x1000),(DRIVER,0x1000),
                              (OBJECTS,0x10000),(SKBS,0x10000),(PHYS,0x10000),(HW,0x10000),
                              (ENTRY,0x1000),(END,0x1000),(JIFFIES,0x1000)):
            self.cpu.mem_map(address, size)
        self.cpu.reg_write(arm.UC_ARM64_REG_SP_EL0, TASK)
        self.put64(DEV+0x858, DRIVER)
        self.put32(DRIVER, DRIVER_FLAGS)
        self.cpu.mem_write(DRIVER+8, struct.pack('<H', 76))
        self.put64(DEV+0x878, DMA_DEV)
        self.put64(DEV, HW)
        self.put64(DEV+0x7d8, HW)
        self.put64(DEV+CACHE_HEAD, DEV+CACHE_HEAD)
        self.put64(DEV+CACHE_HEAD+8, DEV+CACHE_HEAD)
        self.put64(JIFFIES, 123456)
        for band in range(3):
            present = bool(case['phys'] & (1 << band))
            self.put64(DEV+0x790+8*band, PHYS+0x1000*band if present else 0)
            self.put64(PHYS+0x1000*band, HW+0x1000*(band+1))
            self.put32(PHYS+0x1000*band+0x78, 17+band)
        self.tokens, self.buffers, self.expected_unmaps, self.skb_bands = {}, {}, [], {}
        self.expected_status, self.expected_pending, self.expected_frees = [], [], []
        for ordinal, token in enumerate(case.get('tokens', ())):
            buffer, skb = OBJECTS+ordinal*512, SKBS+ordinal*512
            txwi = buffer+76
            has_skb = case['skbs'] == 'all' or case['skbs'] == 'mixed' and ordinal % 2 == 0
            self.put64(txwi+0x18, skb if has_skb else 0)
            self.cpu.mem_write(buffer+37, struct.pack('<H', 0x4aa))
            if case['format'] == 'FW':
                self.cpu.mem_write(buffer+39, bytes([2]))
                for index in range(2):
                    dma, length = 0x23400000+ordinal*8192+index*4096, 64+index
                    self.put32(buffer+40+index*4, dma)
                    self.cpu.mem_write(buffer+64+index*2, struct.pack('<H', length))
                    self.expected_unmaps.append([DMA_DEV,dma,length,1,0])
            else:
                self.put32(buffer+28, 1 << 27)
                dma = 0x23400000+ordinal*4096
                self.put32(buffer+40, dma)
                self.put32(buffer+44, (1 << 12) | 64)
                self.expected_unmaps.append([DMA_DEV,dma | (1 << 32),64,1,0])
            self.tokens[token] = txwi
            self.buffers[txwi] = skb if has_skb else 0
            if has_skb:
                self.prepare_skb(skb, case.get('status', 'immediate'), ordinal % 3)
        self.cpu.mem_write(DEV+TOKEN_COUNT, struct.pack('<H', len(self.tokens)))
        self.initial_tokens = dict(self.tokens)
        if case['mode'] == 'callback':
            skb = SKBS
            self.put64(ENTRY, 0 if case['kind'] == 'txwi-no-skb' else skb)
            self.put64(ENTRY+8, 0 if case['kind'] == 'no-txwi' else OBJECTS+76)
            self.cpu.mem_write(ENTRY+0x24, struct.pack('<H', 0x4aa))
            if case['kind'] == 'no-txwi':
                self.expected_frees.append(skb)
            elif case['kind'] == 'txwi-skb':
                self.prepare_skb(skb, 'immediate', case['band'])
        self.cpu.hook_add(UC_HOOK_CODE, self.code)

    def prepare_skb(self, skb, status, band):
        self.skb_bands[skb] = band
        self.put64(skb+0x28, band << 51)
        self.cpu.mem_write(skb+0x50, struct.pack('<H', 0x4aa))
        self.cpu.mem_write(skb+0x52, bytes([0 if status == 'immediate' else 3,
                                           2 if status == 'ready' else 0]))
        (self.expected_pending if status == 'pending' else self.expected_status).append(skb)

    def put64(self, address, value):
        self.cpu.mem_write(address, struct.pack('<Q', value))

    def put32(self, address, value):
        self.cpu.mem_write(address, struct.pack('<I', value))

    def get64(self, address):
        return struct.unpack('<Q', self.cpu.mem_read(address, 8))[0]

    def get32(self, address):
        return struct.unpack('<I', self.cpu.mem_read(address, 4))[0]

    def cache(self):
        head = DEV+CACHE_HEAD
        address, previous, result = self.get64(head), head, []
        while address != head:
            assert address in self.buffers and address not in result, 'TXWI-cache-integrity'
            assert self.get64(address+8) == previous, 'TXWI-cache-prev-link'
            result.append(address)
            previous = address
            address = self.get64(address)
        assert self.get64(head+8) == previous, 'TXWI-cache-tail-link'
        return result

    def returned(self, pc, value=0):
        for index in range(18):
            self.cpu.reg_write(REGS[index], value if index == 0 else 0xbad00000+index)
        self.cpu.reg_write(arm.UC_ARM64_REG_NZCV, 0xa0000000)
        self.cpu.reg_write(arm.UC_ARM64_REG_X30, pc+4)
        self.cpu.reg_write(arm.UC_ARM64_REG_PC, pc+4)

    def code(self, cpu, pc, size, _data):
        assert size == 4 and any(module.contains(pc) for module in self.modules.values()), ('unexpected-PC', hex(pc))
        self.instructions += 1
        for name, address in self.functions.items():
            if pc == address:
                self.entries[name] += 1
                self.events.append(dict(kind='native-entry', name=name))
                if name == 'mt76_put_txwi':
                    txwi = cpu.reg_read(REGS[1])
                    assert self.get64(txwi+0x18) == 0, 'SKB-cleared-before-cache'
                    ordinal = list(self.buffers).index(txwi)
                    count = (2 if self.case['format'] == 'FW' else 1)*(ordinal+1)
                    assert self.unmaps == self.expected_unmaps[:count], 'DMA-before-cache'
                    skb = self.buffers[txwi]
                    if skb:
                        if skb in self.expected_pending:
                            assert self.cpu.mem_read(skb+0x53,1) == b'\x01', 'pending-SKB-before-cache'
                        else:
                            assert skb in self.statuses, 'SKB-status-before-cache'
        if pc in self.nops or pc not in self.calls:
            return
        name = self.calls[pc]
        args = tuple(cpu.reg_read(REGS[index]) for index in range(5))
        if name in self.functions:
            return
        self.events.append(dict(kind='modeled-kernel-call', name=name, arguments=list(args)))
        result = 0
        if name == 'idr_get_next':
            assert args[0] == DEV+TOKEN_IDR and self.get32(DEV+TOKEN_LOCK) == 1
            completed = len(self.queries)
            remaining = struct.unpack('<H', cpu.mem_read(DEV+TOKEN_COUNT,2))[0]
            assert remaining == len(self.initial_tokens)-completed, 'token-count-progress'
            previous = list(self.initial_tokens.values())[:completed]
            assert self.cache() == list(reversed(previous)), 'TXWI-cache-membership'
            start = self.get32(args[1])
            found = next((token for token in sorted(self.tokens) if token >= start), None)
            self.queries.append([start, found])
            if found is not None:
                self.put32(args[1], found)
                result = self.tokens[found]
        elif name == 'idr_destroy':
            assert args[0] == DEV+TOKEN_IDR and self.get32(DEV+TOKEN_LOCK) == 0
            self.destroyed += 1
            self.tokens.clear()
        elif name == '__local_bh_enable_ip':
            assert args[1] == 0x200 and self.get32(TASK+0x10) >= 0x200
            self.put32(TASK+0x10, self.get32(TASK+0x10)-0x200)
        elif name == 'dma_unmap_page_attrs':
            self.unmaps.append(list(args))
        elif name == 'ieee80211_tx_status_ext':
            skb = self.get64(args[1]+16)
            band = self.skb_bands[skb]
            expected_hw = HW+0x1000*(band+1) if band in (1,2) and self.case['phys'] & (1 << band) else HW
            assert args[0] == expected_hw and self.get64(args[1]) == 0, 'SKB-status-owner'
            assert self.get64(skb+0x28) & (3 << 51) == 0, 'SKB-queue-PHY-bits-cleared'
            self.statuses.append(skb)
        elif name == 'dev_kfree_skb_any_reason':
            assert args[1] == 2, 'SKB-free-reason'
            self.frees.append(args[0])
        elif name == 'memset':
            assert STACK <= args[0] < STACK+0x10000 and 0 <= args[2] <= 256
            cpu.mem_write(args[0], bytes([args[1] & 255])*args[2])
            result = args[0]
        else:
            raise AssertionError(('unmodeled-kernel-call', name, hex(pc)))
        self.returned(pc, result)

    def run(self):
        name = 'mt7996_tx_token_put' if self.case['mode'] == 'tokens' else 'mt76_connac_tx_complete_skb'
        self.cpu.reg_write(REGS[0], DEV)
        self.cpu.reg_write(REGS[1], ENTRY)
        self.cpu.reg_write(arm.UC_ARM64_REG_SP, STACK+0xf000)
        self.cpu.reg_write(arm.UC_ARM64_REG_X30, END)
        self.cpu.emu_start(self.functions[name], END, timeout=3_000_000, count=500000)
        assert self.cpu.reg_read(arm.UC_ARM64_REG_PC) == END, 'bounded-native-return'
        assert self.unmaps == self.expected_unmaps, 'DMA-argument-contract'
        assert self.statuses == self.expected_status, 'SKB-status-count'
        assert self.frees == self.expected_frees, 'SKB-free-count'
        if self.case['mode'] == 'tokens':
            assert self.cache() == list(reversed(self.initial_tokens.values())), 'TXWI-cache-membership'
            assert all(self.get64(txwi+0x18) == 0 for txwi in self.buffers), 'all-token-SKB-fields-cleared'
            assert struct.unpack('<H', self.cpu.mem_read(DEV+TOKEN_COUNT,2))[0] == 0, 'token-count-zero'
            assert self.destroyed == 1 and not self.tokens, 'IDR-destroy-once'
            assert len(self.queries) == len(self.initial_tokens)+1, 'complete-sparse-token-iteration'
            for band in range(3):
                expected = 0 if self.case['phys'] & (1 << band) else 17+band
                assert self.get32(PHYS+0x1000*band+0x78) == expected, 'mgmt-pending-reset'
        assert self.get32(TASK+0x10) == 0, 'bottom-half-depth-balanced'
        assert self.get32(DEV+TOKEN_LOCK) == self.get32(DEV+0x7e4) == self.get32(DEV+0x8e8) == self.get32(DEV+0x4108) == 0, 'spinlocks-released'
        for skb in self.expected_pending:
            assert self.cpu.mem_read(skb+0x53,1) == b'\x01', 'SKB-awaits-TX-status'
            assert self.get64(skb+0x48) == 123456, 'pending-SKB-jiffies'
        return dict(case=self.case, instructions=self.instructions, native_entries=self.entries,
                    unmaps=self.unmaps, modeled_status_completions=self.statuses,
                    modeled_SKB_frees=self.frees, SKBs_awaiting_TX_status=self.expected_pending,
                    token_queries=self.queries, TXWI_cache=self.cache(), events=self.events)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--producer', type=Path, required=True)
    parser.add_argument('--expected-producer-sha256', default=PRODUCER_SHA)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--mac-source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--inspect-only', action='store_true')
    args = parser.parse_args()
    assert sha(args.producer) == args.expected_producer_sha256
    producer = json.loads(args.producer.read_bytes())
    assert producer['passed'] and producer['originals_unchanged']
    context_path = args.producer.parent/'context.json'
    context = json.loads(context_path.read_bytes())
    filenames = dict(core='mt76.ko', radio='mt7996/mt7996e.ko', connac='mt76-connac-lib.ko')
    paths = {label: args.producer.parent/'mt76'/name for label, name in filenames.items()}
    inputs = {str(path.resolve()): sha(path) for path in (args.producer, context_path, *paths.values(), Path(__file__))}
    for name in ('mt7996/mac.c', 'mt7996/mmio.c', 'mt7996/mt7996.h', 'mt76_connac_mac.c', 'tx.c', 'dma.c', 'mt76.h'):
        path = args.mac_source if name == 'mt7996/mac.c' and args.mac_source else args.source/name
        assert sha(path) == context['mt76_sources'][name]['sha256'], ('source-module-profile-mismatch', name)
        inputs[str(path.resolve())] = sha(path)
    for module in list(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename:
            path = Path(filename).resolve()
            if path.is_file() and any(path.is_relative_to(ROOT/directory) for directory in ('tests','tools')):
                inputs[str(path)] = sha(path)
    modules = {label: Module(path, label, producer['inner']['modules'][filenames[label]]['sha256'])
               for label, path in paths.items()}
    link(modules)
    inspection = {label: dict(functions=module.functions, calls=module.calls, instructions=module.instructions)
                  for label, module in modules.items()}
    args.output.mkdir(parents=True)
    if args.inspect_only:
        result = dict(passed=True, inspection_only=True, inputs=inputs, modules=inspection)
    else:
        cases = [dict(mode='tokens', tokens=[], phys=phys, skbs='none', format='FW') for phys in (0,1,5,7)]
        for tokens in ((0,), (7,), (0,3,8191), (0,8192,16383)):
            for skbs in ('none','all','mixed'):
                for format_ in ('FW','MAC'):
                    for phys in (0,5):
                        cases.append(dict(mode='tokens', tokens=list(tokens), skbs=skbs, format=format_, phys=phys))
        for status in ('pending','ready'):
            cases.append(dict(mode='tokens', tokens=[0,3,8191], skbs='all', format='FW', phys=5, status=status))
        cases += [dict(mode='callback', kind=kind, phys=0) for kind in ('no-txwi','txwi-no-skb')]
        cases += [dict(mode='callback', kind='txwi-skb', band=band, phys=phys)
                  for band in range(3) for phys in (0,7)]
        rows = []
        for case in cases:
            replay = Replay(modules, case)
            try:
                rows.append(replay.run())
            except Exception as error:
                with (args.output/'failure.json').open('x') as stream:
                    json.dump(dict(case=case,error=str(error),events=replay.events,
                                   native_entries=replay.entries,inputs=inputs),stream,indent=2)
                raise
            del replay
            gc.collect()
        controls = []
        probe = dict(mode='tokens', tokens=[0,3,8191], skbs='all', format='MAC', phys=5)
        for mutation, assertion in (
                ('omit-token-release','TXWI-cache-membership'), ('omit-token-decrement','token-count-progress'),
                ('omit-IDR-destroy','IDR-destroy-once'), ('omit-SKB-completion','SKB-status-before-cache'),
                ('omit-cache-put','TXWI-cache-membership'), ('omit-DMA-unmaps','DMA-before-cache'),
                ('omit-mgmt-reset','mgmt-pending-reset'), ('omit-SKB-clear','SKB-cleared-before-cache'),
                ('omit-SKB-free','SKB-free-count')):
            case = dict(mode='callback', kind='no-txwi', phys=0) if mutation == 'omit-SKB-free' else probe
            try:
                Replay(modules, case, mutation).run()
            except AssertionError as error:
                assert str(error) == assertion, (mutation, str(error), assertion)
                controls.append(dict(mutation=mutation, failed_assertion=assertion, emulator_bytes_only=True))
            else:
                raise AssertionError(('mutation-survived', mutation))
        entered = {name:sum(row['native_entries'][name] for row in rows)
                   for name in rows[0]['native_entries']}
        result = dict(passed=True, cases=len(rows), controls=controls, rows=rows, inputs=inputs,
                      producer_sha256=sha(args.producer), modules=inspection,
                      native_entry_totals=entered,
                      selected_but_unentered=[name for name,count in entered.items() if not count],
                      IDR_mac80211_DMA_and_physical_effects_are_models=True,
                      MT7996_driver_flags=DRIVER_FLAGS,
                      nonempty_status_IDR_and_station_power_save_not_executed=True,
                      current_FW_high_DMA_fix_acceptance=False, hardware=False)
    for filename, digest in inputs.items():
        assert sha(Path(filename)) == digest, ('input-changed', filename)
    with (args.output/'result.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(passed=True, inspect_only=args.inspect_only, cases=result.get('cases'),
                         controls=len(result.get('controls', ())), inputs=len(inputs))))


if __name__ == '__main__':
    main()
