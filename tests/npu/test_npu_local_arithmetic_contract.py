"""Local SP/clobber controls for LLVM-built RV32 arithmetic fixtures."""
import hashlib
import json
from pathlib import Path
import unittest

from test_npu_direct_stack import decode
from test_npu_original_body_stack import local_body, local_effect
from local_arithmetic_guests import exercise

PATH = Path(__file__).with_name('original_body_arithmetic_fixtures.json')
assert hashlib.sha256(PATH.read_bytes()).hexdigest() == 'c19648b5e814474622f3bedbb560ddf8c0225f61feccc2eaf1ce8efd8aed929e'
RECORD = json.loads(PATH.read_bytes())
SOURCE = PATH.parent / 'fixtures/original_body_arithmetic.S'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == RECORD['source_sha256']
FIXTURES = RECORD['fixtures']
assert len(FIXTURES) == 28
FORMS = ('mul', 'mulh', 'mulhsu', 'mulhu', 'div', 'divu', 'rem', 'remu', 'seqz')


def fixture(name):
    row = FIXTURES['case_' + name]
    return bytes.fromhex(row['bytes_hex']), row['address']


class LocalArithmeticContractTests(unittest.TestCase):
    def test_non_SP_destinations_keep_local_zero_and_no_chain_claim(self):
        for name in FORMS:
            with self.subTest(form=name):
                row = local_body(*fixture(name))
                self.assertEqual(row['local_max_stack_bytes'], 0)
                self.assertFalse(row['complete_call_chain_bound_proven'])

    def test_every_SP_destination_is_rejected(self):
        for name in FORMS:
            with self.subTest(form=name):
                with self.assertRaisesRegex(AssertionError, 'non-relative-SP-write'):
                    local_body(*fixture(name + '_sp'))

    def test_zero_destination_stays_zero(self):
        for name in FORMS:
            with self.subTest(form=name):
                data, address = fixture(name + '_zero')
                before = tuple([0] + [None] * 31)
                after = local_effect(decode(data, address)[0], before, None)
                self.assertEqual(after, before)
                self.assertEqual(local_body(data, address)['local_max_stack_bytes'], 0)

    def test_non_SP_results_are_unknown_not_computed_or_reused(self):
        for name in FORMS:
            with self.subTest(form=name):
                data, address = fixture(name)
                before = [0] * 32
                before[10:13] = [999, 7, 3]
                after = local_effect(decode(data, address)[0], tuple(before), None)
                expected = list(before)
                expected[10] = None
                self.assertEqual(after, tuple(expected))

    def test_arithmetic_does_not_erase_an_existing_frame(self):
        row = local_body(*fixture('mul_framed'))
        self.assertEqual(row['local_max_stack_bytes'], 16)
        self.assertEqual([entry['entry_SP_offset'] for entry in row['stack_memory']], [-4, -4])
        self.assertFalse(row['child_frames_proved'])

    def test_all_fixtures_execute_with_exact_register_and_memory_checks(self):
        records = exercise(FIXTURES)
        self.assertEqual(len(records), 84)
        self.assertTrue(all(row['all_GPRs_compared_before_any_host_restore']
            and row['exact_protected_code_and_stack'] for row in records))


if __name__ == '__main__':
    unittest.main()
