"""Synthetic source-map fixtures only;not compilation or firmware execution."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'tools'))
import npu_world_sources as sources


class PreparedSourcesTests(unittest.TestCase):
    def fixture(self, directory, revision='12345678' + 'a' * 32):
        root = Path(directory)
        build = root / '.build/fixture'
        prepared = build / 'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581'
        kernel = prepared / 'linux-6.18.52'
        mt76 = prepared / ('mt76-fixture~' + revision[:8])
        kernel.mkdir(parents=True)
        mt76.mkdir()
        (kernel / 'provider.c').write_text('current kernel source\n')
        (kernel / 'component.c').write_text('current component\n')
        (mt76 / 'dma.c').write_text('current DMA source\n')
        patch_name = 'target/linux/airoha/patches-6.18/999-w1700k-integrated-npu.patch'
        patch = root / 'firmware/overlay/openwrt' / patch_name
        patch.parent.mkdir(parents=True)
        patch.write_text('--- a/provider.c\n+++ b/provider.c\n@@ -1 +1 @@\n-old\n+current kernel source\n')
        lock = dict(kernel='6.18.52',mt76=revision,
            openwrt={'changed_files':[dict(path=patch_name,sha256=sources.digest(patch))]},
            component_sources=[dict(tree='openwrt',destination='target/linux/airoha/files-6.18/component.c',
                                    sha256=sources.digest(kernel / 'component.c'))])
        (root / 'firmware/source-lock.json').write_text(json.dumps(lock))
        source_lock = sources.digest(root / 'firmware/source-lock.json')
        manifest = root / '.local/current/source-before.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({'dma.c':dict(sha256=sources.digest(mt76 / 'dma.c'),mode=0o644)}))
        provider = dict(passed=True,source_lock_sha256=source_lock,
            inputs={'.local/merge-nonoc-20260923/kernel-merged/provider.c':sources.digest(kernel / 'provider.c')})
        consumer = dict(passed=True,source_lock_sha256=source_lock,
            artifacts={str(manifest.relative_to(root)):sources.digest(manifest)})
        return build,root,lock,provider,consumer,kernel,mt76

    def test_matching_synthetic_prepared_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            build,root,lock,provider,consumer,_,_ = self.fixture(temporary)
            self.assertEqual(sources.verify(build,root,lock,provider,consumer),
                dict(kernel_patch_files=1,component_sources=1,mt76_source_files=1))

    def test_stale_actual_kernel_component_or_mt76_is_rejected(self):
        for name in ('provider.c','component.c','dma.c'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                build,root,lock,provider,consumer,kernel,mt76 = self.fixture(temporary)
                ((mt76 if name == 'dma.c' else kernel) / name).write_text('stale body\n')
                with self.assertRaises(AssertionError): sources.verify(build,root,lock,provider,consumer)

    def test_foreign_source_lock_or_manifest_cannot_be_reused(self):
        for target in ('lock','manifest'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                build,root,lock,provider,consumer,_,_ = self.fixture(temporary)
                if target == 'lock': consumer['source_lock_sha256'] = '0' * 64
                else: (root / next(iter(consumer['artifacts']))).write_text('{}')
                with self.assertRaises(AssertionError): sources.verify(build,root,lock,provider,consumer)

    def test_source_path_escape_or_file_alias_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'source').write_text('body')
            (root / 'alias').symlink_to('source')
            for name in ('../outside','/absolute','alias'):
                with self.subTest(name=name), self.assertRaises(AssertionError): sources.relative_file(root,name)

    def test_exact_pinned_firmware_aliases_keep_full_byte_checks(self):
        revision = next(iter(sources.PINNED_MT76_FIRMWARE_LINKS))
        with tempfile.TemporaryDirectory() as temporary:
            build,root,lock,provider,consumer,kernel,mt76 = self.fixture(temporary,revision)
            (mt76 / 'firmware').mkdir()
            for name,literal in sources.PINNED_MT76_FIRMWARE_LINKS[revision].items():
                (mt76 / 'firmware' / literal).write_bytes(b'synthetic firmware fixture;not real firmware')
                (mt76 / name).symlink_to(literal)
            manifest = root / next(iter(consumer['artifacts']))
            manifest.write_text(json.dumps({str(path.relative_to(mt76)):dict(sha256=sources.digest(path),mode=0o644)
                for path in mt76.rglob('*') if path.is_file()}))
            consumer['artifacts'][str(manifest.relative_to(root))] = sources.digest(manifest)
            self.assertEqual(sources.verify(build,root,lock,provider,consumer),
                dict(kernel_patch_files=1,component_sources=1,mt76_source_files=5))
            literal = next(iter(sources.PINNED_MT76_FIRMWARE_LINKS[revision].values()))
            (mt76 / 'firmware' / literal).write_bytes(b'drifted bytes')
            with self.assertRaises(AssertionError): sources.verify(build,root,lock,provider,consumer)

    def test_unlisted_wrong_revision_wrong_target_or_chained_alias_is_rejected(self):
        revision = next(iter(sources.PINNED_MT76_FIRMWARE_LINKS))
        name,literal = next(iter(sources.PINNED_MT76_FIRMWARE_LINKS[revision].items()))
        for mutation in ('revision','literal','chain','external','c-source','parent'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                (base / 'firmware').mkdir()
                (base / 'firmware' / literal).write_bytes(b'equal fixture bytes')
                (base / 'firmware/other').write_bytes(b'equal fixture bytes')
                (base / name).symlink_to(literal)
                actual_revision,actual_name = revision,name
                if mutation == 'revision': actual_revision = '0' * 40
                elif mutation == 'literal':
                    (base / name).unlink()
                    (base / name).symlink_to('other')
                elif mutation == 'chain':
                    (base / 'firmware' / literal).unlink()
                    (base / 'firmware' / literal).symlink_to('other')
                elif mutation == 'external':
                    (base / 'firmware' / literal).unlink()
                    (base / 'firmware' / literal).symlink_to('/not-an-allowed-source-target')
                elif mutation == 'c-source':
                    (base / 'dma.c').symlink_to('firmware/other')
                    actual_name = 'dma.c'
                else:
                    (base / 'firmware').rename(base / 'real')
                    (base / 'firmware').symlink_to('real')
                with self.assertRaises(AssertionError): sources.mt76_source_file(base,actual_name,actual_revision)

    def test_flattened_source_copy_does_not_need_an_alias_exception(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            (base / 'firmware').mkdir()
            path = base / 'firmware/mt7662.bin'
            path.write_bytes(b'synthetic flattened fixture')
            self.assertEqual(sources.mt76_source_file(base,'firmware/mt7662.bin','0' * 40),path)


if __name__ == '__main__': unittest.main()
