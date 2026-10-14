"""Observer fixtures only: an extra checkpoint never mutates native state."""
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
from cold_wire_native import ColdProviderRequest as PcieReaderObserver
from test_cold_wire_observer import ColdWireObserverTests
from test_provider_plan_native import ProviderRequest
from test_firmware_stop_counterexample import END


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


if __name__ == '__main__':
    unittest.main()
