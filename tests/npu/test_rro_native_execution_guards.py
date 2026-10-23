#!/usr/bin/env python3
"""Negative controls for the RRO native replay observer; no RV32 execution."""
import hashlib
import unittest
from unittest.mock import Mock

from emulation_layout import CODE, SRAM
from test_firmware_memory_layout import STACK_TOPS
from test_rro_native_execution import Machine


TEXT = CODE + 0x100
DATA = CODE + 0x2000
PLAN = DATA + 0x100


class NativeExecutionGuardTests(unittest.TestCase):
    def setUp(self):
        self.machine = Machine.__new__(Machine)
        self.cpu = Mock()
        self.cpu.reg_read.return_value = TEXT
        self.machine.cpu = self.cpu
        self.machine.text = [(TEXT, b'\x13\x00\x00\x00' * 2)]
        self.machine.writable = [(DATA, 0x400)]
        self.machine.plan = PLAN
        self.machine.plan_bytes = 0x80
        self.machine.seen = set()
        self.machine.blocks = 0
        self.machine.max_stack = 0
        self.machine.scope = dict(kind=2, allowed=set(), written=set(),
                                  hash=hashlib.sha256(), stores=0)

    def write(self, address, size=4, value=0x12345678):
        self.machine.write(self.cpu, 0, address, size, value, None)

    def test_instruction_byte_tamper_rejected_on_unseen_block(self):
        self.cpu.mem_read.return_value = b'\x13\x00\x00\x00'
        self.machine.block(self.cpu, TEXT, 4, None)
        self.assertIn((TEXT, 4), self.machine.seen)

        self.cpu.mem_read.return_value = b'\x00\x00\x00\x00'
        with self.assertRaises(AssertionError):
            self.machine.block(self.cpu, TEXT + 4, 4, None)
        self.assertNotIn((TEXT + 4, 4), self.machine.seen)

    def test_execution_outside_exact_elf_text_rejected(self):
        with self.assertRaisesRegex(AssertionError, 'execution-outside-exact-RRO-ELF'):
            self.machine.block(self.cpu, TEXT + 8, 4, None)
        self.cpu.mem_read.assert_not_called()
        self.assertFalse(self.machine.seen)

    def test_write_outside_declared_footprint_rejected(self):
        address = SRAM + 0x100
        self.machine.scope['allowed'] = set(range(address, address + 4))
        self.write(address)
        self.assertEqual(self.machine.scope['written'], set(range(address, address + 4)))
        self.assertEqual(self.machine.scope['stores'], 1)
        digest = self.machine.scope['hash'].digest()

        with self.assertRaisesRegex(AssertionError, 'unexpected-native-RRO-store'):
            self.write(address + 2)
        self.assertEqual(self.machine.scope['stores'], 1)
        self.assertEqual(self.machine.scope['written'], set(range(address, address + 4)))
        self.assertEqual(self.machine.scope['hash'].digest(), digest)

    def test_immutable_plan_write_rejected_after_init(self):
        for address in (PLAN + 4, PLAN - 2):
            with self.subTest(address=hex(address)):
                with self.assertRaisesRegex(AssertionError, 'immutable-plan-write'):
                    self.write(address)
        self.assertEqual(self.machine.scope['stores'], 0)

    def test_writable_metadata_and_init_plan_write_allowed(self):
        self.write(DATA + 0x20)
        self.machine.scope['kind'] = 0
        self.write(PLAN + 4)
        self.assertEqual(self.machine.scope['stores'], 0)
        self.assertFalse(self.machine.scope['written'])

    def test_stack_is_limited_to_declared_call_and_4k_window(self):
        top = STACK_TOPS[0]
        self.write(top - 4096)
        self.write(top - 4)
        self.assertEqual(self.machine.max_stack, 4096)

        for address in (top - 4097, top - 3):
            with self.subTest(address=hex(address)):
                with self.assertRaisesRegex(AssertionError, 'unexpected-native-RRO-store'):
                    self.write(address)
        self.assertEqual(self.machine.scope['stores'], 0)
        self.assertFalse(self.machine.scope['written'])

        self.machine.scope = None
        with self.assertRaisesRegex(AssertionError, 'write-outside-declared-call'):
            self.write(top - 4)


if __name__ == '__main__':
    unittest.main()
