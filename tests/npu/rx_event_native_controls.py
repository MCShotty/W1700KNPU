"""API22 exact effects and native failures; snapshot restoration is test-only."""
import json
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r

from emulation_layout import STATE
from test_bootstrap_native import ADM, BOOT
from tx_buffer_native_controls import SPANS

METADATA = 0x3e903964


def effects(h, before, ring):
    expected = (ring & 0x3fffffff) | 0x40000000
    saved = dict(before)
    for base, length in SPANS:
        data = bytearray(saved[base][:length])
        if base <= METADATA < base + length:
            offset = METADATA - base
            data[offset:offset + 4] = expected.to_bytes(4, 'little')
        assert bytes(h.cpu.mem_read(base, length)) == data, ('API22-unexpected-effect', hex(base))
    owner = h.rx_event.symbols['npu_emulation_rx_event_state']
    prior = int.from_bytes(saved[SPANS[0][0]][METADATA - SPANS[0][0]:METADATA - SPANS[0][0] + 4], 'little')
    assert [h.get32(owner + 4 * i) for i in range(8)] == [0x31455852, 1, 0, 0, 1, 1, 1, prior]
    for rv, name, size in ((h.packet, 'npu_emulation_packet_state', 2076),
                           (h.binding, 'npu_emulation_page_state', 1052),
                           (h.txbuf, 'npu_emulation_txbuf_state', 213200)):
        address = rv.symbols[name]
        old = next(data[address - base:address - base + size] for base, data in before
                   if base <= address and address + size <= base + len(data))
        assert bytes(h.cpu.mem_read(address, size)) == old
    cold = h.rv.symbols['npu_emulation_cold_setup_state']
    assert h.get32(cold + 380) == 1 and h.get32(METADATA) == expected


def check(h, before, request):
    cold = h.rv.symbols['npu_emulation_cold_setup_state']
    owner = h.rx_event.symbols['npu_emulation_rx_event_state']
    cold_bytes = h.rv.elf.get_section_by_name('.symtab').get_symbol_by_name(
        'npu_emulation_cold_setup_state')[0]['st_size']
    after = h.snapshot() + [(cold, bytes(h.cpu.mem_read(cold, cold_bytes)))]
    entry = h.rx_event.symbols['npu_emulation_rx_event_callback']
    reserve = h.rx_event.symbols['npu_emulation_rx_event_reserve']
    publish = h.rx_event.symbols['npu_emulation_rx_event_publish']
    finish = h.rv.symbols['npu_cold_rx_event_finish']
    tx_owner = h.txbuf.symbols['npu_emulation_txbuf_state']
    tables = (0x8401cf70, 0x8401cf74, 0x8401cf78, 0x8401cf7c)
    originals = {address: h.get32(address) for address in tables}
    def put(address, value):
        return lambda cpu: h.put32(address, value)
    def bump(address):
        return lambda cpu: h.put32(address, h.get32(address) ^ 16)
    cases = [(name, 'entry', mutate) for name, mutate in (
        ('preowned-lock', put(h.rx_event.symbols['lock_owned'], 1)),
        ('callback-slot', put(0x3e9001d0, 0)),
        ('TXPKT', bump(0x3e902ab8)), ('static-L2', bump(0x8401cf7c)),
        ('prior-TX-owner', put(tx_owner + 8, 1)),
        ('prior-TX-progress', bump(tx_owner + 28)),
        ('prior-TX-effect', bump(0x3e8a4020)),
        ('prior-descriptor', put(h.descriptor.symbols['npu_emulation_descriptor_state'] + 8, 1)),
        ('held-unparked', put(STATE + 24, 0)), ('deferred-IRQ', put(ADM + 20, 1)),
        ('boot-plan', bump(BOOT + 64)), ('nonce', bump(cold + 28)),
        ('accepted-RX', bump(cold + 368)), ('pending-RX', bump(cold + 376)),
        ('RX-order', put(cold + 380, 1)), ('TX-order', put(cold + 360, 5)),
        ('enrollment-count', put(cold + 120, 13)), ('enrolled-TX-handle', bump(cold + 140)),
    )]
    cases += [
        ('unmapped-computed-address', 'reserve', lambda cpu: cpu.reg_write(r.UC_RISCV_REG_A0, 0xdead0000)),
        ('wrong-computed-width', 'reserve', lambda cpu: cpu.reg_write(r.UC_RISCV_REG_A2, 2)),
        ('wrong-computed-value', 'reserve', lambda cpu: cpu.reg_write(
            r.UC_RISCV_REG_A1, cpu.reg_read(r.UC_RISCV_REG_A1) ^ 16)),
        ('changed-preimage', 'reserve', bump(METADATA)),
        ('late-nonce', 'reserve', bump(cold + 28)),
        ('late-IRQ', 'reserve', lambda cpu: cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 8)),
        ('after-store-held-fault', 'write', put(STATE + 16, 1)),
        ('after-store-readback', 'publish', bump(METADATA)),
        ('after-store-neighbor', 'publish', bump(METADATA + 4)),
        ('after-store-TX-effect', 'publish', bump(0x3e8a4020)),
        ('after-publication-readback', 'finish', bump(METADATA)),
        ('after-publication-nonce', 'finish', bump(cold + 28)),
    ]
    rows = []
    try:
        for name, moment, mutate in cases:
            h.restore(before)
            for address, value in originals.items():
                h.put32(address, value)
            h.unmodeled = None
            injected, delegated, stores = [], [], []
            target_before = h.get32(METADATA)
            def inject(cpu, pc, size, data):
                if not injected:
                    mutate(cpu)
                    injected.append(True)
            def observe(cpu, pc, size, data):
                delegated.append(pc)
            def written(cpu, access, address, size, value, data):
                stores.append([address, size, value])
                if moment == 'write' and not injected:
                    mutate(cpu)
                    injected.append(True)
            hooks = [h.cpu.hook_add(UC_HOOK_CODE, observe, begin=0x8400fbb8, end=0x8400fbb8),
                     h.cpu.hook_add(UC_HOOK_MEM_WRITE, written, begin=METADATA, end=METADATA + 3)]
            if moment != 'write':
                site = {'entry': entry, 'reserve': reserve, 'publish': publish, 'finish': finish}[moment]
                hooks.append(h.cpu.hook_add(UC_HOOK_CODE, inject, begin=site, end=site))
            mmio_start = len(h.mmio)
            try:
                reply = h.message(request)
            finally:
                for hook in hooks:
                    h.cpu.hook_del(hook)
            assert injected and reply['flags'] == 7 and reply['words'][14] == 7, (name, reply)
            assert h.unmodeled is None, (name, h.unmodeled)
            assert h.get32(cold) == h.get32(cold + 4) == h.get32(ADM + 4) == 1
            committed = int(moment in ('write', 'publish', 'finish'))
            published = int(moment == 'finish')
            assert [h.get32(owner + 4 * i) for i in (2, 4, 5, 6)] == [1, committed, committed, published], name
            assert bool(delegated) == (moment != 'entry'), (name, delegated)
            assert len(stores) == committed, (name, stores)
            if moment in ('entry', 'reserve') and name != 'changed-preimage':
                assert h.get32(METADATA) == target_before
            if name == 'preowned-lock':
                assert h.get32(h.rx_event.symbols['lock_owned']) == 1
                assert not [row for row in h.mmio[mmio_start:] if row['kind'] == 'mmio-write'
                            and row['address'] in ('0x1ec031c8', '0x1ec03248')]
            rows.append(dict(name=name, moment=moment, committed=committed, published=published,
                             native_stores=stores, original_helper=bool(delegated),
                             retained_active=1, retained_inflight=1, unowned_access=False))
            print(json.dumps(dict(api22_control=name, passed=True)), flush=True)
    finally:
        h.restore(after)
        for address, value in originals.items():
            h.put32(address, value)
    return rows
