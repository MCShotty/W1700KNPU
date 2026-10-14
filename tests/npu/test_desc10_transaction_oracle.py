"""Exact protocol metadata correction; native constructor behavior is mocked."""
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import desc10_transaction_oracle as oracle


class Desc10TransactionOracleTests(unittest.TestCase):
    def fixture(self):
        words = [0x12345678, 0x9abcdef0, 0x9abcdef0, 0x12345678, 56]
        before = struct.pack('<5I', *words)
        h = SimpleNamespace(cpu=Mock(), rv=SimpleNamespace(
            symbols={'npu_emulation_control_v2_state': 0x3008}), fixed={})
        h.cpu.mem_read.return_value = before
        request = [0x3f, 1, 0x3253434e, 2, 80, 1, 57, *words[2:4], *words[:2], 0x1a, 1, 512] + [0] * 6
        images = {0x3000: bytearray(b'abcdefgh' + before + b'unchanged')}
        return h, request, images, before

    def test_only_exact_sequence_word_changes_and_input_images_stay_untouched(self):
        h, request, images, before = self.fixture()
        saved = bytes(images[0x3000])
        with patch.object(oracle, 'done_oracle', return_value=(images, {0x1000}, {'allocated': 512})):
            result, allowed, footprint = oracle.expected(h, request)
        wanted = bytearray(saved)
        struct.pack_into('<I', wanted, 24, 57)
        self.assertEqual(result[0x3000], wanted)
        self.assertEqual(bytes(images[0x3000]), saved)
        self.assertEqual(allowed, {0x1000, 0x3018, 0x3019, 0x301a, 0x301b})
        self.assertEqual(footprint['transaction_sequence'], {'address': '0x3018', 'before': 56, 'expected': 57, 'bytes': 4})
        h.cpu.mem_write.assert_not_called()
        h.cpu.reg_write.assert_not_called()

    def test_replay_and_wrong_identity_are_rejected_before_constructor_oracle(self):
        h, request, _, _ = self.fixture()
        with patch.object(oracle, 'done_oracle') as constructor:
            for index, value in ((5, 0), (6, 56), (6, 0), (7, 0), (8, 0), (9, 0), (10, 0), (13, 511), (14, 1)):
                changed = request.copy()
                changed[index] = value
                with self.assertRaises(AssertionError):
                    oracle.expected(h, changed)
            constructor.assert_not_called()

    def test_constructor_oracle_cannot_change_other_session_words(self):
        h, request, images, _ = self.fixture()
        images[0x3000][8] ^= 1
        with patch.object(oracle, 'done_oracle', return_value=(images, set(), {})):
            with self.assertRaises(AssertionError):
                oracle.expected(h, request)


if __name__ == '__main__':
    unittest.main()
