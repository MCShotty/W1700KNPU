#!/usr/bin/env python3
"""Cold TXDONE callback guards against original native producers and consumers."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from types import SimpleNamespace

sys.dont_write_bytecode = True
from unicorn import riscv_const as r
from elftools.elf.elffile import ELFFile

from test_allocator_startup import StartupCore, advance, build as build_startup
from test_allocator_reset import build as build_reset
from test_barrier_core5 import jump
from test_barrier_protocol import Rv32
from test_bridge_startup import build_guard, GUARDS, input_bindings
from test_attach_tx_callbacks import done_oracle, HOST, HOST_BYTES, SKB_STATE, SKB_BYTES, REGS, DONE_TARGETS
from test_attach_rx_callbacks import REGISTERS
from test_mt7996_bootstrap_sequence import SET_CALLBACKS, expected, TXFREE
from test_bootstrap_native import ROOT, ADM, BOOT, REQUEST
from test_boot_irq_installation import UnmodeledAccess
from test_firmware_mailbox_dispatch import MBOX, PAYLOAD, ISR
from test_firmware_memory_layout import STACK_TOPS, table
from test_firmware_stop_counterexample import END
from test_multihart_cold_boot import ELF, ELF_SHA
from emulation_layout import CODE, SRAM, SRAM_BYTES, HEAP, HEAP_BYTES, STATE

OUT = ROOT/'research/checkpoints/2026-09-09-npu-txdone-init'
BUILD = ROOT/'.local/npu-txdone-init'
SOURCE = ROOT/'tests/npu/txdone-init-emulation.c'
ASM, LINKER = SOURCE.with_suffix('.S'), SOURCE.with_suffix('.ld')
SITES = {
    0x8400fe34: ('npu_emulation_txdone_callback', '0c410845'),
    0x84004d92: ('npu_emulation_txdone_bufid_guard', '97d68fba'),
    0x84004a28: ('npu_emulation_txdone_lock19_guard', '14c3c18f'),
    0x84004a3a: ('npu_emulation_txdone_lock20_guard', '97650100'),
    0x84004b08: ('npu_emulation_txdone_temp_guard', '83170e00'),
    0x8400b546: ('npu_emulation_txdone_publish_guard', '97878fba'),
}
OWNER = {28: 0x1ec03070, 19: 0x1ec0304c, 20: 0x1ec03050}
SPACES = ((SRAM, SRAM_BYTES), (HEAP, HEAP_BYTES), (0x3e880000, 0x40000),
          (HOST, HOST_BYTES), (SKB_STATE, SKB_BYTES))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build(source=SOURCE, tag='txdone-init', assembly=ASM):
    assert sha(ELF.read_bytes()) == ELF_SHA
    BUILD.mkdir(parents=True, exist_ok=True)
    path = BUILD/(tag+'.elf')
    lld = shutil.which('ld.lld') or str(ROOT/'.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld')
    command = [shutil.which('clang'), '--target=riscv32', '-march=rv32imac_zicsr',
               '-mabi=ilp32', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-fno-builtin',
               '-nostdlib', '-fno-stack-protector', f'--ld-path={lld}',
               '-I', str(ROOT/'firmware/npu'), str(source), str(assembly),
               '-Wl,-T,'+str(LINKER), '-Wl,--no-relax', '-Wl,--just-symbols='+str(ELF),
               '-o', str(path)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout+result.stderr
    return path, command


def images(h):
    return {address: bytearray(h.cpu.mem_read(address, size)) for address, size in SPACES}


class ColdTx(StartupCore):
    def __init__(self, startup_path, reset_path):
        self.txdone_tracking = False
        self.txdone_owners = Counter()
        self.txdone_deny = None
        self.txdone_temp_reads = []
        self.txdone_mutate = False
        self.txdone_entries = Counter()
        self.txdone_ids = []
        self.txdone_counts = []
        self.txdone_min_sp = STACK_TOPS[0]
        self.txdone_writes = set()
        self.txdone_write_ordinal = 0
        self.txdone_ready_writes = []
        self.host_limit = HOST_BYTES
        super().__init__(startup_path, reset_path)
        for base in sorted({address & ~0xfff for address in REGS}):
            self.cpu.mem_map(base, 0x1000)
        self.cpu.mem_map(HOST, HOST_BYTES)
        self.cpu.mem_write(HOST, b'\xa5'*HOST_BYTES)
        for address in OWNER.values():
            self.put32(address, 0x10000)
        guards, _ = build_guard()
        guard = Rv32(guards, self.cpu)
        self.bridge_patches = []
        for site, (kind, before) in GUARDS.items():
            assert bytes(self.cpu.mem_read(site, 4)).hex() == before
            target = guard.symbols[f'npu_emulation_bridge_{kind}_guard']
            self.cpu.mem_write(site, jump(site, target))
            self.bridge_patches.append(site)

    def is_memory(self, address, size):
        if HOST <= address < HOST+HOST_BYTES:
            return address+size <= HOST+self.host_limit
        return super().is_memory(address, size)

    def register_model(self, address, write):
        if address == self.missing:
            return None
        if address in REGISTERS:
            kind, _, description = REGISTERS[address]
            return description if write == (kind == 'write') else None
        if address in REGS:
            return 'TX host setup storage model; no DMA/coherency proof' if write else None
        if address in (0x1ec031d0, 0x1ec03250):
            return 'SKB lock20 request/release storage model' if write else None
        if address == 0x1ec03050:
            return 'SKB lock20 modeled owner input' if not write else None
        return super().register_model(address, write)

    def read_hook(self, cpu, access, address, size, value, data):
        if self.txdone_tracking:
            pc = cpu.reg_read(r.UC_RISCV_REG_PC)
            if address in OWNER.values():
                owner = next(key for key, addr in OWNER.items() if addr == address)
                self.txdone_owners[owner] += 1
                denied = self.txdone_deny == (owner, self.txdone_owners[owner])
                self.put32(address, 0x10100 if denied else 0x10000)
            load = self.txdone_rv.symbols['npu_emulation_txdone_temp_load']
            if pc in (0x84004b08, load):
                self.txdone_temp_reads.append(address)
        super().read_hook(cpu, access, address, size, value, data)

    def write_hook(self, cpu, access, address, size, value, data):
        if self.txdone_tracking and any(base <= address < base+length for base, length in SPACES):
            self.txdone_writes.update(range(address, address+size))
            self.txdone_write_ordinal += 1
            if address <= SRAM+0x46fa < address+size:
                self.txdone_ready_writes.append(dict(pc=hex(cpu.reg_read(r.UC_RISCV_REG_PC)),
                    address=hex(address), size=size, value=value, ordinal=self.txdone_write_ordinal))
        if self.txdone_tracking and SKB_STATE <= address < SKB_STATE+SKB_BYTES:
            self.access(address, size, value, True)
            return
        super().write_hook(cpu, access, address, size, value, data)

    def code_hook(self, cpu, pc, size, data):
        if pc == 0x8400dd82:
            assert cpu.reg_read(r.UC_RISCV_REG_A1) in (0, 2, 10), 'unselected DESC callback'
        if self.txdone_tracking:
            self.txdone_entries[pc] += 1
            self.txdone_min_sp = min(self.txdone_min_sp, cpu.reg_read(r.UC_RISCV_REG_SP))
            if pc == 0x8400b4e4:
                self.txdone_ids.append(cpu.reg_read(r.UC_RISCV_REG_A0))
            if pc == 0x8400b432:
                self.txdone_counts.append(cpu.reg_read(r.UC_RISCV_REG_A0))
            if self.txdone_mutate and pc == self.txdone_rv.symbols['npu_original_desc_callback']:
                self.put32(PAYLOAD+8, 513)
                self.txdone_mutate = False
        super().code_hook(cpu, pc, size, data)

    def packet(self, words, entry=None):
        self.cpu.mem_write(PAYLOAD, struct.pack('<3I', *words))
        self.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 0)
        return self.call_callback(SET_CALLBACKS[words[1]] if entry is None else entry, PAYLOAD)

    def call_callback(self, entry, argument):
        self.cpu.reg_write(r.UC_RISCV_REG_SP, STACK_TOPS[0])
        self.cpu.reg_write(r.UC_RISCV_REG_RA, END)
        self.cpu.reg_write(r.UC_RISCV_REG_A0, argument)
        self.cpu.emu_start(entry, END, count=3000000, timeout=60000000)
        assert self.cpu.reg_read(r.UC_RISCV_REG_PC) == END, (
            hex(self.cpu.reg_read(r.UC_RISCV_REG_PC)), self.txdone_entries.most_common(4))
        return self.cpu.reg_read(r.UC_RISCV_REG_A0)

    def setup(self):
        advance(self)
        assert self.packet([0x10, 14, 2]) == 1
        for selector, count in ((0, 1536), (2, 1024)):
            assert self.packet([0x10|selector, 1, count]) == 1
        for message in expected(0, 2):
            if message['kind'] == 'message' and message['api'] == 19:
                assert self.packet([message['word0'], 19, message['value']]) == 1
        for api, value in ((33, 8192), (22, TXFREE)):
            assert self.packet([0x10, api, value]) == 1
        assert self.get32(SRAM+0x3964) == HOST
        assert self.get32(SRAM+0x1b88) == HEAP+32
        for owner in range(1, 8):
            self.worker(owner)
        self.hart = 0
        self.cpu.context_restore(self.contexts[0])
        self.fixed = {row['type']: row['value'] for row in table(self.code, 0x8401cf70)}
        self.saved_banks = deepcopy(self.plic_banks)
        self.saved_memory = [(lo, bytes(self.cpu.mem_read(lo, hi-lo+1)))
                             for lo, hi, _ in self.cpu.mem_regions()]
        self.saved_context = self.cpu.context_save()

    def restore(self, path, enabled=True, omit=None):
        self.txdone_tracking = False
        self.cpu.context_restore(self.saved_context)
        for address, data in self.saved_memory:
            self.cpu.mem_write(address, data)
        self.plic_banks = deepcopy(self.saved_banks)
        self.txdone_rv = Rv32(path, self.cpu)
        self.txdone_patches = []
        for site, (name, before) in SITES.items():
            assert bytes(self.cpu.mem_read(site, 4)).hex() == before
            if enabled and site != omit:
                replacement = jump(site, self.txdone_rv.symbols[name])
                self.cpu.mem_write(site, replacement)
                self.txdone_patches.append(dict(site=hex(site), before=before, after=replacement.hex(), name=name))
        self.cpu.ctl_remove_cache(CODE, CODE+0x201000)
        self.mmio.clear()
        self.logs.clear()
        self.stub_counts.clear()
        self.txdone_owners.clear()
        self.txdone_deny = None
        self.txdone_temp_reads = []
        self.txdone_entries.clear()
        self.txdone_ids = []
        self.txdone_counts = []
        self.txdone_min_sp = STACK_TOPS[0]
        self.txdone_writes.clear()
        self.txdone_write_ordinal = 0
        self.txdone_ready_writes = []
        self.txdone_mutate = False
        self.host_limit = HOST_BYTES
        self.hart = 0
        self.unmodeled = None

    def invoke(self, count, irq=False, mutate=False, header=0x1a, api=1):
        self.cpu.mem_write(PAYLOAD, struct.pack('<3I', header, api, count))
        self.put32(MBOX+0x30, REQUEST)
        self.put32(MBOX+0x34, 12)
        self.put32(MBOX+0x3c, 1)
        self.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 0)
        self.txdone_mutate = mutate
        self.txdone_tracking = True
        try:
            result = self.call_callback(ISR if irq else 0x8400fe34, 8 if irq else PAYLOAD)
        finally:
            self.txdone_tracking = False
        assert self.cpu.reg_read(r.UC_RISCV_REG_SP) == STACK_TOPS[0]
        assert self.txdone_min_sp >= STACK_TOPS[0]-0x4000
        assert not self.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
        assert set(self.stub_counts) <= {'0x840048f4', '0x84004212', 'mhartid-csr'}, self.stub_counts
        return dict(result=result, ready=self.cpu.mem_read(SRAM+0x46fa, 1)[0],
                    mailbox_flags=self.get32(MBOX+0x3c), owner_reads=dict(self.txdone_owners),
                    temporary_reads=len(self.txdone_temp_reads), min_sp=hex(self.txdone_min_sp),
                    temporary_read_first_last=[hex(a) for a in self.txdone_temp_reads[:1]+self.txdone_temp_reads[-1:]],
                    temporary_unique_reads=len(set(self.txdone_temp_reads)),
                    ready_writes=self.txdone_ready_writes, memory_write_events=self.txdone_write_ordinal,
                    fault=self.get32(ADM+8), patches=self.txdone_patches,
                    descriptor_counts=self.txdone_counts.copy(), returned_ids=self.txdone_ids.copy(),
                    native_helper_entries={hex(pc): self.txdone_entries[pc] for pc in DONE_TARGETS},
                    substitutions=dict(self.stub_counts),
                    mmio=self.mmio.copy())


def partial_oracle(h, count, allocated, empty=False):
    result = images(h)
    writes = set()
    def read(address, fmt='I'):
        for base, data in result.items():
            if base <= address and address+struct.calcsize('<'+fmt) <= base+len(data):
                return struct.unpack_from('<'+fmt, data, address-base)[0]
        raise AssertionError('oracle address outside images')
    def put(address, value, fmt='I'):
        for base, data in result.items():
            encoded = struct.pack('<'+fmt, value)
            if base <= address and address+len(encoded) <= base+len(data):
                data[address-base:address-base+len(encoded)] = encoded
                writes.update(range(address, address+len(encoded)))
                return
        raise AssertionError('oracle write outside images')
    ids_base = h.fixed[0x107]
    head, pool = read(SRAM+0x1ba4, 'H'), read(SRAM+0x1b88)
    packet_base, descriptors, stats = (read(SRAM+offset) for offset in (0x396c, 0x3964, 0x1f08))
    put(SRAM+0x2a7c, count & 0xffff, 'H')
    put(SRAM+0x2cf4, ids_base)
    for index in range(allocated):
        bufid = read(pool+((head+index) % 16384)*2, 'H')
        put(descriptors+index*16, ((packet_base+bufid*2048) & 0x3fffffff | 0x80000000)+128)
        put(descriptors+index*16+4, 0x07000100)
        put(descriptors+index*16+8, 0)
        put(descriptors+index*16+12, 0)
        put(ids_base+index*2, bufid, 'H')
    if allocated:
        put(SRAM+0x1ba4, (head+allocated) % 16384, 'H')
        put(SRAM+0x1b90, read(SRAM+0x1b90)+allocated)
        put(stats+0x1c, read(stats+0x1c)+allocated)
    if empty:
        put(stats+0x20, read(stats+0x20)+1)
    for address in (ADM, ADM+8, STATE+16):
        put(address, 1)
    return result, writes


def lock_oracle(count, allocated, outcome, corrected, denied):
    operations = []
    def request(owner):
        operations.append((0x1ec03180+owner*4, 0x40))
    def release(owner):
        operations.append((0x1ec03200+owner*4, 0))
    if outcome == 'reject':
        return operations
    for _ in range(allocated):
        request(28)
        release(28)
    if allocated != count:
        request(28)
        if not corrected or denied != (28, allocated+1):
            release(28)
        return operations
    request(19)
    if corrected and denied == (19, 1):
        return operations
    request(20)
    if not corrected or denied != (20, 1):
        release(20)
    release(19)
    return operations


def exercise(h, path, name, *, corrected=True, count=512, outcome='full',
             available=None, denied=None, edit=None, allocated=0, irq=False,
             mutate=False, header=0x1a, api=1, omit=None):
    h.restore(path, corrected, omit)
    h.put32(ADM+4, 1)
    h.put32(SRAM+0x3974, 0x87654321)
    if available is not None:
        head = int.from_bytes(h.cpu.mem_read(SRAM+0x1ba4, 2), 'little')
        h.cpu.mem_write(SRAM+0x1b80, struct.pack('<H', (head+available+1) % 16384))
    if edit:
        edit(h)
    h.txdone_deny = denied
    before = images(h)
    if outcome == 'full':
        want, writes, footprint = done_oracle(SimpleNamespace(h=h, fixed=h.fixed), count)
        allocated = footprint['allocated']
    elif outcome == 'reject':
        want = before
        writes = set()
    else:
        assert outcome == 'partial'
        want, writes = partial_oracle(h, count, allocated, empty=available is not None and allocated == available)
        if not corrected:
            for address in (ADM+8, STATE+16):
                struct.pack_into('<I', want[SRAM], address-SRAM, 0)
            for address in (ADM, ADM+8, STATE+16):
                writes.difference_update(range(address, address+4))
    row = h.invoke(count, irq, mutate, header, api)
    expected_result = int(outcome == 'full' or not corrected)
    if irq:
        assert row['mailbox_flags'] == (7 if expected_result else 3), (name, row['mailbox_flags'])
    else:
        assert row['result'] == expected_result, f'{name}: callback status'
        assert row['mailbox_flags'] == 1
    assert row['descriptor_counts'] == ([] if outcome == 'reject' else [count]), 'descriptor count after validation'
    actual = images(h)
    assert actual == want, (name, 'whole-memory mismatch', [(hex(base), next((hex(i) for i, (a, b) in enumerate(zip(actual[base], want[base])) if a != b), None))
                                  for base in want if actual[base] != want[base]])
    assert h.txdone_writes == writes, (name, 'exact write extent',
                                      len(h.txdone_writes-writes), len(writes-h.txdone_writes))
    if outcome == 'full':
        assert row['temporary_reads'] == (2048 if corrected else h.get32(SRAM+0xbc0)), 'temporary ID read bound'
        base = h.get32(SRAM+0x1bc0)
        assert h.txdone_temp_reads == list(range(base, base+row['temporary_reads']*2, 2)), 'temporary read addresses'
        assert len(row['ready_writes']) == 1 and row['ready_writes'][0]['size'] == 1
        assert row['ready_writes'][0]['value'] == 1
        assert row['ready_writes'][0]['ordinal'] == row['memory_write_events'], 'ready must publish last'
    else:
        assert row['temporary_reads'] == 0
        assert not row['ready_writes'], 'failed/rejected request must not publish ready'
    assert row['ready'] == (want[SRAM][0x46fa])
    assert row['native_helper_entries']['0x840049f0'] == int(outcome != 'reject' and allocated == count)
    assert row['native_helper_entries']['0x84009aa6'] == int(outcome == 'full')
    if corrected and outcome == 'reject':
        assert not row['descriptor_counts'] and not row['owner_reads']
    register_writes = [(int(e['address'], 16), e['value']) for e in row['mmio']
                       if e['kind'] == 'mmio-write' and 0x1ec03180 <= int(e['address'], 16) < 0x1ec03300]
    wanted_locks = lock_oracle(count, allocated, outcome, corrected, denied)
    assert register_writes == wanted_locks, (name, 'lock request/release order')
    wanted_reads = {owner: sum(address == 0x1ec03180+owner*4 for address, _ in wanted_locks)
                    for owner in OWNER if any(address == 0x1ec03180+owner*4 for address, _ in wanted_locks)}
    assert row['owner_reads'] == wanted_reads, (name, 'lock owner read count')
    row['locks'] = {owner: dict(requested=wanted_reads.get(owner, 0),
                               released=sum(address == 0x1ec03200+owner*4 for address, _ in register_writes))
                    for owner in OWNER}
    row.update(name=name, corrected=corrected, outcome=outcome, requested_count=count,
               allocated=allocated, irq_entry=irq, mutate_after_validation=mutate,
               whole_memory_compared=sum(size for _, size in SPACES),
               exact_memory_write_bytes=len(writes), exact_lock_write_order=True,
               image_sha256={hex(base): sha(data) for base, data in actual.items()},
               prior_memory_unchanged=actual == before)
    del row['mmio']
    return row


def mutations(h, path):
    rows = []
    for name, old, new, arguments, witness in (
        ('omit-count-bound', '!packet->value || packet->value > 512 ||', '',
         dict(count=513, outcome='reject'), 'callback status'),
        ('omit-private-snapshot', 'npu_original_desc_callback(&snapshot)', 'npu_original_desc_callback(packet)',
         dict(count=1, mutate=True), 'descriptor count after validation'),
        ('omit-callback-failure',
         'if (load(&BARRIER->fault) || *(const volatile uint8_t *)(uintptr_t)0x3e9046fau != 1)', 'if (0)',
         dict(available=17, allocated=17, outcome='partial'), 'callback status'),
    ):
        text = SOURCE.read_text()
        assert text.count(old) == 1
        source = BUILD/(name+'.c')
        source.write_text(text.replace(old, new))
        mutant, _ = build(source, name)
        try:
            exercise(h, mutant, name, **arguments)
        except AssertionError as error:
            assert witness in str(error), (name, 'unexpected mutation failure', str(error))
            rows.append(dict(name=name, detected=True, witness=str(error), elf_sha256=sha(mutant.read_bytes())))
        else:
            raise AssertionError(('undetected mutation', name))
    for name, site, arguments, witness in (
        ('omit-bufid-ownership', 0x84004d92, dict(denied=(28, 18), allocated=17, outcome='partial'), 'callback status'),
        ('omit-lock19-ownership', 0x84004a28, dict(denied=(19, 1), allocated=512, outcome='partial'), 'callback status'),
        ('omit-lock20-ownership', 0x84004a3a, dict(denied=(20, 1), allocated=512, outcome='partial'), 'callback status'),
        ('omit-temporary-read-bound', 0x84004b08, {}, 'temporary ID read bound'),
        ('omit-failed-publication-guard', 0x8400b546, dict(denied=(20, 1), allocated=512, outcome='partial'), 'whole-memory mismatch'),
    ):
        try:
            exercise(h, path, name, omit=site, **arguments)
        except AssertionError as error:
            assert witness in str(error), (name, 'unexpected mutation failure', str(error))
            rows.append(dict(name=name, detected=True, site=hex(site), witness=str(error)))
        else:
            raise AssertionError(('undetected mutation', name))
    return rows


def closed_and_unselected(h, path):
    h.restore(path)
    before = images(h)
    h.txdone_tracking = True
    try:
        result = h.message([0x1a, 1, 512])
    finally:
        h.txdone_tracking = False
    assert result['flags'] == 3 and images(h) == before
    assert not result['callbacks'] and not h.txdone_entries[0x8400fe34]
    assert not h.txdone_writes and not h.txdone_ready_writes
    rows = [dict(name='strict-api1-selector10-still-rejected', result=result)]
    for selector, count in ((0, 1536), (2, 1024)):
        pairs = []
        for corrected in (False, True):
            h.restore(path, corrected)
            h.txdone_tracking = True
            try:
                value = h.packet([0x10|selector, 1, count])
            finally:
                h.txdone_tracking = False
            assert value == 1 and not h.txdone_counts and not h.txdone_ready_writes
            pairs.append(dict(images=images(h), writes=h.txdone_writes.copy(),
                              mmio=[(e['kind'], e['address'], e['size'], e['value']) for e in h.mmio]))
        assert pairs[0] == pairs[1], 'unselected RX fallback changed'
        rows.append(dict(name=f'unselected-rx{selector}-unchanged', requested_count=count,
                         whole_memory_compared=sum(size for _, size in SPACES),
                         written_bytes=len(pairs[0]['writes']), exact_memory_mmio_and_writes_equal=True))
    return rows


def missing_models(h, path):
    rows = []
    for name, missing, backing in (
        ('missing-owner28', OWNER[28], HOST_BYTES),
        ('missing-owner19', OWNER[19], HOST_BYTES),
        ('missing-owner20', OWNER[20], HOST_BYTES),
        ('missing-host-descriptor512-backing', None, 511*16),
    ):
        h.restore(path)
        h.missing, h.host_limit = missing, backing
        try:
            h.invoke(512)
        except UnmodeledAccess as error:
            expected = missing if missing else HOST+backing+4
            assert f'{expected:#x}/4' in str(error), (name, str(error))
            assert not h.txdone_ready_writes
            rows.append(dict(name=name, boundary=str(error), modeled_environment_rejected=True,
                             firmware_backing_validation_claimed=False, ready_writes=0))
        else:
            raise AssertionError(('missing model not rejected', name))
        finally:
            h.missing = None
    return rows


def retained_gate(path, startup, reset, bridge_bytes=None, install_extra=None):
    h = ColdTx(startup, reset)
    if bridge_bytes is not None:
        assert h.get32(0x8401b230) == 58879
        h.put32(0x8401b230, bridge_bytes)
    extra = install_extra(h) if install_extra is not None else []
    h.txdone_rv = Rv32(path, h.cpu)
    patches = []
    for site, (name, before) in SITES.items():
        assert bytes(h.cpu.mem_read(site, 4)).hex() == before
        replacement = jump(site, h.txdone_rv.symbols[name])
        h.cpu.mem_write(site, replacement)
        patches.append(dict(site=hex(site), before=before, after=replacement.hex(), name=name))
    h.setup()
    words = list(struct.unpack('<26I', h.cpu.mem_read(STATE, 104)))
    assert words == [1, 0, 0, 0, 0]+[1]*8+[0]*13
    assert h.get32(ADM) == 1 and h.get32(ADM+4) == h.get32(ADM+8) == 0
    assert h.cpu.mem_read(SRAM+0x46fa, 1) == b'\x00'
    assert not any(row['type'] == 0x81 for row in h.allocation_entries)
    all_patches = h.patches+h.reset_patches+[h.allocator_patch]+patches+extra
    all_sites = [int(row['site'], 16) for row in all_patches]+h.bridge_patches
    assert len(all_sites) == len(set(all_sites)) == 37+len(extra)
    return dict(name=f'all{len(all_sites)}-detours-installed-before-reset', harts_parked=list(range(8)),
                patches=all_patches, bridge_sites=[hex(site) for site in h.bridge_patches],
                barrier_words=words, legacy_txdone_ready=0, bridge_allocation=False,
                physical_readiness_or_containment=False,
                bridge_definition_bytes=h.get32(0x8401b230))


def sections(path):
    with path.open('rb') as file:
        elf = ELFFile(file)
        rows = [dict(name=s.name, address=hex(s['sh_addr']), bytes=s['sh_size'], sha256=sha(s.data()))
                for s in elf.iter_sections() if s['sh_flags'] & 2 and s['sh_size']]
        assert all(0x84052000 <= int(row['address'], 16) and
                   int(row['address'], 16)+row['bytes'] <= 0x84054000 for row in rows)
        assert not any(row['name'] in ('.data', '.bss') for row in rows)
        return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    inputs = input_bindings()
    inputs.update({str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in
                   (SOURCE, ASM, LINKER, Path(__file__), ROOT/'tests/npu/allocator-reset-emulation.ld',
                    ROOT/'tests/npu/allocator-startup-emulation.ld')})
    inputs.update({str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in
                   (ROOT/'tests/npu').glob('*-emulation.ld')})
    path, command = build()
    startup, _ = build_startup()
    reset, _ = build_reset()
    h = ColdTx(startup, reset)
    h.setup()
    def word(offset, value):
        return lambda obj: obj.put32(SRAM+offset, value)
    def half(offset, value):
        return lambda obj: obj.cpu.mem_write(SRAM+offset, struct.pack('<H', value))
    def bad_id(offset, value):
        def edit(obj):
            head = int.from_bytes(obj.cpu.mem_read(SRAM+0x1ba4, 2), 'little')
            pool = obj.get32(SRAM+0x1b88)
            obj.cpu.mem_write(pool+((head+offset) % 16384)*2, struct.pack('<H', value))
        return edit
    def tx_pointer(index, add=0, duplicate=False):
        def edit(obj):
            base = obj.get32(SRAM+0x1f28)
            value = obj.get32(base+8) if duplicate else obj.get32(base+index*32+8)+add
            obj.put32(base+index*32+8, value)
        return edit
    cases = [(f'original-count-{count}', dict(corrected=False, count=count)) for count in (0, 512, 513)]
    cases += [(f'original-exhaust-{n}', dict(corrected=False, available=n, outcome='partial', allocated=n)) for n in (0, 17)]
    cases += [(f'original-denied-{owner}', dict(corrected=False, denied=(owner, 1))) for owner in (28, 19, 20)]
    cases += [(f'checked-count-{count}', dict(count=count)) for count in (1, 2, 511, 512)]
    cases += [(f'rejected-count-{count}', dict(count=count, outcome='reject')) for count in (0, 513, 65535, 0x80000000, 0xffffffff)]
    cases += [(f'checked-exhaust-{n}', dict(available=n, outcome='partial', allocated=n)) for n in (0, 17)]
    cases += [('checked-denied28-first', dict(denied=(28, 1), outcome='partial')),
              ('checked-denied28-after17', dict(denied=(28, 18), outcome='partial', allocated=17)),
              ('checked-denied19', dict(denied=(19, 1), outcome='partial', allocated=512)),
              ('checked-denied20', dict(denied=(20, 1), outcome='partial', allocated=512))]
    for name, edit, allocated in (
        ('head-bound', half(0x1ba4, 16384), 0), ('tail-bound', half(0x1b80, 16384), 0),
        ('id-pool-misaligned', word(0x1b88, HEAP+1), 0),
        ('id-pool-outside', word(0x1b88, HEAP+HEAP_BYTES-32), 0),
        ('invalid-first-id', bad_id(0, 0x8000), 0), ('invalid-id-after17', bad_id(17, 0x8000), 17),
        ('skb-zero-capacity', word(0xbc0, 0), 512), ('skb-small-capacity', word(0xbc0, 2047), 512),
        ('skb-large-capacity', word(0xbc0, 0x7001), 512),
        ('skb-temp-outside', word(0x1bc0, HEAP+HEAP_BYTES-32), 512),
        ('skb-queue-outside', word(0x1b84, HEAP+HEAP_BYTES-32), 512),
        ('skb-state-missing', word(0x469c, 0), 512), ('tx-ring-pointer', word(0x1f28, 0), 512),
        ('tx-packet-misaligned', tx_pointer(0, 1), 512),
        ('tx-packet-outside-capacity', tx_pointer(0, 8192*2048), 512),
        ('tx-packet-duplicate-id', tx_pointer(1, duplicate=True), 512),
    ):
        cases.append((name, dict(edit=edit, allocated=allocated, outcome='partial')))
    for name, edit in (
        ('packet-base-missing', word(0x396c, 0)), ('host-ring-missing', word(0x3964, 0)),
        ('host-ring-misaligned', word(0x3964, HOST+1)), ('host-ring-request-overlap', word(0x3964, PAYLOAD)),
        ('host-ring-wrap', word(0x3964, 0x80000000-4096)),
        ('lock28-id', word(0x1b9c, 27)), ('lock19-id', word(0x1bb8, 20)), ('lock20-id', word(0x1bc4, 19)),
        ('nested-active', word(ADM-SRAM+4, 2)), ('bootstrap-incomplete', word(BOOT-SRAM+8, 5)),
        ('prior-fault', word(STATE-SRAM+16, 1)), ('missing-worker', word(STATE-SRAM+20+3*4, 0)),
        ('released-worker', word(STATE-SRAM+4, 1)), ('armed-worker', word(STATE-SRAM+8, 1)),
        ('prepared-worker', word(STATE-SRAM+12, 1)),
        ('already-ready', lambda obj: obj.cpu.mem_write(SRAM+0x46fa, b'\x01')),
    ):
        cases.append((name, dict(edit=edit, outcome='reject')))
    cases += [('wrong-header', dict(header=0x3a, outcome='reject')),
              ('wrong-api', dict(api=19, outcome='reject')),
              ('immutable-count-snapshot', dict(count=1, mutate=True)),
              ('native-irq-success', dict(irq=True)),
              ('native-irq-exhaust', dict(irq=True, available=17, allocated=17, outcome='partial')),
              ('native-irq-reject', dict(irq=True, count=0, outcome='reject')),
              ('native-irq-denied20', dict(irq=True, denied=(20, 1), allocated=512, outcome='partial'))]
    rows = []
    for name, arguments in cases:
        rows.append(exercise(h, path, name, **arguments))
        print(json.dumps(dict(case=name, passed=True)), flush=True)
    mutants = mutations(h, path)
    print(json.dumps(dict(mutations=len(mutants), passed=True)), flush=True)
    controls = closed_and_unselected(h, path)
    controls.append(retained_gate(path, startup, reset))
    missing = missing_models(h, path)
    assert all(sha((ROOT/name).read_bytes()) == digest for name, digest in inputs.items())
    result = dict(schema=1, command=command, elf_sha256=sha(path.read_bytes()), cases=rows,
                  sections=sections(path), mutations=mutants, controls=controls, missing_models=missing,
                  inputs_before_after=inputs,
                  limits=['Selected API1 selector10 callback; strict admission is not expanded.',
                          'Native IRQ entry tests invoke the original handler explicitly, not a production admission path.',
                          'Physical cold containment, host descriptor backing size and DMA/cache/lock hardware remain contracts.',
                          'No INODE-provider correction, native DESC5/6/7/8 operation, router or image.'])
    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT/'txdone-init.json'
    encoded = (json.dumps(result, indent=2)+'\n').encode()
    if args.check:
        assert output.read_bytes() == encoded
    else:
        output.write_bytes(encoded)
    print(json.dumps(dict(cases=len(rows), mutations=len(mutants), controls=len(controls), evidence_sha256=sha(encoded))))


if __name__ == '__main__':
    main()
