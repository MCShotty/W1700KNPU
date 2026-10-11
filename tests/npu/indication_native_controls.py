"""Negative native replays from an actual-C-produced pre-DESC8 snapshot."""
import struct

from unicorn import UC_HOOK_CODE
from test_bootstrap_native import ADM
from emulation_layout import STATE


def check(h, before, request):
    core = h.binding.symbols['npu_emulation_indication_state']
    plan = h.binding.symbols['npu_emulation_indication_plan']
    cold = h.rv.symbols['npu_emulation_cold_setup_state']
    after = h.snapshot() + [(cold, bytes(h.cpu.mem_read(cold, 120)))]
    packet = h.packet.symbols['npu_emulation_packet_state']
    page = h.binding.symbols['npu_emulation_page_state']
    rows = []
    code_words = {address: h.get32(address) for address in (0x8401cf38, 0x8401cf3c, 0x8401cfcc)}

    def word(address, value):
        return lambda: h.put32(address, value)

    def bump(address):
        return lambda: h.put32(address, h.get32(address) + 32)

    try:
        h.restore(before)
        arena = h.get32(0x3e9030fc)
        base = arena + 0x1f020
        metadata, count = 0x3e901bcc, h.get32(0x3e901bd4)
        entries = metadata + 24
        matching = [entries + i * 8 for i in range(count)
                    if bytes(h.cpu.mem_read(entries + i * 8, 4)) == b'\x01\0\0\0'
                    and h.get32(entries + i * 8 + 4) == arena]
        assert len(matching) == 1 and count < 100
        entry = matching[0]

        def duplicate():
            h.cpu.mem_write(entries + count * 8, struct.pack('<HHI', 1, 0, arena))
            h.put32(metadata + 8, count + 1)

        pre = [
            ('preowned-lock', word(h.binding.symbols['lock_owned'], 1)),
            ('wrong-lock-id', word(metadata, 17)),
            ('denied-lock18', word(0x1ec03048, 0x10100)),
            ('metadata-over-capacity', word(metadata + 8, 101)),
            ('missing-reservation', word(entry, 2)),
            ('reserved-reservation', word(entry, 0x10001)),
            ('duplicate-reservation', duplicate),
            ('arena-changed', bump(0x3e9030fc)),
            ('subregion-type', word(0x8401cf38, 7)),
            ('subregion-offset', word(0x8401cf3c, 0x1f040)),
            ('arena-definition-size', word(0x8401cfcc, 303136)),
            ('bound-indication-pointer', bump(0x3e902a9c)),
            ('preseeded-ring', word(0x3e902aa0, base)),
            ('preseeded-index', word(0x3e901fd4, 1)),
            ('preseeded-index-byte', lambda: h.cpu.mem_write(0x3e904590, b'\x01')),
            ('dirty-first-header', word(base, 1)),
            ('dirty-first-status', word(base + 4, 0xe0000000)),
            ('dirty-last-header', word(base + 12280, 1)),
            ('dirty-last-status', word(base + 12284, 1)),
            ('preseeded-owner', word(core, 0x31444e49)),
        ]
        late = [
            ('late-used', bump(metadata + 20)),
            ('late-count', word(metadata + 8, count + 1)),
            ('late-reservation-address', bump(entry + 4)),
            ('late-reservation-tag', word(entry, 0x10001)),
            ('late-sequence', bump(cold + 12)),
            ('late-nonce', bump(cold + 28)),
            ('late-count-history', word(cold + 64, 1535)),
            ('late-plan-base', bump(plan)),
            ('late-plan-size', word(plan + 4, 12256)),
            ('late-ring-pointer', bump(0x3e902aa0)),
            ('late-arena', bump(0x3e9030fc)),
            ('late-worker-ready', word(STATE + 52 + 4, 1)),
            ('late-worker-unparked', word(STATE + 20 + 4, 0)),
            ('late-drain', word(STATE + 84, 1)),
            ('late-deferred-irq', word(ADM + 20, 1)),
        ]
        for phase, cases in (('pre', pre), ('late', late)):
            for name, mutate in cases:
                h.restore(before)
                h.put32(0x1ec03048, 0x10000)
                for address, value in code_words.items():
                    h.put32(address, value)
                original_packet = bytes(h.cpu.mem_read(packet, 2076))
                original_page = bytes(h.cpu.mem_read(page, 1052))
                hook, injected = None, []
                if phase == 'pre':
                    mutate()
                else:
                    def inject(cpu, pc, size, data):
                        if not injected and pc == h.binding.symbols['npu_emulation_indication_store']:
                            mutate()
                            injected.append(True)
                    hook = h.cpu.hook_add(UC_HOOK_CODE, inject)
                initial_records = bytes(h.cpu.mem_read(base, 12288))
                first_mmio = len(h.mmio)
                try:
                    reply = h.message(request)
                finally:
                    if hook is not None:
                        h.cpu.hook_del(hook)
                assert reply['flags'] == 7 and reply['words'][14] == 7, ('native-indication-denial', name, reply)
                assert h.get32(cold) == h.get32(cold + 4) == h.get32(ADM + 4) == 1
                assert h.get32(cold + 8) == 4095 and h.get32(ADM + 8) == h.get32(STATE + 16) == 1
                assert h.get32(core + 8) == 1 and h.get32(core + 16) == int(phase == 'late')
                assert h.get32(core + 20) == 0
                assert bytes(h.cpu.mem_read(base, 12288)) == initial_records, ('denied-record-store', name)
                assert bytes(h.cpu.mem_read(packet, 2076)) == original_packet
                assert bytes(h.cpu.mem_read(page, 1052)) == original_page
                locks = [(row['address'], row['value']) for row in h.mmio[first_mmio:]
                         if row['kind'] == 'mmio-write' and row['address'] in ('0x1ec031c8', '0x1ec03248')]
                expected_locks = [('0x1ec031c8', 0x40)] if name == 'denied-lock18' else (
                    [('0x1ec031c8', 0x40), ('0x1ec03248', 0)] if phase == 'late' or name in
                    ('missing-reservation', 'reserved-reservation', 'duplicate-reservation',
                     'dirty-first-header', 'dirty-first-status', 'dirty-last-header',
                     'dirty-last-status', 'preseeded-owner') else [])
                assert locks == expected_locks, ('native-lock18-footprint', name, locks)
                if name == 'preowned-lock':
                    assert h.get32(h.binding.symbols['lock_owned']) == 1
                assert phase == 'pre' or injected
                rows.append(dict(name=name, phase=phase, retained_claims=int(phase == 'late'),
                                 published=0, original_record_store=False, locks=locks,
                                 reply_status=reply['words'][14]))
    finally:
        h.restore(after)
        h.put32(0x1ec03048, 0x10000)
        for address, value in code_words.items():
            h.put32(address, value)
    return rows
