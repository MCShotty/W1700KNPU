#!/usr/bin/env python3
"""Fail-closed controls for the static PCI stop verifier (no emulator)."""
import unittest

from verify_pci_stop_status import ABS64, Module, ROOT, STOCK, verify_callers, verify_radio_stop


def stock(name):
    return Module(ROOT / '.local/npu-reset/inputs' / name, STOCK[name])


def change_word(module, section, address, replacement):
    data = module.data(section)
    module.sections[section] = data[:address] + replacement.to_bytes(4, 'little') + data[address + 4:]


class StopStatusChecks(unittest.TestCase):
    def test_static_null_must_have_no_relocation(self):
        pci = stock('mtk_pci.ko')
        pci.null(0x138)
        pci.relocations('.data')[0x138] = (ABS64, '.text', 0x1c14)
        with self.assertRaisesRegex(ValueError, r'0x138: not a static null slot'):
            pci.null(0x138)

    def test_static_null_must_have_zero_bytes(self):
        pci = stock('mtk_pci.ko')
        pci.null(0x28)
        change_word(pci, '.data', 0x28, 1)
        with self.assertRaisesRegex(ValueError, r'0x28: not a static null slot'):
            pci.null(0x28)

    def test_different_idle_bit_is_not_the_evidenced_bit(self):
        radio = stock('mt7990.ko')
        verify_radio_stop(radio)
        ins = int.from_bytes(radio.data('.text')[0xd8c:0xd90], 'little')
        change_word(radio, '.text', 0xd8c, ins ^ (1 << 19))
        with self.assertRaisesRegex(ValueError, r'0xd8c:.*#0,.*got tbz w1, #1,'):
            verify_radio_stop(radio)

    def test_status_gate_would_change_the_caller_contract(self):
        hw = stock('mtk_hwifi.ko')
        verify_callers(hw)
        change_word(hw, '.text', 0xc654, 0x35000080)  # cbnz w0, 0xc664
        with self.assertRaisesRegex(ValueError, r'0xc654:.*got cbnz w0, #0xc664'):
            verify_callers(hw)


if __name__ == '__main__':
    unittest.main()
