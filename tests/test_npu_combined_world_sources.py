"""Synthetic combined-producer contracts;not a Linux build or device test."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import npu_isolated_world as world
import npu_world_sources as sources
import test_npu_world_sources as old_sources_tests


class CombinedProducerTests(unittest.TestCase):
    def fixture(self, temporary):
        build, root, lock, provider, consumer, kernel, mt76 = old_sources_tests.PreparedSourcesTests().fixture(temporary)
        consumer['artifacts'] = {Path(name).as_posix(): value for name, value in consumer['artifacts'].items()}
        directory = root / '.local/npu-checked-irq-modules/fixture'
        directory.mkdir(parents=True)
        inputs = {'firmware/source-lock.json': sources.digest(root / 'firmware/source-lock.json')}
        for label, relative, original in (('kernel', 'provider.c', kernel / 'provider.c'),
                                          ('mt76', 'dma.c', mt76 / 'dma.c')):
            target = root / '.local/merge-nonoc-20260923' / (label + '-merged') / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original.read_bytes())
            inputs[target.relative_to(root).as_posix()] = sources.digest(target)
        patchname = lock['openwrt']['changed_files'][0]['path']
        inputs['firmware/overlay/openwrt/' + patchname] = sources.digest(root / 'firmware/overlay/openwrt' / patchname)
        artifacts = {}
        for name in ('airoha_npu.ko', 'mt76/mt76.ko', 'mt76/mt76-connac-lib.ko', 'mt76/mt7996/mt7996e.ko'):
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            header = bytearray(64)
            header[:6] = b'\x7fELF\x02\x01'
            header[16:20] = b'\x01\x00\xb7\x00'
            target.write_bytes(header + b'synthetic header fixture;not a linked module')
            artifacts[name] = dict(sha256=sources.digest(target), bytes=target.stat().st_size,
                                   vermagic='6.18.52 SMP mod_unload aarch64')
        inner = dict(passed=True, current_checked_header_compiled=True, module_loaded=False,
            image_built=False, hardware=False, provider=artifacts['airoha_npu.ko'],
            modules={name.removeprefix('mt76/'): value for name, value in artifacts.items() if name.startswith('mt76/')})
        record = dict(passed=True, returncode=0, originals_unchanged=True, inner=inner, inputs=inputs,
                      synthetic_unit_fixture_only=True)
        receipt = directory / 'result.json'
        receipt.write_text(json.dumps(record))
        return build, root, lock, provider, consumer, kernel, mt76, receipt, record

    def test_combined_source_and_prepared_contract_without_rewriting_producer(self):
        with tempfile.TemporaryDirectory() as temporary:
            build, root, lock, _, _, _, _, receipt, _ = self.fixture(temporary)
            original = receipt.read_bytes()
            result = sources.linked_module_sources(root, receipt)
            self.assertEqual(set(result['kernel']), {'provider.c'})
            self.assertEqual(set(result['mt76']), {'dma.c'})
            self.assertEqual(len(result['artifacts']), 4)
            self.assertEqual(sources.verify(build, root, lock, module_receipt=receipt),
                dict(kernel_patch_files=1, component_sources=1, mt76_source_files=1))
            self.assertEqual(receipt.read_bytes(), original)

    def test_failed_missing_or_wrong_scope_producer_is_rejected(self):
        mutations = ('passed', 'returncode', 'bool-returncode', 'originals', 'inner-passed', 'header',
                     'loaded', 'image', 'hardware', 'missing-module', 'extra-module', 'missing-kernel', 'missing-mt76')
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                _, root, _, _, _, _, _, receipt, record = self.fixture(temporary)
                if mutation == 'passed': record['passed'] = False
                elif mutation == 'returncode': record['returncode'] = 7
                elif mutation == 'bool-returncode': record['returncode'] = False
                elif mutation == 'originals': record['originals_unchanged'] = False
                elif mutation == 'inner-passed': record['inner']['passed'] = False
                elif mutation == 'header': record['inner']['current_checked_header_compiled'] = False
                elif mutation == 'loaded': record['inner']['module_loaded'] = True
                elif mutation == 'image': record['inner']['image_built'] = True
                elif mutation == 'hardware': record['inner']['hardware'] = True
                elif mutation == 'missing-module': del record['inner']['modules']['mt76.ko']
                elif mutation == 'extra-module': record['inner']['modules']['extra.ko'] = record['inner']['provider']
                else:
                    prefix = '.local/merge-nonoc-20260923/' + ('kernel' if mutation == 'missing-kernel' else 'mt76') + '-merged/'
                    record['inputs'] = {name: value for name, value in record['inputs'].items() if not name.startswith(prefix)}
                receipt.write_text(json.dumps(record))
                with self.assertRaises(AssertionError): sources.linked_module_sources(root, receipt)

    def test_changed_input_or_source_lock_or_unsafe_input_path_is_rejected(self):
        for mutation in ('lock', 'source', 'hash', 'parent', 'absolute', 'backslash'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                _, root, _, _, _, _, _, receipt, record = self.fixture(temporary)
                key = '.local/merge-nonoc-20260923/mt76-merged/dma.c'
                if mutation == 'lock': record['inputs']['firmware/source-lock.json'] = '0' * 64
                elif mutation == 'source': (root / key).write_text('drifted source')
                elif mutation == 'hash': record['inputs'][key] = 'not-sha256'
                else:
                    value = record['inputs'].pop(key)
                    key = {'parent': '../escape', 'absolute': '/absolute', 'backslash': 'directory\\alias'}[mutation]
                    record['inputs'][key] = value
                receipt.write_text(json.dumps(record))
                with self.assertRaises(AssertionError): sources.linked_module_sources(root, receipt)

    def test_changed_missing_wrong_architecture_size_or_vermagic_module_is_rejected(self):
        for mutation in ('bytes', 'missing', 'architecture', 'type', 'size', 'vermagic'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                _, root, _, _, _, _, _, receipt, record = self.fixture(temporary)
                artifact = receipt.parent / 'mt76/mt76.ko'
                if mutation == 'bytes': artifact.write_bytes(b'changed')
                elif mutation == 'missing': artifact.unlink()
                elif mutation in ('architecture', 'type'):
                    contents = bytearray(artifact.read_bytes())
                    contents[18 if mutation == 'architecture' else 16] = 0
                    artifact.write_bytes(contents)
                    record['inner']['modules']['mt76.ko']['sha256'] = sources.digest(artifact)
                elif mutation == 'size': record['inner']['modules']['mt76.ko']['bytes'] += 1
                else: record['inner']['modules']['mt76.ko']['vermagic'] = 'wrong magic'
                receipt.write_text(json.dumps(record))
                with self.assertRaises((AssertionError, FileNotFoundError)): sources.linked_module_sources(root, receipt)

    def test_stale_prepared_kernel_component_or_mt76_still_rejected(self):
        for name in ('provider.c', 'component.c', 'dma.c'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                build, root, lock, _, _, kernel, mt76, receipt, _ = self.fixture(temporary)
                ((mt76 if name == 'dma.c' else kernel) / name).write_text('stale prepared source')
                with self.assertRaises(AssertionError): sources.verify(build, root, lock, module_receipt=receipt)

    def test_unexported_kernel_identity_and_mixed_contracts_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            build, root, lock, provider, consumer, _, _, receipt, record = self.fixture(temporary)
            for pair in ((provider, None), (None, consumer), (provider, consumer)):
                with self.subTest(pair=pair), self.assertRaises(AssertionError):
                    sources.verify(build, root, lock, *pair, module_receipt=receipt)
            extra = root / '.local/merge-nonoc-20260923/kernel-merged/unexported.c'
            extra.write_text('not represented in the patch')
            record['inputs'][extra.relative_to(root).as_posix()] = sources.digest(extra)
            receipt.write_text(json.dumps(record))
            with self.assertRaisesRegex(AssertionError, 'combined-kernel-source-set-drift'):
                sources.verify(build, root, lock, module_receipt=receipt)

    def test_frozen_context_requires_declared_receipt_inputs_and_all_four_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, root, _, _, _, _, _, receipt, record = self.fixture(temporary)
            linked = sources.linked_module_sources(root, receipt)
            files = {**record['inputs'], **linked['artifacts'],
                     receipt.relative_to(root).as_posix(): sources.digest(receipt)}
            args = SimpleNamespace(module_receipt=receipt, provider_receipt=None, mt76_receipt=None)
            original = copy.deepcopy(files)
            with patch.object(world, 'ROOT', root):
                context = dict(source_lock_sha256=linked['source_lock_sha256'])
                world.producer_context(root, dict(files=files), args, context)
                self.assertEqual(context['module_receipt'], receipt.relative_to(root).as_posix())
                self.assertNotIn('provider_receipt', context)
                for name in original:
                    removed = {key: value for key, value in original.items() if key != name}
                    with self.subTest(omitted=name), self.assertRaises(AssertionError):
                        world.producer_context(root, dict(files=removed), args,
                            dict(source_lock_sha256=linked['source_lock_sha256']))

    def test_old_pair_context_and_source_checks_remain_supported(self):
        with tempfile.TemporaryDirectory() as temporary:
            build, root, lock, provider, consumer, _, _, receipt, _ = self.fixture(temporary)
            files = {}
            paths = []
            for name, value in (('provider', provider), ('consumer', consumer)):
                path = receipt.parent / (name + '.json')
                path.write_text(json.dumps(value))
                files[str(path.relative_to(root))] = sources.digest(path)
                paths.append(path)
            args = SimpleNamespace(module_receipt=None, provider_receipt=paths[0], mt76_receipt=paths[1])
            context = dict(source_lock_sha256=provider['source_lock_sha256'])
            with patch.object(world, 'ROOT', root):
                world.producer_context(root, dict(files=files), args, context)
            self.assertEqual(set(context), {'provider_receipt', 'mt76_receipt', 'source_lock_sha256'})
            self.assertEqual(sources.verify(build, root, lock, provider, consumer)['mt76_source_files'], 1)

    def test_postbuild_source_check_uses_receipt_bound_maps_not_old_output_observations(self):
        with tempfile.TemporaryDirectory() as temporary:
            build, root, lock, _, _, kernel, mt76, receipt, record = self.fixture(temporary)
            observed = build / 'bin/prior-image.itb'
            observed.parent.mkdir(parents=True)
            observed.write_bytes(b'synthetic prior output observation')
            record['inputs'][observed.relative_to(root).as_posix()] = sources.digest(observed)
            receipt.write_text(json.dumps(record))
            verified = sources.linked_module_sources(root, receipt)
            observed.write_bytes(b'synthetic newly built output;not the prior observation')
            self.assertEqual(sources.verify(build, root, lock, module_sources=verified)['mt76_source_files'], 1)
            with self.assertRaisesRegex(AssertionError, 'combined-input-drift'):
                sources.linked_module_sources(root, receipt)
            for target in (kernel / 'provider.c', kernel / 'component.c', mt76 / 'dma.c'):
                prior = target.read_bytes()
                target.write_bytes(b'stale actual prepared source')
                with self.assertRaises(AssertionError): sources.verify(build, root, lock, module_sources=verified)
                target.write_bytes(prior)

    def test_prevalidated_maps_remain_bound_to_the_original_receipt(self):
        for mutation in ('receipt', 'inputs', 'kernel', 'mt76', 'source-lock', 'failed-receipt'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                build, root, lock, _, _, _, _, receipt, record = self.fixture(temporary)
                verified = sources.linked_module_sources(root, receipt)
                if mutation == 'receipt': receipt.write_text(json.dumps(dict(record, extra='changed')))
                elif mutation == 'inputs': verified['inputs'] = dict(verified['inputs'], undeclared='0' * 64)
                elif mutation == 'source-lock': verified['source_lock_sha256'] = '0' * 64
                elif mutation == 'failed-receipt':
                    record['passed'] = False
                    receipt.write_text(json.dumps(record))
                    verified['receipt_sha256'] = sources.digest(receipt)
                else: verified[mutation] = {name: '0' * 64 for name in verified[mutation]}
                with self.assertRaises(AssertionError): sources.verify(build, root, lock, module_sources=verified)

    def test_cli_rejects_mixed_producers_before_namespace_work(self):
        for flag in ('--provider-receipt', '--mt76-receipt'):
            result = subprocess.run([sys.executable, world.__file__, 'run', '--name', 'fixture',
                '--snapshot', 'missing.json', '--module-receipt', 'combined.json', flag, 'old.json',
                '--probe-only'], text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertIn('cannot be mixed', result.stderr)


if __name__ == '__main__':
    unittest.main()
