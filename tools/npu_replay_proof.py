"""Recheck the archived evidence of one full-a RV32 invocation, without executing it."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE_LOCK = 'firmware/source-lock.json'
PAIR_FILES = {'code': 'CODE.bin', 'data': 'DATA.bin', 'manifest': 'manifest.json'}
JSON_LIMIT = 8 << 20


class QualificationError(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise QualificationError(reason)


def is_digest(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def path_under(base, spec, *, directory=False):
    path = base / spec
    require(path.is_relative_to(base) and path.resolve(strict=True) == path and
            (path.is_dir() if directory else path.is_file()), f'Unbound or aliased path: {path}')
    return path


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_receipt(path, expected=None):
    with path.open('rb') as stream:
        raw = stream.read(JSON_LIMIT + 1)
    pin = hashlib.sha256(raw).hexdigest()
    require(0 < len(raw) <= JSON_LIMIT, f'Invalid receipt size: {path}')
    require(expected is None or (is_digest(expected) and pin == expected), f'Receipt digest mismatch: {path}')
    value = json.loads(raw)
    require(isinstance(value, dict), f'Expected a JSON record: {path}')
    return value, pin


def read_pinned(path, pin):
    require(is_digest(pin), f'Missing independent receipt digest: {path}')
    return read_receipt(path, pin)


def recipe(profile):
    yield (1, 0, 0)  # OPEN
    for i in range(137 if profile == 2 else 139):
        yield (2, i, 0)
    for i in range(129):
        yield (3, i, 0)
    yield (4, 0, 0)  # HARDWARE (modeled gate)
    for generation in (1, 2):
        for session in range(1025):
            for op in (5, 6, 7):
                yield (op, session, generation)
    yield (8, 0, 0)  # CLOSE


def counts(profile):
    enroll = 137 if profile == 2 else 139
    total = enroll + 129 + 3 * 2050 + 3
    return {'1': 1, '2': enroll, '3': 129, '4': 1, '5': 2050, '6': 2050, '7': 2050, '8': 1,
            'positive_rpc': total, 'complete_journal_compares': total, 'complete_extent_compares': 2179,
            'complete_memory_compares': 4}


def verify_profile(directory, profile, summary):
    expected = iter(recipe(profile))
    totals = counts(profile)
    require(summary['profile'] == profile and summary['counts'] == totals and
            summary['actual_raw_boot'] is True and summary['modeled_MCU_results'] == 2050 and
            summary['whole_cold_setup'] is False and summary['hardware'] is False, 'Wrong replay profile summary')
    rpc = path_under(directory, 'rpc.jsonl')
    require(0 < rpc.stat().st_size <= 32 << 20, 'Invalid replay transcript size')
    hashes = ('request_sha256', 'reply_sha256', 'journal_sha256', 'broker_sha256', 'rolling_sha256')
    total = totals['positive_rpc']
    memory_schedule = [
        ('all-publications', total - 6152), ('generation-1', total - 3076),
        ('generation-2', total - 1), ('closing-retains-all-extents', total),
    ]
    seen = serial = 0
    memory = []
    last = None
    transcript = hashlib.sha256()
    with rpc.open('rb') as stream:
        for line in stream:
            require(line.endswith(b'\n'), 'Incomplete replay transcript line')
            transcript.update(line)
            row = json.loads(line)
            if 'operation' in row:
                key = tuple(row[k] for k in ('operation', 'argument', 'generation'))
                require(all(type(n) is int for n in key) and key == next(expected, None) and
                        type(row['sequence']) is int and row['sequence'] > serial and
                        row['modeled_MCU_result'] is (key[0] == 7) and all(is_digest(row.get(k)) for k in hashes),
                        f'Unordered or incomplete replay operation: profile {profile} row {seen}')
                seen += 1
                serial, last = row['sequence'], row
            if 'complete_DMA_bytes' in row:
                require(row['complete_DMA_bytes'] == 12582912 and is_digest(row.get('DMA_sha256')) and
                        is_digest(row.get('native_SRAM_sha256')), 'Incomplete full-memory comparison')
                memory.append((row['case'], seen, row['DMA_sha256']))
    require(seen == total and [(name, step) for name, step, _ in memory] == memory_schedule and
            memory[-1][2] == summary['complete_DMA_sha256'], 'Incomplete replay profile or full-memory schedule')
    require(last['broker_sha256'] == summary['final_broker_sha256'] == digest(path_under(directory, 'broker-final.bin')) and
            last['journal_sha256'] == summary['final_journal_sha256'] == digest(path_under(directory, 'oracle-journal-final.bin')) and
            last['rolling_sha256'] == summary['rolling_transcript_sha256'] and
            digest(path_under(directory, 'prefix.json')) == summary['prefix_receipt_sha256'], 'Replay final state differs')
    return dict(profile=profile, positive_rpc=total, transcript_sha256=transcript.hexdigest())


def verify_matrix(root, matrix_dir, result, inputs, pair_names, command):
    matrix, _ = read_pinned(path_under(matrix_dir, 'result.json'), result['matrix_sha256'])
    require(matrix['passed'] is True and matrix['actual_raw_pair'] is True and matrix['actual_mailbox_broker'] is True and
            matrix['actual_raw_boots'] == 3 and len(matrix['profiles']) == len(result['profiles']) == 3 and
            all(matrix[k] is False for k in ('hardware', 'whole_cold_setup', 'physical_IRQ_entry',
                                             'physical_retirement', 'MCU_authenticated')),
            'No successful full raw-pair matrix')
    adapter = matrix['native_cold_adapter']
    adapter_path = path_under(root / '.local', command[13]).relative_to(root).as_posix()
    host_evidence = path_under(root / '.local', command[7]).relative_to(root).as_posix()
    require(adapter['cold_observer_API'] == 8 and adapter['build_receipt'] == adapter_path and
            adapter['build_receipt_sha256'] == inputs[adapter_path] and
            adapter['per_engine_GIL_attached_emulation'] is True and adapter['instruction_and_timeout_limits_unchanged'] is True and
            matrix['host_evidence_sha256'] == inputs[host_evidence] and
            matrix['raw_boot_limits'] == dict(instructions_per_run=3000000, timeout_us=10000000) and
            matrix['per_RPC_limits'] == dict(instructions=100000000, timeout_us=60000000, unique_exact_blocks=16384),
            'Different replay limits or backend')
    require(all(matrix['inputs'].get(n) == inputs[n] for n in pair_names.values()) and
            all(inputs.get(n) == pin for n, pin in matrix['inputs'].items()), 'Matrix used a different input cohort')
    names = {p.relative_to(root).as_posix() for p in matrix_dir.rglob('*') if p.is_file()}
    require(not (matrix_dir / 'failure.json').exists() and names == set(matrix['artifacts']) |
            {(matrix_dir / 'result.json').relative_to(root).as_posix()}, 'Different matrix artifact set')
    for name, pin in matrix['artifacts'].items():
        path = path_under(root, name)
        require(path.is_relative_to(matrix_dir) and path.name != 'failure.json' and digest(path) == pin,
                f'Matrix artifact drift: {name}')
    summaries = []
    for profile in range(3):
        directory = path_under(matrix_dir, f'profile-{profile}', directory=True)
        summary, pin = read_receipt(path_under(directory, 'summary.json'))
        info = verify_profile(directory, profile, summary)
        require(summary == matrix['profiles'][profile] and
                result['profiles'][profile] == dict(info, summary_sha256=pin), 'Replay summary binding differs')
        summaries.append(result['profiles'][profile])
    total = {key: sum(counts(i)[key] for i in range(3)) for key in counts(0)}
    require(total['positive_rpc'] == 19261 and result['counts'] == matrix['counts'] == total, 'Replay matrix totals differ')
    return summaries


def terminal_inputs(root, start_path, start_pin, terminal_path, terminal_pin):
    start, _ = read_pinned(path_under(root, start_path), start_pin)
    observation = start['observation']
    inv, boot = observation['invocation'], observation['boot']
    plan_pin = start['private_receipts']['plan.json']
    require(isinstance(inv, str) and re.fullmatch('[0-9a-f]{32}', inv) and
            observation['unit']['InvocationID'] == inv and observation['expected_boot'] == boot and
            observation['status'] == 'live' and start['prior_results_stitched'] is False, 'Invalid original start receipt')
    if not (root / terminal_path).exists():
        raise QualificationError('The selected replay has no terminal receipt; an active or partial run cannot qualify')
    terminal_file = path_under(root / '.local', root / terminal_path)
    require(terminal_file.name == 'terminal.json', 'Expected the full-a terminal receipt')
    terminal, _ = read_pinned(terminal_file, terminal_pin)
    require(terminal['passed'] is True and terminal['service_result'] == 'success' and
            terminal['exit_code'] == 'exited' and terminal['exit_status'] == '0' and
            terminal['observed_unix_ns'] >= observation['observed_unix_ns'] and
            (terminal['invocation'], terminal['boot'], terminal['plan']) == (inv, boot, plan_pin),
            'The original invocation did not pass its terminal gate')
    control = terminal_file.parent
    plan, _ = read_pinned(path_under(control, 'plan.json'), plan_pin)
    controller, controller_pin = read_pinned(path_under(control, 'full-a-controller.json'), terminal['controller_sha256'])
    require((controller['invocation'], controller['boot'], controller['plan']) == (inv, boot, plan_pin) and
            controller['passed'] is True and controller['phase'] == 'full-a' and controller['returncode'] == 0 and
            controller['breach'] is False and controller['hardware'] is False, 'Replay controller mismatch')
    phase = plan['phases']['full-a']
    require(phase['unit'] == start['windows_wait_client']['unit'] and
            (plan['boot'], plan['head']) == (boot, start['source_commit']) and plan['old_transcripts_used'] is False,
            'Replay plan mismatch')
    output = path_under(root / '.local', phase['output'], directory=True)
    prep, _ = read_pinned(path_under(output, 'prepared.json'), start['private_receipts']['prepared.json'])
    inputs = plan['inputs']
    require((prep['boot'], prep['invocation'], prep['plan'], prep['head']) == (boot, inv, plan_pin, plan['head']) and
            prep['from_reset'] is True and prep['earlier_profile_outputs_used'] is False and
            len(inputs) == prep['retained_plan_inputs'] == start['private_plan_input_count'] == 345 and
            prep['runtime_bindings'] == plan['runtime_bindings'] == start['qualified_runtime_input_count'] == 330,
            'Different replay preparation')
    command = prep['command']
    require(command[0:4] == ['/usr/bin/python3', '-u', '-B', str(root / 'tests/npu/test_rro_wire_native_pair.py')] and
            command[4::2] == ['--pair', '--host-evidence', '--name', '--output-root', '--native-cold-receipt'] and
            len(command) == 14 and command[9] == 'matrix-r1' and command[11] == str(output / 'runs'),
            'Different replay command')
    pair = path_under(root / '.local', command[5], directory=True)
    pair_names = {key: (pair / name).relative_to(root).as_posix() for key, name in PAIR_FILES.items()}
    for name in pair_names.values():
        require(is_digest(inputs.get(name)), f'Replayed pair is unbound: {name}')
    return dict(invocation=inv, boot=boot, start_sha256=start_pin, plan_sha256=plan_pin, terminal_sha256=terminal_pin,
                controller_sha256=controller_pin, result_sha256=controller['result'], output=output,
                inputs=inputs, pair_names=pair_names, command=command)


def verify_replay(root, start_path, start_pin, terminal_path, terminal_pin, frozen, declarations):
    bound = terminal_inputs(root, start_path, start_pin, terminal_path, terminal_pin)
    inputs, output, pair_names = (bound[k] for k in ('inputs', 'output', 'pair_names'))
    retained = path_under(output, 'retained-inputs', directory=True)
    for name, pin in inputs.items():
        require(is_digest(pin) and declarations.get(name) == pin, f'World snapshot does not bind replay input: {name}')
        for directory in (retained, frozen):
            path = path_under(directory, name)
            require(not path.stat().st_mode & 0o222 and digest(path) == pin, f'Replay input drift: {path}')
    result, _ = read_pinned(path_under(output, 'result.json'), bound['result_sha256'])
    require(result['passed'] is True and result['from_reset'] is True and
            result['physical_retirement'] is False and result['hardware'] is False and
            (result['invocation'], result['plan']) == (bound['invocation'], bound['plan_sha256']), 'Not the same completed replay')
    matrix = path_under(output, 'runs/matrix-r1', directory=True)
    profiles = verify_matrix(root, matrix, result, inputs, pair_names, bound['command'])
    return {k: bound[k] for k in ('invocation', 'boot', 'start_sha256', 'plan_sha256', 'terminal_sha256',
                                 'controller_sha256', 'result_sha256')} | dict(
        matrix_sha256=result['matrix_sha256'], profiles=profiles, positive_rpc=19261, source_lock_sha256=inputs[SOURCE_LOCK],
        reverified_inputs=len(inputs), pair={key: inputs[name] for key, name in pair_names.items()})
