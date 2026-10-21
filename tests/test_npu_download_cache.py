"""Synthetic cache admission/staging controls;not a world or native verdict."""
import errno
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'tools'))
import npu_isolated_world as world


class DownloadCacheTests(unittest.TestCase):
    def test_buffered_copy_avoids_fast_copy_and_preserves_exact_large_payload(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, target = (Path(temporary) / name for name in ('source', 'copy'))
            source.write_bytes(bytes(range(256)) * 8192 + b'tail')
            source.chmod(0o444)
            with patch.object(world.shutil, 'copyfile', side_effect=AssertionError('fast copy forbidden')), \
                    patch.object(world.shutil, 'copy2', side_effect=AssertionError('fast copy forbidden')), \
                    patch.object(world.os, 'copy_file_range', side_effect=AssertionError('fast copy forbidden')), \
                    patch.object(world.os, 'sendfile', side_effect=AssertionError('fast copy forbidden')):
                self.assertEqual(world.copy_download_file(source, target), str(target))
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o444)

    def test_buffered_copy_does_not_replace_an_existing_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, target = (Path(temporary) / name for name in ('source', 'copy'))
            source.write_bytes(b'source bytes')
            target.write_bytes(b'protected existing bytes')
            with self.assertRaises(FileExistsError): world.copy_download_file(source, target)
            self.assertEqual(target.read_bytes(), b'protected existing bytes')
            self.assertEqual(source.read_bytes(), b'source bytes')

    def test_buffered_copy_rejects_same_length_zero_filled_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, target = (Path(temporary) / name for name in ('source', 'copy'))
            source.write_bytes(b'nonzero archive fixture')
            def zero_copy(reader, writer, length):
                writer.write(b'\0' * len(reader.read()))
            with patch.object(world.shutil, 'copyfileobj', side_effect=zero_copy):
                with self.assertRaisesRegex(AssertionError, 'buffered-download-copy-drift'):
                    world.copy_download_file(source, target)
            self.assertEqual(target.stat().st_size, source.stat().st_size)
            self.assertEqual(source.read_bytes(), b'nonzero archive fixture')

    def test_buffered_copy_propagates_a_writeback_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, target = (Path(temporary) / name for name in ('source', 'copy'))
            source.write_bytes(b'archive fixture')
            with patch.object(world.os, 'fsync', side_effect=OSError(errno.EIO, 'synthetic writeback error')):
                with self.assertRaises(OSError) as failure: world.copy_download_file(source, target)
            self.assertEqual(failure.exception.errno, errno.EIO)

    def test_missing_cache_stops_run_before_output_or_original_tree_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frozen = root / 'frozen'
            (frozen / 'firmware').mkdir(parents=True)
            (frozen / 'firmware/source-lock.json').write_text('{"kernel":"6.18.52"}')
            name = str((world.LINKER_PREFIX / 'bin/ld.lld').relative_to(world.ROOT))
            linker = frozen / name
            linker.parent.mkdir(parents=True)
            linker.write_bytes(b'synthetic linker;not executable code')
            linker.chmod(0o555)
            record = dict(files={name:world.digest(linker)})
            args = SimpleNamespace(name='fixture',snapshot=root / 'synthetic.json',probe_only=False,
                provider_receipt=Path('synthetic-provider.json'),mt76_receipt=Path('synthetic-mt76.json'))
            with patch.object(world,'STORE',root / 'output'),patch.object(world.os,'getuid',return_value=1000), \
                    patch.object(world,'snapshot',return_value=(frozen,record)),patch.object(world,'tree_state') as inventory:
                with self.assertRaisesRegex(AssertionError,'missing-frozen-download-cache'): world.run(args)
                inventory.assert_not_called()
                self.assertFalse((root / 'output').exists())

    def fixture(self, root):
        frozen = root / 'frozen'
        cache = frozen / world.CACHE.relative_to(world.ROOT)
        cache.mkdir(parents=True)
        archive = cache / 'linux-6.18.52.tar.xz'
        archive.write_bytes(b'synthetic kernel archive;not a real tar file')
        (cache / 'nested').mkdir()
        (cache / 'nested/metadata').write_bytes(b'synthetic metadata')
        recipe = frozen / world.BUILD.relative_to(world.ROOT) / 'target/linux/generic/kernel-6.18'
        recipe.parent.mkdir(parents=True)
        recipe.write_text('LINUX_VERSION-6.18 = .52\nLINUX_KERNEL_HASH-6.18.52 = ' + world.digest(archive) + '\n')
        (frozen / 'firmware').mkdir()
        (frozen / 'firmware/source-lock.json').write_text(json.dumps(dict(kernel='6.18.52')))
        files = {str(path.relative_to(frozen)):world.digest(path) for path in frozen.rglob('*') if path.is_file()}
        return frozen,cache,recipe,dict(files=files)

    def test_exact_declared_cache_and_kernel_recipe_hash_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            frozen,cache,recipe,record = self.fixture(Path(temporary))
            result = world.download_cache_input(frozen,record)
            self.assertEqual(result['file_count'],2)
            self.assertEqual(result['kernel_archive_sha256'],world.digest(cache / 'linux-6.18.52.tar.xz'))
            self.assertEqual(result['kernel_recipe_sha256'],world.digest(recipe))

    def test_missing_changed_unlisted_aliased_or_ambiguous_input_is_rejected(self):
        for mutation in ('missing','bytes','unlisted','alias','recipe-unlisted','wrong-hash','duplicate-hash'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temporary:
                frozen,cache,recipe,record = self.fixture(Path(temporary))
                archive = cache / 'linux-6.18.52.tar.xz'
                if mutation == 'missing': archive.unlink()
                elif mutation == 'bytes': archive.write_bytes(b'changed')
                elif mutation == 'unlisted': (cache / 'unexpected').write_bytes(b'extra')
                elif mutation == 'alias':
                    (cache / 'nested/metadata').unlink()
                    (cache / 'nested/metadata').symlink_to('/bin/true')
                elif mutation == 'recipe-unlisted': del record['files'][str(recipe.relative_to(frozen))]
                else:
                    text = recipe.read_text()
                    recipe.write_text(text.replace(world.digest(archive),'0' * 64) if mutation == 'wrong-hash' else text + text)
                    record['files'][str(recipe.relative_to(frozen))] = world.digest(recipe)
                with self.assertRaises(AssertionError): world.download_cache_input(frozen,record)

    def test_special_cache_nodes_are_rejected_without_reading_them(self):
        with tempfile.TemporaryDirectory() as temporary:
            frozen,cache,recipe,record = self.fixture(Path(temporary))
            os.mkfifo(cache / 'pipe')
            with self.assertRaises(AssertionError): world.cache_manifest(cache)

    def test_private_copy_is_byte_exact_writable_and_does_not_change_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frozen,cache,recipe,record = self.fixture(root)
            expected = world.download_cache_input(frozen,record)
            for path in cache.rglob('*'):
                if path.is_file(): path.chmod(0o444)
            before = world.tree_state(cache)
            build = root / 'private-build'
            build.mkdir()
            (build / 'dl').symlink_to(cache)
            result = world.stage_download_cache(build,cache,expected)
            self.assertEqual(result['files_copied'],2)
            self.assertFalse((build / 'dl').is_symlink())
            self.assertEqual(world.cache_manifest(build / 'dl'),world.cache_manifest(cache))
            for path in (build / 'dl').rglob('*'):
                self.assertTrue(stat.S_IMODE(path.stat().st_mode) & stat.S_IWUSR)
            (build / 'dl/linux-6.18.52.tar.xz').write_bytes(b'private replacement')
            self.assertEqual(world.tree_state(cache),before)

    def test_unexpected_destination_is_not_removed_or_modified(self):
        for kind in ('file','directory','wrong-link'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                frozen,cache,recipe,record = self.fixture(root)
                expected = world.download_cache_input(frozen,record)
                build = root / 'private-build'
                build.mkdir()
                if kind == 'file': (build / 'dl').write_bytes(b'protected fixture')
                elif kind == 'directory': (build / 'dl').mkdir()
                else: (build / 'dl').symlink_to(root / 'unexpected-target')
                before = world.tree_state(build)
                with self.assertRaises(AssertionError): world.stage_download_cache(build,cache,expected)
                self.assertEqual(world.tree_state(build),before)

    def test_cache_drift_stops_staging_before_unlinking_the_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frozen,cache,recipe,record = self.fixture(root)
            expected = world.download_cache_input(frozen,record)
            (cache / 'linux-6.18.52.tar.xz').write_bytes(b'changed')
            build = root / 'private-build'
            build.mkdir()
            (build / 'dl').symlink_to(cache)
            before = world.tree_state(build)
            with self.assertRaises(AssertionError): world.stage_download_cache(build,cache,expected)
            self.assertEqual(world.tree_state(build),before)


if __name__ == '__main__': unittest.main()
