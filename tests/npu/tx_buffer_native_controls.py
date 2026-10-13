"""Exact API21 effects and native faults; snapshot restoration is fixture-only."""
import struct

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r
from emulation_layout import STATE, SRAM, HEAP, HEAP_BYTES
from test_native_wifi_boot import L2, L2_BYTES
from test_bootstrap_native import ADM, BOOT
import test_cold_tx_buffer as oracle

SPANS = ((SRAM, 0x4800), (HEAP, HEAP_BYTES), (L2, L2_BYTES))


def profile(h):
    cold = h.rv.symbols['npu_emulation_cold_setup_state']
    values = list(struct.unpack('<29I', h.cpu.mem_read(cold + 128, 116)))
    values[0] = h.get32(cold + 108)
    return values


def effects(h, before, phase):
    saved = dict(before)
    expected = {base: bytearray(saved[base][:length]) for base, length in SPANS}
    plan = profile(h)
    for index in range(oracle.COUNTS[phase]):
        address, width, value = oracle.original(phase, index, plan)
        base = next(base for base, length in SPANS if base <= address and address + width <= base + length)
        expected[base][address - base:address - base + width] = value.to_bytes(width, 'little')
    for base, data in expected.items():
        assert bytes(h.cpu.mem_read(base, len(data))) == data, ('API21-unexpected-effects', phase, hex(base))
    return dict(phase=phase, selector=oracle.SELECTORS[phase], stores=oracle.COUNTS[phase],
                exact_heap_data_l2=True, untouched_neighbors_and_tails=True)


def check(h, before, request, phase):
    cold = h.rv.symbols['npu_emulation_cold_setup_state']
    owner = h.txbuf.symbols['npu_emulation_txbuf_state']
    cold_bytes = h.rv.elf.get_section_by_name('.symtab').get_symbol_by_name(
        'npu_emulation_cold_setup_state')[0]['st_size']
    after = h.snapshot() + [(cold, bytes(h.cpu.mem_read(cold, cold_bytes)))]
    tables = (0x8401cf18, 0x8401cf58, 0x8401cf60, 0x8401cf70, 0x8401cf74,
              0x8401cf78, 0x8401cf7c, 0x8401cfc8, 0x8401cfcc)
    originals = {address: h.get32(address) for address in tables}
    rows, prefix = [], sum(oracle.COUNTS[:phase])
    plan = profile(h)
    address, width, value = oracle.original(phase, 0, plan)
    prior_target = next(data[address - base:address - base + width] for base, data in before
                        if base <= address and address + width <= base + len(data))
    entry = h.txbuf.symbols['npu_emulation_txbuf_callback']
    reserve = h.txbuf.symbols['npu_emulation_txbuf_reserve']
    def put(address, value):
        return lambda cpu: h.put32(address, value)
    def bump(address):
        return lambda cpu: h.put32(address, h.get32(address) + 32)
    cases = []
    if phase == 0:
        cases += [(name, 'entry', mutate) for name, mutate in (
            ('preowned-lock', put(h.txbuf.symbols['lock_owned'], 1)),
            ('TXPKT-zero', put(0x3e902ab8, 0)), ('TXPKT-wrong', bump(0x3e902ab8)),
            ('static-type100', put(0x8401cf70, 0x102)), ('static-L2-0', bump(0x8401cf74)),
            ('static-type101', put(0x8401cf78, 0x102)), ('static-L2-1', bump(0x8401cf7c)),
            ('typed-table', bump(0x8401cf58)), ('arena-type', put(0x8401cfc8, 2)),
            ('arena-size', bump(0x8401cfcc)), ('callback-slot', put(0x3e9001cc, 0)),
            ('port-type', lambda cpu: h.cpu.mem_write(0x3e90390e, b'\x03')),
            ('allocator-lock', put(0x3e901bcc, 17)), ('allocator-count', bump(0x3e901bd4)),
            ('allocator-used', bump(0x3e901be0)), ('arena-pointer', bump(0x3e9030fc)),
            ('descriptor-slot', bump(0x3e9021ec)), ('boot-plan', bump(BOOT + 64)),
            ('held-ready', put(STATE + 56, 1)), ('held-unparked', put(STATE + 24, 0)),
            ('deferred-IRQ', put(ADM + 20, 1)), ('nonce', bump(cold + 28)),
            ('prior-descriptor-fault', put(h.descriptor.symbols['npu_emulation_descriptor_state'] + 8, 1)),
            ('prior-TX-fault', put(h.tx.symbols['npu_emulation_tx_state'] + 8, 1)),
            ('enrollment-count', put(cold + 120, 13)), ('enrolled-handle', bump(cold + 140)),
            ('descriptor-order', put(cold + 104, 8)), ('API21-order', put(cold + 360, 1)),
        )]
    cases += [
        ('computed-unmapped-address', 'reserve', lambda cpu: cpu.reg_write(r.UC_RISCV_REG_A0, 0xdead0000)),
        ('computed-wrong-width', 'reserve', lambda cpu: cpu.reg_write(r.UC_RISCV_REG_A2, 1)),
        ('computed-wrong-value', 'reserve', lambda cpu: cpu.reg_write(
            r.UC_RISCV_REG_A1, cpu.reg_read(r.UC_RISCV_REG_A1) ^ 256)),
        ('late-setup', 'reserve', bump(cold + 28)),
        ('late-IRQ-enable', 'reserve', lambda cpu: cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 8)),
        ('after-first-store', 'write', put(STATE + 16, 1)),
    ]
    cases = [(*case, 0) for case in cases]
    if oracle.COUNTS[phase] > 1:
        cases += [('computed-unmapped-record', 'reserve', lambda cpu: cpu.reg_write(
            r.UC_RISCV_REG_A0, 0xdead0000), oracle.metadata_count(phase))]
        cases += [(name, 'write', put(STATE + 16, 1), index) for name, index in (
            ('after-middle-store', oracle.COUNTS[phase] // 2),
            ('after-last-store', oracle.COUNTS[phase] - 1))]
    try:
        for name, moment, mutate, at in cases:
            h.restore(before)
            for location, original in originals.items():
                h.put32(location, original)
            h.put32(0x1ec03048, 0x10000)
            h.unmodeled = None
            injected, delegated = [], []
            def inject(cpu, pc, size, data):
                if not injected and (moment == 'entry' or h.get32(owner + 28) == prefix + at):
                    mutate(cpu)
                    injected.append(True)
            def observe(cpu, pc, size, data):
                delegated.append(pc)
            def written(cpu, access, location, size, data_value, data):
                if not injected and h.get32(owner + 28) == prefix + at + 1:
                    mutate(cpu)
                    injected.append(True)
            hooks = [h.cpu.hook_add(UC_HOOK_CODE, observe, begin=0x8400fbce, end=0x8400fbce)]
            if moment == 'write':
                target, target_width, _ = oracle.original(phase, at, plan)
                hooks.append(h.cpu.hook_add(UC_HOOK_MEM_WRITE, written, begin=target,
                                           end=target + target_width - 1))
            else:
                site = entry if moment == 'entry' else reserve
                hooks.append(h.cpu.hook_add(UC_HOOK_CODE, inject, begin=site, end=site))
            mmio_start = len(h.mmio)
            try:
                reply = h.message(request)
            finally:
                for hook in hooks:
                    h.cpu.hook_del(hook)
            assert injected and reply['flags'] == 7 and reply['words'][14] == 7, (phase, name, reply)
            assert h.unmodeled is None, (phase, name, h.unmodeled)
            assert h.get32(cold) == h.get32(cold + 4) == h.get32(ADM + 4) == 1
            expected_steps = phase + int(name == 'API21-order')
            assert h.get32(owner + 8) == 1 and h.get32(cold + 360) == expected_steps, (
                phase, name, h.get32(owner + 8), h.get32(cold + 360), expected_steps)
            published = prefix + at
            committed = published + int(moment == 'write')
            assert h.get32(owner + 28) == committed and h.get32(owner + 32) == published, (phase, name)
            assert bool(delegated) == (moment != 'entry'), (phase, name, delegated)
            assert bytes(h.cpu.mem_read(address, width)) == (
                value.to_bytes(width, 'little') if moment == 'write' or at else prior_target), (phase, name)
            if name == 'preowned-lock':
                assert h.get32(h.txbuf.symbols['lock_owned']) == 1
                assert not [row for row in h.mmio[mmio_start:] if row['kind'] == 'mmio-write'
                            and row['address'] in ('0x1ec031c8', '0x1ec03248')]
            rows.append(dict(phase=phase, name=name, moment=moment, committed=committed,
                             store_index=at, published=published, retained_active=1, retained_inflight=1,
                             unowned_access=False, original_helper=bool(delegated)))
    finally:
        h.restore(after)
        for location, original in originals.items():
            h.put32(location, original)
        h.put32(0x1ec03048, 0x10000)
    return rows
