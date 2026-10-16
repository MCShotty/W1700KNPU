"""Synthetic aggregate admission controls, not the native tail fault matrix."""
from copy import deepcopy
import unittest

from pcie_tail_retained_controls import CASES, case_contract, matrix, retained, summary_contract


def receipt(stage, case):
    count = (5 if stage == 2 else 2) if case.boundary == 'release' else case.stores
    published = count if case.boundary == 'release' else case.published
    return dict(passed=True, stage=stage, case=case.name, actual_native_guards=True, input_drift_waivers=False,
        diagnostic_prefix=True, fresh_loader_allocator_caller_proof=False, full_setup=False, hardware=False,
        exact_prior_private_and_code=True, exact_owner_bytes=256, exact_setup_bytes=412, packet_claims=3072,
        original_stores=count, committed=stage * 2 + count, published=stage * 2 + published,
        protected_memory=[dict(base=hex(base), bytes=size, differing_bytes=0) for base, size in
                          (*retained.SPACES, *((base, 4096) for base in retained.MODEL_BAR_PAGES))])


class TailMatrixContractTests(unittest.TestCase):
    def test_all_twelve_cases_are_required_at_all_three_stages(self):
        self.assertEqual(matrix(), [(stage, case) for stage in range(3) for case in CASES])
        self.assertEqual(len({(stage, case.name) for stage, case in matrix()}), 36)

    def test_each_exact_scoped_shape_passes(self):
        for stage, case in matrix(): case_contract(receipt(stage, case), stage, case)

    def test_stage_and_effect_counts_cannot_be_reused_from_another_case(self):
        stage, case = 2, CASES[-1]
        for field in ('stage', 'original_stores', 'committed', 'published', 'packet_claims', 'exact_setup_bytes'):
            row = receipt(stage, case)
            row[field] += 1
            with self.assertRaises(AssertionError): case_contract(row, stage, case)

    def test_diagnostic_result_cannot_be_promoted_or_weakened(self):
        case = CASES[0]
        for field in ('passed', 'actual_native_guards', 'input_drift_waivers', 'diagnostic_prefix',
                      'fresh_loader_allocator_caller_proof', 'full_setup', 'hardware', 'exact_prior_private_and_code'):
            row = receipt(0, case)
            row[field] = not row[field]
            with self.assertRaises(AssertionError): case_contract(row, 0, case)

    def test_missing_or_different_protected_bytes_cannot_pass(self):
        case = CASES[0]
        for field in ('bytes', 'differing_bytes'):
            row = deepcopy(receipt(0, case))
            row['protected_memory'][0][field] += 1
            with self.assertRaises(AssertionError): case_contract(row, 0, case)

    def test_equal_total_size_does_not_replace_exact_protected_regions(self):
        case = CASES[0]
        row = receipt(0, case)
        row['protected_memory'][0]['base'] = '0x1000'
        with self.assertRaises(AssertionError): case_contract(row, 0, case)

    def test_cached_aggregate_requires_all_exact_rows_and_scope(self):
        rows = [dict(stage=stage, case=case.name) for stage, case in matrix()]
        record = dict(passed=True, actual_native_guards=True, diagnostic_prefix=True, input_drift_waivers=False,
            fresh_loader_allocator_caller_proof=False, full_setup=False, hardware=False,
            cases=[[stage, case.name] for stage, case in matrix()], controls=rows)
        summary_contract(record, rows)
        for field in ('full_setup', 'hardware', 'input_drift_waivers', 'fresh_loader_allocator_caller_proof'):
            wrong = deepcopy(record)
            wrong[field] = True
            with self.assertRaises(AssertionError): summary_contract(wrong, rows)
        for incomplete in (rows[:-1], rows[:-1] + rows[:1]):
            wrong = dict(record, controls=incomplete)
            with self.assertRaises(AssertionError): summary_contract(wrong, incomplete)


if __name__ == '__main__': unittest.main()
