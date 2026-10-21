"""Frozen launcher contracts only; not extraction or hardware acceptance."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import npu_isolated_world as world


class FrozenBubblewrapTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory).resolve()
        selected = root / '.local/bwrap/bin/bwrap'
        frozen = root / '.local/npu-validation-capsules/example/root'
        name = selected.relative_to(root).as_posix()
        for path in (selected, frozen / name):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'synthetic launcher fixture, not executable code')
            path.chmod(0o555)
        return root, selected, frozen, name, dict(files={name:world.digest(selected)})

    def test_default_is_absolute_system_executable_and_reports_actual_hash(self):
        with patch.object(world, 'digest', return_value='system-hash') as digest:
            executable, metadata = world.bubblewrap_input(SimpleNamespace(), Path('/unused'), {})
        self.assertEqual(executable, Path('/usr/bin/bwrap'))
        self.assertEqual(metadata, dict(path='/usr/bin/bwrap',sha256='system-hash',frozen=False))
        digest.assert_called_once_with(executable)

    def test_selected_binary_executes_from_declared_frozen_path_not_mutable_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, selected, frozen, name, record = self.fixture(temporary)
            with patch.object(world, 'ROOT', root):
                executable, metadata = world.bubblewrap_input(SimpleNamespace(bubblewrap=selected), frozen, record)
            self.assertEqual(executable, frozen / name)
            self.assertTrue(metadata['frozen'])
            self.assertEqual(metadata['sha256'], record['files'][name])

    def test_undeclared_changed_and_unsafe_executables_are_rejected(self):
        for mutation in ('unlisted','source-bytes','frozen-bytes','writable','nonexecutable','setuid','setgid','sticky','symlink','external','capsule'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root, selected, frozen, name, record = self.fixture(temporary)
                target = frozen / name
                if mutation == 'unlisted': record['files'].clear()
                elif mutation.endswith('-bytes'):
                    changed = selected if mutation == 'source-bytes' else target
                    changed.chmod(0o755)
                    changed.write_bytes(b'changed')
                    changed.chmod(0o555)
                elif mutation in ('writable','nonexecutable','setuid','setgid','sticky'):
                    target.chmod({'writable':0o755,'nonexecutable':0o444,'setuid':0o4555,'setgid':0o2555,'sticky':0o1555}[mutation])
                elif mutation == 'symlink':
                    alias = root / '.local/alias'
                    alias.symlink_to(selected.parent, target_is_directory=True)
                    selected = alias / 'bwrap'
                elif mutation == 'external': selected = Path('/usr/bin/bwrap')
                else: selected = target
                with patch.object(world, 'ROOT', root), self.assertRaises((AssertionError, FileNotFoundError)):
                    world.bubblewrap_input(SimpleNamespace(bubblewrap=selected), frozen, record)

    def test_command_changes_only_executable_and_keeps_all_isolation_flags(self):
        args = (Path('/snapshot'),Path('/session'),'fixture',dict(uid=1000),False)
        default = world.command(*args)
        selected = world.command(*args, bubblewrap=Path('/snapshot/.local/bwrap/bin/bwrap'))
        self.assertEqual(default[1:], selected[1:])
        self.assertEqual(selected[0], '/snapshot/.local/bwrap/bin/bwrap')
        self.assertIn('--unshare-all',selected)
        self.assertEqual(selected.count('--overlay'),2)
        self.assertIn('--clearenv',selected)


if __name__ == '__main__': unittest.main()
