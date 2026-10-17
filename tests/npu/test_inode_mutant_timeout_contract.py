"""Host deadline option only;never a native-budget or sanitizer success proof."""
from contextlib import redirect_stderr
import io
import unittest

from test_cold_inode_mutants import arguments


class InodeMutantTimeoutTests(unittest.TestCase):
    base = ['--name', 'timeout-contract', '--baseline', 'unused-fixture.elf']

    def test_default_keeps_original_host_limit(self):
        self.assertEqual(arguments(self.base).sanitizer_host_timeout, 120)

    def test_explicit_finite_host_limits(self):
        for seconds in (120, 180, 600):
            self.assertEqual(arguments(self.base + ['--sanitizer-host-timeout', str(seconds)]).sanitizer_host_timeout, seconds)

    def test_out_of_range_limits_fail_before_execution(self):
        for seconds in (0, 119, 601):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                arguments(self.base + ['--sanitizer-host-timeout', str(seconds)])
            self.assertEqual(raised.exception.code, 2)

    def test_noninteger_limit_is_rejected(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            arguments(self.base + ['--sanitizer-host-timeout', 'many'])
        self.assertEqual(raised.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
