"""Read-only byte-difference recorder units; no native ownership proof."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from test_desc10_native_replay import compare, ROOT


class Desc10MemoryCompareTests(unittest.TestCase):
    def fixture(self, contents):
        cpu = Mock()
        cpu.mem_read.side_effect = lambda address, size: contents[address][:size]
        return SimpleNamespace(cpu=cpu)

    def test_equal_regions_keep_exact_bytes_without_guest_writes(self):
        contents = {0x1000: b'abc', 0x2000: bytes(range(12))}
        h = self.fixture(contents)
        with tempfile.TemporaryDirectory(dir=ROOT / '.local') as name:
            directory = Path(name)
            rows = compare(h, contents, directory)
            self.assertEqual([row['differing_bytes'] for row in rows], [0, 0])
            for i, data in enumerate(contents.values()):
                self.assertEqual((directory / f'region-{i:02d}-actual.bin').read_bytes(), data)
                self.assertEqual((directory / f'region-{i:02d}-expected.bin').read_bytes(), data)
        h.cpu.mem_write.assert_not_called()
        h.cpu.reg_write.assert_not_called()

    def test_mismatches_at_boundaries_have_exact_addresses_and_saved_bytes(self):
        actual, expected = b'xbcdyz', b'abcdef'
        h = self.fixture({0x1000: actual})
        with tempfile.TemporaryDirectory(dir=ROOT / '.local') as name:
            directory = Path(name)
            row = compare(h, {0x1000: expected}, directory)[0]
            self.assertEqual(row['differing_bytes'], 3)
            self.assertEqual([item['address'] for item in row['examples']], ['0x1000', '0x1004', '0x1005'])
            self.assertEqual((directory / 'region-00-actual.bin').read_bytes(), actual)
            self.assertEqual((directory / 'region-00-expected.bin').read_bytes(), expected)
        h.cpu.mem_write.assert_not_called()
        h.cpu.reg_write.assert_not_called()

    def test_existing_record_is_not_overwritten(self):
        h = self.fixture({0x1000: b'abc'})
        with tempfile.TemporaryDirectory(dir=ROOT / '.local') as name:
            directory = Path(name)
            target = directory / 'region-00-actual.bin'
            target.write_bytes(b'prior')
            with self.assertRaises(FileExistsError):
                compare(h, {0x1000: b'abc'}, directory)
            self.assertEqual(target.read_bytes(), b'prior')


if __name__ == '__main__':
    unittest.main()
