"""Host-only result-checker tests; synthetic logs do not prove kernel execution."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / 'npu'))
import test_linux_lifetime as lifetime


class ResultChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.log = self.root / 'kernel.log'
        self.parser = self.root / 'kunit.py'
        self.parser.write_text('# synthetic parser identity only\n')
        self.output = self.root / 'checked'
        self.raw = 'Linux version 6.18.52 synthetic-host-only\n'
        self.record = dict(sub_groups=[dict(name=suite,
            test_cases=[dict(name=name, status='PASS') for name in names])
            for suite,names in lifetime.CASES.items()],
            misc=dict(tests=14, passed=14, failed=0, crashed=0, skipped=0, errors=0))

    def run_check(self, record=None, raw=None, mutation=None, returncode=0):
        record = self.record if record is None else record
        self.log.write_text(self.raw if raw is None else raw)

        def parsed(command, **kwargs):
            target = Path(next(argument.removeprefix('--json=') for argument in command if argument.startswith('--json=')))
            target.write_text(json.dumps(record))
            return subprocess.CompletedProcess(command, returncode, 'synthetic checker unit\n', '')

        with patch.object(lifetime.subprocess, 'run', side_effect=parsed):
            return lifetime.check_log(self.output, self.log, self.parser, mutation)

    def control(self):
        record = dict(sub_groups=[dict(name='w1700k-linux-work',
            test_cases=[dict(name='k_init_joins', status='FAIL')])],
            misc=dict(tests=1, passed=0, failed=1, crashed=0, skipped=0, errors=0))
        raw = self.raw + 'w1700k_linux_lifetime.work_mutation=1\nwork must reject queue after cleanup\n'
        return record, raw

    def test_exact_positive(self):
        result = self.run_check()
        self.assertTrue(result['passed'])
        self.assertFalse(result['expected_failure'])
        self.assertTrue(result['kernel_execution_must_be_bound_by_outer_runner'])
        self.assertFalse(result['physical_hardware'])

    def test_missing_case_rejected(self):
        record = copy.deepcopy(self.record)
        record['sub_groups'][0]['test_cases'].pop()
        with self.assertRaises(AssertionError):
            self.run_check(record)

    def test_skip_rejected(self):
        record = copy.deepcopy(self.record)
        record['sub_groups'][0]['test_cases'][0]['status'] = 'SKIP'
        record['misc'].update(passed=13, skipped=1)
        with self.assertRaises(AssertionError):
            self.run_check(record)

    def test_wrong_kernel_rejected(self):
        with self.assertRaises(AssertionError):
            self.run_check(raw=self.raw.replace('6.18.52', '6.18.53'))

    def test_kernel_warning_rejected(self):
        with self.assertRaises(AssertionError):
            self.run_check(raw=self.raw + 'WARNING: CPU: 0 synthetic\n')

    def test_duplicate_suite_rejected(self):
        record = copy.deepcopy(self.record)
        record['sub_groups'].insert(0, dict(name=record['sub_groups'][0]['name'], test_cases=[]))
        with self.assertRaisesRegex(AssertionError, 'duplicate-suite'):
            self.run_check(record)

    def test_intended_control(self):
        record, raw = self.control()
        result = self.run_check(record, raw, 'cancel-init', 1)
        self.assertTrue(result['expected_failure'])

    def test_wrong_control_message_rejected(self):
        record, raw = self.control()
        with self.assertRaises(AssertionError):
            self.run_check(record, raw.replace('work must reject queue after cleanup', 'unrelated error'), 'cancel-init', 1)

    def test_control_parameter_required(self):
        record, raw = self.control()
        with self.assertRaisesRegex(AssertionError, 'mutation-parameter-not-observed'):
            self.run_check(record, raw.replace('work_mutation=1', 'work_mutation=0'), 'cancel-init', 1)

    def test_control_crash_rejected(self):
        record, raw = self.control()
        record['sub_groups'][0]['test_cases'][0]['status'] = 'ERROR'
        record['misc'].update(failed=0, crashed=1)
        with self.assertRaises(AssertionError):
            self.run_check(record, raw, 'cancel-init', 1)

    def test_control_parser_must_fail(self):
        record, raw = self.control()
        with self.assertRaises(AssertionError):
            self.run_check(record, raw, 'cancel-init', 0)


if __name__ == '__main__':
    unittest.main()
