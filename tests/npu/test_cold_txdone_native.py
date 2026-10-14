#!/usr/bin/env python3
"""Shared cold PKT ownership across native RX and TXDONE, including SKB reset."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import struct
import sys
from types import SimpleNamespace

sys.dont_write_bytecode = True
from unicorn import riscv_const as r
import test_cold_packet_native as packets
import test_cold_page_native as pages
import test_rx_stats as stats
import test_bootstrap_v2_composition as composition
from test_attach_tx_callbacks import HOST, HOST_BYTES, SKB_STATE, SKB_BYTES, REGS, done_oracle
from test_bootstrap_native import ADM, Bootstrap
from test_mt7996_bootstrap_sequence import SET_CALLBACKS, expected, TXFREE
from test_firmware_mailbox_dispatch import PAYLOAD
from test_firmware_memory_layout import STACK_TOPS, table
from test_firmware_stop_counterexample import END
from test_txdone_init import partial_oracle
from emulation_layout import STATE, SRAM, SRAM_BYTES, HEAP, HEAP_BYTES

ROOT, TESTS = packets.ROOT, packets.TESTS
OWNER = {28: 0x1ec03070, 19: 0x1ec0304c, 20: 0x1ec03050}
SPACES = ((SRAM, SRAM_BYTES), (HEAP, HEAP_BYTES), (0x3e880000, 0x40000),
          (HOST, HOST_BYTES), (SKB_STATE, SKB_BYTES))


class TxPackets(packets.NativePackets):
    def __init__(self, paths, parts):
        self.done_tracking = False
        self.done_mode = None
        self.done_writes = []
        self.owner_reads = Counter()
        self.done_min_sp = STACK_TOPS[0]
        super().__init__(paths, parts)
        self.cpu.mem_map(HOST, HOST_BYTES)
        self.cpu.mem_write(HOST, b'\xa5' * HOST_BYTES)
        for base in sorted({address & ~0xfff for address in REGS}):
            self.cpu.mem_map(base, 0x1000)
        for address in OWNER.values():
            self.put32(address, 0x10000)
        self.fixed = {row['type']: row['value'] for row in table(self.code, 0x8401cf70)}

    def is_memory(self, address, size):
        if HOST <= address < HOST + HOST_BYTES:
            return address + size <= HOST + HOST_BYTES
        return super().is_memory(address, size)

    def register_model(self, address, write):
        if address in REGS:
            return 'Original TX setup register read/write storage; no DMA proof'
        if address in (0x1ec031cc, 0x1ec0324c, 0x1ec031d0, 0x1ec03250) and write:
            return 'Original SKB lock19/20 request/release storage; no physical grant'
        if address in (0x1ec0304c, 0x1ec03050) and not write:
            return 'Original SKB lock19/20 modeled owner readback'
        return super().register_model(address, write)

    def read_hook(self, cpu, access, address, size, value, data):
        if self.done_tracking and address in OWNER.values():
            owner = next(key for key, location in OWNER.items() if location == address)
            self.owner_reads[owner] += 1
            denied = ((self.done_mode == 'denied' and owner == 28 and self.owner_reads[owner] == 1) or
                      (self.done_mode == 'denied-skb19' and owner == 19 and self.owner_reads[owner] == 1) or
                      (self.done_mode == 'denied-skb20' and owner == 20 and self.owner_reads[owner] == 1))
            self.put32(address, 0x10100 if denied else 0x10000)
        super().read_hook(cpu, access, address, size, value, data)

    def code_hook(self, cpu, pc, size, data):
        if self.done_tracking:
            self.done_min_sp = min(self.done_min_sp, cpu.reg_read(r.UC_RISCV_REG_SP))
            if not self.packet_changed and pc == self.packet.symbols['npu_emulation_packet_txdone_publish']:
                core = self.packet.symbols['npu_emulation_packet_state']
                if self.done_mode == 'before-ready':
                    self.put32(STATE + 16, 1)
                elif self.done_mode == 'before-ready-packet-fault':
                    self.put32(core + 8, 1)
                elif self.done_mode == 'before-ready-count':
                    self.put32(core + 16, self.get32(core + 16) + 1)
                elif self.done_mode == 'before-ready-head':
                    self.put32(core + 12, self.get32(core + 12) + 1)
                    self.cpu.mem_write(packets.HEAD, struct.pack('<H', self.get32(core + 12)))
                elif self.done_mode == 'before-ready-bitmap':
                    self.put32(core + 28 + 511 * 4, 1)
                elif self.done_mode == 'before-ready-plan':
                    plan = self.packet.symbols['npu_emulation_packet_plan']
                    self.put32(plan, self.get32(plan) + 2048)
                else:
                    super().code_hook(cpu, pc, size, data)
                    return
                self.packet_changed = True
            if pc == 0x8400dd82:
                assert cpu.reg_read(r.UC_RISCV_REG_A1) == 10
                self.executions[pc] += 1
                super(composition.Composed, self).code_hook(cpu, pc, size, data)
                return
        super().code_hook(cpu, pc, size, data)

    def write_hook(self, cpu, access, address, size, value, data):
        if self.done_tracking:
            pc = cpu.reg_read(r.UC_RISCV_REG_PC)
            self.done_writes.append((pc, address, size, value))
            if SKB_STATE <= address < SKB_STATE + SKB_BYTES:
                self.packet_writes.append((pc, address, size, value))
                self.access(address, size, value, True)
                if self.done_mode == 'during-skb-reset' and not self.packet_changed:
                    self.put32(STATE + 16, 1)
                    self.packet_changed = True
                return
        super().write_hook(cpu, access, address, size, value, data)

    def snapshot(self):
        extra = [(0x84084000, bytes(self.cpu.mem_read(0x84084000, 0x4000)))] if hasattr(self, 'tx') else []
        if hasattr(self, 'descriptor'):
            extra.append((0x84088000, bytes(self.cpu.mem_read(0x84088000, 0x4000))))
        if hasattr(self, 'txbuf'):
            extra.append((0x84090000, bytes(self.cpu.mem_read(0x84090000, 0x40000))))
        if hasattr(self, 'rx_event'):
            extra.append((0x840d0000, bytes(self.cpu.mem_read(0x840d0000, 0x4000))))
        if hasattr(self, 'desc10'):
            extra.append((0x840d4000, bytes(self.cpu.mem_read(0x840d4000, 0x10000))))
        if hasattr(self, 'rx_pcie'):
            extra.append((0x840e4000, bytes(self.cpu.mem_read(0x840e4000, 0x4000))))
        return super().snapshot() + extra + [(HOST, bytes(self.cpu.mem_read(HOST, HOST_BYTES))),
                                            (SKB_STATE, bytes(self.cpu.mem_read(SKB_STATE, SKB_BYTES)))]

    def restore(self, saved):
        self.done_tracking = False
        super().restore(saved)
        for address in OWNER.values():
            self.put32(address, 0x10000)

    def packet_fields(self):
        result = {}
        binary = self.packet.elf
        for symbol in binary.get_section_by_name('.symtab').iter_symbols():
            section = symbol['st_shndx']
            if isinstance(section, int) and symbol['st_size'] and symbol['st_info']['type'] == 'STT_OBJECT':
                if binary.get_section(section).name in ('.data', '.bss'):
                    result[symbol.name] = bytes(self.cpu.mem_read(symbol['st_value'], symbol['st_size']))
        return result

    def restore_packet_fields(self, values):
        binary = self.packet.elf
        symbols = {s.name: s for s in binary.get_section_by_name('.symtab').iter_symbols()}
        for name, value in values.items():
            symbol = symbols[name]
            assert symbol['st_size'] == len(value)
            assert binary.get_section(symbol['st_shndx']).name in ('.data', '.bss')
            self.cpu.mem_write(symbol['st_value'], value)

    def invoke_done(self, count, mode=None, *, header=0x1a, api=1):
        self.done_mode = self.packet_mode = mode
        self.packet_changed = False
        self.requested = count
        self.done_writes, self.packet_writes, self.owner_reads = [], [], Counter()
        self.getter_calls = 0
        self.done_min_sp = STACK_TOPS[0]
        core = self.packet.symbols['npu_emulation_packet_state']
        self.before_state = list(struct.unpack('<519I', self.cpu.mem_read(core, 2076)))
        self.claim_trigger = self.before_state[4] + 1
        self.head_before = int.from_bytes(self.cpu.mem_read(packets.HEAD, 2), 'little')
        self.at_allocator = None
        self.unmodeled = None
        self.cpu.mem_write(PAYLOAD, struct.pack('<3I', header, api, count) + bytes(12))
        for register, value in ((r.UC_RISCV_REG_SP, STACK_TOPS[0]), (r.UC_RISCV_REG_RA, END),
                                (r.UC_RISCV_REG_A0, PAYLOAD), (r.UC_RISCV_REG_MSTATUS, 0)):
            self.cpu.reg_write(register, value)
        self.done_tracking = self.packet_tracking = self.probing = True
        try:
            assert self.run(0x8400fe34, []) == END
            result = self.cpu.reg_read(r.UC_RISCV_REG_A0)
        finally:
            self.done_tracking = self.packet_tracking = self.probing = False
        self.check_hooks()
        assert self.cpu.reg_read(r.UC_RISCV_REG_SP) == STACK_TOPS[0]
        assert self.done_min_sp >= STACK_TOPS[0] - 0x4000
        state = list(struct.unpack('<519I', self.cpu.mem_read(core, 2076)))
        ready = [row for row in self.done_writes if row[1] == SRAM + 0x46fa and row[3] == 1]
        descriptors = [row for row in self.done_writes if row[0] == 0x8400b4ba]
        locks = [(address, value) for _, address, _, value in self.done_writes
                 if address in (0x1ec031f0, 0x1ec03270, 0x1ec031cc, 0x1ec0324c, 0x1ec031d0, 0x1ec03250)]
        return dict(returned=result, mode=mode, requested=count, claimed=state[4], private_head=state[3],
                    population=sum(w.bit_count() for w in state[7:]), packet_fault=state[2],
                    buffer_head=int.from_bytes(self.cpu.mem_read(packets.HEAD, 2), 'little'),
                    ready=self.cpu.mem_read(SRAM + 0x46fa, 1)[0], ready_one_stores=len(ready),
                    descriptor_stores=len(descriptors), locks=locks, owner_reads=dict(self.owner_reads),
                    admission_fault=self.get32(ADM + 8), barrier_fault=self.get32(STATE + 16),
                    active=self.get32(ADM + 4), guarded=self.get32(self.allocator_rv.symbols['npu_emulation_callback_guarded']),
                    min_sp=hex(self.done_min_sp), state_sha256=composition.packets.headers.sha(struct.pack('<519I', *state)))


def prepare(paths, parts, page_path, rx_path, packet_path, quick):
    h = TxPackets(paths, parts)
    h.hart = 0
    h.cpu.context_restore(h.fresh)
    assert h.reset() == 0x8400420a
    host = composition.control.Host(paths)
    assert composition.control.exchange(host, h)[0] == composition.control.ACCEPTED
    composition.boot.setup(h, run_clear=True)
    composition.control.advance(host, h)
    h.finish_coordinator()
    for hart in range(1, 8):
        h.worker(hart)
    h.on_core0()
    denied = Bootstrap.message(h, [0x1a, 1, 512])
    assert denied['flags'] == 3 and not denied['callbacks']
    h.put32(ADM + 4, 1)
    h.install(page_path)
    h.install_rx(rx_path)
    h.install_packet(packet_path)
    assert h.direct(h.packet.symbols['npu_emulation_packet_init']) == 0
    prefix = []
    for selector, count in ((0, 32), (2, 32)) if quick else ((0, 1536), (2, 1024)):
        row = h.invoke_packet(selector, count)
        stats.expected(row, 1, count, 1, 250)
        prefix.append(row)
        print(json.dumps(dict(rx_prefix_selector=selector, packet_claims=row['claimed'])), flush=True)
    calls = [[0x10, 14, 2]]
    calls += [[m['word0'], 19, m['value']] for m in expected(0, 2) if m.get('api') == 19]
    calls += [[0x10, 33, 8192], [0x10, 22, TXFREE]]
    for words in calls:
        h.cpu.mem_write(PAYLOAD, struct.pack('<3I', *words) + bytes(12))
        assert h.direct(SET_CALLBACKS[words[1]], PAYLOAD) == 1
    assert h.get32(SRAM + 0xbc0) == 8192 and h.get32(SRAM + 0x3964) == HOST
    h.put32(SRAM + 0x3974, 0x87654321)
    return h, denied, prefix


def oracle(h, count):
    return done_oracle(SimpleNamespace(h=h, fixed=h.fixed), count)


def check_success(h, before, want, row, count):
    assert row['returned'] == row['ready'] == row['ready_one_stores'] == 1, ('txdone-success', row)
    assert row['claimed'] == row['population'] == before[4] + count, ('shared-claims', row)
    assert row['buffer_head'] == row['private_head'] == (before[3] + count) % 16384
    assert row['packet_fault'] == row['barrier_fault'] == row['admission_fault'] == row['guarded'] == 0
    assert row['active'] == 1
    assert row['descriptor_stores'] == count, ('descriptor-store-count', row)
    actual = {base: bytes(h.cpu.mem_read(base, len(value))) for base, value in want.items()}
    assert actual == want, ('whole-native-ram-oracle', row)
    state = list(before)
    for ident in range(before[4], before[4] + count):
        state[7 + ident // 32] |= 1 << (ident % 32)
    state[3] = (before[3] + count) % 16384
    state[4] += count
    assert bytes(h.cpu.mem_read(h.packet.symbols['npu_emulation_packet_state'], 2076)) == struct.pack('<519I', *state), 'exact-packet-state'
    assert row['locks'] == [(0x1ec031f0, 0x40), (0x1ec03270, 0)] * count + [
        (0x1ec031cc, 0x40), (0x1ec031d0, 0x40), (0x1ec03250, 0), (0x1ec0324c, 0)], 'ordered-lock-footprint'
    native_writes = [w for w in h.done_writes if any(base <= w[1] < base + size for base, size in SPACES)]
    assert native_writes[-1][1:] == (SRAM + 0x46fa, 1, 1), 'ready-last-native-write'


def check_control(h, mode, before, count, row):
    pre_reject = mode in ('zero-count', 'oversize-count', 'bad-header', 'bad-api')
    completed_skb = mode.startswith('before-ready') or mode == 'during-skb-reset'
    full_claims = completed_skb or mode in ('denied-skb19', 'denied-skb20', 'bad-skb-capacity')
    partial = mode == 'partial-pool'
    late = mode in ('claim-fault', 'head-changed', 'tail-changed', 'id-changed',
                    'published-fault', 'release-fault')
    committed = count if full_claims else 17 if partial else 1 if late else 0
    descriptors = count if full_claims else 17 if partial else 0
    published = 0 if mode in ('head-changed', 'tail-changed', 'id-changed') else committed
    failure = int(mode in ('bad-id', 'duplicate', 'partial-pool', 'claim-fault',
                          'head-changed', 'tail-changed', 'id-changed', 'published-fault'))
    if completed_skb:
        want, _, _ = oracle(h, count)
        struct.pack_into('<I', want[SRAM], 0x3974, h.get32(SRAM + 0x3974))
        want[SRAM][0x46fa] = 0
    elif pre_reject:
        want = {base: bytearray(h.cpu.mem_read(base, size)) for base, size in SPACES}
    else:
        want, _ = partial_oracle(h, count, descriptors)
    # This function is called with the pre-call native memory snapshot restored
    # while retaining the observed row and separately saved post-call bytes.
    for address in (ADM, ADM + 8, STATE + 16):
        struct.pack_into('<I', want[SRAM], address - SRAM, 1)
    head = 37 if mode == 'head-changed' else (before[3] + published + int(mode == 'before-ready-head')) % 16384
    struct.pack_into('<H', want[SRAM], packets.HEAD - SRAM, head)
    struct.pack_into('<I', want[SRAM], 0x1b90, (h.get32(SRAM + 0x1b90) + published) & 0xffffffff)
    statistic = h.get32(SRAM + 0x1f08)
    for offset, delta in ((0x1c, published), (0x20, failure)):
        struct.pack_into('<I', want[HEAP], statistic - HEAP + offset,
                         (h.get32(statistic + offset) + delta) & 0xffffffff)
    if mode == 'tail-changed':
        struct.pack_into('<H', want[SRAM], packets.TAIL - SRAM, 3)
    elif mode == 'id-changed':
        struct.pack_into('<H', want[HEAP], packets.POOL - HEAP + 2 * before[3], 42)
    elif mode == 'lock-changed-after-grant':
        struct.pack_into('<I', want[SRAM], 0x1b9c, 27)
    assert row['returned'] == row['ready'] == row['ready_one_stores'] == 0, ('failed-publication', row)
    assert row['descriptor_stores'] == descriptors, ('failed-descriptors', row)
    assert row['buffer_head'] == head, ('retained-native-head', row)
    assert row['claimed'] == before[4] + committed + int(mode == 'before-ready-count'), ('retained-ownership', row)
    assert row['active'] == 1 and row['guarded'] == 0
    assert row['packet_fault'] == row['barrier_fault'] == row['admission_fault'] == 1
    state = list(before)
    for ident in range(before[4], before[4] + committed):
        state[7 + ident // 32] |= 1 << (ident % 32)
    state[2] = 1
    state[3] = (before[3] + committed + int(mode == 'before-ready-head')) % 16384
    state[4] += committed + int(mode == 'before-ready-count')
    if mode == 'before-ready-bitmap':
        state[7 + 511] = 1
    requests = (0 if pre_reject else count if full_claims else 18 if partial else 1)
    locks = [(0x1ec031f0, 0x40), (0x1ec03270, 0)] * requests
    if mode == 'denied':
        locks = [(0x1ec031f0, 0x40)]
    if full_claims:
        locks += [(0x1ec031cc, 0x40)]
        if mode != 'denied-skb19':
            locks += [(0x1ec031d0, 0x40)]
            if mode != 'denied-skb20':
                locks += [(0x1ec03250, 0)]
            locks += [(0x1ec0324c, 0)]
    assert row['locks'] == locks, ('failed-lock-order', row)
    return want, struct.pack('<519I', *state)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--quick', action='store_true')
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-cold-txdone-20261010' / args.name
    assert not dest.exists()
    dest.mkdir(parents=True)
    paths, parts = composition.build()
    page_dir, rx_dir = dest / 'page-component', dest / 'rx-component'
    page_dir.mkdir()
    rx_dir.mkdir()
    page_path = pages.build(page_dir, parts)
    rx_path = stats.build(rx_dir, parts, page_path)
    packet_path = packets.build(dest, parts, rx_path)
    composition.memory_layout(parts | {'cold-pages': page_path, 'rx-stats': rx_path, 'cold-packets': packet_path})
    h, denied, prefix = prepare(paths, parts, page_path, rx_path, packet_path, args.quick)
    initial = h.snapshot()
    fields = h.packet_fields()
    core = h.packet.symbols['npu_emulation_packet_state']
    before = list(struct.unpack('<519I', h.cpu.mem_read(core, 2076)))
    valid = []
    for count in (16,) if args.quick else (1, 512):
        h.restore(initial)
        want, allowed, footprint = oracle(h, count)
        row = h.invoke_done(count)
        check_success(h, before, want, row, count)
        valid.append(row)
        print(json.dumps(dict(txdone_descriptors=count, total_retained=row['claimed'], passed=True)), flush=True)
    modes = ('denied', 'bad-id', 'duplicate', 'partial-pool', 'claim-fault',
             'head-changed', 'tail-changed', 'id-changed', 'published-fault', 'release-fault',
             'lock-changed-after-grant', 'denied-skb19', 'denied-skb20', 'bad-skb-capacity',
             'during-skb-reset', 'before-ready', 'before-ready-packet-fault',
             'before-ready-count', 'before-ready-head', 'before-ready-bitmap', 'before-ready-plan',
             'zero-count', 'oversize-count', 'bad-header', 'bad-api')
    controls = []
    for mode in modes:
        h.restore(initial)
        if mode == 'partial-pool':
            h.cpu.mem_write(packets.TAIL, struct.pack('<H', (before[3] + 18) % 16384))
        elif mode in ('bad-id', 'duplicate'):
            h.cpu.mem_write(packets.POOL + 2 * before[3], struct.pack('<H', 16384 if mode == 'bad-id' else 0))
        elif mode == 'bad-skb-capacity':
            h.put32(SRAM + 0xbc0, 1024)
        count = 0 if mode == 'zero-count' else 513 if mode == 'oversize-count' else 32
        seeded = h.snapshot()
        row = h.invoke_done(count, mode, header=0x11a if mode == 'bad-header' else 0x1a,
                            api=2 if mode == 'bad-api' else 1)
        actual = {base: bytes(h.cpu.mem_read(base, size)) for base, size in SPACES}
        actual_state = bytes(h.cpu.mem_read(core, 2076))
        h.restore(seeded)
        want, state = check_control(h, mode, before, count, row)
        assert actual == want, ('whole-native-fault-oracle', mode,
                                [(hex(base), next((i for i, pair in enumerate(zip(actual[base], want[base]))
                                                 if pair[0] != pair[1]), None))
                                 for base in want if actual[base] != want[base]])
        assert actual_state == state, ('exact-failed-packet-state', mode)
        controls.append(row)
        print(json.dumps(dict(txdone_control=mode, passed=True)), flush=True)
    source_text = (TESTS / 'cold-packet-native-emulation.c').read_text()
    assembly_text = (TESTS / 'cold-packet-native-emulation.S').read_text()
    mutations = (
        ('omit-txdone-getter-route', 'assembly', 'li t1, 0x8400b4e4',
         'li t1, 0', 'claim-fault'),
        ('omit-txdone-publication-guard', 'assembly', 'call npu_emulation_packet_txdone_ready',
         'nop', 'before-ready-packet-fault'),
        ('omit-ready-count-consistency', 'source',
         'state->head != (state->count & (NPU_COLD_PACKET_IDS - 1))', '0', 'before-ready-head'),
        ('omit-ready-bitmap-population', 'source', 'if (population != state->count)', 'if ((void)population, 0)', 'before-ready-bitmap'),
        ('omit-ready-plan-identity', 'source', 'state->packet_base != npu_emulation_packet_plan.packet_base', '0', 'before-ready-plan'),
        ('always-success-txdone', 'source', 'return result;', 'return 1;', 'denied-skb19'),
    )
    mutants = []
    for name, kind, old, new, mode in mutations:
        directory = dest / name
        directory.mkdir()
        text = source_text if kind == 'source' else assembly_text
        assert text.count(old) == 1, (name, text.count(old))
        mutant = directory / ('mutant.c' if kind == 'source' else 'mutant.S')
        mutant.write_text(text.replace(old, new))
        path = packets.build(directory, parts, rx_path, **{kind: mutant})
        h.restore(initial)
        h.install_packet(path)
        # Preserve RX ownership by named writable ELF objects across relocated
        # mutant layouts. This is fixture restoration, never a runtime reset API.
        h.restore_packet_fields(fields)
        assert h.get32(h.packet.symbols['npu_emulation_packet_state'] + 16) == before[4]
        row = h.invoke_done(16, mode)
        try:
            h.restore(initial)
            check_control(h, mode, before, 16, row)
        except AssertionError as exc:
            reason = exc.args[0][0] if isinstance(exc.args[0], tuple) else exc.args[0]
            assert reason in ('failed-publication', 'failed-descriptors', 'retained-native-head',
                              'retained-ownership', 'failed-lock-order'), exc
            mutants.append(dict(name=name, rejected_by=reason))
        else:
            raise AssertionError(('surviving-txdone-mutant', name))
    sources = {ROOT / 'firmware/npu' / name for name in ('cold-page.c', 'cold-packet.c', 'cold-packet.h',
                                                       'bootstrap.h', 'allocator.h')}
    sources |= {Path(module.__file__).resolve() for module in list(sys.modules.values())
                if getattr(module, '__file__', None) and Path(module.__file__).resolve().is_relative_to(TESTS)}
    sources |= {TESTS / name for name in ('cold-packet-native-emulation.c', 'cold-packet-native-emulation.S',
                                        'cold-packet-native-emulation.ld', 'allocator-startup-emulation.c',
                                        'allocator-startup-emulation.S', 'rx-stats-emulation.c',
                                        'rx-stats-emulation.S', 'rx-stats-emulation.ld',
                                        'cold-page-native-emulation.c', 'cold-page-native-emulation.S',
                                        'cold-page-native-emulation.ld', 'txdone-init-emulation.c',
                                        'txdone-init-emulation.S', 'txdone-init-emulation.ld')}
    result = dict(passed=True, full_nominal=not args.quick, hooks=63, nominal=valid, prefix=prefix,
                  controls=controls, rejected_mutants=mutants,
                  strict_denial=denied, packet_state_fields=list(fields),
                  inputs={str(p.relative_to(ROOT)): composition.sha(p) for p in sorted(sources)},
                  binaries={str(p.relative_to(ROOT)): composition.sha(p) for p in [*paths, *parts.values(), page_path, rx_path, packet_path]},
                  limits=['Selected shared cold RX/TXDONE instruction composition; modeled backing/grants and held lease.',
                          'No physical loader installation,hot recycle,drain/recovery or actual-client acceptance.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, full_nominal=not args.quick, receipt=str(dest / 'result.json'))))


if __name__ == '__main__':
    main()
