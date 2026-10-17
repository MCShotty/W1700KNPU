"""Synthetic inventory/ELF-parser controls,not real module-link evidence."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_current_provider_module import inventory, module


class ProviderModuleContractTests(unittest.TestCase):
    def test_inventory_records_exact_content_and_file_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'source'
            path.write_bytes(b'value')
            path.chmod(0o640)
            self.assertEqual(inventory(root), {'source': dict(sha256=hashlib.sha256(b'value').hexdigest(), mode=0o640)})

    def test_content_or_mode_changes_cannot_reuse_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'source'
            path.write_bytes(b'value')
            path.chmod(0o640)
            before = inventory(root)
            path.write_bytes(b'other')
            self.assertNotEqual(inventory(root), before)
            path.write_bytes(b'value')
            path.chmod(0o600)
            self.assertNotEqual(inventory(root), before)

    def test_addition_or_removal_cannot_reuse_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = inventory(root)
            path = root / 'added'
            path.write_bytes(b'new')
            added = inventory(root)
            self.assertNotEqual(added, before)
            path.unlink()
            self.assertNotEqual(inventory(root), added)
            self.assertEqual(inventory(root), before)

    def test_internal_relative_link_preserves_literal_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'source').write_bytes(b'value')
            (root / 'alias').symlink_to('source')
            self.assertEqual(inventory(root)['alias'], dict(link='source'))

    def test_absolute_link_is_rejected_even_if_original_target_is_internal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'source').write_bytes(b'value')
            (root / 'alias').symlink_to(root / 'source')
            with self.assertRaises(AssertionError): inventory(root)

    def test_relative_link_cannot_escape_the_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / 'kernel'
            root.mkdir()
            (parent / 'outside').write_bytes(b'value')
            (root / 'alias').symlink_to('../outside')
            with self.assertRaises(AssertionError): inventory(root)

    def test_host_ELF_is_not_an_AArch64_module(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, obj = root / 'fixture.c', root / 'fixture.o'
            source.write_text('int fixture_value;\n')
            subprocess.run([shutil.which('clang'), '-c', str(source), '-o', str(obj)], check=True, capture_output=True)
            with self.assertRaises(AssertionError): module(obj)

    def test_synthetic_AArch64_metadata_parser_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, obj = root / 'fixture.S', root / 'fixture.o'
            source.write_text('.section .modinfo,"a"\n.asciz "vermagic=synthetic parser fixture"\n'
                '.text\n.global demo\n.type demo,%function\ndemo: b external_fixture\n.size demo,.-demo\n'
                '.section __ksymtab,"a"\n.global __ksymtab_demo\n__ksymtab_demo: .quad demo\n')
            subprocess.run([shutil.which('clang'), '--target=aarch64-none-elf', '-c', str(source), '-o', str(obj)],
                check=True, capture_output=True)
            result = module(obj)
            self.assertEqual(result['vermagic'], 'synthetic parser fixture')
            self.assertEqual(result['exports'], ['demo'])
            self.assertEqual(result['imports'], ['external_fixture'])
            self.assertEqual(result['sha256'], hashlib.sha256(obj.read_bytes()).hexdigest())


if __name__ == '__main__': unittest.main()
