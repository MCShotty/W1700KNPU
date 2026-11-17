#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


class RestoreArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.part = self.root / 'part'
        self.part.write_bytes(b'fixture bytes')
        sha = hashlib.sha256(self.part.read_bytes()).hexdigest()
        self.manifest = self.root / 'manifest.json'
        self.manifest.write_text(json.dumps({'bytes': 13, 'sha256': sha,
            'parts': [{'path': 'part', 'bytes': 13, 'sha256': sha}]}))
        self.output = self.root / 'output.bin'

    def run_restore(self):
        return subprocess.run([sys.executable, str(ROOT / 'tools/restore_artifact.py'),
            str(self.manifest), '--output', str(self.output)], capture_output=True).returncode

    def test_valid_reassembly(self):
        self.assertEqual(self.run_restore(), 0)
        self.assertEqual(self.output.read_bytes(), self.part.read_bytes())

    def test_mismatch_removes_only_own_partial(self):
        self.part.write_bytes(b'changed bytes')
        self.assertNotEqual(self.run_restore(), 0)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.with_name('output.bin.partial').exists())

    def test_existing_output_is_preserved(self):
        self.output.write_bytes(b'preserve')
        self.assertNotEqual(self.run_restore(), 0)
        self.assertEqual(self.output.read_bytes(), b'preserve')

    def test_existing_partial_is_preserved(self):
        partial = self.output.with_name('output.bin.partial')
        partial.write_bytes(b'preserve partial')
        self.assertNotEqual(self.run_restore(), 0)
        self.assertEqual(partial.read_bytes(), b'preserve partial')

    def test_dangling_output_is_not_followed(self):
        missing = self.root / 'missing'
        try:
            self.output.symlink_to(missing)
        except OSError as error:
            if getattr(error, 'winerror', None) == 1314:
                self.skipTest('Windows account lacks the symlink privilege')
            raise
        self.assertNotEqual(self.run_restore(), 0)
        self.assertTrue(self.output.is_symlink())
        self.assertFalse(missing.exists())

    def test_output_created_during_restore_is_preserved(self):
        read = Path.read_bytes

        def read_part(path):
            if path == self.part:
                self.output.write_bytes(b'other writer')
            return read(path)

        tool = str(ROOT / 'tools/restore_artifact.py')
        with patch.object(Path, 'read_bytes', read_part), patch.object(sys, 'argv',
                [tool, str(self.manifest), '--output', str(self.output)]):
            with self.assertRaises((FileExistsError, SystemExit)):
                runpy.run_path(tool, run_name='__main__')
        self.assertEqual(self.output.read_bytes(), b'other writer')
        self.assertFalse(self.output.with_suffix('.bin.partial').exists())


if __name__ == '__main__':
    unittest.main()
