"""Observer fixtures only: an extra checkpoint never mutates native state."""
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
from cold_wire_native import ColdProviderRequest as PcieReaderObserver
from test_cold_wire_observer import ColdWireObserverTests
from test_provider_plan_native import ProviderRequest
from test_firmware_stop_counterexample import END
from unicorn import riscv_const as r


class ReaderObserverTests(unittest.TestCase):
    def observer(self):
        base = ColdWireObserverTests().observer()
        h = object.__new__(PcieReaderObserver)
        h.__dict__.update(base.__dict__)
        h.desc10.symbols.update(npu_emulation_desc10_read=0x40, npu_cold_txdone_memory_live=0x30)
        return h

    def test_message_uses_reader_and_both_prior_entries_without_writes(self):
        h = self.observer()
        words = [0] * 20
        words[2], words[11:14] = 0x3253434e, [0x1a, 0, 0x200d4590]

        def message(request):
            self.assertEqual(h.run(0x50, []), END)
            return {'flags': 7}

        with patch.object(ProviderRequest, 'message', side_effect=message):
            with patch.object(ProviderRequest, 'run', side_effect=[0x40, 0x30, 0x20, 0x40, END]) as run:
                reply = h.message(words)
        self.assertEqual([call.args[0] for call in run.call_args_list], [0x50, 0x40, 0x30, 0x20, 0x40])
        self.assertTrue(all(set(call.args[1]) == {0x20, 0x30, 0x40} for call in run.call_args_list))
        self.assertEqual(h.cold_checkpoint_hits, {'0x30': 1, '0x20': 1, '0x40': 2})
        self.assertEqual(reply['pcie_final_memory_entries'], 1)
        self.assertEqual(h.cold_count, 64 * 53260)
        self.assertFalse(h.cold_request or h.cold_pcie)
        h.cpu.mem_write.assert_not_called()
        h.cpu.reg_write.assert_not_called()

    def test_checkpoint_budget_remains_finite_and_hook_is_removed_on_failure(self):
        h = self.observer()
        h.cold_pcie, h.cold_count = True, 2
        with patch.object(ProviderRequest, 'run', return_value=0x40) as run:
            with self.assertRaisesRegex(AssertionError, 'cold-wire-getter-progress'):
                h.run(0x50, [])
        self.assertEqual(run.call_count, 6)
        h.cpu.hook_del.assert_called_once()
        h.cpu.mem_write.assert_not_called()
        h.cpu.reg_write.assert_not_called()

    def test_other_commands_do_not_add_reader_checkpoint(self):
        h = self.observer()
        with patch.object(ProviderRequest, 'run', return_value=END):
            self.assertEqual(h.run(0x50, []), END)
        self.assertEqual(h.cold_checkpoints, (0x10, 0x20))
        h.cpu.hook_add.assert_not_called()

    def test_missing_bound_reader_never_gets_a_silent_fallback(self):
        h = self.observer()
        h.cold_pcie = True
        del h.desc10.symbols['npu_emulation_desc10_read']
        with self.assertRaises(KeyError):
            h.run(0x50, [])
        h.cpu.mem_write.assert_not_called()
        h.cpu.reg_write.assert_not_called()

    def test_all_tail_stages_keep_real_reader_checkpoints_and_finite_budget(self):
        for header in (0x10, 0x12, 0x1f):
            h = self.observer()
            words = [0] * 20
            words[2], words[11:14] = 0x3253434e, [header, 0, 0]

            def message(request):
                self.assertTrue(h.cold_tail)
                self.assertFalse(h.probing or h.cold_pcie or h.cold_desc10)
                self.assertEqual(h.cold_count, 64 * 53260)
                self.assertEqual(h.run(0x50, []), END)
                return {'flags': 7}

            with patch.object(ProviderRequest, 'message', side_effect=message):
                with patch.object(ProviderRequest, 'run', side_effect=[0x40, 0x30, 0x20, END]) as run:
                    reply = h.message(words)
            self.assertTrue(all(set(call.args[1]) == {0x20, 0x30, 0x40} for call in run.call_args_list))
            self.assertEqual(reply['pcie_tail_checkpoints'], {'0x30': 1, '0x20': 1, '0x40': 1})
            self.assertEqual(reply['pcie_tail_final_memory_entries'], 1)
            self.assertFalse(h.cold_request or h.cold_tail)
            h.cpu.mem_write.assert_not_called()
            h.cpu.reg_write.assert_not_called()

    def test_tail_checkpoint_failure_removes_hooks_and_restores_mode(self):
        h = self.observer()
        words = [0] * 20
        words[2], words[11:14] = 0x3253434e, [0x1f, 0, 0]

        def message(request):
            h.cold_count = 2
            return h.run(0x50, [])

        with patch.object(ProviderRequest, 'message', side_effect=message):
            with patch.object(ProviderRequest, 'run', return_value=0x40) as run:
                with self.assertRaisesRegex(AssertionError, 'cold-wire-getter-progress'):
                    h.message(words)
        self.assertEqual(run.call_count, 6)
        self.assertFalse(h.cold_request or h.cold_tail or h.probing)
        self.assertEqual(h.cpu.hook_del.call_count, 7)
        h.cpu.mem_write.assert_not_called()
        h.cpu.reg_write.assert_not_called()

    def test_tail_never_exempts_unexpected_original_allocator(self):
        h = self.observer()
        h.cold_tail = True
        h.cpu.reg_read.side_effect = {r.UC_RISCV_REG_A0: 512, r.UC_RISCV_REG_A1: 10}.__getitem__
        with patch.object(ProviderRequest, 'code_hook') as inherited:
            with self.assertRaisesRegex(AssertionError, 'unexpected-tail-allocator'):
                h.code_hook(h.cpu, 0x8400dd82, 2, None)
        inherited.assert_not_called()
        h.cpu.mem_write.assert_not_called()
        h.cpu.reg_write.assert_not_called()

    def test_tail_bar_model_is_selected_hif_exact_cells_and_read_only_neighbors(self):
        for tx2 in (0x200d4450, 0x200d8450):
            h = self.observer()
            h.cold_tail = True
            h.owner_words.update({0x1030: 0x20000000, 0x1184: tx2})
            stores = (0x200d4588, tx2 + 0x118, 0x200d45a8, 0x200d45b8,
                      0x200d45c8, 0x2000a048, 0x200d4598)
            with patch.object(ProviderRequest, 'register_model', return_value=None) as inherited:
                for address in stores:
                    self.assertIsNotNone(h.register_model(address, True))
                    for delta in (-4, 0, 4):
                        self.assertIsNotNone(h.register_model(address + delta, False))
                    for delta in (-4, 4):
                        self.assertIsNone(h.register_model(address + delta, True))
                for address in (tx2 + 0x119, 0x200d4568 if tx2 == 0x200d8450 else 0x200d8568):
                    self.assertIsNone(h.register_model(address, True))
                h.cold_tail = False
                self.assertIsNone(h.register_model(stores[0], True))
                h.cold_tail = True
                for address, value in ((0x1030, 0x21000000), (0x1184, 0x200d4454)):
                    saved = h.owner_words[address]
                    h.owner_words[address] = value
                    self.assertIsNone(h.register_model(stores[0], True))
                    h.owner_words[address] = saved
            self.assertGreater(inherited.call_count, 0)
            h.cpu.mem_write.assert_not_called()
            h.cpu.reg_write.assert_not_called()

    def test_non_tail_header_or_api_does_not_enable_tail_observer(self):
        for header, api in ((0x1f, 1), (0x10, 19), (0x11, 0)):
            h = self.observer()
            words = [0] * 20
            words[2], words[11:14] = 0x3253434e, [header, api, 0]

            def message(request):
                self.assertFalse(h.cold_tail)
                return {'flags': 3}

            with patch.object(ProviderRequest, 'message', side_effect=message):
                reply = h.message(words)
            self.assertNotIn('pcie_tail_checkpoints', reply)
            self.assertFalse(h.cold_tail)


if __name__ == '__main__':
    unittest.main()
