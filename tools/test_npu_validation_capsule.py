"""Synthetic capsule copy/path controls; no privileged mount is performed."""
import argparse
from contextlib import redirect_stdout
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import npu_validation_capsule as capsule
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

    def prior_snapshot(self):
        directory = self.root / '.local/npu-validation-capsules/prior'
        files = {}
        add_file(self.root, files, 'input')
        total = copy_files(self.root, directory / 'root', files)
        record = dict(format='npu-validation-capsule-v1', preservation_verified=True,
            source_root=str(self.root), input_root=str(directory / 'root'), sources_read_only=True,
            files=files, file_count=len(files), bytes=total)
        receipt = directory / 'receipt.json'
        receipt.write_text(json.dumps(record))
        return receipt, capsule.load_reuse_snapshot(self.root, receipt)

    def test_reuse_shares_only_readonly_prior_not_writable_source(self):
        receipt, reuse = self.prior_snapshot()
        prior = reuse['root'] / 'input'
        before = prior.stat()
        receipt_bytes = receipt.read_bytes()
        target = self.root / 'next'
        self.assertEqual(copy_files(self.root, target, reuse['files'], reuse), 5)
        self.assertTrue((target / 'input').samefile(prior))
        self.assertFalse((target / 'input').samefile(self.root / 'input'))
        self.assertEqual(prior.stat().st_nlink, before.st_nlink + 1)
        self.assertEqual(prior.stat().st_mode, before.st_mode)
        self.assertEqual(prior.stat().st_uid, before.st_uid)
        self.assertEqual(receipt.read_bytes(), receipt_bytes)
        (self.root / 'input').write_bytes(b'later')
        self.assertEqual((target / 'input').read_bytes(), b'proof')

    def test_changed_content_is_copied_independently(self):
        _, reuse = self.prior_snapshot()
        (self.root / 'input').write_bytes(b'later')
        files = {}
        add_file(self.root, files, 'input')
        target = self.root / 'next'
        copy_files(self.root, target, files, reuse)
        self.assertFalse((target / 'input').samefile(reuse['root'] / 'input'))
        self.assertEqual((target / 'input').read_bytes(), b'later')
        self.assertEqual((reuse['root'] / 'input').read_bytes(), b'proof')

    def test_changed_mode_is_copied_without_chmod_of_shared_inode(self):
        _, reuse = self.prior_snapshot()
        (self.root / 'input').chmod(0o755)
        target = self.root / 'next'
        copy_files(self.root, target, reuse['files'], reuse)
        self.assertFalse((target / 'input').samefile(reuse['root'] / 'input'))
        self.assertEqual((target / 'input').stat().st_mode & 0o777, 0o555)
        self.assertEqual((reuse['root'] / 'input').stat().st_mode & 0o777, 0o444)

    def test_different_owner_does_not_share_an_inode(self):
        _, reuse = self.prior_snapshot()
        target = self.root / 'next'
        with patch.object(capsule.os, 'geteuid', return_value=os.geteuid() + 1):
            copy_files(self.root, target, reuse['files'], reuse)
        self.assertFalse((target / 'input').samefile(reuse['root'] / 'input'))

    def test_writable_or_drifted_prior_input_is_rejected(self):
        receipt, reuse = self.prior_snapshot()
        prior = reuse['root'] / 'input'
        prior.chmod(0o644)
        with self.assertRaises(AssertionError): capsule.load_reuse_snapshot(self.root, receipt)
        prior.write_bytes(b'wrong')
        prior.chmod(0o444)
        with self.assertRaises(AssertionError): capsule.load_reuse_snapshot(self.root, receipt)

    def test_prior_symlink_or_extra_file_is_rejected(self):
        receipt, reuse = self.prior_snapshot()
        extra = reuse['root'] / 'extra'
        extra.write_bytes(b'extra')
        with self.assertRaises(AssertionError): capsule.load_reuse_snapshot(self.root, receipt)
        extra.unlink()
        prior = reuse['root'] / 'input'
        prior.unlink()
        prior.symlink_to(self.root / 'input')
        with self.assertRaises(AssertionError): capsule.load_reuse_snapshot(self.root, receipt)

    def test_prior_special_node_is_rejected_without_reading_it(self):
        receipt, reuse = self.prior_snapshot()
        os.mkfifo(reuse['root'] / 'pipe')
        with self.assertRaises(AssertionError): capsule.load_reuse_snapshot(self.root, receipt)

    def test_prior_receipt_escape_and_invalid_identity_are_rejected(self):
        receipt, _ = self.prior_snapshot()
        outside = self.root / 'outside.json'
        outside.write_bytes(receipt.read_bytes())
        with self.assertRaises(AssertionError): capsule.load_reuse_snapshot(self.root, outside)
        initial = json.loads(receipt.read_bytes())
        for key, value in (('source_root', '/elsewhere'), ('input_root', str(self.root)),
                           ('file_count', True), ('bytes', 6), ('sources_read_only', False)):
            with self.subTest(key=key):
                receipt.write_text(json.dumps(initial | {key: value}))
                with self.assertRaises(AssertionError): capsule.load_reuse_snapshot(self.root, receipt)

    def test_existing_target_and_target_inside_prior_are_rejected(self):
        _, reuse = self.prior_snapshot()
        target = self.root / 'next'
        target.mkdir()
        for destination in (target, reuse['root'] / 'nested'):
            with self.assertRaises(AssertionError): copy_files(self.root, destination, reuse['files'], reuse)
        self.assertFalse((reuse['root'] / 'nested').exists())

    def test_failed_hardlink_does_not_silently_increase_copy_budget(self):
        _, reuse = self.prior_snapshot()
        target = self.root / 'next'
        with patch.object(capsule.os, 'link', side_effect=OSError(errno.EXDEV, 'different filesystem')):
            with self.assertRaises(OSError): copy_files(self.root, target, reuse['files'], reuse)
        self.assertFalse((target / 'input').exists())

    def test_after_link_drift_is_rejected(self):
        _, reuse = self.prior_snapshot()
        real_link = os.link

        def drift(source, target, **options):
            real_link(source, target, **options)
            source.chmod(0o644)
            source.write_bytes(b'wrong')

        with patch.object(capsule.os, 'link', side_effect=drift):
            with self.assertRaises(AssertionError):
                copy_files(self.root, self.root / 'next', reuse['files'], reuse)

    def test_create_records_shared_storage_without_claiming_independent_copies(self):
        receipt, _ = self.prior_snapshot()
        script = self.root / 'tools/npu_validation_capsule.py'
        script.parent.mkdir()
        script.write_bytes(b'fixture')

        def git_output(command, **options):
            if command[1:] == ['ls-files', '-z']: return b'input\0'
            if command[1:] == ['rev-parse', 'HEAD']: return 'a' * 40
            raise AssertionError(command)

        args = argparse.Namespace(name='next', receipt=[], snapshot=[], include=[], reuse_snapshot=receipt)
        with patch.object(capsule, 'ROOT', self.root), \
             patch.object(capsule, 'CAPSULES', receipt.parent.parent), \
             patch.object(capsule, '__file__', str(script)), \
             patch.object(capsule.subprocess, 'check_output', side_effect=git_output), \
             patch.object(capsule.subprocess, 'run') as run, redirect_stdout(io.StringIO()):
            run.return_value.returncode = 0
            capsule.create(args)
        record = json.loads((receipt.parent.parent / 'next/receipt.json').read_bytes())
        material = record['materialization']
        self.assertEqual(material['strategy'], 'verified-readonly-hardlinks-with-copy-fallback')
        self.assertEqual((material['shared_readonly_files'], material['shared_readonly_bytes']), (1, 5))
        self.assertEqual((material['independently_copied_files'], material['copied_regular_file_payload_bytes']), (1, 7))
        self.assertTrue(material['shared_inode_link_counts_ctime_atime_not_preserved'])
        self.assertFalse(record['replay_verified'])


if __name__ == '__main__': unittest.main()
