"""Synthetic host-observer/deadline controls;not a native fault verdict."""
import json
from pathlib import Path
import signal
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import desc10_progress_probe as probe


class ProgressProbeTests(unittest.TestCase):
    def arguments(self, root):
        return SimpleNamespace(pair=root / 'pair',snapshot=root / 'snapshot.json',output=root / 'probe',
            case='before-ready-bitmap',host_timeout=10800)

    def test_progress_list_keeps_every_event_in_exact_order(self):
        events = []
        actual = probe.ProgressList(events.append)
        expected = [(0x84000000 + index,0x3000,4,index) for index in range(25606)]
        for row in expected: actual.append(row)
        self.assertEqual(actual,expected)
        counts = [row['original_stores_observed'] for row in events]
        self.assertEqual(counts,[1,*range(1024,25601,1024),25604,25606])
        self.assertEqual(events[-1]['last_original_store'],list(expected[-1]))

    def test_progress_emitter_failure_is_not_silently_ignored(self):
        observer = Mock(side_effect=RuntimeError('synthetic log failure'))
        events = probe.ProgressList(observer)
        with self.assertRaises(RuntimeError): events.append((1,2,4,5))
        self.assertEqual(events,[(1,2,4,5)])

    def test_injection_adds_only_host_logging_to_the_original_single_mutation(self):
        cpu = Mock()
        cpu.mem_read.return_value = b'\x11\x22\x33\x44'
        owner = Mock(cpu=cpu)
        injection = probe.ProgressInjection(owner,None,probe.CASES['before-ready-bitmap'])
        with patch.object(probe,'emit') as emit:
            injection.mark(0x3000,4,0x55667788)
        cpu.mem_read.assert_called_once_with(0x3000,4)
        cpu.mem_write.assert_called_once_with(0x3000,b'\x88\x77\x66\x55')
        self.assertEqual(len(injection.injected),1)
        emit.assert_called_once_with(dict(fault_injected='before-ready-bitmap',injection=injection.injected[0]))
        cpu.reg_write.assert_not_called()

    def test_success_and_nonzero_worker_exits_are_preserved(self):
        for code in (0,7):
            with self.subTest(code=code),tempfile.TemporaryDirectory() as temporary:
                child = Mock(pid=123)
                child.wait.return_value = code
                context = Mock()
                context.__enter__ = Mock(return_value=child)
                context.__exit__ = Mock(return_value=False)
                with patch.object(probe.subprocess,'Popen',return_value=context),patch.object(probe.os,'killpg') as kill:
                    result = probe.run_worker(['synthetic'],Path(temporary) / 'run.log',9)
                self.assertEqual(result,dict(returncode=code,host_timeout=False,host_timeout_seconds=9))
                child.wait.assert_called_once_with(timeout=9)
                kill.assert_not_called()

    def test_deadline_kills_only_the_workers_process_group_and_waits(self):
        with tempfile.TemporaryDirectory() as temporary:
            child = Mock(pid=123)
            child.wait.side_effect = [subprocess.TimeoutExpired(['synthetic'],9),-signal.SIGKILL]
            context = Mock()
            context.__enter__ = Mock(return_value=child)
            context.__exit__ = Mock(return_value=False)
            with patch.object(probe.subprocess,'Popen',return_value=context) as launch, \
                    patch.object(probe.os,'killpg') as kill:
                result = probe.run_worker(['synthetic'],Path(temporary) / 'run.log',9)
            self.assertEqual(result,dict(returncode=-signal.SIGKILL,host_timeout=True,host_timeout_seconds=9))
            kill.assert_called_once_with(123,signal.SIGKILL)
            self.assertTrue(launch.call_args.kwargs['start_new_session'])
            self.assertEqual(child.wait.call_count,2)

    def test_existing_worker_log_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / 'run.log'
            log.write_bytes(b'prior failure')
            with patch.object(probe.subprocess,'Popen') as launch:
                with self.assertRaises(FileExistsError): probe.run_worker(['synthetic'],log,9)
                launch.assert_not_called()
            self.assertEqual(log.read_bytes(),b'prior failure')

    def test_deadline_racing_with_worker_exit_still_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            child = Mock(pid=123)
            child.wait.side_effect = [subprocess.TimeoutExpired(['synthetic'],9),0]
            context = Mock()
            context.__enter__ = Mock(return_value=child)
            context.__exit__ = Mock(return_value=False)
            with patch.object(probe.subprocess,'Popen',return_value=context), \
                    patch.object(probe.os,'killpg',side_effect=ProcessLookupError):
                result = probe.run_worker(['synthetic'],Path(temporary) / 'run.log',9)
            self.assertTrue(result['host_timeout'])

    def test_failed_or_timed_out_worker_cannot_promote_an_existing_case_record(self):
        base = probe.ROOT / '.local'
        for code,timed_out in ((7,False),(-signal.SIGKILL,True),(0,True)):
            with self.subTest(code=code,timed_out=timed_out),tempfile.TemporaryDirectory(dir=base) as temporary:
                args = self.arguments(Path(temporary))

                def failed(command,log,timeout):
                    log.write_bytes(b'synthetic worker failure')
                    case = log.parent / 'case'
                    case.mkdir()
                    (case / 'result.json').write_text('{"passed":true,"synthetic_forged_fixture":true}')
                    return dict(returncode=code,host_timeout=timed_out,host_timeout_seconds=timeout)

                with patch.dict(probe.os.environ,NPU_EMULATION_TIMEOUT_US='60000000'), \
                        patch.object(probe,'run_worker',side_effect=failed), \
                        patch.object(probe.retained,'case_receipt') as validate,patch.object(probe,'emit'):
                    result = probe.attempt(args)
                    validate.assert_not_called()
                self.assertFalse(result['passed'])
                self.assertFalse(result['prior_failed_matrix_repaired'])
                self.assertTrue(result['artifacts'])
                self.assertFalse(json.loads((args.output / 'attempt.json').read_bytes())['passed'])

    def test_zero_worker_exit_without_a_valid_original_case_is_failed(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT / '.local') as temporary:
            args = self.arguments(Path(temporary))

            def empty(command,log,timeout):
                log.write_bytes(b'synthetic zero exit;no native verdict')
                return dict(returncode=0,host_timeout=False,host_timeout_seconds=timeout)

            with patch.dict(probe.os.environ,NPU_EMULATION_TIMEOUT_US='60000000'), \
                    patch.object(probe,'run_worker',side_effect=empty),patch.object(probe,'emit'):
                result = probe.attempt(args)
            self.assertFalse(result['passed'])
            self.assertEqual(result['validation_error_type'],'AssertionError')

    def test_native_budget_change_is_rejected_before_output_creation(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT / '.local') as temporary:
            args = self.arguments(Path(temporary))
            with patch.dict(probe.os.environ,NPU_EMULATION_TIMEOUT_US='120000000'), \
                    patch.object(probe,'run_worker') as launch:
                with self.assertRaisesRegex(AssertionError,'native-wall-budget-must-stay-unchanged'): probe.attempt(args)
                launch.assert_not_called()
            self.assertFalse(args.output.exists())


if __name__ == '__main__': unittest.main()
