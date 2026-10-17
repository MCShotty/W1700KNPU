"""Synthetic inventory/command-contract checks,not a world or hardware test."""
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import npu_isolated_world as world


class IsolatedWorldTests(unittest.TestCase):
    def test_host_timeout_is_recorded_without_a_successful_exit_code(self):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / 'run.log'
            with patch.object(world.subprocess, 'run', side_effect=subprocess.TimeoutExpired(['synthetic'], 9)):
                result = world.run_logged(['synthetic'], log, timeout=9)
            self.assertEqual(result, dict(returncode=None, host_timeout=True, host_timeout_seconds=9))
            self.assertTrue(log.is_file())

    def test_nonzero_exit_is_preserved_and_existing_logs_are_not_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / 'run.log'
            with patch.object(world.subprocess, 'run', return_value=subprocess.CompletedProcess(['synthetic'], 7)):
                result = world.run_logged(['synthetic'], log, timeout=9)
            self.assertEqual(result, dict(returncode=7, host_timeout=False, host_timeout_seconds=9))
            with self.assertRaises(FileExistsError): world.run_logged(['synthetic'], log)

    def synthetic_snapshot(self, directory):
        directory = Path(directory)
        frozen = directory / 'root'
        for path in ('tools', '.build/merged-openwrt', '.build/openwrt/dl', '.local/merge-nonoc-20260923'):
            (frozen / path).mkdir(parents=True, exist_ok=True)
        script = frozen / 'tools/npu_isolated_world.py'
        script.write_bytes(Path(world.__file__).read_bytes())
        script.chmod(0o444)
        record = dict(format='npu-validation-capsule-v1',preservation_verified=True,
            input_root=str(frozen),source_root=str(world.ROOT),
            files={'tools/npu_isolated_world.py':world.digest(script)},
            synthetic_unit_fixture_only=True,hardware=False)
        receipt = directory / 'receipt.json'
        receipt.write_text(json.dumps(record))
        return receipt, frozen, script

    def test_linker_preflight_requires_exact_declared_readonly_executable(self):
        with tempfile.TemporaryDirectory() as temporary:
            frozen = Path(temporary)
            name = str((world.LINKER_PREFIX / 'bin/ld.lld').relative_to(world.ROOT))
            linker = frozen / name
            linker.parent.mkdir(parents=True)
            linker.write_bytes(b'synthetic linker fixture;not executable code')
            linker.chmod(0o555)
            expected = dict(path=name,sha256=world.digest(linker))
            self.assertEqual(world.linker_input(frozen,dict(files={name:expected['sha256']})),expected)

    def test_missing_linker_stops_run_before_output_creation_or_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frozen = root / 'root'
            (frozen / 'firmware').mkdir(parents=True)
            (frozen / 'firmware/source-lock.json').write_bytes(b'{}')
            args = SimpleNamespace(name='fixture',snapshot=root / 'synthetic.json',probe_only=False,
                provider_receipt=Path('synthetic-provider.json'),mt76_receipt=Path('synthetic-mt76.json'))
            with patch.object(world,'STORE',root / 'output'), \
                    patch.object(world.os,'getuid',return_value=1000), \
                    patch.object(world,'snapshot',return_value=(frozen,dict(files={}))), \
                    patch.object(world,'tree_state') as inventory:
                with self.assertRaisesRegex(AssertionError,'missing-frozen-linker'): world.run(args)
                inventory.assert_not_called()
                self.assertFalse((root / 'output').exists())

    def test_missing_alias_unlisted_changed_or_wrong_mode_linker_is_rejected(self):
        for mutation in ('missing','unlisted','bytes','nonexecutable','writable','link'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                frozen = Path(temporary)
                name = str((world.LINKER_PREFIX / 'bin/ld.lld').relative_to(world.ROOT))
                linker = frozen / name
                linker.parent.mkdir(parents=True)
                linker.write_bytes(b'synthetic fixture')
                record = dict(files={name:world.digest(linker)})
                linker.chmod(0o555)
                if mutation == 'missing': linker.unlink()
                elif mutation == 'unlisted': record['files'].clear()
                elif mutation == 'bytes':
                    linker.chmod(0o755)
                    linker.write_bytes(b'changed')
                    linker.chmod(0o555)
                elif mutation == 'nonexecutable': linker.chmod(0o444)
                elif mutation == 'writable': linker.chmod(0o755)
                else:
                    linker.unlink()
                    linker.symlink_to('/bin/true')
                with self.assertRaises(AssertionError): world.linker_input(frozen,record)

    def test_synthetic_snapshot_requires_exact_declared_readonly_files(self):
        base = world.ROOT / '.local/npu-validation-capsules'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='world-unit-',dir=base) as temporary:
            receipt, frozen, script = self.synthetic_snapshot(temporary)
            result, record = world.snapshot(receipt)
            self.assertEqual(result, frozen)
            self.assertTrue(record['synthetic_unit_fixture_only'])

    def test_snapshot_drift_extra_files_links_and_writable_source_are_rejected(self):
        base = world.ROOT / '.local/npu-validation-capsules'
        base.mkdir(parents=True, exist_ok=True)
        for mutation in ('bytes','extra','link','mode'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(prefix='world-unit-',dir=base) as temporary:
                receipt, frozen, script = self.synthetic_snapshot(temporary)
                if mutation == 'bytes':
                    script.chmod(0o644)
                    script.write_bytes(b'changed')
                    script.chmod(0o444)
                elif mutation == 'extra': (frozen / 'undeclared').write_bytes(b'new')
                elif mutation == 'link': (frozen / 'outside').symlink_to('/usr')
                else: script.chmod(0o644)
                with self.assertRaises(AssertionError): world.snapshot(receipt)

    def test_invalid_inner_name_is_rejected_before_any_namespace_or_build_work(self):
        result = subprocess.run([sys.executable,world.__file__,'inner','--name','../unsafe','--context','{}'],
            text=True,capture_output=True,timeout=10)
        self.assertEqual(result.returncode,2)
        self.assertIn('Invalid result name',result.stderr)

    def test_world_requires_current_producers_before_opening_snapshot_or_output(self):
        result = subprocess.run([sys.executable,world.__file__,'run','--name','fixture',
            '--snapshot','/missing-synthetic-snapshot.json'],text=True,capture_output=True,timeout=10)
        self.assertEqual(result.returncode,2)
        self.assertIn('producer receipts are required',result.stderr)

    def test_inventory_retains_absolute_link_literal_without_following_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'source').write_bytes(b'data')
            (root / 'alias').symlink_to('/not-a-real-target')
            state = world.tree_state(root)
            self.assertEqual(state['alias']['target'], '/not-a-real-target')
            self.assertEqual(state['alias']['kind'], 'link')
            self.assertEqual(state['source']['sha256'], world.digest(root / 'source'))

    def test_content_mode_owner_and_directory_are_part_of_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.write_bytes(b'data')
            source.chmod(0o640)
            before = world.tree_state(root)
            self.assertEqual(before['source']['uid'], os.getuid())
            self.assertEqual(before['source']['gid'], os.getgid())
            source.chmod(0o600)
            self.assertNotEqual(world.tree_state(root), before)
            source.chmod(0o640)
            source.write_bytes(b'else')
            self.assertNotEqual(world.tree_state(root), before)
            source.write_bytes(b'data')
            (root / 'new-directory').mkdir()
            self.assertNotEqual(world.tree_state(root), before)

    def test_special_file_cannot_enter_build_lower(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.mkfifo(root / 'pipe')
            with self.assertRaisesRegex(AssertionError, 'special-build-input'): world.tree_state(root)

    def test_command_has_readonly_host_and_snapshot_and_exact_two_overlays(self):
        context = {'uid':1000,'example':'synthetic context'}
        result = world.command(Path('/snapshot'), Path('/session'), 'fixture', context, True)
        self.assertEqual(result[:8], ['bwrap','--unshare-all','--ro-bind','/','/','--ro-bind','/snapshot',str(world.ROOT)])
        self.assertNotIn('--share-net', result)
        self.assertEqual(result.count('--overlay-src'), 2)
        self.assertEqual(result.count('--overlay'), 2)
        first, second = [i for i, value in enumerate(result) if value == '--overlay']
        self.assertEqual(result[first+1:first+4], ['/session/build-upper','/session/build-work',str(world.BUILD)])
        self.assertEqual(result[second+1:second+4], ['/session/log-upper','/session/log-work',str(world.WORK)])
        self.assertEqual(result[result.index('--bind')+1:result.index('--bind')+3], ['/session/tmp','/tmp'])
        self.assertIn('--clearenv', result)
        self.assertIn('--probe-only', result)
        self.assertEqual(json.loads(result[result.index('--context')+1]), context)

    def test_full_build_does_not_silently_enable_network_or_probe_mode(self):
        result = world.command(Path('/snapshot'), Path('/session'), 'fixture', {}, False)
        self.assertNotIn('--probe-only', result)
        self.assertNotIn('--share-net', result)
        self.assertIn('--die-with-parent', result)
        self.assertIn('--new-session', result)


if __name__ == '__main__': unittest.main()
