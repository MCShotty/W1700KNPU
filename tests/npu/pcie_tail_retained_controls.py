"""Complete tail fault matrix over strictly restored actual caller prefixes."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import native_prefix_snapshot
import raw_pair_retained as retained
from test_pcie_tail_native_controls import CASES

ROOT = retained.ROOT


def matrix():
    return [(stage, case) for stage in range(3) for case in CASES]


def case_contract(row, stage, case):
    assert row['passed'] is True and row['stage'] == stage and row['case'] == case.name
    assert row['actual_native_guards'] is True and row['input_drift_waivers'] is False
    assert row['diagnostic_prefix'] is True and row['fresh_loader_allocator_caller_proof'] is False
    assert row['full_setup'] is False and row['hardware'] is False
    assert row['exact_prior_private_and_code'] is True and row['exact_owner_bytes'] == 256
    assert row['exact_setup_bytes'] == 404 and row['packet_claims'] == 3072
    first, count = stage * 2, (5 if stage == 2 else 2) if case.boundary == 'release' else case.stores
    published = count if case.boundary == 'release' else case.published
    assert (row['original_stores'], row['committed'], row['published']) == (count, first + count, first + published)
    memory = row['protected_memory']
    spans = (*retained.SPACES, *((base, 4096) for base in retained.MODEL_BAR_PAGES))
    assert sorted((region['base'], region['bytes']) for region in memory) == \
           sorted((hex(base), size) for base, size in spans), 'tail-fault-protected-regions'
    assert sum(region['bytes'] for region in memory) == 868352 and all(region['differing_bytes'] == 0 for region in memory)


def summary_contract(record, rows):
    assert record['passed'] is True and record['actual_native_guards'] is True
    assert record['diagnostic_prefix'] is True and record['input_drift_waivers'] is False
    assert record['fresh_loader_allocator_caller_proof'] is False and record['full_setup'] is False and record['hardware'] is False
    assert record['cases'] == [[stage, case.name] for stage, case in matrix()]
    assert record['controls'] == rows and len(rows) == 36
    assert [(row['stage'], row['case']) for row in rows] == [(stage, case.name) for stage, case in matrix()]


def run_controls(pair, caller, directory, *, workers=4):
    pair, caller, directory = pair.resolve(), caller.resolve(), directory.resolve()
    assert all(path.is_relative_to(ROOT / '.local') for path in (pair, caller, directory))
    assert 1 <= workers <= 4
    snapshots = [caller / ('tail-prefix-' + str(stage)) / 'snapshot.json' for stage in range(3)]
    for stage, snapshot in enumerate(snapshots):
        record = json.loads(snapshot.read_bytes())
        assert record['origin'] == 'actual-provider-allocator-caller-before-PCIE-tail-' + str(stage)
        retained.verify_inputs(record['inputs'])
    initial = native_prefix_snapshot.source_inputs({})
    manifest_path = pair / 'manifest.json'
    manifest_name = str(manifest_path.relative_to(ROOT))
    manifest_hash = retained.captured.digest(manifest_path)
    summary = directory / 'result.json'
    cached = retained.read_receipt(summary) if summary.exists() else None
    if cached is not None:
        retained.verify_inputs(cached['artifacts'])
    directory.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment['PYTHONPATH'] = os.pathsep.join(str(ROOT / name) for name in
        ('.local/npu-reset/python-lib', 'tests/npu', 'tools'))
    environment['NPU_EMULATION_TIMEOUT_US'] = '60000000'

    def execute(stage, case):
        output = directory / ('stage-' + str(stage)) / case.name
        receipt = output / 'result.json'
        if receipt.exists(): return receipt
        assert cached is None and not output.exists(), ('incomplete-tail-case', stage, case.name)
        output.parent.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, '-u', '-B', str(ROOT / 'tests/npu/test_pcie_tail_native_controls.py'),
            '--pair', str(pair), '--snapshot', str(snapshots[stage]), '--output', str(output), '--case', case.name]
        with (output.parent / (case.name + '.log')).open('x') as stream:
            done = subprocess.run(command, cwd=ROOT, env=environment, stdout=stream,
                                  stderr=subprocess.STDOUT, timeout=10800)
        return receipt if done.returncode == 0 else None

    outcomes = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {pool.submit(execute, stage, case): (stage, case.name) for stage, case in matrix()}
        for future in as_completed(pending):
            identity = pending[future]
            try: outcomes[identity] = future.result()
            except Exception as error:
                outcomes[identity] = None
                print(json.dumps(dict(stage=identity[0], tail_fault=identity[1], error_type=type(error).__name__)), flush=True)
            if cached is None:
                print(json.dumps(dict(stage=identity[0], tail_fault=identity[1], passed=outcomes[identity] is not None)), flush=True)
    assert all(outcomes.values()), ('tail-native-controls-failed', [key for key, value in outcomes.items() if value is None])
    inputs, rows = initial, []
    for stage, case in matrix():
        receipt = outcomes[(stage, case.name)]
        record = retained.read_receipt(receipt)
        case_contract(record, stage, case)
        assert record['inputs'][manifest_name] == manifest_hash
        snapshot = snapshots[stage]
        assert record['inputs'][str(snapshot.relative_to(ROOT))] == retained.captured.digest(snapshot)
        relative = str(receipt.relative_to(ROOT))
        if cached is not None:
            assert cached['artifacts'].get(relative) == retained.captured.digest(receipt)
        for name, expected in record['inputs'].items():
            assert name not in inputs or inputs[name] == expected, ('tail-cohort-conflict', name)
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
        input_drift_waivers=False, fresh_loader_allocator_caller_proof=False, full_setup=False, hardware=False)
    summary_contract(result, rows)
    with summary.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--caller', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    result = run_controls(args.pair, args.caller, args.output, workers=args.workers)
    print(json.dumps(dict(passed=True, native_tail_fault_cases=len(result['cases']),
        input_drift_waivers=False, fresh_loader_allocator_caller_proof=False)), flush=True)


if __name__ == '__main__': main()
