"""Bounded diagnostic replay with host-only progress;original guards stay intact."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
import native_prefix_snapshot
import raw_pair_retained as retained
import test_desc10_retained_controls as controls

ROOT = controls.ROOT
CASES = {case.name:case for case in controls.CASES if case.name in ('denied','before-ready-bitmap')}


def emit(event):
    print(json.dumps(event),flush=True)


class ProgressList(list):
    def __init__(self, observer):
        super().__init__()
        self.observer = observer

    def append(self, value):
        super().append(value)
        count = len(self)
        if count == 1 or count % 1024 == 0 or count in (25604,25606):
            self.observer(dict(original_stores_observed=count,last_original_store=list(value)))


class ProgressTrace(controls.Desc10Trace):
    def __init__(self, *args):
        super().__init__(*args)
        assert not self.stores
        self.stores = ProgressList(emit)


class ProgressInjection(controls.Injection):
    def mark(self, address, width, value):
        super().mark(address,width,value)
        emit(dict(fault_injected=self.case.name,injection=self.injected[-1]))


def run_worker(command, log, timeout):
    with log.open('x') as stream:
        with subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stream,
                stderr=subprocess.STDOUT,start_new_session=True) as child:
            try:
                code = child.wait(timeout=timeout)
                timed_out = False
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:
                    pass
                code = child.wait()
                timed_out = True
    return dict(returncode=code,host_timeout=timed_out,host_timeout_seconds=timeout)


def attempt(args):
    assert os.environ.get('NPU_EMULATION_TIMEOUT_US') == '60000000', 'native-wall-budget-must-stay-unchanged'
    output = args.output.resolve()
    assert output.is_relative_to(ROOT / '.local') and not output.exists()
    pair,snapshot = args.pair.resolve(),args.snapshot.resolve()
    assert all(path.is_relative_to(ROOT / '.local') for path in (pair,snapshot))
    output.mkdir(parents=True)
    command = [sys.executable,'-u','-B',str(Path(__file__).resolve()),'--worker',
        '--pair',str(pair),'--snapshot',str(snapshot),'--output',str(output / 'case'),
        '--case',args.case,'--host-timeout',str(args.host_timeout)]
    emit(dict(diagnostic_started=True,case=args.case,host_timeout_seconds=args.host_timeout,
        native_emulator_wall_budget_us=60000000,output=str(output)))
    execution = run_worker(command,output / 'worker.log',args.host_timeout)
    receipt = output / 'case/result.json'
    row,validation_error = None,None
    if execution['returncode'] == 0 and not execution['host_timeout']:
        try:
            row = retained.case_receipt(receipt,CASES[args.case],snapshot)
        except Exception as error:
            validation_error = type(error).__name__
    inputs = native_prefix_snapshot.source_inputs({})
    if row is not None:
        for name,expected in row['inputs'].items():
            assert name not in inputs or inputs[name] == expected, ('probe-cohort-conflict',name)
            inputs[name] = expected
    retained.verify_inputs(inputs)
    files = [path for path in output.rglob('*') if path.is_file()]
    assert not any(path.is_symlink() for path in output.rglob('*'))
    artifacts = {str(path.relative_to(ROOT)):retained.captured.digest(path) for path in sorted(files)}
    result = dict(passed=row is not None,**execution,case=args.case,command=command,
        inputs=inputs,artifacts=artifacts,validation_error_type=validation_error,
        native_emulator_wall_budget_us=60000000,full_request_count=512,
        original_guard_consumer='tests/npu/test_desc10_retained_controls.py',
        progress_changes_guest_memory=False,progress_changes_guest_registers=False,
        input_drift_waivers=False,diagnostic_prefix=True,fresh_loader_allocator_caller_proof=False,
        prior_failed_matrix_repaired=False,full_setup=False,hardware=False,
        worker_log_sha256=retained.captured.digest(output / 'worker.log'))
    if row is not None:
        result.update(original_case_receipt=str(receipt.relative_to(ROOT)),
            original_case_receipt_sha256=retained.captured.digest(receipt),
            original_stores=row['original_stores'],packet_claims=row['packet_claims'])
    with (output / 'attempt.json').open('x') as stream: stream.write(json.dumps(result,indent=2) + '\n')
    emit(dict(passed=result['passed'],host_timeout=result['host_timeout'],case=args.case,
        prior_failed_matrix_repaired=False,diagnostic_prefix=True))
    return result


def main():
    parser = argparse.ArgumentParser()
    for flag in ('pair','snapshot','output'): parser.add_argument('--' + flag,type=Path,required=True)
    parser.add_argument('--case',choices=sorted(CASES),default='before-ready-bitmap')
    parser.add_argument('--host-timeout',type=int,choices=(10800,21600),default=10800)
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        assert os.environ.get('NPU_EMULATION_TIMEOUT_US') == '60000000'
        with patch.object(controls,'Desc10Trace',ProgressTrace),patch.object(controls,'Injection',ProgressInjection):
            controls.run(args.pair.resolve(),args.snapshot.resolve(),args.output.resolve(),CASES[args.case])
    else:
        raise SystemExit(0 if attempt(args)['passed'] else 1)


if __name__ == '__main__': main()
