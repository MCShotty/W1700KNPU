"""Synthetic pre-state tests; no native execution or ownership admission."""
import struct
from types import SimpleNamespace
import unittest

from unicorn import riscv_const as r

from desc10_effect_oracle import EffectOracle, STORES
import desc10_transaction_oracle as legacy
from emulation_layout import SRAM, HEAP, STATE
from test_attach_tx_callbacks import IMAGES, HOST, HOST_BYTES, SKB_STATE, SKB_BYTES
from test_bootstrap_native import ADM


class Memory:
    def __init__(self):
        self.images = {base: bytearray(b'\xa5' * size) for base, size in
                       (*IMAGES, (HOST, HOST_BYTES), (SKB_STATE, SKB_BYTES))}

    def mem_read(self, address, size):
        for base, data in self.images.items():
            if base <= address and address + size <= base + len(data):
                return bytes(data[address - base:address - base + size])
        raise AssertionError(('fixture-read', hex(address), size))

    def reg_read(self, register):
        assert register == r.UC_RISCV_REG_GP
        return SRAM + 0x13a8

    def put(self, address, value, size=4):
        EffectOracle.put(self.images, address, size, value)


class EffectOracleTests(unittest.TestCase):
    def fixture(self, head=2560):
        cpu = Memory()
        queue, temporary, pool, stats = (HEAP + offset for offset in (0x30000, 0x26000, 0, 0x24000))
        for address, value, width in ((SRAM + 0x1ba4, head, 2), (SRAM + 0x1b80, 7000, 2),
            (SRAM + 0x1b88, pool, 4), (SRAM + 0x396c, 0x8a000000, 4),
            (SRAM + 0x3964, HOST, 4), (SRAM + 0x1f08, stats, 4),
            (SRAM + 0xbc0, 8192, 4), (SRAM + 0x1bc0, temporary, 4),
            (SRAM + 0x469c, SKB_STATE, 4), (SRAM + 0x1b84, queue, 4),
            (SRAM + 0x2ab8, 0x8cc00000, 4), (SRAM + 0x3974, 0x87654321, 4),
            (SRAM + 0x46fa, 0, 1), (SRAM + 0x1b90, 1234, 4),
            (stats + 0x1c, 5678, 4), (stats + 0x20, 23, 4)):
            cpu.put(address, value, width)
        self.ids = tuple(8000 + i * 13 % 512 for i in range(512))
        for i, ident in enumerate(self.ids):
            cpu.put(pool + ((head + i) % 16384) * 2, ident, 2)
        for band in range(2):
            ring = HEAP + 0x10000 + band * 0x8000
            cpu.put(SRAM + 0x1f28 + band * 4, ring)
            for i in range(1024):
                occupied = ((band * 1024 + i) * 17 + 7) % 8192
                cpu.put(ring + i * 32 + 8, 0x8cc00000 + occupied * 2048)
        state = SRAM + 0x6380
        session = [0x12345678, 0x9abcdef0, 0x9abcdef0, 0x12345678, 56]
        for i, value in enumerate(session):
            cpu.put(state + i * 4, value)
        h = SimpleNamespace(cpu=cpu, rv=SimpleNamespace(symbols={'npu_emulation_control_v2_state': state}),
                            fixed={0x107: 0x3e8adc70})
        request = [0x3f, 1, 0x3253434e, 2, 80, 1, 57, *session[2:4], *session[:2],
                   0x1a, 1, 512] + [0] * 6
        return h, request

    def test_full_fold_matches_independent_existing_constructor_oracle(self):
        h, request = self.fixture()
        before = {base: bytes(data) for base, data in h.cpu.images.items()}
        oracle = EffectOracle(h, request)
        reference, _, _ = legacy.expected(h, request)
        self.assertEqual(oracle.memory_prefix(STORES, 512), reference)
        self.assertEqual({base: bytes(data) for base, data in h.cpu.images.items()}, before)
        self.assertEqual(len(oracle.events), 25606)
        self.assertEqual(oracle.ids, self.ids)

    def test_partial_descriptor_prefix_and_neighbors_are_retained(self):
        h, request = self.fixture()
        oracle = EffectOracle(h, request)
        result = oracle.memory_prefix(2 + 17 * 6, 17, fault=True)
        full = oracle.memory_prefix(STORES, 512)
        self.assertEqual(result[HOST][:17 * 16], full[HOST][:17 * 16])
        self.assertEqual(result[HOST][17 * 16:], oracle.before[HOST][17 * 16:])
        self.assertEqual(int.from_bytes(result[SRAM][0x1ba4:0x1ba6], 'little'), 2577)
        self.assertEqual(result[SRAM][0x46fa], 0)
        for address in (ADM, ADM + 8, STATE + 16):
            self.assertEqual(int.from_bytes(result[SRAM][address - SRAM:address - SRAM + 4], 'little'), 1)

    def test_before_ready_guard_prefix_has_no_counter_or_ready_store(self):
        h, request = self.fixture()
        oracle = EffectOracle(h, request)
        result = oracle.memory_prefix(STORES - 2, 512, fault=True)
        self.assertEqual(result[SRAM][0x3974:0x3978], oracle.before[SRAM][0x3974:0x3978])
        self.assertEqual(result[SRAM][0x46fa], 0)
        self.assertEqual(oracle.events[-2:], ((SRAM + 0x3974, 4, 0), (SRAM + 0x46fa, 1, 1)))

    def test_fault_injections_are_explicit_not_copied_from_post_state(self):
        h, request = self.fixture()
        oracle = EffectOracle(h, request)
        h.cpu.put(SRAM + 0x2a7c, 999, 2)
        nominal = oracle.memory_prefix(1, 0)
        mutated = oracle.memory_prefix(1, 0, mutations=((SRAM + 0x2a7c, 2, 513),))
        self.assertEqual(nominal[SRAM][0x2a7c:0x2a7e], struct.pack('<H', 512))
        self.assertEqual(mutated[SRAM][0x2a7c:0x2a7e], struct.pack('<H', 513))

    def test_queue_publication_is_distinct_from_private_claim(self):
        h, request = self.fixture()
        oracle = EffectOracle(h, request)
        packet = [0x314b5043, 1, 0, 2560, 2560, 0x8a000000, 0x2c00000] + [0] * 512
        for ident in range(2560):
            packet[7 + ident // 32] |= 1 << (ident % 32)
        retained = struct.unpack('<519I', oracle.packet_prefix(struct.pack('<519I', *packet), 1, fault=True))
        images = oracle.memory_prefix(2, 0, fault=True)
        self.assertEqual(retained[2:5], (1, 2561, 2561))
        self.assertEqual(int.from_bytes(images[SRAM][0x1ba4:0x1ba6], 'little'), 2560)

    def test_queue_wrap_and_u32_statistics_wrap(self):
        h, request = self.fixture(head=16380)
        stats = HEAP + 0x24000
        h.cpu.put(stats + 0x1c, 0xfffffff0)
        oracle = EffectOracle(h, request)
        result = oracle.memory_prefix(STORES, 512)
        self.assertEqual(int.from_bytes(result[SRAM][0x1ba4:0x1ba6], 'little'), 508)
        self.assertEqual(int.from_bytes(result[HEAP][0x2401c:0x24020], 'little'), 0x1f0)

    def test_duplicate_fifo_or_occupied_inputs_are_rejected(self):
        for target in (HEAP + (2560 + 1) * 2, HEAP + 0x10000 + 32 + 8):
            h, request = self.fixture()
            original = target - (2 if target < HEAP + 0x10000 else 32)
            size = 2 if target < HEAP + 0x10000 else 4
            h.cpu.put(target, int.from_bytes(h.cpu.mem_read(original, size), 'little'), size)
            with self.assertRaises(AssertionError):
                EffectOracle(h, request)

    def test_bad_prefix_and_out_of_span_mutation_are_rejected(self):
        h, request = self.fixture()
        oracle = EffectOracle(h, request)
        for stores, claims in ((-1, 0), (STORES + 1, 512), (0, -1), (0, 513)):
            with self.assertRaises(AssertionError):
                oracle.memory_prefix(stores, claims)
        with self.assertRaisesRegex(AssertionError, 'oracle-write-span'):
            oracle.memory_prefix(0, 0, mutations=((0xdead0000, 4, 1),))

    def test_packet_claim_count_alone_is_not_an_ownership_witness(self):
        h, request = self.fixture()
        oracle = EffectOracle(h, request)
        packet = [0] * 519
        packet[1:5] = [1, 0, 2560, 2560]
        with self.assertRaises(AssertionError):
            oracle.packet_prefix(struct.pack('<519I', *packet), 0)


if __name__ == '__main__':
    unittest.main()
