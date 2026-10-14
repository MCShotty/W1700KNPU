"""The normal archive must contain each verified object once with exact bytes."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from verify_merged_image import verify_core_archive


@unittest.skipUnless(shutil.which('ar'), 'GNU ar is required')
class CoreArchiveTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='npu-core-archive-')
        self.addCleanup(self.directory.cleanup)
        self.core = Path(self.directory.name)
        for name, data in (('first.o', b'first compiled object'), ('second.o', b'second compiled object')):
            (self.core / name).write_bytes(data)
        self.objects = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in self.core.glob('*.o')}

    def archive(self, *names, append=False):
        subprocess.run(['ar', 'qD' if append else 'qcD', self.core / 'libw1700k-npu.a',
                        *(self.core / name for name in names)], check=True, capture_output=True)

    def test_exact_members(self):
        self.archive('first.o', 'second.o')
        self.assertEqual(verify_core_archive(self.core, self.objects), self.objects)

    def test_member_order_is_not_an_object_difference(self):
        self.archive('second.o', 'first.o')
        self.assertEqual(verify_core_archive(self.core, self.objects), self.objects)

    def test_missing_member(self):
        self.archive('first.o')
        with self.assertRaisesRegex(AssertionError, 'member set'):
            verify_core_archive(self.core, self.objects)

    def test_extra_member(self):
        (self.core / 'obsolete.o').write_bytes(b'obsolete object')
        self.archive('first.o', 'second.o', 'obsolete.o')
        with self.assertRaisesRegex(AssertionError, 'member set'):
            verify_core_archive(self.core, self.objects)

    def test_duplicate_member(self):
        self.archive('first.o', 'second.o')
        self.archive('first.o', append=True)
        with self.assertRaisesRegex(AssertionError, 'Duplicate'):
            verify_core_archive(self.core, self.objects)

    def test_stale_member_bytes(self):
        (self.core / 'first.o').write_bytes(b'old compiled object')
        self.archive('first.o', 'second.o')
        with self.assertRaisesRegex(AssertionError, 'stale or different'):
            verify_core_archive(self.core, self.objects)

    def test_invalid_archive(self):
        (self.core / 'libw1700k-npu.a').write_bytes(b'not an archive')
        with self.assertRaises(AssertionError):
            verify_core_archive(self.core, self.objects)


if __name__ == '__main__':
    unittest.main()
