"""CLI refusal paths never launch a compiler or create a build output."""
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import build_npu_read_api as builder


class ReadAPIBuildCLITests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='read-api-cli-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / '.local').mkdir()

    def invoke(self, arguments, **changes):
        with patch.object(builder, 'ROOT', self.root), \
             patch.object(sys, 'argv', ['build_npu_read_api.py', *arguments]), \
             patch.object(builder.platform, 'machine', return_value=changes.get('machine', 'x86_64')), \
             patch.object(sys, 'platform', 'linux'), \
             patch.object(sys, 'version_info', (3, 14, 0)), \
             patch.object(sys, '_is_gil_enabled', return_value=changes.get('gil', True), create=True), \
             patch.object(builder.subprocess, 'run') as run, \
             patch.object(builder.subprocess, 'check_output') as query, \
             redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as result:
                builder.main()
            run.assert_not_called()
            query.assert_not_called()
            return result.exception.code

    def test_help_needs_no_dependency_query_or_compiler(self):
        self.assertEqual(self.invoke(['--help']), 0)

    def test_existing_output_is_not_overwritten(self):
        output = self.root / '.local/existing'
        output.mkdir()
        marker = output / 'keep.txt'
        marker.write_text('unchanged')
        self.assertEqual(self.invoke(['--output', str(output)]), 2)
        self.assertEqual(marker.read_text(), 'unchanged')
        self.assertEqual(list(output.iterdir()), [marker])

    def test_outside_private_project_tree_is_refused(self):
        output = self.root / 'outside'
        self.assertEqual(self.invoke(['--output', str(output)]), 2)
        self.assertFalse(output.exists())

    def test_unsupported_host_is_refused_before_output_creation(self):
        output = self.root / '.local/new'
        self.assertEqual(self.invoke(['--output', str(output)], machine='aarch64'), 2)
        self.assertFalse(output.exists())

    def test_disabled_gil_is_refused_before_output_creation(self):
        output = self.root / '.local/new'
        self.assertEqual(self.invoke(['--output', str(output)], gil=False), 2)
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
