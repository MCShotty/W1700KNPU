"""Source export include closure is checked independently of kernel compilation."""
from pathlib import Path
import tempfile
import unittest

from migration.source_component_headers import verify_header_closure


class HeaderClosureTests(unittest.TestCase):
    def fixture(self, directory, files, exported):
        root = Path(directory)
        for name, contents in files.items():
            path = root / 'firmware/npu' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)
        return root, [dict(tree='openwrt', source='firmware/npu/' + name,
                           destination='files/airoha/w1700k/' + name) for name in exported]

    def test_transitive_closure_and_angle_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, rows = self.fixture(tmp, {'setup.h': '#include "pcie.h"\n#include <stdint.h>\n',
                'pcie.h': '#include "done.h"\n', 'done.h': '#include "packet.h"\n', 'packet.h': ''},
                ('setup.h', 'pcie.h', 'done.h', 'packet.h'))
            self.assertEqual(len(verify_header_closure(root, rows)), 3)

    def test_missing_direct_header_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, rows = self.fixture(tmp, {'setup.h': '#include "pcie.h"\n'}, ('setup.h',))
            with self.assertRaisesRegex(RuntimeError, 'Missing exported NPU header'):
                verify_header_closure(root, rows)

    def test_missing_transitive_header_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, rows = self.fixture(tmp, {'setup.h': '#include "pcie.h"\n',
                'pcie.h': '#include "done.h"\n'}, ('setup.h', 'pcie.h'))
            with self.assertRaisesRegex(RuntimeError, 'done.h'):
                verify_header_closure(root, rows)

    def test_nested_local_header_is_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, rows = self.fixture(tmp, {'setup.h': '# include "sub/leaf.h"\n', 'sub/leaf.h': ''},
                                      ('setup.h', 'sub/leaf.h'))
            self.assertEqual(verify_header_closure(root, rows)[0]['dependency'],
                             'files/airoha/w1700k/sub/leaf.h')

    def test_absolute_include_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, rows = self.fixture(tmp, {'setup.h': '#include "/private.h"\n'}, ('setup.h',))
            with self.assertRaisesRegex(RuntimeError, 'Absolute quoted NPU include'):
                verify_header_closure(root, rows)

    def test_non_npu_components_are_not_reinterpreted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, rows = self.fixture(tmp, {'setup.h': '#include <stdint.h>\n'}, ('setup.h',))
            rows.append(dict(tree='luci', source='nonexistent.h', destination='other.h'))
            self.assertEqual(verify_header_closure(root, rows), [])


if __name__ == '__main__':
    unittest.main()
