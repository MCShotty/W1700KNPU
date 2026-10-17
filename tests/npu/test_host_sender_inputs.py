"""Synthetic sender identity checks; no shared library is executed."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_host_tx_lifetime_native as caller


class HostSenderInputTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.asset = self.root / '.local/sender.so'
        self.asset.parent.mkdir()
        self.asset.write_bytes(b'synthetic-not-an-executable-library')
        self.receipt = dict(passed=True, shared='.local/sender.so',
            shared_sha256=hashlib.sha256(self.asset.read_bytes()).hexdigest())

    def test_matching_binary_is_recorded_by_exact_path_and_digest(self):
        with patch.object(caller.parent, 'ROOT', self.root):
            path, inputs = caller.checked_host_sender(self.receipt)
        self.assertEqual(path, self.asset)
        self.assertEqual(inputs, {'.local/sender.so': self.receipt['shared_sha256']})

    def test_changed_binary_does_not_rebase_the_receipt_hash(self):
        self.asset.write_bytes(b'different')
        with patch.object(caller.parent, 'ROOT', self.root):
            with self.assertRaisesRegex(AssertionError, 'host-sender-binary-drift'):
                caller.checked_host_sender(self.receipt)

    def test_missing_binary_is_rejected_before_execution(self):
        self.receipt['shared'] = '.local/missing.so'
        with patch.object(caller.parent, 'ROOT', self.root):
            with self.assertRaises(FileNotFoundError):
                caller.checked_host_sender(self.receipt)

    def test_path_outside_private_storage_is_rejected_before_hashing(self):
        self.receipt['shared'] = 'outside.so'
        with patch.object(caller.parent, 'ROOT', self.root), patch.object(caller.parent.loader, 'sha') as digest:
            with self.assertRaisesRegex(AssertionError, 'outside-private-storage'):
                caller.checked_host_sender(self.receipt)
        digest.assert_not_called()

    def test_unpassed_receipt_is_rejected_before_hashing(self):
        self.receipt['passed'] = False
        with patch.object(caller.parent, 'ROOT', self.root), patch.object(caller.parent.loader, 'sha') as digest:
            with self.assertRaisesRegex(AssertionError, 'receipt-not-passed'):
                caller.checked_host_sender(self.receipt)
        digest.assert_not_called()


if __name__ == '__main__':
    unittest.main()
