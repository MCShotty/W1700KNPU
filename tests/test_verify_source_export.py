"""Cumulative-index, overlay and canonical-component source selection."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SourceExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / '.local')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        script = self.root / 'tools/migration/verify_source_export.py'
        script.parent.mkdir(parents=True)
        shutil.copy2(ROOT / 'tools/migration/verify_source_export.py', script)
        self.script = script
        (self.root / '.migration').mkdir()
        self.lock = dict(build_directory='.build/current', component_sources=[])
        for label in ('openwrt', 'luci'):
            tree = self.root / '.build/current'
            if label == 'luci':
                tree /= 'feeds/luci'
            tree.mkdir(parents=True, exist_ok=True)
            self.git(tree, 'init')
            (tree / 'tracked.txt').write_text('before\n')
            self.git(tree, 'add', 'tracked.txt')
            self.git(tree, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'fixture')
            revision = self.git(tree, 'rev-parse', 'HEAD').decode().strip()
            (tree / 'tracked.txt').write_text('after\n')
            patch = self.root / 'firmware/patches' / (label + '.patch')
            patch.parent.mkdir(parents=True, exist_ok=True)
            patch.write_bytes(self.git(tree, 'diff'))
            (tree / 'tracked.txt').write_text('unrelated working copy\n')
            self.lock[label] = dict(base=revision, changed_files=[dict(path='tracked.txt', sha256=self.sha(b'after\n'))])
        self.component = self.root / 'firmware/npu/shared.c'
        self.component.parent.mkdir(parents=True)
        self.component.write_text('int component;\n')
        destination = 'package/kernel/mt76/w1700k/shared.c'
        self.lock['component_sources'] = [dict(tree='openwrt', source='firmware/npu/shared.c', destination=destination,
                                               sha256=self.sha(self.component.read_bytes()))]
        self.lock['openwrt']['changed_files'].append(dict(path=destination, sha256=self.sha(self.component.read_bytes())))
        live_component = self.root / '.build/current' / destination
        live_component.parent.mkdir(parents=True)
        live_component.write_text('incorrect generated component\n')
        self.overlay = self.root / 'firmware/overlay/openwrt/files/value.txt'
        self.overlay.parent.mkdir(parents=True)
        self.overlay.write_text('overlay\n')
        self.lock['openwrt']['changed_files'].append(dict(path='files/value.txt', sha256=self.sha(self.overlay.read_bytes())))

    def git(self, tree, *args):
        return subprocess.check_output(['git', '-C', tree, *args], env=self.env, stderr=subprocess.DEVNULL)

    @staticmethod
    def sha(data):
        return hashlib.sha256(data).hexdigest()

    def run_check(self):
        (self.root / 'firmware/source-lock.json').write_text(json.dumps(self.lock))
        report = self.root / 'proof.json'
        done = subprocess.run(['python3', self.script, '--output', report], env=self.env,
                              capture_output=True, text=True, timeout=30)
        return done, report

    def test_locked_build_index_and_canonical_component(self):
        done, report = self.run_check()
        self.assertEqual(done.returncode, 0, done.stderr)
        results = json.loads(report.read_bytes())
        self.assertEqual([row['changed_files_verified'] for row in results], [3, 1])

    def test_changed_component_rejected(self):
        self.component.write_text('altered canonical component\n')
        done, report = self.run_check()
        self.assertNotEqual(done.returncode, 0)
        self.assertIn('Export mismatch', done.stderr)
        self.assertFalse(report.exists())

    def test_conflicting_component_metadata_rejected(self):
        self.lock['component_sources'][0]['sha256'] = '0' * 64
        done, report = self.run_check()
        self.assertNotEqual(done.returncode, 0)
        self.assertIn('Component metadata mismatch', done.stderr)
        self.assertFalse(report.exists())

    def test_changed_overlay_rejected(self):
        self.overlay.write_text('altered overlay\n')
        done, report = self.run_check()
        self.assertNotEqual(done.returncode, 0)
        self.assertIn('Export mismatch', done.stderr)
        self.assertFalse(report.exists())


if __name__ == '__main__':
    unittest.main()
