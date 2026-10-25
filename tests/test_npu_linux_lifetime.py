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

    def run_check(self, record=None, raw=None, mutation=None, returncode=0, require_smp=False):
        record = self.record if record is None else record
        self.log.write_text(self.raw if raw is None else raw)

        def parsed(command, **kwargs):
            target = Path(next(argument.removeprefix('--json=') for argument in command if argument.startswith('--json=')))
            target.write_text(json.dumps(record))
            return subprocess.CompletedProcess(command, returncode, 'synthetic checker unit\n', '')

        with patch.object(lifetime.subprocess, 'run', side_effect=parsed):
            return lifetime.check_log(self.output, self.log, self.parser, mutation, require_smp)

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

    def smp_raw(self):
        raw = self.raw + 'w1700k_linux_lifetime.work_smp=1 w1700k_linux_lifetime.hif_smp=1\n'
        for suite, names in lifetime.CASES.items():
            for name in names:
                if name == 'k_ctor_admission':
                    row = dict(kind='ctor', case=name, online=2)
                elif suite == 'w1700k-linux-work':
                    row = dict(kind='work', case=name, callback=0, cleanup=1, online=2)
                else:
                    row = dict(kind='hif', case=name, probe=0, unbind=1, online=2)
                raw += '# W1700K_SMP ' + json.dumps(row) + '\n'
        return raw

    def test_exact_SMP_observations(self):
        result = self.run_check(raw=self.smp_raw(), require_smp=True)
        self.assertTrue(result['SMP_required'])
        self.assertEqual(len(result['SMP_observations']), 14)

    def test_SMP_parameters_required(self):
        with self.assertRaisesRegex(AssertionError, 'SMP-parameter-not-observed'):
            self.run_check(raw=self.smp_raw().replace('hif_smp=1', 'hif_smp=0'), require_smp=True)

    def test_SMP_marker_missing(self):
        with self.assertRaisesRegex(AssertionError, 'SMP-case-markers'):
            self.run_check(raw=self.smp_raw().split('# W1700K_SMP ')[0], require_smp=True)

    def test_SMP_marker_duplicate(self):
        raw = self.smp_raw()
        with self.assertRaisesRegex(AssertionError, 'SMP-case-markers'):
            self.run_check(raw=raw + raw.splitlines()[-1] + '\n', require_smp=True)

    def test_SMP_wrong_CPU_rejected(self):
        with self.assertRaisesRegex(AssertionError, 'unexpected-SMP-placement'):
            self.run_check(raw=self.smp_raw().replace('"cleanup": 1', '"cleanup": 0'), require_smp=True)

    def test_SMP_bool_CPU_rejected(self):
        with self.assertRaisesRegex(AssertionError, 'SMP-CPU-ID-type'):
            self.run_check(raw=self.smp_raw().replace('"unbind": 1', '"unbind": true'), require_smp=True)

    def test_SMP_online_count_rejected(self):
        with self.assertRaisesRegex(AssertionError, 'SMP-online-CPU-count'):
            self.run_check(raw=self.smp_raw().replace('"online": 2', '"online": 1'), require_smp=True)

    def test_SMP_same_CPU_control(self):
        record, _ = self.control()
        raw = self.raw + 'w1700k_linux_lifetime.work_smp=1 w1700k_linux_lifetime.hif_smp=1\n'
        raw += 'w1700k_linux_lifetime.work_mutation=5\ncleanup must execute on CPU 1\n'
        raw += '# W1700K_SMP ' + json.dumps(dict(kind='work', case='k_init_joins',
            callback=0, cleanup=0, online=2)) + '\n'
        self.assertTrue(self.run_check(record, raw, 'work-same-cpu', 1, True)['expected_failure'])

    def test_SMP_control_cannot_use_UP_checker(self):
        record, raw = self.control()
        with self.assertRaisesRegex(AssertionError, 'SMP-control-requires-SMP-mode'):
            self.run_check(record, raw, 'work-same-cpu', 1)


if __name__ == '__main__':
    unittest.main()
