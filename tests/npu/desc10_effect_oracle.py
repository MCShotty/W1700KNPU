"""Pre-state-derived original DESC10 stores and retained partial-memory effects.

This is a test oracle, not an ownership grant or evidence of store execution.
Runtime callers must compare actual site events as well as final memory.
"""
import struct

from unicorn import riscv_const as r

from desc10_transaction_oracle import transaction_metadata
from emulation_layout import SRAM, STATE
from test_attach_tx_callbacks import done_images
from test_bootstrap_native import ADM

IDS, CAPACITY, OCCUPIED, STORES = 512, 8192, 2048, 25606


class EffectOracle:
    def __init__(self, h, request):
        self.before = {base: bytes(data) for base, data in done_images(h).items()}
        self.state_address, session, self.transaction = transaction_metadata(h, request)
        assert self.read(self.state_address, 20) == session
        self.gp = h.cpu.reg_read(r.UC_RISCV_REG_GP)
        self.head = self.number(SRAM + 0x1ba4, 2)
        tail = self.number(SRAM + 0x1b80, 2)
        assert self.head < 16384 and tail < 16384 and (tail - self.head - 1) % 16384 >= IDS
        pool = self.number(SRAM + 0x1b88)
        self.ids = tuple(self.number(pool + ((self.head + i) % 16384) * 2, 2) for i in range(IDS))
        assert len(set(self.ids)) == IDS and all(ident < 16384 for ident in self.ids)
        assert h.fixed[0x107] == 0x3e8adc70
        packet, ring = self.number(SRAM + 0x396c), self.number(SRAM + 0x3964)
        self.stats = self.number(SRAM + 0x1f08)
        self.number(self.stats + 0x20)
        assert self.number(self.gp - 0x7e8) == CAPACITY
        temporary, check, queue = (self.number(address) for address in
                                    (SRAM + 0x1bc0, SRAM + 0x469c, self.gp + 0x7dc))
        tx_packet = self.number(SRAM + 0x2ab8)
        occupied = []
        for band in range(2):
            descriptors = self.number(SRAM + 0x1f28 + band * 4)
            for index in range(1024):
                pointer = self.number(descriptors + index * 32 + 8)
                occupied.append(((pointer - tx_packet) & 0xffffffff) >> 11 & 0xffff)
        self.occupied = tuple(occupied)
        assert len(set(occupied)) == OCCUPIED and all(ident < CAPACITY for ident in occupied)
        events = [(SRAM + 0x2a7c, 2, IDS), (SRAM + 0x2cf4, 4, h.fixed[0x107])]
        for index, ident in enumerate(self.ids):
            address = ring + index * 16
            pointer = ((packet + ident * 2048) & 0x3fffffff | 0x80000000) + 128
            events.extend(((address + 4, 4, 0), (address, 4, pointer),
                           (address + 8, 4, 0), (address + 12, 4, 0),
                           (address + 4, 4, 0x07000100), (h.fixed[0x107] + index * 2, 2, ident)))
        events.extend((temporary + i * 2, 2, 65535) for i in range(OCCUPIED))
        events.extend((temporary + i * 2, 2, ident) for i, ident in enumerate(occupied))
        events.extend((check + i * 2, 2, 0) for i in range(CAPACITY))
        events.extend((check + ident * 2, 2, 3) for ident in occupied)
        taken = set(occupied)
        ordered = occupied + [ident for ident in range(CAPACITY) if ident not in taken]
        events.extend((queue + i * 2, 2, ident) for i, ident in enumerate(ordered))
        events.extend(((SRAM + 0x1bb4, 2, OCCUPIED), (self.gp + 0x7ec, 2, 0),
                       (SRAM + 0x3974, 4, 0), (SRAM + 0x46fa, 1, 1)))
        assert len(events) == STORES
        self.events = tuple(events)

    def read(self, address, size):
        matches = [data[address - base:address - base + size] for base, data in self.before.items()
                   if base <= address and address + size <= base + len(data)]
        assert len(matches) == 1, ('oracle-read-span', hex(address), size)
        return matches[0]

    def number(self, address, size=4):
        return int.from_bytes(self.read(address, size), 'little')

    @staticmethod
    def put(images, address, size, value):
        assert size in (1, 2, 4) and address % size == 0
        matches = [(base, data) for base, data in images.items()
                   if base <= address and address + size <= base + len(data)]
        assert len(matches) == 1, ('oracle-write-span', hex(address), size)
        base, image = matches[0]
        image[address - base:address - base + size] = (value & ((1 << (8 * size)) - 1)).to_bytes(size, 'little')

    def memory_prefix(self, stores, queue_publications, *, allocation_errors=0, fault=False, mutations=()):
        assert isinstance(stores, int) and 0 <= stores <= STORES
        assert isinstance(queue_publications, int) and 0 <= queue_publications <= IDS
        assert isinstance(allocation_errors, int) and 0 <= allocation_errors <= 1
        images = {base: bytearray(data) for base, data in self.before.items()}
        for effect in self.events[:stores]:
            self.put(images, *effect)
        if queue_publications:
            self.put(images, SRAM + 0x1ba4, 2, (self.head + queue_publications) % 16384)
            for address in (SRAM + 0x1b90, self.stats + 0x1c):
                self.put(images, address, 4, self.number(address) + queue_publications)
        if allocation_errors:
            self.put(images, self.stats + 0x20, 4, self.number(self.stats + 0x20) + allocation_errors)
        self.put(images, int(self.transaction['address'], 16), 4, self.transaction['expected'])
        if fault:
            for address in (ADM, ADM + 8, STATE + 16):
                self.put(images, address, 4, 1)
        for mutation in mutations:
            self.put(images, *mutation)
        return images

    def packet_prefix(self, before, claims, *, fault=False):
        assert len(before) == 2076 and isinstance(claims, int) and 0 <= claims <= IDS
        words = list(struct.unpack('<519I', before))
        assert words[:3] == [0x314b5043, 1, 0] and words[3] == self.head and words[4] == 2560
        assert sum(word.bit_count() for word in words[7:]) == words[4]
        for ident in self.ids[:claims]:
            word, bit = 7 + ident // 32, 1 << (ident % 32)
            assert not words[word] & bit, ('already-claimed-input', ident)
            words[word] |= bit
        words[2] = int(fault)
        words[3] = (words[3] + claims) % 16384
        words[4] += claims
        return struct.pack('<519I', *words)
