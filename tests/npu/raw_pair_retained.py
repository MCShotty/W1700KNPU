"""Broader raw regression using a verified actual caller, never a seeded lease."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys

import native_prefix_snapshot
import restore_native_prefix as captured
from test_desc10_retained_controls import CASES, expected_locks
from test_cold_txdone_native import SPACES
from pcie_tail_wire_native import MODEL_BAR_PAGES

ROOT = captured.ROOT


def verify_inputs(inputs):
    assert isinstance(inputs, dict) and inputs
    for name, expected in inputs.items():
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT) and path.is_file(), ('receipt-input-path', name)
        assert captured.digest(path) == expected, ('receipt-input-drift', name)


def read_receipt(path):
    path = path.resolve()
    assert path.is_relative_to(ROOT / '.local') and path.is_file()
    record = json.loads(path.read_bytes())
    assert record['passed'] is True, ('receipt-not-passed', str(path))
    verify_inputs(record['inputs'])
    return record


def case_receipt(receipt, case, snapshot):
    row = read_receipt(receipt)
    assert row['case'] == case.name and row['full_request_count'] == 512
    assert row['actual_native_guards'] is True and row['input_drift_waivers'] is False
    assert row['fresh_loader_allocator_caller_proof'] is False and row['diagnostic_prefix'] is True
    assert row['full_setup'] is False and row['hardware'] is False
    assert row['inputs'][str(snapshot.relative_to(ROOT))] == captured.digest(snapshot)
    assert row['original_stores'] == case.stores and row['packet_claims'] == 2560 + case.claims
    assert row['private_claims'] == case.claims and row['queue_publications'] == case.published
    assert row['original_lock_writes'] == len(expected_locks(case))
    return row


def run_controls(pair, snapshot, directory, *, workers=4):
    pair, snapshot, directory = pair.resolve(), snapshot.resolve(), directory.resolve()
    initial_inputs = native_prefix_snapshot.source_inputs({})
    assert directory.is_relative_to(ROOT / '.local') and 1 <= workers <= 4
    directory.mkdir(parents=True, exist_ok=True)
    summary = directory / 'result.json'
    if summary.exists():
        record = read_receipt(summary)
        assert record['cases'] == [case.name for case in CASES]
        verify_inputs(record['artifacts'])
        rows = []
        for case in CASES:
            receipt = directory / case.name / 'result.json'
            row = case_receipt(receipt, case, snapshot)
            relative = str(receipt.relative_to(ROOT))
            assert record['artifacts'].get(relative) == captured.digest(receipt), ('cached-case-artifact', case.name)
            rows.append(dict(case=case.name, original_stores=case.stores,
                             packet_claims=row['packet_claims'], receipt=relative))
        assert record['controls'] == rows, 'cached-control-row-mismatch'
        return record
    environment = dict(os.environ)
    environment['PYTHONPATH'] = os.pathsep.join(str(ROOT / name) for name in
        ('.local/npu-reset/python-lib', 'tests/npu', 'tools'))

    def execute(case):
        output = directory / case.name
        receipt = output / 'result.json'
        if receipt.exists():
            return receipt
        assert not output.exists(), ('incomplete-retained-case', case.name, str(output))
        command = [sys.executable, '-u', '-B', str(ROOT / 'tests/npu/test_desc10_retained_controls.py'),
                   '--pair', str(pair), '--snapshot', str(snapshot), '--output', str(output), '--case', case.name]
        with (directory / (case.name + '.log')).open('x') as stream:
            completed = subprocess.run(command, cwd=ROOT, env=environment, stdout=stream,
                                       stderr=subprocess.STDOUT, timeout=10800)
        return receipt if completed.returncode == 0 else None

    outcomes = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {pool.submit(execute, case): case.name for case in CASES}
        for job in as_completed(pending):
            name = pending[job]
            try:
                outcomes[name] = job.result()
            except Exception as error:
                outcomes[name] = None
                print(json.dumps(dict(retained_case=name, error_type=type(error).__name__)), flush=True)
            print(json.dumps(dict(retained_case=name, passed=outcomes[name] is not None)), flush=True)
    assert all(outcomes.values()), ('retained-native-controls-failed',
                                    [name for name, receipt in outcomes.items() if receipt is None])
    inputs, artifacts, rows = initial_inputs, {}, []
    for case in CASES:
        receipt = outcomes[case.name]
        row = case_receipt(receipt, case, snapshot)
        for name, expected in row['inputs'].items():
            assert name not in inputs or inputs[name] == expected, ('control-cohort-conflict', name)
            inputs[name] = expected
        rows.append(dict(case=case.name, original_stores=case.stores,
                         packet_claims=row['packet_claims'], receipt=str(receipt.relative_to(ROOT))))
    for path in directory.rglob('*'):
        if path.is_file():
            artifacts[str(path.relative_to(ROOT))] = captured.digest(path)
    inputs = native_prefix_snapshot.source_inputs(inputs)
    result = dict(passed=True, cases=[case.name for case in CASES], controls=rows, inputs=inputs,
                  artifacts=artifacts, workers=workers, full_request_count=512,
                  diagnostic_prefix=True, fresh_loader_allocator_caller_proof=False,
                  full_setup=False, hardware=False)
    with summary.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    return result


def tail_caller_contract(native, commands, pcie, inode_api):
    assert inode_api is not None, 'tail-INODE-enum-not-bound-to-sender'
    tx2 = [row['value'] for row in commands if (row['header'], row['api']) == (0x12, 19)]
    assert len(tx2) == 1 and tx2[0] in (0x200d4450, 0x200d8450)
    appended = commands[commands.index(pcie) + 1:]
    assert [(row['header'], row['api'], row['value']) for row in appended] == [
        (0x10, 0, 0x200d4580), (0x12, 0, tx2[0] + 0x110), (0x1f, 0, 0), (0x12, inode_api, 0)], 'tail-command-order'
    events = [(0x8400ba0c, 0x3e902cf0, 4, 0x200d4580), (0x8400ba18, 0x200d4588, 4, 1535),
        (0x8400ba24, 0x3e903904, 4, tx2[0] + 0x110), (0x8400ba30, tx2[0] + 0x118, 4, 1023),
        (0x8400b9ae, 0x200d45a8, 4, 255), (0x8400b9c0, 0x200d45b8, 4, 511),
        (0x8400b9d2, 0x200d45c8, 4, 1023), (0x8400b9ea, 0x2000a048, 4, 1535),
        (0x8400ba00, 0x200d4598, 4, 511)]
    for stage, row in enumerate(appended[:3]):
        assert row['pcie_tail_stage'] == stage and row['packet_claims'] == 3072 and row['page_claims'] == 1792
        reply = row['reply']['reply']
        assert reply['flags'] == 7 and reply['words'][14] == 0
        trace = row['pcie_tail_original_store_trace']
        count = 5 if stage == 2 else 2
        assert trace['validated'] is True and trace['actual_stores'] == trace['expected_stores'] == count
        assert [tuple(event) for event in trace['stores']] == events[stage * 2:stage * 2 + count], 'tail-original-effects'
        assert [tuple(write) for write in trace['ordered_lock_writes']] == [(0x1ec031c8, 4, 0x40), (0x1ec03248, 4, 0)]
        assert trace['guest_writes_by_observer'] is False
        spans = (*SPACES, *((base, 4096) for base in MODEL_BAR_PAGES))
        assert sorted((region['base'], region['bytes']) for region in trace['protected_memory']) == \
               sorted((hex(base), size) for base, size in spans), 'tail-protected-regions'
        assert trace['protected_bytes'] == sum(region['bytes'] for region in trace['protected_memory']) == 868352
        assert all(region['differing_bytes'] == 0 for region in trace['protected_memory'])
    boundary = appended[-1]
    assert boundary['error'] == -22 and boundary['actual_legacy_provider_framing'] is True
    assert boundary['native_legacy_denial'] is True and boundary['protected_memory_unchanged'] is True
    assert boundary['full_setup'] is False
    assert boundary['reply']['request'] == [0x12, inode_api, 0, 0, 0, 0]
    assert boundary['reply']['reply']['flags'] == 3 and not boundary['reply']['reply']['callbacks']
    senders = [row for row in native['cold'] if row.get('actual_pcie_tail_sender')]
    assert len(senders) == 1 and senders[0]['pcie_tail_stages'] == 3 and senders[0]['pcie_tail_original_stores'] == 9
    assert senders[0]['native_inode_legacy_denial'] is True and senders[0]['inode_api'] == inode_api
    assert senders[0]['full_setup'] is False


def caller_contract(caller, *, inode_api=None):
    native = caller['native']
    assert caller['passed'] is True and native['passed'] is True
    assert native['actual_c_linux_setup'] and native['actual_c_txrx_sender']
    assert native['synthetic_plan_identity_writes'] is False and native['post_load_elf_injection'] is False
    assert caller['native_enrollment_records'] == 15 and caller['rx_event_bytes'] == 8192
    commands = [row for row in native['cold'] if 'header' in row]
    shape = [(row['header'], row['api'], row['value']) for row in commands]
    for command in ((0x10, 1, 1536), (0x12, 1, 1024), (0x15, 1, 256),
                    (0x16, 1, 512), (0x17, 1, 1024), (0x1a, 1, 512), (0x1a, 0, 0x200d4590)):
        assert command in shape, ('missing-actual-caller-stage', command)
    assert [row['header'] & 15 for row in commands if row['api'] == 4] == [0, 2, 10, 11, 12, 8, 5, 7]
    assert [row['header'] & 15 for row in commands if row['api'] == 21] == [0, 5, 10, 2, 7, 12]
    assert all(row['packet_claims'] == 2560 and row['page_claims'] == 1792
               for row in commands if row['api'] == 21)
    pcie = [row for row in commands if (row['header'], row['api'], row['value']) == (0x1a, 0, 0x200d4590)]
    assert len(pcie) == 1 and pcie[0]['packet_claims'] == 3072 and pcie[0]['page_claims'] == 1792
    if native.get('pcie_tail_requested') is True:
        tail_caller_contract(native, commands, pcie[0], inode_api)
    else:
        assert commands[-1] is pcie[0], 'unexpected-command-after-RX-PCIE'
    senders = [row for row in native['cold'] if row.get('actual_rx_event_sender')]
    assert len(senders) == 1 and senders[0]['desc10_executed'] and senders[0]['rx_pcie_executed']
    assert senders[0]['full_setup'] is False
    assert len(native['workers']) == 7
    assert all(row['flags'] == 3 and not row['callbacks'] for row in native['strict_denials'])
    assert len(native['strict_denials']) == 3
    return native


def sender_provenance(caller):
    matches = []
    for name in caller['inputs']:
        if not name.endswith('/result.json'):
            continue
        path = (ROOT / name).resolve()
        record = json.loads(path.read_bytes())
        if record.get('completed_offload') is True and 'shared_sha256' in record:
            matches.append((path, read_receipt(path)))
    assert len(matches) == 1, ('actual-sender-receipt-count', len(matches))
    path, record = matches[0]
    shared = (ROOT / record['shared']).resolve()
    assert shared.is_relative_to(path.parent) and shared.is_file()
    assert captured.digest(shared) == record['shared_sha256'], 'actual-sender-binary-drift'
    binary = shared.with_name('host-test')
    assert captured.digest(binary) == record['binary_sha256'], 'actual-sender-matrix-binary-drift'
    return dict(receipt=str(path.relative_to(ROOT)), shared=str(shared.relative_to(ROOT)),
                expected_sha256=record['shared_sha256'],
                hash_origin='independent-preexisting-compiler-receipt',
                inputs={str(shared.relative_to(ROOT)): record['shared_sha256'],
                        str(binary.relative_to(ROOT)): record['binary_sha256']})


def check(pair, caller_receipt, destination, boot_controls):
    initial_inputs = native_prefix_snapshot.source_inputs({})
    caller = read_receipt(caller_receipt)
    sender = sender_provenance(caller)
    inode_api = None
    if caller['native'].get('pcie_tail_requested') is True:
        host = ctypes.CDLL(str(ROOT / sender['shared']))
        host.npu_host_inode_api.restype = ctypes.c_uint
        inode_api = host.npu_host_inode_api()
    native = caller_contract(caller, inode_api=inode_api)
    manifest_path = pair / 'manifest.json'
    manifest_name = str(manifest_path.relative_to(ROOT))
    assert caller['inputs'][manifest_name] == captured.digest(manifest_path)
    snapshot = caller_receipt.parent / 'desc10-prefix/snapshot.json'
    controls = run_controls(pair, snapshot, caller_receipt.parent / 'desc10-retained-controls')
    observed_path = caller_receipt.parent / 'desc10-observed.json'
    observed = json.loads(observed_path.read_bytes())
    assert observed['error'] == 0 and observed['packet_claims'] == 3072
    assert observed['protected_memory_matches'] is True
    trace = observed['original_store_trace']
    assert trace['validated'] is True and trace['actual_stores'] == trace['expected_stores'] == 25606
    assert trace['original_copied_store_sites'] == 20 and trace['guest_writes_by_observer'] is False
    assert sum(row['bytes'] for row in observed['memory_comparison']) == 856064
    assert all(row['differing_bytes'] == 0 for row in observed['memory_comparison'])
    early = boot_controls(pair)
    assert len(early) == 6
    inputs = initial_inputs
    for name, expected in caller['inputs'].items():
        assert name not in inputs or inputs[name] == expected, ('raw-producer-consumer-conflict', name)
        inputs[name] = expected
    for name, expected in sender['inputs'].items():
        assert name not in inputs or inputs[name] == expected, ('raw-sender-input-conflict', name)
        inputs[name] = expected
    for name, expected in controls['inputs'].items():
        assert name not in inputs or inputs[name] == expected, ('raw-cohort-conflict', name)
        inputs[name] = expected
    for path in (caller_receipt, observed_path, snapshot, caller_receipt.parent / 'desc10-retained-controls/result.json'):
        inputs[str(path.relative_to(ROOT))] = captured.digest(path)
    inputs = native_prefix_snapshot.source_inputs(inputs)
    verify_inputs(inputs)
    return dict(passed=True, broader_raw_regression_passed=True, full_nominal=True,
        full_request_count=512, raw_pair=True, post_load_elf_injection=False,
        actual_caller_receipt=str(caller_receipt.relative_to(ROOT)),
        actual_sender_provenance=sender,
        retained_packet_claims=3072, retained_ba_claims=1792,
        boot_controls=early, controls=controls['controls'], strict_denials=native['strict_denials'],
        original_store_trace=trace, initial_test_active_writes=False, initial_direct_owner_init=False,
        later_txdone_lease_modeled=False, negative_snapshot_restores=True,
        fresh_nominal_caller=True, full_setup=False, full_npu_goal_complete=False, hardware=False,
        pair_manifest_sha256=captured.digest(manifest_path), inputs=inputs,
        limits=['Fresh nominal execution is supplied by the strictly current actual allocator/provider/host-caller receipt.',
                'Six raw boot controls, actual2560 RX/1792 BA claims, eight descriptor getters, all six API21 phases, API22, full512 DESC10 and RX PCIe are required.',
                'All eight full-size fault classes execute original guarded instructions from a hash-bound actual prefix; those restores are diagnostic, not fresh boot.',
                'The host sender binary is additionally bound to its independent compiler receipt; that binary hash was not duplicated in prefix.inputs.',
                'The original25606 stores, ordered locks, exact856064 protected bytes and2076 PKT bytes are checked without a forged lease or guard bypass.',
                'Earlier producer negative suites may be explicitly skipped; this is not a complete native initialization or fault matrix.',
                'Remaining native PCIe/INODE/IRQ, full hot datapath/worker/lifecycle and physical ownership/drains/recovery/clients remain open.'])
