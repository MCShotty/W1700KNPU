"""All24 strictly restored constructor faults with complete pair provenance."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import native_prefix_snapshot
import raw_pair_retained as retained
import restore_native_prefix
from test_inode_native_controls import CASES
from inode_trace import callback_abi_contract, END, STACK_TOPS

ROOT = retained.ROOT


def matrix(): return [(stage, case) for stage in (0, 1) for case in CASES]


def case_contract(row, stage, case):
    assert row['passed'] is True and row['stage'] == stage and row['case'] == case.name
    assert row['actual_native_guards'] is True and row['diagnostic_prefix'] is True
    assert row['input_drift_waivers'] is False and row['fresh_loader_allocator_caller_proof'] is False
    assert row['full_setup'] is False and row['hardware'] is False
    assert row['exact_owner_bytes'] == 4372 and row['exact_setup_bytes'] == 412 and row['exact_code_private_bytes'] == 0x200000
    assert row['exact_prior_private_and_code'] is True
    assert row['release_irq_checked'] is True
    trace = row.get('trace')
    assert isinstance(trace, dict), 'INODE-fault-missing-ABI-trace'
    saved, interrupt = trace['entry_saved_registers'], trace['entry_interrupt_csrs']
    callback_abi_contract(trace.get('callback_entry'), trace.get('callback_returns'), saved, interrupt)
    returns = trace['native_returns']
    assert len(returns) == 1 and returns[0]['pc'] == END and returns[0]['mstatus'] == 0
    assert returns[0]['sp'] == STACK_TOPS[0] - 0x1000
    assert tuple(returns[0]['saved']) == tuple(saved) and tuple(returns[0]['interrupt']) == tuple(interrupt)
    assert trace['abi_observed_before_context_restore'] is True
    assert row['packet_claims'] == 3072
    first, size = (0, 1030) if stage == 0 else (1030, 6)
    stores = size if case.boundary == 'release' else case.stores
    published = size if case.boundary == 'release' else case.published
    assert (row['original_stores'], row['committed'], row['published']) == (stores, first + stores, first + published)
    memory = row['protected_memory']
    spans = (*retained.SPACES, *((base, 4096) for base in retained.MODEL_BAR_PAGES))
    assert sorted((region['base'], region['bytes']) for region in memory) == sorted((hex(base), size) for base, size in spans)
    assert sum(region['bytes'] for region in memory) == 868352 and all(region['differing_bytes'] == 0 for region in memory)


def summary_contract(record, rows):
    assert record['passed'] is True and record['actual_native_guards'] is True and record['diagnostic_prefix'] is True
    assert record['input_drift_waivers'] is False and record['fresh_loader_allocator_caller_proof'] is False
    assert record['full_setup'] is False and record['hardware'] is False
    assert record['cases'] == [[stage, case.name] for stage, case in matrix()]
    assert record['controls'] == rows and len(rows) == 24
    assert [(row['stage'], row['case']) for row in rows] == [(stage, case.name) for stage, case in matrix()]


def run_controls(pair, caller, directory, workers=4):
    pair, caller, directory = pair.resolve(), caller.resolve(), directory.resolve()
    assert 1 <= workers <= 4 and all(path.is_relative_to(ROOT / '.local') for path in (pair, caller, directory))
    snapshots = [caller / ('inode-prefix-' + str(stage)) / 'snapshot.json' for stage in (0, 1)]
    for stage, snapshot in enumerate(snapshots):
        record = json.loads(snapshot.read_bytes())
        assert record['origin'] == 'actual-provider-allocator-caller-before-INODE-' + str(stage)
        assert record['fresh_loader_allocator_caller_proof'] is False
        retained.verify_inputs(record['inputs'])
    required = restore_native_prefix.pair_artifact_inputs(pair, json.loads((pair / 'manifest.json').read_bytes()))
    inputs = native_prefix_snapshot.source_inputs({})
    summary = directory / 'result.json'
    cached = retained.read_receipt(summary) if summary.exists() else None
    if cached is not None: retained.verify_inputs(cached['artifacts'])
    directory.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, NPU_EMULATION_TIMEOUT_US='60000000')
    environment['PYTHONPATH'] = os.pathsep.join(str(ROOT / name) for name in ('.local/npu-reset/python-lib', 'tests/npu', 'tools'))

    def execute(stage, case):
        output = directory / ('stage-' + str(stage)) / case.name
        receipt = output / 'result.json'
        if receipt.exists(): return receipt
        assert cached is None and not output.exists(), ('incomplete-INODE-case', stage, case.name)
        output.parent.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, '-u', '-B', str(ROOT / 'tests/npu/test_inode_native_controls.py'),
            '--pair', str(pair), '--snapshot', str(snapshots[stage]), '--output', str(output), '--case', case.name]
        with (output.parent / (case.name + '.log')).open('x') as stream:
            completed = subprocess.run(command, cwd=ROOT, env=environment, stdout=stream, stderr=subprocess.STDOUT)
        return receipt if completed.returncode == 0 else None

    outcomes = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {pool.submit(execute, stage, case): (stage, case.name) for stage, case in matrix()}
        for job in as_completed(pending):
            identity = pending[job]
            try: outcomes[identity] = job.result()
            except Exception as error:
                outcomes[identity] = None
                print(json.dumps(dict(stage=identity[0], inode_fault=identity[1], error_type=type(error).__name__)), flush=True)
            if cached is None: print(json.dumps(dict(stage=identity[0], inode_fault=identity[1], passed=outcomes[identity] is not None)), flush=True)
    assert all(outcomes.values()), ('INODE-controls-failed', [identity for identity, result in outcomes.items() if result is None])
    rows = []
    for stage, case in matrix():
        receipt = outcomes[(stage, case.name)]
        record = retained.read_receipt(receipt)
        case_contract(record, stage, case)
        for name, expected in required.items(): assert record['inputs'].get(name) == expected, ('INODE-case-pair-artifact', name)
        assert record['inputs'][str(snapshots[stage].relative_to(ROOT))] == retained.captured.digest(snapshots[stage])
        relative = str(receipt.relative_to(ROOT))
        if cached is not None: assert cached['artifacts'].get(relative) == retained.captured.digest(receipt)
        for name, expected in record['inputs'].items():
            assert name not in inputs or inputs[name] == expected, ('INODE-case-cohort-conflict', name)
            inputs[name] = expected
        rows.append(dict(stage=stage, case=case.name, original_stores=record['original_stores'], receipt=relative))
    if cached is not None:
        summary_contract(cached, rows)
        return cached
    artifacts = {str(path.relative_to(ROOT)): retained.captured.digest(path) for path in directory.rglob('*') if path.is_file()}
    inputs = native_prefix_snapshot.source_inputs(inputs)
    retained.verify_inputs(inputs)
    result = dict(passed=True, cases=[[stage, case.name] for stage, case in matrix()], controls=rows,
        inputs=inputs, artifacts=artifacts, workers=workers, actual_native_guards=True, diagnostic_prefix=True,
        input_drift_waivers=False, fresh_loader_allocator_caller_proof=False, full_setup=False, hardware=False,
        limits=['All12 exact faults at both actual constructor prefixes;no native-store or guard-size reduction.',
                'Each raw run retains its original finite instruction/checkpoint bounds;no aggregate wall-time shortcut.',
                'Restored controls are diagnostic,not new loader/allocator/caller or physical acceptance.'])
    summary_contract(result, rows)
    with summary.open('x') as stream: stream.write(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--caller', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    result = run_controls(args.pair, args.caller, args.output, args.workers)
    print(json.dumps(dict(passed=True, diagnostic_native_INODE_fault_cases=len(result['cases']), full_setup=False)), flush=True)


if __name__ == '__main__': main()
