#!/usr/bin/env python3
"""Exercise builder PATH selection with workspace fake make, never a real build."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
BUILDER = ROOT / 'tools/build_firmware.py'
spec = importlib.util.spec_from_file_location('build_firmware', BUILDER)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

FAKE_MAKE = '''#!{python}
import json
import os
from pathlib import Path
import sys
stage = 'npu' if '-C' in sys.argv else 'openwrt'
entry = dict(stage=stage, argv=sys.argv[1:], cwd=os.getcwd(), executable=__file__,
             path=os.environ['PATH'], git_prompt=os.environ['GIT_TERMINAL_PROMPT'],
             cppflags=os.environ.get('CPPFLAGS'), ldflags=os.environ.get('LDFLAGS'),
             library_path=os.environ.get('LIBRARY_PATH'))
with Path(os.environ['BUILD_TEST_TRACE']).open('a') as stream:
    stream.write(json.dumps(entry) + '\\n')
sys.exit(int(os.environ.get('BUILD_TEST_OPENWRT_EXIT', '0')) if stage == 'openwrt' else 0)
'''


class HostToolsTests(unittest.TestCase):
    def setUp(self):
        for name in ('.local', '.build'):
            (ROOT / name).mkdir(exist_ok=True)
        self.local_temp = tempfile.TemporaryDirectory(prefix='builder-test-', dir=ROOT / '.local')
        self.build_temp = tempfile.TemporaryDirectory(prefix='builder-test-', dir=ROOT / '.build')
        self.addCleanup(self.local_temp.cleanup)
        self.addCleanup(self.build_temp.cleanup)
        self.local = Path(self.local_temp.name)
        self.build = Path(self.build_temp.name)
        self.destination = self.build / 'openwrt'
        self.destination.mkdir()
        (self.destination / '.config').write_text('# fake configuration\n')
        self.trace = self.local / 'trace.jsonl'

    def prefix(self, parent, name='host'):
        prefix = parent / name
        (prefix / 'bin').mkdir(parents=True)
        executable = prefix / 'bin/make'
        executable.write_text(FAKE_MAKE.format(python=Path(sys.executable).resolve()))
        executable.chmod(0o755)
        return prefix

    def invoke(self, prefixes, *, code=0, target='tools/compile'):
        name = 'host-tools-test-' + uuid.uuid4().hex
        log_dir = ROOT / '.local/merge-nonoc-20260923'
        for suffix in ('.log', '.json'):
            path = log_dir / ('build-' + name + suffix)
            self.addCleanup(path.unlink, missing_ok=True)
        hostile = self.prefix(self.local, 'ambient-' + uuid.uuid4().hex)
        env = dict(os.environ, PATH=str(hostile / 'bin'), BUILD_TEST_TRACE=str(self.trace),
                   BUILD_TEST_OPENWRT_EXIT=str(code), GIT_TERMINAL_PROMPT='1',
                   CPPFLAGS='-I/workspace/include-test', LDFLAGS='-L/workspace/lib-test',
                   LIBRARY_PATH='/workspace/library-test')
        command = [sys.executable, str(BUILDER), '--destination', str(self.destination),
                   '--target', target, '--jobs', '2', '--name', name]
        for prefix in prefixes:
            command += ['--host-tools', str(prefix)]
        result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                capture_output=True, timeout=20)
        state = log_dir / ('build-' + name + '.json')
        return result, state, hostile

    def test_default_path_is_unchanged_and_ignores_ambient_path(self):
        hostile = self.prefix(self.local)
        with mock.patch.dict(os.environ, PATH=str(hostile / 'bin'), CPPFLAGS='-I/caller',
                             LDFLAGS='-L/caller', GIT_TERMINAL_PROMPT='1'):
            env, provenance = builder.build_environment([])
        self.assertEqual(env['PATH'], '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin')
        self.assertEqual(env['GIT_TERMINAL_PROMPT'], '0')
        self.assertEqual(env['CPPFLAGS'], '-I/caller')
        self.assertEqual(env['LDFLAGS'], '-L/caller')
        self.assertEqual(provenance['host_tools'], [])
        self.assertEqual(provenance['path'], env['PATH'])
        self.assertNotIn(str(hostile), provenance['make']['path'])
        selected = Path(provenance['make']['path'])
        self.assertEqual(provenance['make']['sha256'], hashlib.sha256(selected.read_bytes()).hexdigest())
        self.assertFalse(self.trace.exists())

    def check_success(self, prefixes, *, code=0):
        result, state, hostile = self.invoke(prefixes, code=code)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        trace = [json.loads(line) for line in self.trace.read_text().splitlines()]
        self.assertEqual([entry['stage'] for entry in trace], ['npu', 'openwrt'])
        expected_path = ':'.join(str(prefix.resolve() / 'bin') for prefix in prefixes) + ':' + builder.SYSTEM_PATH
        for entry in trace:
            self.assertEqual(entry['path'], expected_path)
            self.assertNotIn(str(hostile), entry['path'])
            self.assertEqual(Path(entry['executable']), prefixes[0].resolve() / 'bin/make')
            self.assertEqual(entry['git_prompt'], '0')
            self.assertEqual(entry['cppflags'], '-I/workspace/include-test')
            self.assertEqual(entry['ldflags'], '-L/workspace/lib-test')
            self.assertEqual(entry['library_path'], '/workspace/library-test')
        self.assertEqual(trace[0]['argv'], ['-C', str(ROOT / 'firmware/npu'),
                                          'OUT=' + str(self.destination / 'bin/npu')])
        self.assertEqual(trace[1]['argv'], ['-j2', 'tools/compile', 'V=s'])
        self.assertEqual(trace[1]['cwd'], str(self.destination))
        info = json.loads(state.read_text())
        self.assertEqual(info['exit_code'], code)
        self.assertIsNone(info['checked_npu_pair'])
        self.assertIn('finished', info)
        provenance = info['tool_provenance']
        self.assertEqual(provenance['path'], expected_path)
        self.assertEqual(provenance['host_tools'], [dict(prefix=str(prefix.resolve()),
                                                      bin=str(prefix.resolve() / 'bin')) for prefix in prefixes])
        make = prefixes[0].resolve() / 'bin/make'
        self.assertEqual(provenance['make'], dict(path=str(make), sha256=hashlib.sha256(make.read_bytes()).hexdigest()))
        started = json.loads(result.stdout.splitlines()[0])
        self.assertEqual(started['tool_provenance'], provenance)

    def test_local_prefix_reaches_both_stages_and_state(self):
        self.check_success([self.prefix(self.local)])

    def test_build_prefix_reaches_both_stages_and_state(self):
        self.check_success([self.prefix(self.build)])

    def test_repeatable_prefix_order_is_preserved(self):
        self.check_success([self.prefix(self.local), self.prefix(self.build)])

    def test_resolved_in_workspace_symlink_is_accepted(self):
        prefix = self.prefix(self.local)
        alias = self.local / 'alias'
        alias.symlink_to(prefix, target_is_directory=True)
        self.check_success([alias])

    def test_failed_openwrt_stage_retains_tool_provenance(self):
        self.check_success([self.prefix(self.local)], code=7)

    def test_invalid_prefixes_are_rejected(self):
        no_bin = self.local / 'no-bin'
        no_bin.mkdir()
        file_prefix = self.local / 'file'
        file_prefix.write_text('not a directory')
        file_bin = self.local / 'file-bin'
        file_bin.mkdir()
        (file_bin / 'bin').write_text('not a directory')
        escaped = self.local / 'escaped'
        escaped.symlink_to('/usr', target_is_directory=True)
        escaped_bin = self.local / 'escaped-bin'
        escaped_bin.mkdir()
        (escaped_bin / 'bin').symlink_to('/usr/bin', target_is_directory=True)
        dangling = self.local / 'dangling'
        dangling.symlink_to(self.local / 'absent', target_is_directory=True)
        loop = self.local / 'loop'
        loop.symlink_to(loop, target_is_directory=True)
        colon = self.prefix(self.local, 'colon:prefix')
        paths = [self.local / 'missing', no_bin, file_prefix, file_bin, Path('/usr'),
                 ROOT / '.local', ROOT / '.build', escaped, escaped_bin, dangling, loop, colon]
        for path in paths:
            with self.subTest(path=str(path)), self.assertRaises(ValueError):
                builder.build_environment([path])

    def test_invalid_cli_prefix_exits_before_any_build(self):
        for path in (self.local / 'missing', Path('/usr')):
            with self.subTest(path=str(path)):
                result, state, _ = self.invoke([path])
                self.assertEqual(result.returncode, 2)
                self.assertIn('error:', result.stderr)
                self.assertFalse(state.exists())
                self.assertFalse(self.trace.exists())
                self.assertFalse((self.destination / '.codex-build.lock').exists())

    def test_pair_required_for_world_and_package_install(self):
        for target in ('world', 'package/install', 'package/firmware/linux-firmware/compile', 'target/install', 'target/linux/install'):
            self.assertTrue(builder.pair_required(target), target)
        for target in ('tools/compile', 'toolchain/compile', 'target/linux/compile'):
            self.assertFalse(builder.pair_required(target), target)

    def test_package_depends_on_all_staged_pair_files_before_package_rules(self):
        patch = (ROOT / 'firmware/patches/openwrt.patch').read_text()
        name = 'package/firmware/linux-firmware/Makefile'
        delta = patch.split('diff --git a/' + name + ' b/' + name + '\n', 1)[1].split('\ndiff --git ', 1)[0]
        self.assertIn('+PKG_FILE_DEPENDS +=', delta)
        for name in ('en7581_MT7996_npu_rv32.bin', 'en7581_MT7996_npu_data.bin', 'w1700k-npu-pair.json'):
            self.assertIn('+\t$(TOPDIR)/bin/npu-checked/' + name, delta)
        self.assertLess(delta.index('+PKG_FILE_DEPENDS +='), delta.index(' include $(INCLUDE_DIR)/package.mk'))

    def staged_fixture(self, suffix):
        pair = self.destination / 'bin' / ('pair-' + suffix)
        pair.mkdir(parents=True)
        source = self.local / ('source-' + suffix)
        source.write_bytes(b'fixture source')
        (pair / 'CODE.bin').write_bytes(b'fixture code')
        (pair / 'DATA.bin').write_bytes(b'fixture data')
        manifest = dict(inputs={str(source.relative_to(ROOT)): hashlib.sha256(source.read_bytes()).hexdigest()},
                        code=dict(bytes=12), data=dict(bytes=12))
        (pair / 'manifest.json').write_text(json.dumps(manifest))
        return pair, source, manifest

    def test_atomic_staging_validates_and_preserves_previous_pair(self):
        import npu_image
        first, _, manifest = self.staged_fixture('first')
        with mock.patch.object(npu_image, 'validate') as validate:
            receipt = builder.stage_checked_pair(self.destination, first, 'first')
            validate.assert_called_once_with(b'fixture code', b'fixture data', manifest)
        link = self.destination / 'bin/npu-checked'
        self.assertEqual(link.resolve(), first / 'package')
        self.assertFalse(receipt['loader_provisioned'])
        self.assertFalse(receipt['physical_acceptance'])
        second, _, _ = self.staged_fixture('second')
        with mock.patch.object(npu_image, 'validate'):
            builder.stage_checked_pair(self.destination, second, 'second')
        self.assertEqual(link.resolve(), second / 'package')
        self.assertEqual((first / 'package/en7581_MT7996_npu_rv32.bin').read_bytes(), b'fixture code')
        self.assertEqual((link / 'w1700k-npu-pair.json').read_bytes(), (second / 'manifest.json').read_bytes())

    def test_failed_validation_or_stale_input_never_changes_package_link(self):
        import npu_image
        pair, source, _ = self.staged_fixture('invalid')
        link = self.destination / 'bin/npu-checked'
        with mock.patch.object(npu_image, 'validate', side_effect=ValueError('invalid pair')):
            with self.assertRaisesRegex(ValueError, 'invalid pair'):
                builder.stage_checked_pair(self.destination, pair, 'invalid')
        self.assertFalse(link.exists())
        source.write_bytes(b'changed source')
        with mock.patch.object(npu_image, 'validate'):
            with self.assertRaisesRegex(ValueError, 'input has changed'):
                builder.stage_checked_pair(self.destination, pair, 'stale')
        self.assertFalse(link.exists())

    def test_world_without_pinned_originals_never_starts_openwrt(self):
        result, state, _ = self.invoke([self.prefix(self.local)], target='world')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('hash-pinned original NPU pair is required', result.stderr)
        trace = [json.loads(line) for line in self.trace.read_text().splitlines()]
        self.assertEqual([entry['stage'] for entry in trace], ['npu'])
        self.assertFalse(state.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
