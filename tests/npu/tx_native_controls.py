"""Native TX denials from an authenticated pre-TX0 snapshot; no reset API."""
import struct

from unicorn import UC_HOOK_CODE
from test_bootstrap_native import ADM
from emulation_layout import STATE

REGS = (0x1fc08030, 0x1fc08034, 0x1fc48030, 0x1fc48034)


def check(h, before, request):
    cold = h.rv.symbols['npu_emulation_cold_setup_state']
    after = h.snapshot() + [(cold, bytes(h.cpu.mem_read(cold, 120)))]
    registers_after = [h.get32(address) for address in REGS]
    core = h.tx.symbols['npu_emulation_tx_state']
    plan = h.tx.symbols['npu_emulation_tx_plan']
    packet = h.packet.symbols['npu_emulation_packet_state']
    page = h.binding.symbols['npu_emulation_page_state']
    induction = h.binding.symbols['npu_emulation_indication_state']
    metadata, rows = 0x3e901bcc, []
    code_address = 0x8401cf24
    code_value = h.get32(code_address)
    def set_word(address, value):
        return lambda: h.put32(address, value)
    def bump(address):
        return lambda: h.put32(address, h.get32(address) + 32)
    try:
        h.restore(before['memory'])
        arena = h.get32(0x3e9030fc)
        count = h.get32(metadata + 8)
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
            ('preowned-lock', set_word(h.tx.symbols['lock_owned'], 1)),
            ('wrong-lock', set_word(metadata, 17)),
            ('denied-lock', set_word(0x1ec03048, 0x10100)),
            ('oversize-metadata', set_word(metadata + 8, 101)),
            ('missing-reservation', set_word(entry, 2)),
            ('reserved-reservation', set_word(entry, 0x10001)),
            ('duplicate-reservation', duplicate),
            ('arena-changed', bump(0x3e9030fc)),
            ('subregion-changed', set_word(code_address, 0x22040)),
            ('wrong-port', lambda: h.cpu.mem_write(0x3e90390e, b'\x03')),
            ('preseeded-host-pointer', set_word(0x3e904700, 1)),
            ('dirty-index0', set_word(0x3e903978, 1)),
            ('dirty-index1', set_word(0x3e9021f4, 1)),
            ('indication-fault', set_word(induction + 8, 1)),
            ('indication-incomplete', set_word(induction + 20, 1535)),
            ('preseeded-TX-owner', set_word(core, 0x31585443)),
        ]
        late = [
            ('late-used', bump(metadata + 20)), ('late-count', set_word(metadata + 8, count + 1)),
            ('late-entry', bump(entry + 4)), ('late-sequence', bump(cold + 12)),
            ('late-nonce', bump(cold + 28)), ('late-host-plan', bump(plan + 16)),
            ('late-register-preimage', bump(REGS[0])), ('late-worker-ready', set_word(STATE + 56, 1)),
            ('late-worker-unparked', set_word(STATE + 24, 0)), ('late-deferred', set_word(ADM + 20, 1)),
            ('late-drain', set_word(STATE + 84, 1)), ('late-indication', set_word(induction + 8, 1)),
        ]
        for phase, cases in [('pre', pre), ('late', late)]:
            for name, mutate in cases:
                h.restore(before['memory'])
                for address, value in zip(REGS, before['registers']): h.put32(address, value)
                h.put32(0x1ec03048, 0x10000); h.put32(code_address, code_value)
                protected = {address: bytes(h.cpu.mem_read(address, size)) for address, size in
                             ((packet,2076), (page,1052), (induction,32))}
                hook, injected = None, []
                if phase == 'pre': mutate()
                else:
                    def inject(cpu, pc, size, data):
                        if not injected and pc == h.tx.symbols['npu_emulation_tx_reg0']:
                            mutate(); injected.append(True)
                    hook = h.cpu.hook_add(UC_HOOK_CODE, inject)
                first = len(h.mmio)
                try: reply = h.message(request)
                finally:
                    if hook is not None: h.cpu.hook_del(hook)
                assert reply['flags'] == 7 and reply['words'][14] == 7, (name, reply)
                assert h.get32(cold) == h.get32(cold + 4) == h.get32(ADM + 4) == 1
                assert h.get32(cold + 8) == 16383 and h.get32(STATE + 16) == h.get32(ADM + 8) == 1
                assert h.get32(core + 8) == 1
                assert h.get32(core + 24) == h.get32(core + 28) == (3 if phase == 'late' else 0)
                stores = [row for row in h.mmio[first:] if row['kind'] == 'mmio-write' and int(row['address'],16) in REGS]
                assert not stores, ('denied-native-register-store', name)
                if name == 'preowned-lock':
                    assert h.get32(h.tx.symbols['lock_owned']) == 1
                    assert not [row for row in h.mmio[first:] if row['kind'] == 'mmio-write'
                                and row['address'] in ('0x1ec031c8', '0x1ec03248')]
                for address, value in protected.items():
                    if address != induction or name not in ('indication-fault', 'indication-incomplete', 'late-indication'):
                        assert bytes(h.cpu.mem_read(address,len(value))) == value
                assert phase == 'pre' or injected
                rows.append(dict(name=name, phase=phase, register_stores=0,
                                 committed=h.get32(core + 24), published=h.get32(core + 28),
                                 retained_active=1, retained_inflight=1))
    finally:
        h.restore(after)
        for address,value in zip(REGS,registers_after): h.put32(address,value)
        h.put32(code_address,code_value); h.put32(0x1ec03048,0x10000)
    return rows
