"""Observer-only checkpoint tests; these do not establish native ownership."""
import sys
import unittest
from collections import Counter
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
from unicorn import riscv_const as r
from cold_wire_native import ColdProviderRequest
from test_provider_plan_native import ProviderRequest
from test_firmware_stop_counterexample import END
from test_boot_irq_installation import Installation, TX
import test_bootstrap_v2_composition as composition


class ColdWireObserverTests(unittest.TestCase):
    def observer(self):
        h = object.__new__(ColdProviderRequest)
        h.cold_request = h.cold_desc10 = True
        h.cold_txbuf = h.cold_rx_event = False
        h.cold_pcie = h.cold_tail = h.cold_inode = False
        h.cold_count, h.cold_callback_count = 64 * 53260, 512
        h.cold_getter, h.cold_getters = 0x10, 0
        h.cold_checkpoints = (0x10, 0x20)
        h.cold_checkpoint_hits = {'0x10': 0, '0x20': 0}
        h.rv = SimpleNamespace(symbols={'npu_cold_txbuf_recipe': 0x20,
                                      'npu_emulation_cold_setup_state': 0x1000})
        h.allocator_rv = SimpleNamespace(symbols={'npu_emulation_callback_guarded': 0x4000})
        h.desc10 = SimpleNamespace(symbols={'npu_cold_txdone_recipe': 0x10,
            'npu_emulation_desc10_state': 0x2000, 'npu_emulation_desc10_running': 0x3000,
            'npu_emulation_desc10_4aac_store': 0x5000, 'npu_emulation_desc10_4ad2_store': 0x6000})
        h.owner_words = {0x2000: 0x31445443, 0x2004: 1, 0x2008: 0, 0x200c: 1}
        h.get32 = Mock(side_effect=lambda address: h.owner_words.get(address, 1))
        h.executions = Counter()
        h.cpu = Mock()
        h.code, h.probing = bytes(16), False
        h.instruction_hook, h.callback_hook = 71, 72
        h.cpu.hook_add.side_effect = range(1, 32)
        return h

    def skb_observer(self, value=0):
        h = self.observer()
        words = [0x31445443, 1, 0, 1, 7171, 7171, 7170, 512, 512, 512, 1,
                 0, 0, value, TX, 2]
        h.owner_words.update({0x2000 + 4 * i: word for i, word in enumerate(words)})
        registers = {r.UC_RISCV_REG_PC: 0x5000 if value == 0 else 0x6000,
                     r.UC_RISCV_REG_MSTATUS: 0}
        h.cpu.reg_read.side_effect = registers.__getitem__
        h.clear_count = 0x7000
        return h, registers

    def test_resumes_both_real_checkpoint_addresses(self):
        h = self.observer()
        with patch.object(ProviderRequest, 'run', side_effect=[0x20, 0x20, 0x10, END]) as run:
            self.assertEqual(h.run(0x30, []), END)
        self.assertEqual([call.args[0] for call in run.call_args_list], [0x30, 0x20, 0x20, 0x10])
        self.assertTrue(all(set(call.args[1]) == {0x10, 0x20} for call in run.call_args_list))
        self.assertEqual(h.cold_checkpoint_hits, {'0x10': 1, '0x20': 2})
        self.assertEqual(h.cold_getters, 1)
        h.cpu.reg_write.assert_not_called()
        h.cpu.mem_write.assert_not_called()

    def test_preserves_caller_stop(self):
        h = self.observer()
        with patch.object(ProviderRequest, 'run', return_value=0x40) as run:
            self.assertEqual(h.run(0x30, [0x40]), 0x40)
        self.assertEqual(set(run.call_args.args[1]), {0x10, 0x20, 0x40})

    def test_keeps_finite_checkpoint_bound(self):
        h = self.observer()
        h.cold_count = 2
        with patch.object(ProviderRequest, 'run', return_value=0x20) as run:
            with self.assertRaisesRegex(AssertionError, 'cold-wire-getter-progress'):
                h.run(0x30, [])
        self.assertEqual(run.call_count, 6)

    def test_non_cold_run_is_unchanged(self):
        h = self.observer()
        h.cold_request = False
        with patch.object(ProviderRequest, 'run', return_value=END) as run:
            self.assertEqual(h.run(0x30, [0x40]), END)
        run.assert_called_once_with(0x30, [0x40])

    def test_selector10_uses_callback_count_not_checkpoint_budget(self):
        h = self.observer()
        registers = {r.UC_RISCV_REG_A0: 512, r.UC_RISCV_REG_A1: 10}
        h.cpu.reg_read.side_effect = registers.__getitem__
        with patch.object(composition.Composed.__mro__[1], 'code_hook'):
            h.code_hook(h.cpu, 0x8400dd82, 2, None)
            registers[r.UC_RISCV_REG_A0] = 511
            with self.assertRaises(AssertionError):
                h.code_hook(h.cpu, 0x8400dd82, 2, None)
            registers[r.UC_RISCV_REG_A0] = 512
            for selector in (0, 9):
                registers[r.UC_RISCV_REG_A1] = selector
                with self.assertRaises(AssertionError):
                    h.code_hook(h.cpu, 0x8400dd82, 2, None)

    def test_owned_desc10_bypasses_only_legacy_observer(self):
        h = self.observer()
        registers = {r.UC_RISCV_REG_A0: 512, r.UC_RISCV_REG_A1: 10}
        h.cpu.reg_read.side_effect = registers.__getitem__
        with patch.object(composition.Composed, 'code_hook', side_effect=AssertionError('legacy')) as old:
            with patch.object(composition.Composed.__mro__[1], 'code_hook') as base:
                h.code_hook(h.cpu, 0x8400dd82, 2, None)
        old.assert_not_called()
        base.assert_called_once_with(h.cpu, 0x8400dd82, 2, None)
        h.cpu.reg_write.assert_not_called()
        h.cpu.mem_write.assert_not_called()

    def test_dirty_desc10_owner_is_not_exempt(self):
        h = self.observer()
        h.cpu.reg_read.side_effect = {r.UC_RISCV_REG_A0: 512, r.UC_RISCV_REG_A1: 10}.__getitem__
        for address, value in ((0x2000, 0), (0x2004, 2), (0x2008, 1), (0x200c, 0), (0x3000, 0)):
            saved = h.owner_words.get(address, 1)
            h.owner_words[address] = value
            with self.assertRaises(AssertionError):
                h.code_hook(h.cpu, 0x8400dd82, 2, None)
            h.owner_words[address] = saved

    def test_unmarked_dispatch_retains_legacy_observer(self):
        h = self.observer()
        h.cold_request = False
        with patch.object(ProviderRequest, 'code_hook', side_effect=AssertionError('legacy')) as old:
            with self.assertRaisesRegex(AssertionError, 'legacy'):
                h.code_hook(h.cpu, 0x8400dd82, 2, None)
        old.assert_called_once_with(h.cpu, 0x8400dd82, 2, None)

    def test_desc10_observer_registers_and_reports_both_entries(self):
        h = self.observer()
        words = [0] * 20
        words[2], words[11], words[12], words[13] = 0x3253434e, 0x1a, 1, 512
        with patch.object(ProviderRequest, 'message', return_value={'flags': 7}):
            reply = h.message(words)
        points = {call.kwargs.get('begin') for call in h.cpu.hook_add.call_args_list}
        self.assertTrue({0x10, 0x20}.issubset(points))
        self.assertEqual(reply['desc10_checkpoints'], {'0x10': 0, '0x20': 0})
        self.assertEqual(h.cold_callback_count, 512)
        self.assertFalse(h.cold_request)
        h.cpu.reg_write.assert_not_called()
        h.cpu.mem_write.assert_not_called()

    def test_inode_observer_keeps_prior_checkpoints_and_bounded_store_budget(self):
        for selector, stores in ((2, 1030), (7, 6)):
            h = self.observer()
            h.desc10.symbols['npu_cold_txdone_memory_live'] = 0x10
            h.desc10.symbols['npu_emulation_desc10_read'] = 0x30
            words = [0] * 20
            words[2], words[11], words[12] = 0x3253434e, 0x10 | selector, 24
            with patch.object(ProviderRequest, 'message', return_value={'flags': 7}):
                reply = h.message(words)
            self.assertEqual(h.cold_count, 64 * 53260 * stores)
            self.assertEqual(reply['inode_checkpoints'], {'0x10': 0, '0x20': 0})
            self.assertFalse(h.cold_inode)
            h.cpu.mem_write.assert_not_called()
            h.cpu.reg_write.assert_not_called()

    def test_inode_never_allows_original_dynamic_allocator(self):
        h = self.observer()
        h.cold_inode = True
        with self.assertRaisesRegex(AssertionError, 'unexpected-INODE-allocator'):
            h.code_hook(h.cpu, 0x8400dd82, 2, None)

    def test_pcie_observer_checkpoints_final_memory_and_prior_recipe(self):
        h = self.observer()
        h.desc10.symbols['npu_cold_txdone_memory_live'] = 0x30
        words = [0] * 20
        words[2], words[11], words[12], words[13] = 0x3253434e, 0x1a, 0, 0x200d4590
        with patch.object(ProviderRequest, 'message', return_value={'flags': 7}):
            reply = h.message(words)
        points = {call.kwargs.get('begin') for call in h.cpu.hook_add.call_args_list}
        self.assertTrue({0x20, 0x30}.issubset(points))
        self.assertEqual(h.cold_checkpoints, (0x30, 0x20))
        self.assertEqual(reply['pcie_final_memory_entries'], 0)
        self.assertFalse(h.cold_request or h.cold_pcie or h.cold_desc10)
        h.cpu.reg_write.assert_not_called()
        h.cpu.mem_write.assert_not_called()

    def test_boot_clear_observer_remains_sequential_zero_only(self):
        h = self.observer()
        h.cold_request = False
        h.clear_count = 0
        h.observe_tx_write(h.cpu, TX, 2, 0)
        self.assertEqual(h.clear_count, 1)
        for address, size, value in ((TX, 2, 0), (TX + 2, 4, 0), (TX + 2, 2, 3)):
            with self.assertRaises(AssertionError):
                h.observe_tx_write(h.cpu, address, size, value)
            self.assertEqual(h.clear_count, 1)

    def test_owned_skb_writes_keep_boot_count_and_native_state_unchanged(self):
        for value in (0, 3):
            h, _ = self.skb_observer(value)
            before = h.owner_words.copy()
            h.observe_tx_write(h.cpu, TX, 2, value)
            self.assertEqual(h.clear_count, 0x7000)
            self.assertEqual(h.owner_words, before)
            h.cpu.mem_write.assert_not_called()
            h.cpu.reg_write.assert_not_called()

    def test_owned_skb_rejects_wrong_store_pc_width_value_or_address(self):
        h, registers = self.skb_observer()
        for address, size, value in ((TX + 2, 2, 0), (TX, 4, 0), (TX, 2, 1)):
            with self.assertRaises(AssertionError):
                h.observe_tx_write(h.cpu, address, size, value)
        for pc in (0x6000, 0x7000):
            registers[r.UC_RISCV_REG_PC] = pc
            with self.assertRaises(AssertionError):
                h.observe_tx_write(h.cpu, TX, 2, 0)
        registers[r.UC_RISCV_REG_PC] = 0x5000
        registers[r.UC_RISCV_REG_MSTATUS] = 8
        with self.assertRaises(AssertionError):
            h.observe_tx_write(h.cpu, TX, 2, 0)

    def test_owned_skb_rejects_dirty_or_missing_native_reservation(self):
        h, _ = self.skb_observer()
        for index in (*range(11), 13, 14, 15):
            address = 0x2000 + 4 * index
            saved = h.owner_words[address]
            h.owner_words[address] = saved + 1
            with self.assertRaises(AssertionError, msg=f'owner word {index}'):
                h.observe_tx_write(h.cpu, TX, 2, 0)
            h.owner_words[address] = saved
        for address in (0x3000, 0x4000):
            h.owner_words[address] = 0
            with self.assertRaises(AssertionError):
                h.observe_tx_write(h.cpu, TX, 2, 0)
            h.owner_words[address] = 1

    def test_unowned_later_skb_writes_retain_boot_observer(self):
        h, _ = self.skb_observer()
        for field in ('cold_request', 'cold_desc10'):
            setattr(h, field, False)
            with self.assertRaises(AssertionError):
                h.observe_tx_write(h.cpu, TX, 2, 0)
            setattr(h, field, True)

    def test_skb_observation_preserves_inherited_memory_access(self):
        h, _ = self.skb_observer()
        h.access = Mock()
        Installation.write_hook(h, h.cpu, 17, TX, 2, 0, None)
        h.access.assert_called_once_with(TX, 2, 0, True)
        self.assertEqual(h.clear_count, 0x7000)


if __name__ == '__main__':
    unittest.main()
