"""Synthetic dependency binding, not firmware execution or board acceptance."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_bootstrap_native as bootstrap
import test_provider_session as provider


class ProviderBootstrapInputTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.asset = self.root / 'candidate.dtb'
        self.asset.write_bytes(b'synthetic-DTB-dependency')

    def test_validated_asset_is_bound_by_exact_path_and_digest(self):
        with patch.object(provider, 'ROOT', self.root), patch.object(bootstrap, 'DTB', self.asset), \
                patch.object(bootstrap, 'plan') as validate:
            actual = provider.native_bootstrap_inputs()
        validate.assert_called_once_with()
        self.assertEqual(actual, {'candidate.dtb': hashlib.sha256(self.asset.read_bytes()).hexdigest()})

    def test_validation_failure_is_not_replaced_by_a_current_hash(self):
        with patch.object(provider, 'ROOT', self.root), patch.object(bootstrap, 'DTB', self.asset), \
                patch.object(bootstrap, 'plan', side_effect=AssertionError('pinned-DTB-mismatch')), \
                patch.object(provider.loader, 'sha') as digest:
            with self.assertRaisesRegex(AssertionError, 'pinned-DTB-mismatch'):
                provider.native_bootstrap_inputs()
        digest.assert_not_called()

    def test_missing_asset_cannot_produce_an_input_manifest(self):
        missing = self.root / 'missing.dtb'
        with patch.object(provider, 'ROOT', self.root), patch.object(bootstrap, 'DTB', missing), \
                patch.object(bootstrap, 'plan'):
            with self.assertRaises(FileNotFoundError):
                provider.native_bootstrap_inputs()

    def test_asset_outside_project_is_rejected_before_hashing(self):
        with patch.object(provider, 'ROOT', self.root / 'other'), patch.object(bootstrap, 'DTB', self.asset), \
                patch.object(bootstrap, 'plan'), patch.object(provider.loader, 'sha') as digest:
            with self.assertRaises(ValueError):
                provider.native_bootstrap_inputs()
        digest.assert_not_called()


if __name__ == '__main__':
    unittest.main()
