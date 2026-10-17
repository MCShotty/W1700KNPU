"""Synthetic symbol-index and patch-copy controls,not real module-link proof."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_current_mt76_modules import checked_union, dependency_rows, object_symbols, source_copy, symvers


class CurrentMt76ModuleTests(unittest.TestCase):
    ROW = '0x00000000\tdemo\tdrivers/demo\tEXPORT_SYMBOL_GPL\t\n'

    def test_exact_columns_keep_empty_namespace_and_real_crc(self):
        self.assertEqual(symvers(self.ROW)['demo'], ['0x00000000', 'demo', 'drivers/demo', 'EXPORT_SYMBOL_GPL', ''])
        row = self.ROW.replace('0x00000000', '0xA0b102Ff').replace('GPL\t\n', 'GPL\tEXAMPLE_NS\n')
        self.assertEqual(symvers(row)['demo'][0::4], ['0xA0b102Ff', 'EXAMPLE_NS'])

    def test_bad_column_counts_and_empty_index_are_rejected(self):
        for text in ('', self.ROW.replace('GPL\t\n', 'GPL\n'), self.ROW.rstrip('\n') + '\textra\n'):
            with self.subTest(text=text), self.assertRaises(AssertionError): symvers(text)

    def test_invalid_crc_name_owner_kind_and_namespace_are_rejected(self):
        for before, after in [('0x00000000', '0'), ('\tdemo\t', '\tbad-name\t'),
            ('drivers/demo', '/absolute'), ('drivers/demo', 'drivers/../escape'),
            ('EXPORT_SYMBOL_GPL', 'EXPORT_UNKNOWN'), ('GPL\t\n', 'GPL\tbad\x00namespace\n')]:
            with self.subTest(after=after), self.assertRaises(AssertionError): symvers(self.ROW.replace(before, after))

    def test_literal_module_restricted_namespace_is_preserved(self):
        text = self.ROW.replace('GPL\t\n', 'GPL\tmodule:kvm\n')
        self.assertEqual(symvers(text)['demo'][4], 'module:kvm')

    def test_duplicate_index_names_are_rejected(self):
        with self.assertRaises(AssertionError): symvers(self.ROW + self.ROW)

    def test_union_preserves_rows_and_rejects_even_identical_overlap(self):
        one = symvers(self.ROW)
        two = symvers(self.ROW.replace('\tdemo\t', '\tother\t'))
        self.assertEqual(set(checked_union(one, two)), {'demo', 'other'})
        with self.assertRaises(AssertionError): checked_union(one, one)

    def test_compiled_import_selects_all_real_rows_of_only_its_owner(self):
        text = self.ROW + self.ROW.replace('\tdemo\t', '\tsecond\t')
        text += self.ROW.replace('\tdemo\t', '\tother\t').replace('drivers/demo', 'drivers/other')
        original = symvers(text)
        self.assertEqual(dependency_rows({'demo'}, original), {name: original[name] for name in ('demo', 'second')})
        self.assertEqual(dependency_rows(set(), original), {})

    def test_unknown_or_stale_provider_import_cannot_be_invented(self):
        with self.assertRaisesRegex(AssertionError, 'unknown-compiled-imports'):
            dependency_rows({'missing'}, symvers(self.ROW))
        for owner in ('vmlinux', 'drivers/airoha_npu'):
            with self.subTest(owner=owner), self.assertRaisesRegex(AssertionError, 'stale-provider-or-builtin-index'):
                dependency_rows({'demo'}, symvers(self.ROW.replace('drivers/demo', owner)))

    def test_object_parser_rejects_host_ELF(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, obj = Path(temporary) / 'test.c', Path(temporary) / 'test.o'
            source.write_text('int local;\n')
            subprocess.run([shutil.which('clang'), '-c', str(source), '-o', str(obj)], check=True, capture_output=True)
            with self.assertRaises(AssertionError): object_symbols(obj)

    def test_synthetic_AArch64_object_does_not_need_module_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, obj = Path(temporary) / 'test.S', Path(temporary) / 'test.o'
            for metadata in ('.section __ksymtab,"a"\n.global __ksymtab_demo\n__ksymtab_demo: .quad demo\n',
                '.section .export_symbol,"a"\n__export_symbol_demo: .asciz "GPL"\n.asciz ""\n.balign 8\n.quad demo\n'):
                with self.subTest(metadata=metadata):
                    source.write_text('.text\n.global demo\ndemo: b external_fixture\n' + metadata)
                    subprocess.run([shutil.which('clang'), '--target=aarch64-none-elf', '-c', str(source), '-o', str(obj)],
                        check=True, capture_output=True)
                    result = object_symbols(obj)
                    self.assertEqual(result['exports'], {'demo'})
                    self.assertEqual(result['imports'], {'external_fixture'})
                    self.assertIn('demo', result['defined'])

    def copied_fixture(self, directory, extra=None, reference=False):
        root = Path(directory)
        upstream, merged = root / 'upstream', root / 'merged'
        for tree, body in ((upstream, 'old\n'), (merged, 'new\n')):
            (tree / 'mt7996').mkdir(parents=True)
            (tree / 'mt7996/mmio.c').write_text(body)
            (tree / 'other.c').write_text('#include "w1700k/unused.h"\n' if reference else 'unchanged\n')
        if extra:
            path = merged / extra
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('unexported\n')
        patch = root / 'current.patch'
        patch.write_text('--- a/mt7996/mmio.c\n+++ b/mt7996/mmio.c\n@@ -1 +1 @@\n-old\n+new\n')
        return upstream, merged, patch, root / 'copied'

    def test_real_patch_copy_checks_whole_source_and_unmodified_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            upstream, merged, patch, output = self.copied_fixture(temporary)
            selected, identity, log = source_copy(upstream, merged, patch, output)
            self.assertEqual(selected, ['mt7996/mmio.c'])
            self.assertEqual(set(identity), {'mt7996/mmio.c', 'other.c'})
            self.assertIn('patching file mt7996/mmio.c', log)
            self.assertEqual((upstream / 'mt7996/mmio.c').read_text(), 'old\n')
            self.assertEqual((merged / 'mt7996/mmio.c').read_text(), 'new\n')

    def test_clean_copy_omits_git_and_preexisting_patch_backup_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            upstream, merged, patch, output = self.copied_fixture(temporary)
            (upstream / '.git').write_text('gitdir: /not-a-build-input\n')
            (upstream / 'other.c.orig').write_text('old backup\n')
            (upstream / 'other.c.rej').write_text('old rejected hunk\n')
            source_copy(upstream, merged, patch, output)
            for name in ('.git', 'other.c.orig', 'other.c.rej'): self.assertFalse((output / name).exists())

    def test_unexported_nonlegacy_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(AssertionError, 'unexported-source'):
                source_copy(*self.copied_fixture(temporary, extra='new.c'))

    def test_unpatched_existing_source_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            upstream, merged, patch, output = self.copied_fixture(temporary)
            (merged / 'other.c').write_text('changed outside patch\n')
            with self.assertRaisesRegex(AssertionError, 'mt76-patch-result-drift'):
                source_copy(upstream, merged, patch, output)

    def test_unused_legacy_copies_are_not_added_to_the_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            upstream, merged, patch, output = self.copied_fixture(temporary, extra='w1700k/unused.h')
            source_copy(upstream, merged, patch, output)
            self.assertFalse((output / 'w1700k').exists())

    def test_legacy_source_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(AssertionError): source_copy(*self.copied_fixture(temporary, reference=True))


if __name__ == '__main__': unittest.main()
