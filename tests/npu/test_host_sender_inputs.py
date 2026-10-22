"""Synthetic sender identity checks; no shared library is executed."""
import hashlib
import json
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


class CompilePreflightTests(unittest.TestCase):
    def setUp(self):
        HostSenderInputTests.setUp(self)

    def preflight(self):
        with patch.object(caller.parent, 'ROOT', self.root):
            return caller.record_compile_preflight(self.asset.parent, self.asset,
                {'.local/sender.so': self.receipt['shared_sha256']})

    def test_compile_receipt_is_not_a_native_result(self):
        result = self.preflight()
        self.assertTrue(result['compiled'])
        self.assertFalse(result['native_executed'])
        self.assertFalse(result['full_native_caller_verdict'])
        self.assertFalse(result['hardware'])
        self.assertNotIn('passed', result)
        self.assertFalse((self.asset.parent / 'result.json').exists())
        self.assertEqual(json.loads((self.asset.parent / 'compile-preflight.json').read_bytes()), result)

    def test_compile_receipt_rejects_changed_input(self):
        self.asset.write_bytes(b'changed-after-linkage')
        with self.assertRaises(AssertionError):
            self.preflight()
        self.assertFalse((self.asset.parent / 'compile-preflight.json').exists())

    def test_compile_receipt_rechecks_nonsender_source(self):
        source = self.root / 'provider.c'
        source.write_bytes(b'changed')
        with patch.object(caller.parent, 'ROOT', self.root):
            with self.assertRaises(AssertionError):
                caller.record_compile_preflight(self.asset.parent, self.asset,
                    {'.local/sender.so': self.receipt['shared_sha256'],
                     'provider.c': hashlib.sha256(b'original').hexdigest()})
        self.assertFalse((self.asset.parent / 'compile-preflight.json').exists())

    def test_compile_receipt_cannot_overwrite_previous_observation(self):
        self.preflight()
        original = (self.asset.parent / 'compile-preflight.json').read_bytes()
        with self.assertRaises(FileExistsError):
            self.preflight()
        self.assertEqual((self.asset.parent / 'compile-preflight.json').read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
