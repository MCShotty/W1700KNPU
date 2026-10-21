"""Current-authority staging into synthetic private builds;not image acceptance."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import npu_world_sources as sources


class WorldStagingTests(unittest.TestCase):
    def fixture(self, directory):
        root, build = directory / 'root', directory / 'private-build'
        root.mkdir()
        build.mkdir()

        def make(base, name, data):
            path = base / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(0o644)
            return hashlib.sha256(data).hexdigest()

        overlay = 'package/kernel/mt76/patches/current.patch'
        overlay_sha = make(root, 'firmware/overlay/openwrt/' + overlay, b'current checked IRQ recipe')
        cumulative_sha = make(build, 'base-only.c', b'unchanged cumulative source')
        luci_sha = make(build, 'feeds/luci/network.js', b'unchanged UI source')
        component_sha = make(root, 'firmware/npu/control.c', b'current provider component')
        make(build, overlay, b'old prepared recipe')
        make(build, 'target/linux/files/control.c', b'old provider component')
        make(root, 'firmware/build.config', b'CONFIG_CURRENT=y\n')
        make(build, '.config', b'CONFIG_OLD=y\n')
        lock = dict(openwrt=dict(changed_files=[dict(path=overlay, sha256=overlay_sha, mode='0644'),
            dict(path='base-only.c', sha256=cumulative_sha, mode='0644')]),
            luci=dict(changed_files=[dict(path='network.js', sha256=luci_sha, mode='0644')]),
            component_sources=[dict(tree='openwrt', source='firmware/npu/control.c',
                destination='target/linux/files/control.c', sha256=component_sha, mode='0644')])
        make(root, 'firmware/source-lock.json', json.dumps(lock).encode())
        return root, build, lock, overlay

    def stage(self, root, build, lock, copier=shutil.copy2):
        return sources.stage_locked_overlays(build, root, lock, copier)

    def test_stale_overlay_components_and_config_are_refreshed_and_all_sources_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, build, lock, overlay = self.fixture(Path(temporary))
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            result = self.stage(root, build, lock)
            self.assertEqual(set(result['copied']), {overlay, 'target/linux/files/control.c', '.config'})
            self.assertEqual(result['locked_files_checked'], dict(openwrt=2, luci=1))
            self.assertEqual(result['component_sources_checked'], 1)
            self.assertEqual({str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}, before)
            self.assertEqual(self.stage(root, build, lock)['copied'], [])

    def test_wrong_authority_bytes_fail_before_any_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, build, lock, overlay = self.fixture(Path(temporary))
            (root / 'firmware/overlay/openwrt' / overlay).write_bytes(b'unbound source')
            with self.assertRaisesRegex(AssertionError, 'overlay-source-drift'):
                self.stage(root, build, lock)
            self.assertEqual((build / overlay).read_bytes(), b'old prepared recipe')

    def test_missing_or_stale_cumulative_only_source_is_not_invented(self):
        for missing in (False, True):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as temporary:
                root, build, lock, overlay = self.fixture(Path(temporary))
                path = build / 'base-only.c'
                if missing: path.unlink()
                else: path.write_bytes(b'stale cumulative source')
                with self.assertRaisesRegex(AssertionError, 'prebuild-locked-source-drift'):
                    self.stage(root, build, lock)

    def test_escaped_paths_aliased_targets_and_conflicting_authorities_are_rejected(self):
        for mutation in ('escape', 'alias', 'conflict'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root, build, lock, overlay = self.fixture(Path(temporary))
                if mutation == 'escape': lock['component_sources'][0]['destination'] = '../escape.c'
                elif mutation == 'alias':
                    (build / overlay).unlink()
                    (build / overlay).symlink_to(root / 'firmware/build.config')
                else: lock['component_sources'][0]['destination'] = overlay
                with self.assertRaises(AssertionError): self.stage(root, build, lock)

    def test_wrong_modes_and_corrupt_copy_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, build, lock, overlay = self.fixture(Path(temporary))
            (build / 'base-only.c').chmod(0o600)
            with self.assertRaisesRegex(AssertionError, 'prebuild-locked-source-mode'):
                self.stage(root, build, lock)
        with tempfile.TemporaryDirectory() as temporary:
            root, build, lock, overlay = self.fixture(Path(temporary))
            def corrupt(source, target):
                target.write_bytes(b'corrupt copy')
            with self.assertRaisesRegex(AssertionError, 'staged-overlay-drift'):
                self.stage(root, build, lock, corrupt)


if __name__ == '__main__': unittest.main()
