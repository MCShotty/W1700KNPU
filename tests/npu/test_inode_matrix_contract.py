"""Synthetic24-case admission contracts;no native fault execution."""
from copy import deepcopy
import unittest

from inode_retained_controls import CASES, matrix, case_contract, summary_contract, retained


def receipt(stage, case):
    first, size = (0, 1030) if stage == 0 else (1030, 6)
    count = size if case.boundary == 'release' else case.stores
    published = size if case.boundary == 'release' else case.published
    spans = (*retained.SPACES, *((base, 4096) for base in retained.MODEL_BAR_PAGES))
    return dict(passed=True, stage=stage, case=case.name, actual_native_guards=True, diagnostic_prefix=True,
        input_drift_waivers=False, fresh_loader_allocator_caller_proof=False, full_setup=False, hardware=False,
        exact_owner_bytes=4372, exact_setup_bytes=412, exact_code_private_bytes=0x200000, packet_claims=3072,
        exact_prior_private_and_code=True, release_irq_checked=True,
        original_stores=count, committed=first + count, published=first + published,
        protected_memory=[dict(base=hex(base), bytes=size, differing_bytes=0) for base, size in spans])


class InodeMatrixContractTests(unittest.TestCase):
    def test_all_exact_cases_at_both_stages(self):
        self.assertEqual(len(matrix()), 24)
        self.assertEqual(len({(stage, case.name) for stage, case in matrix()}), 24)
        for stage, case in matrix(): case_contract(receipt(stage, case), stage, case)

    def test_progress_and_scope_cannot_be_weakened(self):
        for stage, case in matrix():
            for field in ('stage', 'original_stores', 'committed', 'published', 'packet_claims',
                          'exact_owner_bytes', 'exact_setup_bytes', 'exact_code_private_bytes'):
                row = receipt(stage, case)
                row[field] += 1
                with self.assertRaises(AssertionError): case_contract(row, stage, case)

    def test_diagnostic_result_cannot_be_promoted(self):
        for field in ('passed', 'actual_native_guards', 'diagnostic_prefix', 'input_drift_waivers',
                      'fresh_loader_allocator_caller_proof', 'full_setup', 'hardware', 'exact_prior_private_and_code',
                      'release_irq_checked'):
            row = receipt(0, CASES[0])
            row[field] = not row[field]
            with self.assertRaises(AssertionError): case_contract(row, 0, CASES[0])

    def test_exact_regions_and_zero_differences_required(self):
        for field, value in (('base', '0x1000'), ('bytes', 0), ('differing_bytes', 1)):
            row = receipt(0, CASES[0])
            row['protected_memory'][0][field] = value
            with self.assertRaises(AssertionError): case_contract(row, 0, CASES[0])

    def test_cached_summary_requires_complete_ordered_matrix(self):
        rows = [dict(stage=stage, case=case.name) for stage, case in matrix()]
        record = dict(passed=True, actual_native_guards=True, diagnostic_prefix=True,
            input_drift_waivers=False, fresh_loader_allocator_caller_proof=False, full_setup=False, hardware=False,
            cases=[[stage, case.name] for stage, case in matrix()], controls=rows)
        summary_contract(record, rows)
        for controls in (rows[:-1], rows[:-1] + rows[:1], list(reversed(rows))):
            changed = dict(record, controls=controls)
            with self.assertRaises(AssertionError): summary_contract(changed, controls)
        for field in ('hardware', 'full_setup', 'fresh_loader_allocator_caller_proof', 'input_drift_waivers'):
            changed = deepcopy(record)
            changed[field] = True
            with self.assertRaises(AssertionError): summary_contract(changed, rows)


if __name__ == '__main__': unittest.main()
