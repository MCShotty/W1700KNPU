"""Synthetic capsule copy/path controls; no privileged mount is performed."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from npu_validation_capsule import add_file, copy_files, receipt_inputs, source_file


class ValidationCapsuleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'input').write_bytes(b'proof')

    def test_path_escape_and_nonfiles_are_rejected(self):
        for name in ('../elsewhere', '/etc/passwd', '.', 'missing'):
            with self.assertRaises(AssertionError): source_file(self.root, name)

    def test_declared_hashes_are_required(self):
        files = {}
        add_file(self.root, files, 'input', hashlib.sha256(b'proof').hexdigest())
        with self.assertRaises(AssertionError): add_file(self.root, files, 'input', '0' * 64)

    def test_copy_is_independent_read_only_and_does_not_overwrite(self):
        files = {}
        add_file(self.root, files, 'input')
        target = self.root / 'capsule'
        self.assertEqual(copy_files(self.root, target, files), 5)
        self.assertEqual((target / 'input').read_bytes(), b'proof')
        self.assertEqual((target / 'input').stat().st_mode & 0o222, 0)
        (self.root / 'input').write_bytes(b'later')
        self.assertEqual((target / 'input').read_bytes(), b'proof')
        with self.assertRaises(AssertionError): copy_files(self.root, target, files)

    def test_drift_before_copy_does_not_create_an_execution_copy(self):
        files = {}
        add_file(self.root, files, 'input')
        (self.root / 'input').write_bytes(b'changed')
        target = self.root / 'capsule'
        with self.assertRaises(AssertionError): copy_files(self.root, target, files)
        self.assertFalse(target.exists())

    def test_only_typed_hash_maps_are_dependency_maps(self):
        expected = {'input': 'a' * 64}
        self.assertEqual(list(receipt_inputs({'nested': [{'inputs': expected}], 'inputs': {'other': 7}})), [expected])
        self.assertEqual(list(receipt_inputs({'inputs': {'value': 'not-a-digest'}})), [])


if __name__ == '__main__': unittest.main()
