"""Synthetic projection bounds and byte-shape tests, not original execution."""
import struct
import unittest

from test_inode_rro_original import ALIAS, ALIAS_BYTES, SRAM, SRAM_BYTES, project


class InodeRroProjectionTests(unittest.TestCase):
    def setUp(self):
        self.sram, self.alias = bytes(SRAM_BYTES), b'\xa5' * ALIAS_BYTES

    def test_element_block_is_cleared_with_only_signature_bytes_set(self):
        sram, alias, written, base, size = project(0, 127, 0x887f0000, self.sram, self.alias)
        self.assertEqual((base, size), (ALIAS + 0x7f0000, 65536))
        self.assertEqual(struct.unpack_from('<I', sram, 0x1fdc + 127 * 4)[0], base)
        self.assertEqual(alias[base - ALIAS:base - ALIAS + 16], bytes(7) + b'\xff' + bytes(7) + b'\xff')
        self.assertEqual(len(written), 65540)
        self.assertEqual(alias[:base - ALIAS], self.alias[:base - ALIAS])

    def test_session_table_preserves_non_signature_bytes(self):
        sram, alias, written, base, size = project(1, 0, 0x88801000, self.sram, self.alias)
        offset = base - ALIAS
        self.assertEqual(alias[offset:offset + 16], b'\xa5' * 7 + b'\xff' + b'\xa5' * 7 + b'\xff')
        self.assertEqual((size, len(written)), (8192, 1028))

    def test_reset_selects_block_slot_or_special_session_table(self):
        sram = bytearray(self.sram)
        struct.pack_into('<I', sram, 0x1fdc + 127 * 4, ALIAS + 0x7f0000)
        struct.pack_into('<I', sram, 0x458c, ALIAS + 0x801000)
        for session, expected in ((1023, ALIAS + 0x7fe000), (1024, ALIAS + 0x801000)):
            result, alias, written, base, size = project(3, session, 0, sram, self.alias)
            self.assertEqual((base, size, len(written)), (expected, 8192, 1024))
            self.assertEqual(result, sram)

    def test_unsupported_selector_or_outside_named_geometry_is_rejected(self):
        for selector, argument in ((2, 0), (0, -1), (0, 128), (1, 1), (3, 1025)):
            with self.assertRaises(AssertionError): project(selector, argument, 0x88000000, self.sram, self.alias)

    def test_unmapped_alias_is_not_treated_as_backing(self):
        with self.assertRaises(AssertionError): project(0, 0, 0, self.sram, self.alias)


if __name__ == '__main__': unittest.main()
