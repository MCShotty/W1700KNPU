"""Synthetic budgets/probes; no build, disk mutation, or privileged operation."""
import base64
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import npu_storage_budget as budget


class StorageBudgetTests(unittest.TestCase):
    def setUp(self):
        self.budgets = dict(snapshot=100, cache=200, overlay=300, output=100, margin=100)
        self.observation = dict(host=dict(free_bytes=900, total_bytes=2000),
            guest=dict(free_bytes=10000, total_bytes=20000))
        self.host = dict(distro='Ubuntu', vhd_path=r'D:\WSL\Ubuntu\ext4.vhdx',
            vhd_bytes=1000, drive='D', free_bytes=900, total_bytes=2000)

    def test_both_spaces_must_cover_sum_with_margin(self):
        result = budget.evaluate(self.observation, self.budgets)
        self.assertTrue(result['passed'])
        self.assertEqual(result['required_bytes'], 800)
        self.assertEqual(result['remaining_after_budget_bytes'], dict(host=100, guest=9200))
        self.assertFalse(result['space_reserved'])
        self.assertFalse(result['full_npu_goal_complete'])

    def test_guest_headroom_cannot_hide_host_exhaustion(self):
        self.observation['host']['free_bytes'] = 799
        self.assertFalse(budget.evaluate(self.observation, self.budgets)['passed'])

    def test_host_headroom_cannot_hide_guest_exhaustion(self):
        self.observation['guest']['free_bytes'] = 799
        self.assertFalse(budget.evaluate(self.observation, self.budgets)['passed'])

    def test_exact_total_including_margin_is_accepted(self):
        self.observation['host']['free_bytes'] = 800
        self.assertTrue(budget.evaluate(self.observation, self.budgets)['passed'])

    def test_all_components_required(self):
        for name in self.budgets:
            values = self.budgets.copy()
            del values[name]
            with self.subTest(name=name), self.assertRaises(ValueError):
                budget.evaluate(self.observation, values)
        with self.assertRaises(ValueError):
            budget.evaluate(self.observation, self.budgets | dict(extra=1))

    def test_invalid_budget_types_and_negative_values_are_rejected(self):
        for value in (-1, True, 2.5, '1', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                budget.evaluate(self.observation, self.budgets | dict(snapshot=value))
        with self.assertRaises(ValueError):
            budget.evaluate(self.observation, self.budgets | dict(margin=0))

    def test_invalid_observations_are_rejected(self):
        for value in (-1, True, None, 2001):
            observation = copy.deepcopy(self.observation)
            observation['host']['free_bytes'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                budget.evaluate(observation, self.budgets)

    def test_untrusted_distro_name_cannot_become_powershell_code(self):
        for name in ('', "Ubuntu';throw 'x", 'Ubuntu\n', '../Ubuntu', 'a' * 65):
            with self.subTest(name=name), patch.object(subprocess, 'run') as run:
                with self.assertRaises(ValueError):
                    budget.windows_query(name)
                run.assert_not_called()

    def test_host_probe_uses_registered_vhd_and_no_disk_write_commands(self):
        response = subprocess.CompletedProcess([], 0, json.dumps(self.host).encode(), b'')
        with patch.object(subprocess, 'run', return_value=response) as run:
            self.assertEqual(budget.windows_query('Ubuntu'), self.host)
        argv = run.call_args.args[0]
        self.assertEqual(argv[:5], ['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand'])
        script = base64.b64decode(argv[-1]).decode('utf-16le')
        for text in ('Lxss', 'VhdFileName', 'Get-Volume', "-ceq 'Ubuntu'"):
            self.assertIn(text, script)
        for text in ('Set-', 'Remove-', 'diskpart', 'wsl.exe', 'Format-', 'Resize-'):
            self.assertNotIn(text, script)

    def test_failed_or_malformed_host_probe_is_not_success(self):
        for response in (subprocess.CompletedProcess([], 1, b'', b'diagnostic'),
                         subprocess.CompletedProcess([], 0, b'not JSON', b'')):
            with self.subTest(response=response), patch.object(subprocess, 'run', return_value=response):
                with self.assertRaises(ValueError):
                    budget.windows_query('Ubuntu')
        with patch.object(subprocess, 'run', side_effect=subprocess.TimeoutExpired('probe', 30)):
            with self.assertRaises(subprocess.TimeoutExpired):
                budget.windows_query('Ubuntu')

    def observe(self, host=None, filesystem='ext4', flags=0):
        with patch.dict(os.environ, WSL_DISTRO_NAME='Ubuntu'), \
             patch.object(budget, 'windows_query', return_value=host or self.host), \
             patch.object(subprocess, 'check_output', return_value=filesystem), \
             patch.object(os, 'statvfs') as vfs:
            vfs.return_value.f_flag = flags
            return budget.observe(Path(__file__).resolve().parent)

    def test_live_collection_keeps_backing_identity(self):
        result = self.observe()
        self.assertEqual(result['host'], self.host)
        self.assertEqual(result['filesystem'], 'ext4')
        self.assertTrue(result['writable_ext4'])

    def test_ntfs_or_readonly_project_is_denied(self):
        for filesystem, flags in (('9p', 0), ('ext4', os.ST_RDONLY)):
            with self.subTest(filesystem=filesystem, flags=flags), self.assertRaises(ValueError):
                self.observe(filesystem=filesystem, flags=flags)

    def test_wrong_distro_drive_or_unc_backing_is_denied(self):
        for changed in (dict(distro='Other'), dict(drive='C'), dict(vhd_path=r'\\host\share\ext4.vhdx'),
                        dict(vhd_bytes=0)):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.observe(host=self.host | changed)

    def cli(self, root, observation, output, command):
        argv = ['npu_storage_budget.py', '--output', str(output)]
        for name, value in self.budgets.items():
            argv += ['--' + name + '-bytes', str(value)]
        argv += ['--', *command]
        with patch.object(budget, 'ROOT', root), patch.object(sys, 'argv', argv), \
             patch.object(budget, 'observe', return_value=observation), \
             patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess(command, 7)) as run, \
             patch('builtins.print'):
            with self.assertRaises(SystemExit) as raised:
                budget.main()
            return raised.exception.code, run

    def test_insufficient_capacity_records_refusal_without_running_child(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / '.local').mkdir()
            output = root / '.local/check.json'
            self.observation['host']['free_bytes'] = 799
            status, run = self.cli(root, self.observation, output, ['build-command'])
            self.assertEqual(status, 2)
            run.assert_not_called()
            self.assertFalse(json.loads(output.read_bytes())['passed'])

    def test_success_executes_exact_argv_and_propagates_child_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / '.local').mkdir()
            output = root / '.local/check.json'
            command = ['build-command', 'one argument', 'literal;not-shell']
            status, run = self.cli(root, self.observation, output, command)
            self.assertEqual(status, 7)
            run.assert_called_once_with(command, stdin=subprocess.DEVNULL)
            self.assertEqual(json.loads(output.read_bytes())['command'], command)

    def test_existing_receipt_is_not_overwritten_and_child_is_not_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / '.local').mkdir()
            output = root / '.local/check.json'
            output.write_text('original')
            status, run = self.cli(root, self.observation, output, ['build-command'])
            self.assertEqual(status, 2)
            run.assert_not_called()
            self.assertEqual(output.read_text(), 'original')

    def test_second_cooperating_launch_is_denied(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / '.local').mkdir()
            with (root / '.local/npu-storage-budget.lock').open('a') as lock:
                budget.fcntl.flock(lock, budget.fcntl.LOCK_EX | budget.fcntl.LOCK_NB)
                status, run = self.cli(root, self.observation, root / '.local/check.json', ['build-command'])
            self.assertEqual(status, 2)
            run.assert_not_called()
            self.assertFalse((root / '.local/check.json').exists())


class LinkerAliasPreservationTests(unittest.TestCase):
    def test_explicit_logical_identities_materialize_all_four_aliases(self):
        import npu_validation_capsule as capsule
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'lld').write_bytes(b'pinned-linker-fixture')
            (root / 'lld').chmod(0o755)
            names = ('ld.lld', 'ld64.lld', 'lld-link', 'wasm-ld')
            for name in names:
                (root / name).symlink_to('lld')
            expected = capsule.digest(root / 'lld')
            aliases = {name: expected for name in names}
            maps = list(capsule.receipt_inputs(dict(passed=True, inputs=aliases)))
            self.assertEqual(maps, [aliases])
            files = {}
            for name, digest in maps[0].items():
                capsule.add_file(root, files, name, digest)
            target = root / 'frozen'
            capsule.copy_files(root, target, files)
            self.assertEqual(set(files), set(names))
            for name in names:
                path = target / name
                self.assertFalse(path.is_symlink())
                self.assertEqual(capsule.digest(path), expected)
                self.assertEqual(path.stat().st_mode & 0o222, 0)
                self.assertTrue(path.stat().st_mode & 0o111)


if __name__ == '__main__':
    unittest.main()
