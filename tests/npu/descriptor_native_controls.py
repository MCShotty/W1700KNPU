"""Native getter denials from authenticated snapshots; restores are test-only."""
import struct

from unicorn import UC_HOOK_CODE
from test_bootstrap_native import ADM
from emulation_layout import STATE


def check(h, before, request, *, tx=False):
    cold = h.rv.symbols['npu_emulation_cold_setup_state']
    owner = h.descriptor.symbols['npu_emulation_descriptor_state']
    cold_bytes = h.rv.elf.get_section_by_name('.symtab').get_symbol_by_name(
        'npu_emulation_cold_setup_state')[0]['st_size']
    after = h.snapshot() + [(cold, bytes(h.cpu.mem_read(cold, cold_bytes)))]
    metadata, rows = 0x3e901bcc, []
    packet = h.packet.symbols['npu_emulation_packet_state']
    page = h.binding.symbols['npu_emulation_page_state']
    indication = h.binding.symbols['npu_emulation_indication_state']
    tx_state = h.tx.symbols['npu_emulation_tx_state']
    table = 0x8401cf2c
    original = h.get32(table)
    def put(address, value): return lambda: h.put32(address, value)
    def bump(address): return lambda: h.put32(address, h.get32(address) + 32)
    try:
        h.restore(before)
        arena, count = h.get32(0x3e9030fc), h.get32(metadata + 8)
        entries = metadata + 24
        matches = [entries + i * 8 for i in range(count)
                   if h.get32(entries + i * 8) == 1 and h.get32(entries + i * 8 + 4) == arena]
        assert len(matches) == 1 and count < 100
        entry = matches[0]
        def duplicate():
            h.cpu.mem_write(entries + count * 8, struct.pack('<HHI',1,0,arena))
            h.put32(metadata + 8,count + 1)
        pre = [
            ('preowned-lock',put(h.descriptor.symbols['lock_owned'],1)),
            ('wrong-lock', put(metadata,17)), ('denied-lock', put(0x1ec03048,0x10100)),
            ('metadata-overflow',put(metadata + 8,101)), ('missing-entry',put(entry,2)),
            ('reserved-entry',put(entry,0x10001)), ('duplicate-entry',duplicate),
            ('changed-slot0',bump(0x3e902ab0)), ('changed-slot7',bump(0x3e90459c)),
            ('changed-table',put(table,0x22040)),
            ('wrong-port',lambda: h.cpu.mem_write(0x3e90390e,b'\x03')),
            ('packet-fault',put(packet + 8,1)), ('page-fault',put(page + 8,1)),
            ('indication-fault',put(indication + 8,1)), ('TX-fault',put(tx_state + 8,1)),
            ('preseeded-descriptor-owner',put(owner,0x31445343)),
        ]
        late = [
            ('late-used',bump(metadata + 20)), ('late-entry',bump(entry + 4)),
            ('late-slot',bump(0x3e9021ec)), ('late-sequence',bump(cold + 12)),
            ('late-nonce',bump(cold + 28)), ('late-ready',put(STATE + 56,1)),
            ('late-unparked',put(STATE + 24,0)), ('late-deferred',put(ADM + 20,1)),
            ('late-drain',put(STATE + 84,1)), ('late-TX',put(tx_state + 8,1)),
            ('late-preimage',bump(owner + 44)), ('late-owner-stage',put(owner + 16,5)),
        ]
        cases = late if tx else pre
        for name, mutate in cases:
            h.restore(before); h.put32(table,original); h.put32(0x1ec03048,0x10000)
            protected = {address:bytes(h.cpu.mem_read(address,size)) for address,size in
                         ((packet,2076),(page,1052),(indication,32),(tx_state,80))}
            before_ring = bytes(h.cpu.mem_read(arena + 0x6020,8192))
            delegated, injected = [], []
            def observe(cpu,pc,size,data):
                if pc == 0x8400d836: delegated.append(pc)
                if tx and not injected and pc == h.descriptor.symbols['npu_emulation_descriptor_status0']:
                    mutate(); injected.append(True)
            hook = h.cpu.hook_add(UC_HOOK_CODE,observe)
            first_mmio = len(h.mmio)
            try:
                if not tx: mutate()
                reply = h.message(request)
            finally: h.cpu.hook_del(hook)
            assert reply['flags'] == 7 and reply['words'][14] == 7, (name,reply)
            assert h.get32(cold) == h.get32(cold + 4) == h.get32(ADM + 4) == 1
            assert h.get32(cold + 8) == 131071 and h.get32(ADM + 8) == h.get32(STATE + 16) == 1
            assert h.get32(owner + 8) == 1 and h.get32(owner + 36) == h.get32(owner + 40) == 0
            assert h.get32(cold + 104) == (6 if tx else 0)
            assert (len(delegated) == 1 and injected) if tx else not delegated
            assert bytes(h.cpu.mem_read(arena + 0x6020,8192)) == before_ring
            if name == 'preowned-lock':
                assert h.get32(h.descriptor.symbols['lock_owned']) == 1
                assert not [row for row in h.mmio[first_mmio:] if row['kind'] == 'mmio-write'
                            and row['address'] in ('0x1ec031c8','0x1ec03248')]
            skipped = {'packet-fault':packet,'page-fault':page,'indication-fault':indication,
                       'TX-fault':tx_state,'late-TX':tx_state}.get(name)
            for address,value in protected.items():
                if address != skipped: assert bytes(h.cpu.mem_read(address,len(value))) == value
            rows.append(dict(name=name,phase='late' if tx else 'pre',original_helper=bool(delegated),
                             descriptor_stores=0,committed=0,published=0,retained_active=1,retained_inflight=1))
    finally:
        h.restore(after); h.put32(table,original); h.put32(0x1ec03048,0x10000)
    return rows
