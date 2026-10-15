"""Synthetic trace checks, including idempotent omissions and wrong store PCs."""
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from unicorn import riscv_const as r

from desc10_store_trace import Desc10Trace, original_sites
from desc10_effect_oracle import STORES
from native_prefix_snapshot import ROOT
import test_desc10_effect_oracle as effects
from txdone_wire_native import STORES as HOOK_SITES


class StoreTraceTests(unittest.TestCase):
    def fixture(self, complete=True):
        h, request = effects.EffectOracleTests().fixture()
        packet = 0x84078000
        words = [0x314b5043, 1, 0, 2560, 2560, 0x8a000000, 0x2c00000] + [0] * 512
        for ident in range(2560):
            words[7 + ident // 32] |= 1 << (ident % 32)
        h.cpu.images[packet] = bytearray(struct.pack('<519I', *words))
        h.packet = SimpleNamespace(symbols={'npu_emulation_packet_state': packet})
        locations = {site: 0x840d0000 + index * 16 for index, site in enumerate((*HOOK_SITES, 0xb4bc))}
        h.desc10 = SimpleNamespace(symbols={f'npu_emulation_desc10_{site:x}_store': address
                                            for site, address in locations.items()})
        h.cpu.hook_add, h.cpu.hook_del = Mock(return_value=17), Mock()
        trace = Desc10Trace(h, request)
        if complete:
            choices = original_sites()
            trace.stores = [(sites[0], *effect) for sites, effect in zip(choices, trace.oracle.events)]
            trace.locks = [(trace.LOCKS[0], 4, 0x40), (trace.LOCKS[1], 4, 0)] * 512
            trace.locks += [(trace.LOCKS[2], 4, 0x40), (trace.LOCKS[3], 4, 0x40),
                            (trace.LOCKS[4], 4, 0), (trace.LOCKS[5], 4, 0)]
            h.cpu.images.update(trace.oracle.memory_prefix(STORES, 512))
            h.cpu.images[packet] = bytearray(trace.oracle.packet_prefix(trace.packet_before, 512))
        return trace

    def test_complete_sites_effects_locks_memory_and_private_claims(self):
        trace = self.fixture()
        trace.validate()
        self.assertEqual(trace.stores[4][0], 0x8400b4bc)
        self.assertEqual(len(trace.sites), 20)

    def test_idempotent_omission_fails_despite_matching_final_memory(self):
        trace = self.fixture()
        del trace.stores[8000]
        with self.assertRaisesRegex(AssertionError, 'original-store-count'):
            trace.validate()

    def test_wrong_site_fails_even_with_identical_address_width_value(self):
        trace = self.fixture()
        old = trace.stores[2]
        trace.stores[2] = (0x84004aac, *old[1:])
        with self.assertRaisesRegex(AssertionError, 'wrong-original-store-site'):
            trace.validate()

    def test_wrong_lock_order_fails(self):
        trace = self.fixture()
        trace.locks[-1], trace.locks[-2] = trace.locks[-2], trace.locks[-1]
        with self.assertRaisesRegex(AssertionError, 'lock-footprint'):
            trace.validate()

    def test_callback_normalizes_width_and_ignores_unrelated_store_pcs(self):
        trace = self.fixture(complete=False)
        pc, original = next(iter(trace.sites.items()))
        cpu = SimpleNamespace(reg_read=lambda register: pc)
        trace.write(cpu, 0, 0x3e902a7c, 2, 0xffff00000200, None)
        self.assertEqual(trace.stores, [(original, 0x3e902a7c, 2, 512)])
        other = SimpleNamespace(reg_read=lambda register: 0x84001000)
        trace.write(other, 0, 0x3e902a7c, 2, 512, None)
        trace.write(other, 0, trace.LOCKS[0], 4, 0x40, None)
        self.assertEqual(len(trace.stores), 1)
        self.assertEqual(trace.locks, [(trace.LOCKS[0], 4, 0x40)])

    def test_observer_is_removed_and_partial_trace_is_preserved_on_error(self):
        trace = self.fixture(complete=False)
        with self.assertRaisesRegex(RuntimeError, 'injected'):
            with trace:
                trace.stores.append((0x8400b45e, *trace.oracle.events[0]))
                raise RuntimeError('injected')
        trace.h.cpu.hook_del.assert_called_once_with(17)
        self.assertIsNone(trace.hook)
        with tempfile.TemporaryDirectory(prefix='desc10-trace-unit-', dir=ROOT / '.local') as temporary:
            result = trace.save(Path(temporary) / 'trace')
            self.assertEqual(result['actual_stores'], 1)
            self.assertTrue(result['validation_is_separate'])


if __name__ == '__main__':
    unittest.main()
