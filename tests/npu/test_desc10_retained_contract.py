"""Synthetic retained-fault oracle and injection contracts, not native proof."""
from types import SimpleNamespace
import struct
import unittest

from emulation_layout import SRAM, STATE
from test_bootstrap_native import ADM
from test_desc10_retained_controls import CASES, Injection, expected_locks, expected_memory, validate_trace
import test_desc10_store_trace as traces


class RetainedFaultContractTests(unittest.TestCase):
    def trace(self):
        return traces.StoreTraceTests().fixture()

    def test_all_eight_legacy_classes_keep_full_size_prefix_contracts(self):
        self.assertEqual([case.name for case in CASES], [
            'denied', 'partial-pool', 'claim-fault', 'head-changed', 'release-fault',
            'denied-skb19', 'before-ready-bitmap', 'before-ready-plan'])
        for case in CASES:
            with self.subTest(case=case.name):
                trace = self.trace()
                trace.stores = trace.stores[:case.stores]
                trace.locks = expected_locks(case)
                validate_trace(trace, case)
                images, packet = expected_memory(trace, case)
                self.assertEqual(images[SRAM][0x46fa], 0)
                self.assertEqual(struct.unpack_from('<I', images[SRAM], ADM + 4 - SRAM)[0], 1)
                self.assertEqual(struct.unpack_from('<3I', packet, 8), (1, 2560 + case.claims, 2560 + case.claims))
                self.assertEqual(len(packet), 2076)

    def test_private_claim_is_retained_when_native_head_cannot_publish(self):
        trace = self.trace()
        case = next(case for case in CASES if case.name == 'head-changed')
        images, packet = expected_memory(trace, case)
        self.assertEqual(struct.unpack_from('<H', images[SRAM], 0x1ba4)[0], 37)
        self.assertEqual(struct.unpack_from('<2I', packet, 12), (2561, 2561))
        self.assertEqual(case.published, 0)

    def test_readiness_prefix_retains_counter_and_excludes_two_final_stores(self):
        trace = self.trace()
        for case in CASES[-2:]:
            images, _ = expected_memory(trace, case)
            self.assertEqual(case.stores, 25604)
            self.assertEqual(images[SRAM][0x3974:0x3978], trace.oracle.before[SRAM][0x3974:0x3978])
            self.assertEqual(len(expected_locks(case)), 1028)

    def test_missing_idempotent_store_wrong_site_and_wrong_value_each_fail(self):
        case = CASES[-1]
        for mutation in ('missing', 'site', 'value'):
            with self.subTest(mutation=mutation):
                trace = self.trace()
                trace.stores = trace.stores[:case.stores]
                trace.locks = expected_locks(case)
                old = trace.stores[8000]
                if mutation == 'missing':
                    del trace.stores[8000]
                elif mutation == 'site':
                    trace.stores[8000] = (0x8400b4b6, *old[1:])
                else:
                    trace.stores[8000] = (*old[:3], old[3] ^ 1)
                with self.assertRaises(AssertionError):
                    validate_trace(trace, case)

    def injection(self, name):
        trace = self.trace()
        h = trace.h
        h.cpu.mem_write = lambda address, contents: h.cpu.put(address, int.from_bytes(contents, 'little'), len(contents))
        h.get32 = lambda address: int.from_bytes(h.cpu.mem_read(address, 4), 'little')
        return Injection(h, trace, next(case for case in CASES if case.name == name))

    def test_partial_pool_mutates_only_at_eighteenth_take(self):
        injection = self.injection('partial-pool')
        for _ in range(17):
            injection.instruction(None, 0, 4, None)
        self.assertFalse(injection.injected)
        injection.instruction(None, 0, 4, None)
        self.assertEqual(len(injection.injected), 1)
        self.assertEqual(injection.h.cpu.mem_read(SRAM + 0x1b80, 2), struct.pack('<H', 2578))
        injection.instruction(None, 0, 4, None)
        self.assertEqual(len(injection.injected), 1)

    def test_release_fault_waits_for_actual_private_claim(self):
        injection = self.injection('release-fault')
        packet = injection.trace.packet
        injection.h.cpu.put(packet + 16, 2560)
        injection.instruction(None, 0x8400651c, 4, None)
        self.assertFalse(injection.injected)
        injection.h.cpu.put(packet + 16, 2561)
        injection.instruction(None, 0x8400651c, 4, None)
        self.assertEqual(injection.h.get32(STATE + 16), 1)
        self.assertEqual(len(injection.injected), 1)

    def test_claim_fault_target_is_not_the_native_head(self):
        injection = self.injection('claim-fault')
        injection.count(None, 0, injection.trace.packet + 16, 4, 2560, None)
        self.assertFalse(injection.injected)
        injection.count(None, 0, injection.trace.packet + 16, 4, 2561, None)
        self.assertEqual(injection.h.get32(injection.trace.packet + 8), 1)
        self.assertEqual(injection.h.cpu.mem_read(SRAM + 0x1ba4, 2), struct.pack('<H', 3072))


if __name__ == '__main__':
    unittest.main()
