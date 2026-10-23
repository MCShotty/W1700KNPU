"""Exercise complete on-disk inventory comparison without compiling a module."""
import os
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_rro_reset_modules as builder


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.target = self.root / 'tree'
        self.target.mkdir()
        (self.target / 'one').write_bytes(b'first')
        (self.target / 'two').write_bytes(b'second')
        (self.target / 'alias').symlink_to('one')
        self.before = builder.snapshot(self.root, 'before.json', self.target)

    def after(self):
        return builder.snapshot(self.root, 'after.json', self.target)

    def test_order_independent(self):
        entries = builder.inventory(self.target)
        with patch.object(builder, 'inventory', return_value=dict(reversed(list(entries.items())))):
            self.assertEqual(self.before, self.after())
        self.assertEqual(self.before['entries'], 3)

    def test_content_change(self):
        (self.target / 'one').write_bytes(b'changed')
        self.assertNotEqual(self.before, self.after())

    def test_mode_change(self):
        path = self.target / 'one'
        os.chmod(path, path.stat().st_mode ^ 0o100)
        self.assertNotEqual(self.before, self.after())

    def test_symlink_change(self):
        path = self.target / 'alias'
        path.unlink()
        path.symlink_to('two')
        self.assertNotEqual(self.before, self.after())

    def test_replaced_name_same_count(self):
        (self.target / 'two').rename(self.target / 'three')
        self.assertNotEqual(self.before, self.after())

    def verify_status(self, changes, accepted=False):
        directory = self.root / '.local/npu-checked-irq-modules/q1'
        directory.mkdir(parents=True)
        state = dict(producer_unit='w1700k-npu-rro-reset-modules-q5.service',invocation_id='fixture-invocation')
        (directory / 'outer-state.json').write_text(json.dumps(state))
        status = dict(InvocationID='fixture-invocation',SubState='exited',Result='success',ExecMainStatus='0')
        status.update(changes)
        output = '\n'.join(name+'='+value for name,value in status.items())+'\n'
        with patch.object(builder,'ROOT',self.root), \
             patch('sys.argv',['test_rro_reset_modules.py','--name','q1','--verify-only']), \
             patch.object(builder.subprocess,'check_output',return_value=output), \
             patch.object(builder,'finish',return_value=0) as finish:
            if accepted:
                with self.assertRaises(SystemExit) as stopped:
                    builder.main()
                self.assertEqual(stopped.exception.code,0)
                finish.assert_called_once_with(directory,state,0,status)
            else:
                with self.assertRaises(AssertionError):
                    builder.main()
                finish.assert_not_called()

    def test_completed_exact_invocation(self):
        self.verify_status({},accepted=True)

    def test_wrong_invocation_rejected(self):
        self.verify_status(dict(InvocationID='different-invocation'))

    def test_failed_producer_rejected(self):
        self.verify_status(dict(Result='oom-kill'))

    def test_nonzero_producer_rejected(self):
        self.verify_status(dict(ExecMainStatus='1'))

    def test_active_producer_rejected(self):
        self.verify_status(dict(SubState='start'))


if __name__ == '__main__':
    unittest.main()
