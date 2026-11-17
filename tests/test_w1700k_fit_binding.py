"""Default FIT selection and exact packaged-module provenance, without a build or board."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import npu_isolated_world as world
import verify_merged_image as image


class DefaultConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.types = {'ka': 'kernel', 'da': 'flat_dt', 'ra': 'filesystem',
                      'kb': 'kernel', 'db': 'flat_dt', 'rb': 'filesystem'}
        self.config = 'board-a'
        self.props = {'kernel': b'ka\0', 'fdt': b'da\0', 'loadables': b'ra\0'}

    def select(self):
        def prop(path, node, key, kind):
            self.assertEqual(kind, 'bx')
            data = (self.config.encode() + b'\0' if (node, key) == ('/configurations', 'default')
                    else self.props[key])
            return ' '.join(f'{x:x}' for x in data)

        def run(args):
            if args[1] == '-l' and args[-1] == '/configurations':
                return b'board-a\nboard-b\n'
            self.assertEqual((args[1], args[-1]), ('-p', '/configurations/board-a'))
            return ('\n'.join(['description', *self.props]) + '\n').encode()

        with patch.object(image, 'prop', side_effect=prop), patch.object(image, 'run', side_effect=run):
            return image.select_fit_configuration(Path('candidate.itb'), self.types)

    def test_named_default_not_last_component_of_type(self):
        self.assertEqual(self.select(), dict(name='board-a', kernel='ka', fdt='da', rootfs='ra'))

    def test_reordered_subimages_do_not_change_selection(self):
        expected = self.select()
        self.types = dict(reversed(self.types.items()))
        self.assertEqual(self.select(), expected)

    def test_missing_default_or_member_does_not_fall_back(self):
        self.config = 'other'
        with self.assertRaises(ValueError): self.select()
        self.config = 'board-a'
        del self.types['ra']
        with self.assertRaises(ValueError): self.select()

    def test_wrong_role_and_missing_property_are_refused(self):
        for key, value in [('kernel', b'da\0'), ('fdt', b'ra\0'), ('loadables', b'kb\0')]:
            with self.subTest(key=key), patch.dict(self.props, {key:value}), self.assertRaises(ValueError):
                self.select()
        del self.props['loadables']
        with self.assertRaises(ValueError): self.select()

    def test_ambiguous_or_unsupported_boot_layout_is_refused(self):
        for key, value in [('kernel', b'ka\0kb\0'), ('fdt', b'da\0db\0'),
                           ('loadables', b'ra\0rb\0'), ('ramdisk', b'ra\0')]:
            with self.subTest(key=key), patch.dict(self.props, {key:value}), self.assertRaises(ValueError):
                self.select()

    def test_reference_is_one_terminated_node_name(self):
        for value in (b'', b'ra', b'ra\0\0', b'ra rb\0', b'/images/ra\0', b'\xff\0'):
            with self.subTest(value=value), patch.dict(self.props, {'loadables':value}), self.assertRaises(ValueError):
                self.select()


@unittest.skipUnless(all(shutil.which(t) for t in ('fdtput', 'fdtget', 'dumpimage')), 'FIT host tools unavailable')
class FitExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fit = self.root / 'fixture.itb'
        # Packed empty v17 FDT from libfdt; fdtput builds two configurations
        # with inert string payloads. No compiler, real firmware or board.
        self.fit.write_bytes(bytes.fromhex(
            'd00dfeed00000048000000380000004800000028000000110000001000000000'
            '0000000000000010000000000000000000000000000000000000000100000000'
            '0000000200000009'))
        self.put('/', 'description', 'Fixture')
        self.put('/', 'timestamp', '0', kind='x')
        self.values = {}
        for board in ('a', 'b'):
            for key, role in [('kernel', 'kernel'), ('fdt', 'flat_dt'), ('loadables', 'filesystem')]:
                name = key + '-' + board
                node = '/images/' + name
                data = name.encode()
                self.values[name] = data
                for k, v in [('description', name), ('type', role), ('arch', 'arm64'), ('compression', 'none')]:
                    self.put(node, k, v)
                self.put(node, 'data', *data.hex(' ').split(), kind='bx')
                self.put(node + '/hash-1', 'algo', 'sha256')
                self.put(node + '/hash-1', 'value', *hashlib.sha256(data).digest().hex(' ').split(), kind='bx')
                self.put('/configurations/board-' + board, key, name)
        self.put('/configurations', 'default', 'board-a')

    def put(self, node, prop, *values, kind='s'):
        subprocess.run(['fdtput', '-p', '-t', kind, self.fit, node, prop, *values], check=True, capture_output=True)

    def test_switching_only_the_default_selects_different_verified_payloads(self):
        for board in ('a', 'b'):
            self.put('/configurations', 'default', 'board-' + board)
            out = self.root / board
            out.mkdir()
            config, rows, paths = image.extract_fit_components(self.fit, out)
            self.assertEqual(config['name'], 'board-' + board)
            self.assertEqual(len(rows), 6)
            for key, prefix in [('kernel', 'kernel'), ('fdt', 'fdt'), ('rootfs', 'loadables')]:
                self.assertEqual(paths[key].read_bytes(), self.values[prefix + '-' + board])

    def test_hash_checks_still_cover_unselected_nodes(self):
        self.put('/images/kernel-b', 'data', '01', kind='bx')
        out = self.root / 'bad'
        out.mkdir()
        with self.assertRaises(AssertionError):
            image.extract_fit_components(self.fit, out)


class PackagedModuleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.build = self.root / 'build'
        self.tool = self.build / 'staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin/aarch64-openwrt-linux-musl-objcopy'
        self.tool.parent.mkdir(parents=True)
        self.tool.write_bytes(b'tool identity')
        self.config = self.root / 'firmware/build.config'
        self.config.parent.mkdir()
        self.config.write_text('CONFIG_KERNEL_KALLSYMS=y\nCONFIG_GCC_VERSION="14.4.0"\n'
                               'CONFIG_TARGET_ARCH_PACKAGES="aarch64_cortex-a53"\nCONFIG_TARGET_SUFFIX="musl"\n'
                               '# CONFIG_KERNEL_PROFILING is not set\n# CONFIG_NO_STRIP is not set\n')
        (self.build / '.config').write_bytes(self.config.read_bytes())
        self.files = {}
        self.packaged = {}
        for name in ('airoha_npu.ko', 'mt76.ko', 'mt76-connac-lib.ko', 'mt7996e.ko'):
            ref = self.root / name
            ref.write_bytes(b'debug:' + name.encode())
            self.files[name] = image.sha(ref)
            self.packaged[name] = hashlib.sha256(name.encode()).hexdigest()
        self.linked = dict(artifacts=self.files, receipt='producer.json', receipt_sha256='7'*64,
                           source_lock_sha256='9'*64)

    def compare(self):
        def objcopy(args):
            self.assertEqual(Path(args[0]), self.tool)
            self.assertIn('--strip-unneeded', args)
            self.assertIn('__this_module', args)
            src, dest = map(Path, args[-2:])
            self.assertNotEqual(src, dest)
            self.assertFalse(dest.exists())
            dest.write_bytes(src.read_bytes().removeprefix(b'debug:'))
            return b''
        with patch.object(image, 'run', side_effect=objcopy):
            return image.compare_packaged_modules(self.root, self.build, self.linked, self.packaged, self.root)

    def test_exact_four_transformed_bytes_and_preserved_inputs(self):
        row = self.compare()
        self.assertTrue(row['matches'])
        self.assertEqual(set(row['modules']), set(self.files))
        for name, details in row['modules'].items():
            self.assertEqual(details['linked_sha256'], image.sha(self.root / name))
            self.assertEqual(details['expected_packaged_sha256'], self.packaged[name])
            self.assertEqual(details['actual_packaged_sha256'], self.packaged[name])
        self.assertEqual(row['producer_sha256'], self.linked['receipt_sha256'])

    def test_matching_three_is_not_a_current_image(self):
        self.packaged['mt7996e.ko'] = 'a'*64
        result = self.compare()
        self.assertFalse(result['matches'])
        self.assertEqual(result['mismatches'], ['mt7996e.ko'])

    def test_missing_artifact_or_mutated_source_is_rejected(self):
        with patch.dict(self.packaged, clear=True), self.assertRaises(ValueError):
            self.compare()
        (self.root / 'mt76.ko').write_bytes(b'changed')
        with self.assertRaises(ValueError): self.compare()

    def test_unsupported_locked_packaging_is_rejected(self):
        original = self.config.read_text()
        for line in ('CONFIG_NO_STRIP=y', 'CONFIG_KERNEL_PROFILING=y'):
            with self.subTest(line=line):
                self.config.write_text(original + line + '\n')
                (self.build / '.config').write_bytes(self.config.read_bytes())
                with self.assertRaises(ValueError): self.compare()

    def test_mismatched_build_config_is_not_used_as_packaging_authority(self):
        with (self.build / '.config').open('a') as stream:
            stream.write('CONFIG_OTHER=y\n')
        with self.assertRaises(ValueError): self.compare()

    def test_uses_locked_toolchain_not_other_installed_version(self):
        other = Path(str(self.tool).replace('gcc-14.4.0_', 'gcc-13.1.0_'))
        other.parent.mkdir(parents=True)
        other.write_bytes(b'other')
        self.assertTrue(self.compare()['matches'])
        self.tool.unlink()
        with self.assertRaises(ValueError): self.compare()

    def test_packaged_file_is_not_itself_normalized(self):
        self.packaged['mt76.ko'] = self.files['mt76.ko']
        self.assertEqual(self.compare()['mismatches'], ['mt76.ko'])

    def test_tool_must_belong_to_the_selected_build(self):
        staging = self.build / 'staging_dir'
        saved = self.root / 'other-build-staging'
        staging.rename(saved)
        try:
            staging.symlink_to(saved, target_is_directory=True)
        except OSError as error:
            if getattr(error, 'winerror', None) == 1314:
                self.skipTest('Windows account lacks symlink privilege')
            raise
        with patch.object(image, 'run') as unneeded, self.assertRaises(ValueError):
            image.compare_packaged_modules(self.root, self.build, self.linked, self.packaged, self.root)
        unneeded.assert_not_called()

    def test_wrong_producer_pin_is_rejected_before_consumption(self):
        receipt = self.root / 'producer.json'
        receipt.write_text('{}')
        with patch('npu_world_sources.linked_module_sources') as verified, self.assertRaises(ValueError):
            image.bound_producer(self.root, receipt, '0'*64)
        verified.assert_not_called()

    def test_world_rejects_missing_or_wrong_receipt_even_after_zero_exit(self):
        name = 'test-world'
        work = self.root / (name + '-image')
        work.mkdir()
        path = work / 'result.json'
        image_row = dict(passed=True, source_lock_sha256=self.linked['source_lock_sha256'],
                         pinned_module_bytes_verified=True,
                         selected_modules={n: {'sha256': h} for n, h in self.packaged.items()})
        with patch.object(world, 'WORK', self.root), patch.object(world.subprocess, 'run',
                return_value=subprocess.CompletedProcess([], 0)) as run:
            for binding in (None, dict(matches=True, producer_sha256='b'*64), self.compare() | dict(matches=False)):
                path.write_text(json.dumps(image_row | dict(packaged_module_provenance=binding)))
                with self.assertRaises(ValueError):
                    world.verify_world_image(name, self.linked['source_lock_sha256'], self.linked)
            path.write_text(json.dumps(image_row | dict(packaged_module_provenance=self.compare())))
            receipt, _ = world.verify_world_image(name, self.linked['source_lock_sha256'], self.linked)
            self.assertTrue(receipt['passed'])
            args = run.call_args.args[0]
            self.assertIn(self.linked['receipt'], args)
            self.assertIn(self.linked['receipt_sha256'], args)

    def test_world_does_not_trust_a_match_flag_without_the_four_bytestring_digests(self):
        with patch.object(world, 'WORK', self.root), patch.object(world.subprocess, 'run',
                return_value=subprocess.CompletedProcess([], 0)):
            dst = self.root / 'real-image'
            dst.mkdir()
            for defect in ('missing module', 'other linked digest', 'other packaged digest'):
                binding = self.compare()
                if defect == 'missing module': binding['modules'].pop('mt76.ko')
                elif defect == 'other linked digest': binding['modules']['mt7996e.ko']['linked_sha256'] = 'b'*64
                else: binding['modules']['mt7996e.ko']['actual_packaged_sha256'] = 'b'*64
                (dst / 'result.json').write_text(json.dumps(dict(passed=True, pinned_module_bytes_verified=True,
                    source_lock_sha256=self.linked['source_lock_sha256'], packaged_module_provenance=binding,
                    selected_modules={n: {'sha256': h} for n, h in self.packaged.items()})))
                with self.subTest(defect=defect), self.assertRaises(ValueError):
                    world.verify_world_image('real', self.linked['source_lock_sha256'], self.linked)

    def test_image_cli_refuses_optimized_verification_before_creating_output(self):
        result = subprocess.run([sys.executable, '-B', '-O', image.__file__, '--module-receipt', 'not-read',
                                 '--expected-producer-sha256', '0'*64], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Python assertions enabled', result.stderr)

    def test_world_never_reads_an_old_result_after_verifier_failure(self):
        with patch.object(world.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)):
            with self.assertRaisesRegex(RuntimeError, 'verifier exited 1'):
                world.verify_world_image('not-read', self.linked['source_lock_sha256'], self.linked)
