"""Fresh CSR reader through the actual observer hook; no native owner claim."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from unicorn import Uc, UcError, UC_ARCH_RISCV, UC_MODE_RISCV32, riscv_const as r
from npu_csr_sampler import CsrSampler, REGISTERS
from test_boot_irq_installation import Installation


class CsrObserverIntegrationTests(unittest.TestCase):
    def observer(self, batched):
        h = object.__new__(Installation)
        h.cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        h.tick, h.events, h.csr_events, h.last_csr = 0, [], [], None
        if batched:
            h.csr_sampler = Mock(wraps=CsrSampler(h.cpu))
        return h

    def test_actual_hook_transcripts_match_scalar_and_remain_fresh(self):
        observers = [self.observer(False), self.observer(True)]
        for values in ((0, 0, 0), (0x1888, 0x800, 0x84004100),
                       (0x1888, 0x800, 0x84004100), (0, 0, 0)):
            for h in observers:
                for register, value in zip(REGISTERS, values): h.cpu.reg_write(register, value)
                Installation.code_hook(h, h.cpu, 0x84004212, 2, None)
        self.assertEqual(observers[0].events, observers[1].events)
        self.assertEqual(len(observers[1].csr_events), 3)
        self.assertEqual(observers[1].csr_sampler.call_count, 4)
        self.assertEqual(observers[0].last_csr, observers[1].last_csr)

    def test_context_restore_is_visible_to_the_hook(self):
        h = self.observer(True)
        saved = h.cpu.context_save()
        h.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 8)
        Installation.code_hook(h, h.cpu, 0x84004212, 2, None)
        h.cpu.context_restore(saved)
        Installation.code_hook(h, h.cpu, 0x84004212, 2, None)
        self.assertEqual(h.last_csr[0], 0)
        self.assertEqual(len(h.csr_events), 2)

    def test_backend_failure_is_not_hidden_by_scalar_fallback(self):
        h = self.observer(True)
        h.csr_sampler.side_effect = UcError(15)
        with self.assertRaises(UcError): Installation.code_hook(h, h.cpu, 0x84004212, 2, None)
        self.assertEqual(h.csr_events, [])

    def test_other_engine_cannot_be_read_through_the_sampler(self):
        h = self.observer(True)
        with self.assertRaisesRegex(RuntimeError, 'different engine'):
            Installation.sample_csr(h, Uc(UC_ARCH_RISCV, UC_MODE_RISCV32))
        h.csr_sampler.assert_not_called()

    def test_opt_out_observers_keep_scalar_calls_in_original_order(self):
        cpu = Mock()
        cpu.reg_read.side_effect = (1, 2, 3)
        self.assertEqual(Installation.sample_csr(SimpleNamespace(), cpu), (1, 2, 3))
        self.assertEqual([call.args[0] for call in cpu.reg_read.call_args_list], list(REGISTERS))


if __name__ == '__main__': unittest.main()
