"""Compiler allocation is flexible; the cache identity and field are not."""
import struct
import unittest

from txwi_skb_binding import skb_binding


class TxwiSkbBindingTests(unittest.TestCase):
    @staticmethod
    def body(base=19, edits=None):
        words = [0xaa0103e0 | base, 0xf9400c02 | base << 5, 0x94000000,
                 0xf9000c1f | base << 5, 0xaa0003e1 | base << 16, 0x94000000, 0xd65f03c0]
        for index, word in (edits or {}).items():
            words[index] = word
        return skb_binding(struct.pack('<7I', *words), 0x1000,
                           {0x1008: '__mt76_tx_complete_skb', 0x1014: 'mt76_put_txwi'})

    def test_old_and_new_register_allocations(self):
        for reg in (19, 22):
            with self.subTest(reg=reg):
                b = self.body(reg)
                self.assertEqual((b['cache_register'], b['skb_offset'], b['clear_pc']), (f'x{reg}', 24, 0x100c))

    def test_refuses_wrong_cache_or_field(self):
        for name, edits in {
            'not-input': {0: 0xaa0003f3}, 'truncated-pointer': {0: 0x2a0103f3},
            'wrong-load-offset': {1: 0xf9401262},
            'other-clear-base': {3: 0xf9000e9f}, 'wrong-clear-offset': {3: 0xf900127f},
            'nonzero-clear': {3: 0xf9000e60}, 'other-returned-cache': {4: 0xaa1403e1},
            'missing-completion-call': {2: 0xd503201f}, 'missing-return-call': {5: 0xd503201f},
        }.items():
            with self.subTest(name=name), self.assertRaises(AssertionError):
                self.body(edits=edits)

    def test_all_completion_paths_reach_the_same_clear(self):
        words = [0xaa0103f3, 0xf9400e62, 0x34000068, 0x94000000, 0x14000002,
                 0x94000000, 0xf9000e7f, 0xaa1303e1, 0x94000000, 0xd65f03c0]
        calls = {12: '__mt76_tx_complete_skb', 20: '__mt76_tx_complete_skb', 32: 'mt76_put_txwi'}
        result = skb_binding(struct.pack('<10I', *words), 0, calls)
        self.assertEqual((result['complete_pcs'], result['clear_pc']), ([12, 20], 24))
        words[4] = 0x14000003  # One completion now jumps over the clear.
        with self.assertRaisesRegex(AssertionError, 'clear-must-precede-cache-return'):
            skb_binding(struct.pack('<10I', *words), 0, calls)

    def test_discarded_load_cannot_provide_skb(self):
        words = [0xaa0103f3, 0xf9400e7f, 0xaa1f03e2, 0x94000000,
                 0xf9000e7f, 0xaa1303e1, 0x94000000, 0xd65f03c0]
        with self.assertRaisesRegex(AssertionError, 'completion-must-load-cache-skb'):
            skb_binding(struct.pack('<8I', *words), 0, {12: '__mt76_tx_complete_skb', 24: 'mt76_put_txwi'})

    def test_partial_write_invalidates_clear(self):
        words = [0xaa0103f3, 0xf9400e62, 0x94000000, 0xf9000e7f,
                 0x39006260, 0xaa1303e1, 0x94000000, 0xd65f03c0]
        with self.assertRaisesRegex(AssertionError, 'clear-must-precede-cache-return'):
            skb_binding(struct.pack('<8I', *words), 0, {8: '__mt76_tx_complete_skb', 24: 'mt76_put_txwi'})


if __name__ == '__main__':
    unittest.main()
