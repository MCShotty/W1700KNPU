"""Synthetic cached-receipt integrity checks, never native execution evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import raw_pair_retained as retained
from test_desc10_retained_controls import CASES, expected_locks


class RetainedCacheTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='retained-cache-unit-', dir=retained.ROOT / '.local')
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.snapshot = self.directory / 'snapshot.json'
        self.snapshot.write_text('synthetic unit fixture, not a native prefix')
        snapshot_name = str(self.snapshot.relative_to(retained.ROOT))
        self.inputs = {snapshot_name: retained.captured.digest(self.snapshot)}
        self.records, self.artifacts, rows = {}, {}, []
        for case in CASES:
            path = self.directory / case.name / 'result.json'
            path.parent.mkdir()
            record = dict(passed=True, case=case.name, full_request_count=512,
                actual_native_guards=True, input_drift_waivers=False, diagnostic_prefix=True,
                fresh_loader_allocator_caller_proof=False, full_setup=False, hardware=False,
                original_stores=case.stores, packet_claims=2560 + case.claims,
                private_claims=case.claims, queue_publications=case.published,
                original_lock_writes=len(expected_locks(case)), inputs=self.inputs)
            self.records[case.name] = record
            path.write_text(json.dumps(record))
            relative = str(path.relative_to(retained.ROOT))
            self.artifacts[relative] = retained.captured.digest(path)
            rows.append(dict(case=case.name, original_stores=case.stores,
                             packet_claims=2560 + case.claims, receipt=relative))
        self.summary = dict(passed=True, cases=[case.name for case in CASES],
                            controls=rows, inputs=self.inputs, artifacts=self.artifacts)
        self.save()

    def save(self):
        (self.directory / 'result.json').write_text(json.dumps(self.summary))

    def run_cache(self):
        with patch.object(retained.subprocess, 'run') as execute:
            result = retained.run_controls(self.directory, self.snapshot, self.directory)
        execute.assert_not_called()
        return result

    def change_case(self, name, **fields):
        self.records[name].update(fields)
        path = self.directory / name / 'result.json'
        path.write_text(json.dumps(self.records[name]))
        self.artifacts[str(path.relative_to(retained.ROOT))] = retained.captured.digest(path)
        self.save()

    def test_valid_cache_does_not_repeat_expensive_native_execution(self):
        self.assertEqual(self.run_cache()['cases'], [case.name for case in CASES])

    def test_cached_summary_cannot_drop_all_control_rows(self):
        self.summary['controls'] = []
        self.save()
        with self.assertRaises(AssertionError):
            self.run_cache()

    def test_cached_receipt_must_exist_even_if_omitted_from_artifact_map(self):
        path = self.directory / CASES[0].name / 'result.json'
        self.artifacts.pop(str(path.relative_to(retained.ROOT)))
        path.unlink()
        self.save()
        with self.assertRaises(AssertionError):
            self.run_cache()

    def test_cached_case_with_short_request_is_not_full_size_coverage(self):
        self.change_case(CASES[0].name, full_request_count=32)
        with self.assertRaises(AssertionError):
            self.run_cache()

    def test_cached_case_counters_must_match_the_named_fault(self):
        self.change_case('partial-pool', original_stores=2, private_claims=0)
        with self.assertRaises(AssertionError):
            self.run_cache()

    def test_cached_row_must_agree_with_its_individual_receipt(self):
        self.summary['controls'][0]['packet_claims'] = 3072
        self.save()
        with self.assertRaises(AssertionError):
            self.run_cache()


if __name__ == '__main__':
    unittest.main()
