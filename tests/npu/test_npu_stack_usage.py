"""Compiler frame-record parsing, not native stack execution."""
import unittest
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import npu_stack_usage as audit
from npu_stack_usage import parse_usage


class StackUsageTests(unittest.TestCase):
    def test_static_leaf_and_large_frame(self):
        rows = parse_usage('owner.c:11:leaf\t0\tstatic\nowner.c:132:context\t4688\tstatic\n')
        self.assertEqual([row['bytes'] for row in rows], [0, 4688])
        self.assertEqual(rows[1]['function'], 'context')

    def test_source_colon_is_not_a_line_separator(self):
        self.assertEqual(parse_usage('C:/source/owner.c:7:guard\t16\tstatic')[0]['source'],
                         'C:/source/owner.c')

    def test_dynamic_and_bounded_dynamic_are_not_static_proof(self):
        for qualifier in ('dynamic', 'dynamic,bounded', 'unknown'):
            with self.subTest(qualifier=qualifier), self.assertRaises(AssertionError):
                parse_usage(f'owner.c:1:guard\t16\t{qualifier}')

    def test_negative_or_noninteger_sizes_are_rejected(self):
        for size in ('-16', '1.5', 'unknown'):
            with self.subTest(size=size), self.assertRaises(AssertionError):
                parse_usage(f'owner.c:1:guard\t{size}\tstatic')

    def test_duplicate_function_measurement_is_rejected(self):
        with self.assertRaisesRegex(AssertionError, 'duplicate-stack-frame'):
            parse_usage('owner.c:1:guard\t16\tstatic\nowner.c:2:guard\t32\tstatic')

    def test_bad_field_and_location_shapes_are_rejected(self):
        for line in ('owner.c:guard\t16\tstatic', 'owner.c:0:guard\t16\tstatic',
                     'owner.c:1:\t16\tstatic', 'owner.c:1:guard\t16',
                     'owner.c:1:guard\t16\tstatic\textra'):
            with self.subTest(line=line), self.assertRaises(AssertionError):
                parse_usage(line)

    def test_unaligned_frame_is_rejected(self):
        with self.assertRaisesRegex(AssertionError, 'rv32-stack-alignment'):
            parse_usage('owner.c:1:guard\t12\tstatic')

    def test_empty_measurements_are_not_coverage(self):
        with self.assertRaisesRegex(AssertionError, 'empty-stack-usage'):
            parse_usage('')


class InventoryTests(unittest.TestCase):
    """Synthetic files and explicit ELF stubs exercise rejection mechanics only."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='stack-inventory-unit-', dir=audit.ROOT / '.local')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.instrumented, self.reference = self.root / 'instrumented', self.root / 'reference'
        self.instrumented.mkdir()
        self.reference.mkdir()
        (self.root / 'firmware/npu').mkdir(parents=True)
        self.driver = self.root / 'synthetic-driver.py'
        self.driver.write_text('synthetic inventory fixture, not executable evidence')
        for index in range(22):
            name = f'unit-{index}.o'
            data = f'synthetic non-ELF object {index}'.encode()
            (self.instrumented / name).write_bytes(data)
            (self.reference / name).write_bytes(data)
            (self.instrumented / name).with_suffix('.su').write_text('fixture.c:1:guard\t16\tstatic\n')
        for directory in (self.instrumented, self.reference):
            (directory / 'libw1700k-npu.a').write_bytes(b'synthetic archive fixture')

    def run_inventory(self, archive=None):
        class Symbol:
            name = 'guard'

            def __getitem__(self, key):
                return {'st_info': {'type': 'STT_FUNC'}, 'st_size': 16}[key]

        class Binary(dict):
            elfclass = 32

            def get_section_by_name(self, name):
                return SimpleNamespace(iter_symbols=lambda: iter([Symbol()]))

        with patch.object(audit, 'ROOT', self.root), patch.object(audit, '__file__', str(self.driver)), \
             patch.object(audit, 'ELFFile', return_value=Binary(e_machine='EM_RISCV')):
            return audit.inventory(self.instrumented, self.reference, archive)

    def test_complete_fixture_keeps_its_limited_scope(self):
        result = self.run_inventory()
        self.assertEqual((result['normal_objects_byte_identical'], result['functions']), (22, 22))
        self.assertFalse(result['complete_call_chain_bound_proven'])
        self.assertFalse(result['hardware'])

    def test_object_drift_is_rejected_before_elf_inspection(self):
        (self.instrumented / 'unit-0.o').write_bytes(b'changed synthetic bytes')
        with self.assertRaisesRegex(AssertionError, 'instrumentation-changed-object'):
            self.run_inventory()

    def test_archive_drift_is_not_waived_for_matching_objects(self):
        (self.instrumented / 'libw1700k-npu.a').write_bytes(b'changed synthetic archive')
        with self.assertRaisesRegex(AssertionError, 'normal-archive-drift'):
            self.run_inventory()

    def test_missing_normal_object_is_not_complete_coverage(self):
        (self.reference / 'unit-0.o').unlink()
        with self.assertRaisesRegex(AssertionError, 'normal-object-set'):
            self.run_inventory()

    def test_function_records_must_cover_actual_defined_symbols(self):
        (self.instrumented / 'unit-0.su').write_text('fixture.c:1:wrong\t16\tstatic\n')
        with self.assertRaisesRegex(AssertionError, 'stack-function-coverage'):
            self.run_inventory()

    def test_alternate_container_keeps_the_same_exact_byte_requirement(self):
        alternate = self.instrumented / 'different-order.a'
        alternate.write_bytes(b'changed synthetic archive')
        with self.assertRaisesRegex(AssertionError, 'normal-archive-drift'):
            self.run_inventory(alternate)


if __name__ == '__main__':
    unittest.main()
