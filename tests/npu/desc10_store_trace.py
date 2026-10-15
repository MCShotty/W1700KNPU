"""Read-only original-store/lock tracing for the authenticated DESC10 caller."""
import hashlib
import json
import struct

from unicorn import UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r

from desc10_effect_oracle import EffectOracle, STORES, IDS, OCCUPIED, CAPACITY
from txdone_wire_native import STORES as HOOK_SITES


def original_sites():
    result = [(0xb45e, 0xb530), (0xb46a, 0xb53c)]
    result += [(site,) for _ in range(IDS) for site in (0xb4b6, 0xb4ba, 0xb4bc, 0xb4c0, 0xb4ce, 0xb4d6)]
    for site, count in ((0x4a62, OCCUPIED), (0x9b04, OCCUPIED), (0x4aac, CAPACITY),
                        (0x4ad2, OCCUPIED), (0x4afa, OCCUPIED), (0x4b32, CAPACITY - OCCUPIED)):
        result += [(site,)] * count
    result += [(site,) for site in (0x4b5c, 0x4b60, 0xb54a, 0xb558)]
    assert len(result) == STORES
    return tuple(tuple(0x84000000 + site for site in choices) for choices in result)


class Desc10Trace:
    LOCKS = (0x1ec031f0, 0x1ec03270, 0x1ec031cc, 0x1ec031d0, 0x1ec03250, 0x1ec0324c)

    def __init__(self, h, request):
        self.h, self.oracle = h, EffectOracle(h, request)
        self.packet = h.packet.symbols['npu_emulation_packet_state']
        self.packet_before = bytes(h.cpu.mem_read(self.packet, 2076))
        self.sites = {h.desc10.symbols[f'npu_emulation_desc10_{site:x}_store']: 0x84000000 + site
                      for site in (*HOOK_SITES, 0xb4bc)}
        assert len(self.sites) == 20
        self.stores, self.locks, self.hook = [], [], None

    def write(self, cpu, access, address, size, value, unused):
        pc = cpu.reg_read(r.UC_RISCV_REG_PC)
        if pc in self.sites:
            self.stores.append((self.sites[pc], address, size, value & ((1 << (size * 8)) - 1)))
        if address in self.LOCKS:
            self.locks.append((address, size, value))

    def __enter__(self):
        assert self.hook is None
        self.hook = self.h.cpu.hook_add(UC_HOOK_MEM_WRITE, self.write)
        return self

    def __exit__(self, *error):
        self.h.cpu.hook_del(self.hook)
        self.hook = None

    def validate(self):
        assert len(self.stores) == STORES, ('original-store-count', len(self.stores))
        choices = original_sites()
        for index, ((site, address, size, value), expected) in enumerate(zip(self.stores, self.oracle.events)):
            assert site in choices[index], ('wrong-original-store-site', index, hex(site), choices[index])
            assert (address, size, value) == expected, ('original-store-effect', index)
        expected_locks = [(self.LOCKS[0], 4, 0x40), (self.LOCKS[1], 4, 0)] * IDS
        expected_locks += [(self.LOCKS[2], 4, 0x40), (self.LOCKS[3], 4, 0x40),
                           (self.LOCKS[4], 4, 0), (self.LOCKS[5], 4, 0)]
        assert self.locks == expected_locks, 'original-ordered-lock-footprint'
        expected_memory = self.oracle.memory_prefix(STORES, IDS)
        assert all(bytes(self.h.cpu.mem_read(base, len(data))) == data for base, data in expected_memory.items()), (
            'effect-oracle-memory')
        assert bytes(self.h.cpu.mem_read(self.packet, 2076)) == self.oracle.packet_prefix(self.packet_before, IDS), (
            'exact-private-packet-state')

    def save(self, directory):
        directory.mkdir()
        actual = b''.join(struct.pack('<4I', *event) for event in self.stores)
        expected = b''.join(struct.pack('<3I', *event) for event in self.oracle.events)
        for name, contents in (('actual-stores.bin', actual), ('expected-effects.bin', expected)):
            with (directory / name).open('xb') as stream:
                stream.write(contents)
        result = dict(actual_stores=len(self.stores), expected_stores=STORES,
            original_copied_store_sites=len(self.sites), ordered_lock_writes=self.locks,
            actual_stores_sha256=hashlib.sha256(actual).hexdigest(),
            expected_effects_sha256=hashlib.sha256(expected).hexdigest(),
            guest_writes_by_observer=False, validation_is_separate=True,
            limits=['Only actual copied original store PCs count; the b4bc store shares the six-byte b4ba detour.',
                    'The observer records writes without changing guest memory/registers or native guards.',
                    'A saved trace is not a passing verdict until ordered sites/effects/locks/private state and memory validate.'])
        (directory / 'trace.json').write_text(json.dumps(result, indent=2) + '\n')
        return result
