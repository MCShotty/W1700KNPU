#!/usr/bin/env python3
"""Freeze and run the promoted W1700K RV32 replay without modifying the baseline."""
import argparse
from contextlib import ExitStack
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time

import npu_isolated_world as world
import npu_replay_proof as proof
import npu_storage_budget as storage
import npu_successor_sources as sources
import npu_validation_capsule as capsule
from npu_world_stream_host import save

ROOT = world.ROOT
LOCAL = ROOT / '.local'
SCRATCH = LOCAL / 'npu-build-scratch/native-c2'
CONTROL = LOCAL / 'npu-successor-replays'
CAP = 400 << 20
RESERVE = 2 << 30
MAX_OUTPUT = 512 << 20
TIME_LIMIT = 24 * 60 * 60
BASE_CAPSULE = LOCAL / 'npu-validation-capsules/world-txp-20261118-a/receipt.json'
BASE_CAPSULE_PIN = '3d166089dbb5a89650521a1d7331f8e2ce967472ed67ed1eebe0af50362caff3'
BASE_START = ROOT / 'research/checkpoints/2026-11-18-npu-txp-current-target/RV32-STARTED.json'
BASE_START_PIN = '7742f7d08849a7d238b72367d45a9a161a3aea017826b044eb9662871c87fcff'
BASE_TERMINAL = LOCAL / 'npu-rv32-fresh-20261118/terminal.json'
BASE_TERMINAL_PIN = 'e5214834c100cd4855941026d2ee781ced3603be6f772a00d3075341e6ab0d71'
RUNTIME_TABLE = (SCRATCH / 'native-memory-hook-full-q16/retained-inputs.json').relative_to(ROOT).as_posix()
DROPPED = {'.local/npu-native-memory-hook-20261027/' + name for name in ('post-q15.json', 'full_q16.py')}
REPLAY_KEEP = ('.build/openwrt/dl/', '.local/npu-reset/python-lib/',
               '.local/npu-barrier/lld/usr/lib/llvm-21/')
if not __debug__:
    raise RuntimeError('Successor replay validation requires Python assertions')


def command(args, timeout=45):
    return subprocess.check_output(args, text=True, cwd=ROOT, timeout=timeout).strip()


def read_json(path):
    return json.loads(path.read_bytes())


def boot():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def locations(name):
    proof.require(re.fullmatch('[a-z][a-z0-9-]{0,27}', name), 'Invalid new replay name')
    return CONTROL / name, SCRATCH / ('rv32-' + name), f'w1700k-npu-{name}.service'


def acquire_writers(stack):
    for path in (LOCAL / 'npu-storage-budget.lock', SCRATCH / '.world-storage.lock'):
        fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
        stack.callback(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def admission(preparing=False):
    marker = proof.path_under(SCRATCH, 'storage-marker-q1.json')
    proof.require(proof.digest(marker) == '88204019cf6b25344f75c97fdca80954018427519f8d023c46edb7490a9e2ebf'
                  and SCRATCH.stat().st_dev != ROOT.stat().st_dev, 'Wrong replay scratch filesystem')
    mount, = json.loads(command(['findmnt', '--json', '--target', SCRATCH,
                                 '--output', 'source,fstype,uuid,options']))['filesystems']
    proof.require(mount['fstype'] == 'ext4' and mount['uuid'] == 'b0b1bc48-d684-4090-a8cf-1ecb2939c36d'
                  and {'rw', 'nosuid', 'nodev'} <= set(mount['options'].split(',')),
                  'Native C-backed scratch mount differs')
    root = storage.observe(ROOT)
    scratch = storage.windows_query('W1700K-BuildScratch-20261021')
    proof.require(root['host']['vhd_path'] == r'D:\WSL\Ubuntu\ext4.vhdx' and scratch['vhd_path'] ==
                  r'C:\Users\captain\W1700K-BuildScratch\2026-10-21-native-wsl-v1\distro\ext4.vhdx',
                  'Changed Windows backing volumes')
    win = int(command(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                       '[Math]::Min([long](Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory * 1024,'
                       ' [long](Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory).AvailableBytes)']))
    guest = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                     if line.startswith('MemAvailable:'))) * 1024
    usage = shutil.disk_usage(SCRATCH)
    budgets = {
        'C': storage.evaluate(dict(host=scratch, guest=dict(free_bytes=usage.free, total_bytes=usage.total)),
            dict(snapshot=0, cache=0, overlay=0, output=MAX_OUTPUT, margin=RESERVE)),
        'D': storage.evaluate(root, dict(snapshot=(1 << 30) if preparing else 0, cache=0,
                                       overlay=0, output=64 << 20, margin=RESERVE)),
    }
    proof.require(min(win, guest) >= RESERVE + CAP and all(row['passed'] for row in budgets.values()),
                  'Replay memory or backing volume budget was not met')
    return dict(windows_available_bytes=win, guest_available_bytes=guest, budgets=budgets,
                scratch_mount=mount, memory_max_bytes=CAP, memory_swap_max_bytes=0, hardware=False)


def replay_runtime(prior, reuse):
    table, _ = proof.read_pinned(proof.path_under(reuse['root'], RUNTIME_TABLE), prior['inputs'][RUNTIME_TABLE])
    by_name = {Path(name).relative_to(ROOT).as_posix(): row['sha256'] for name, row in table.items()}
    proof.require(len(by_name) == 332 and DROPPED <= by_name.keys(), 'Unexpected reference runtime roster')
    runtime = {name: pin for name, pin in by_name.items() if name not in DROPPED}
    proof.require(len(runtime) == 330 and all(reuse['files'].get(name) == prior['inputs'].get(name) == pin
                                              for name, pin in runtime.items()), 'Reference runtime differs')
    return runtime


def map_sources(tracked, runtime, reuse, authority, checked, contract, release):
    files, selected = dict(tracked), {}

    def add(name, pin, path):
        proof.require(not Path(name).is_absolute() and '..' not in Path(name).parts and
                      Path(name).as_posix() == name and proof.is_digest(pin), f'Invalid bound source: {name}')
        if name not in files:
            files[name], selected[name] = pin, path
        else:
            proof.require(files[name] == pin, f'Conflicting capsule source: {name}')

    kernel_recipe = f'.build/merged-openwrt/target/linux/generic/kernel-{release.rsplit(".", 1)[0]}'
    for name, pin in reuse['files'].items():
        if name in runtime or name == kernel_recipe or name == proof.REPLAY_BWRAP or name.startswith(REPLAY_KEEP):
            add(name, pin, proof.path_under(reuse['root'], name))
    proof.require(set(runtime) <= files.keys() and kernel_recipe in files and proof.REPLAY_BWRAP in files,
                  'Incomplete world or replay inputs in the reference capsule')
    for name, pin in (checked['inputs'] | checked['artifacts'] | {checked['receipt']: checked['receipt_sha256']}).items():
        add(name, pin, proof.path_under(authority, name))
    proof.require(all(files.get(name) == tracked.get(name) == pin for name, pin in contract['files'].items()
                      if name.startswith('firmware/')),
                  'The tracked source does not entirely match the promoted authority')
    return files, selected


def prepare(args):
    control, output, unit = locations(args.name)
    target = capsule.CAPSULES / args.name
    proof.require(not any(os.path.lexists(path) for path in (target, control, output)),
                  'The replay name already has a capsule, control record or output')
    head = command(['git', 'rev-parse', 'HEAD'])
    proof.require(head == command(['git', 'rev-parse', 'origin/main']) and
                  not command(['git', 'status', '--porcelain']), 'Freeze only a clean published canonical tree')
    authority = proof.path_under(LOCAL, ROOT / args.authority, directory=True)
    contract, pin, lock = sources.verify_authority(authority, args.contract_sha256)
    checked = sources.verify_producer(authority, contract, pin, args.producer, args.producer_sha256)
    proof.require(proof.digest(ROOT / sources.SOURCE_LOCK) == contract['source_lock_sha256'] and
                  proof.digest(ROOT / sources.CONFIG) == contract['config_sha256'], 'Successor is not the active lock')
    proof.require(proof.digest(proof.path_under(capsule.CAPSULES, BASE_CAPSULE)) == BASE_CAPSULE_PIN,
                  'Original world capsule pin differs')
    prior = proof.terminal_inputs(ROOT, BASE_START, BASE_START_PIN, BASE_TERMINAL, BASE_TERMINAL_PIN)
    with ExitStack() as stack:
        acquire_writers(stack)
        capacity = admission(preparing=True)
        reuse = capsule.load_reuse_snapshot(ROOT, BASE_CAPSULE)
        proof.require(reuse['receipt_sha256'] == BASE_CAPSULE_PIN, 'Baseline capsule changed before reuse')
        runtime = replay_runtime(prior, reuse)
        tracked = {}
        for name in filter(None, command(['git', 'ls-files', '-z']).split('\0')):
            capsule.add_file(ROOT, tracked, name)
        files, selected = map_sources(tracked, runtime, reuse, authority, checked, contract, lock['kernel'])
        frozen = target / 'root'
        total = capsule.copy_files(ROOT, frozen, files, reuse, selected_sources=selected)
        placeholder = frozen / output.relative_to(ROOT)
        proof.require(not placeholder.exists(), 'Replay output overlaps a frozen input')
        placeholder.mkdir(parents=True)
        after = capsule.load_reuse_snapshot(ROOT, BASE_CAPSULE)
        proof.require(reuse['metadata'] == after['metadata'] and after['receipt_sha256'] == BASE_CAPSULE_PIN and
                      head == command(['git', 'rev-parse', 'HEAD']) and
                      not command(['git', 'status', '--porcelain']), 'Baseline or promoted source moved while freezing')
        shared = [name for name in files if name in reuse['files'] and
                  (frozen / name).samefile(reuse['root'] / name)]
        shared_bytes = sum((frozen / name).stat().st_size for name in shared)
        proof.require(total - shared_bytes <= 1 << 30, 'Capsule exceeded its admitted new payload size')
        receipt = target / 'receipt.json'
        save(receipt, dict(format='npu-validation-capsule-v1', preservation_verified=True, source_root=str(ROOT),
             input_root=str(frozen), files=files, file_count=len(files), bytes=total, source_commit=head,
             tracked_dirty=False, sources_read_only=True, original_receipts_rewritten=False,
             producer_sha256=checked['receipt_sha256'], source_contract_sha256=pin, hardware=False,
             replay_output_mountpoint=output.relative_to(ROOT).as_posix(),
             materialization=dict(strategy='selected-successor-sources-and-verified-readonly-baseline-links',
                shared_readonly_files=len(shared), shared_readonly_bytes=shared_bytes,
                independently_copied_files=len(files) - len(shared), copied_regular_file_payload_bytes=total - shared_bytes,
                prior_receipt_sha256=BASE_CAPSULE_PIN, prior_file_content_modes_ownership_mtime_unchanged=True,
                shared_inode_link_counts_ctime_atime_not_preserved=bool(shared))))
        capsule_pin = proof.digest(receipt)
        frozen, _ = world.snapshot(receipt)
        sources.verify_producer(frozen, contract, pin, Path(checked['receipt']), checked['receipt_sha256'])
        controls = {name: files[name] for name in (sources.SOURCE_LOCK, sources.CONFIG, sources.CONTRACT,
            checked['receipt'], proof.REPLAY_LAUNCHER, proof.REPLAY_CHECKER, proof.REPLAY_BWRAP)}
        argv = [str(output / 'runs') if n == 11 else arg for n, arg in enumerate(prior['command'])]
        plan = dict(format=proof.SUCCESSOR_PLAN, head=head, boot=boot(), capsule=str(receipt),
            capsule_sha256=capsule_pin, runtime_bindings=len(runtime), runtime_inputs=runtime, inputs=runtime | controls,
            source_lock_sha256=controls[sources.SOURCE_LOCK], config_sha256=controls[sources.CONFIG],
            source_contract_sha256=controls[sources.CONTRACT], producer=checked['receipt'],
            producer_sha256=checked['receipt_sha256'], launcher_sha256=controls[proof.REPLAY_LAUNCHER],
            checker_sha256=controls[proof.REPLAY_CHECKER], bwrap_sha256=controls[proof.REPLAY_BWRAP],
            phases={'full-a': dict(unit=unit, output=str(output), command=argv)},
            old_transcripts_used=False, from_reset=True, hardware=False)
        proof.plan_cohort(plan)
        control.mkdir(parents=True)
        save(control / 'admission-preparation.json', capacity)
        save(control / 'plan.json', plan)
    print(json.dumps(dict(capsule=str(receipt), capsule_sha256=capsule_pin, source_commit=head,
          replay_plan=str(control / 'plan.json'), plan_sha256=proof.digest(control / 'plan.json'),
          reused_bytes=shared_bytes, new_payload_bytes=total - shared_bytes, runtime_inputs=len(runtime))), flush=True)


def load_plan(name, pin):
    control, output, unit = locations(name)
    plan, _ = proof.read_pinned(proof.path_under(CONTROL, control / 'plan.json'), pin)
    proof.plan_cohort(plan)
    proof.require(plan['boot'] == boot() and plan['phases']['full-a']['unit'] == unit and
                  plan['phases']['full-a']['output'] == str(output) and plan['old_transcripts_used'] is False,
                  'Replay plan boot, unit, or output differs')
    argv = plan['phases']['full-a']['command']
    proof.require(len(argv) == 14 and argv[:4] == ['/usr/bin/python3', '-u', '-B',
                  str(ROOT / 'tests/npu/test_rro_wire_native_pair.py')] and
                  argv[4::2] == ['--pair', '--host-evidence', '--name', '--output-root', '--native-cold-receipt']
                  and argv[9] == 'matrix-r1' and argv[11] == str(output / 'runs'), 'Different full replay command')
    return control, output, unit, plan


def unit_state(unit):
    properties = ('InvocationID', 'MainPID', 'ActiveState', 'SubState', 'ControlGroup',
                  'MemoryMax', 'MemorySwapMax', 'CPUUsageNSec')
    rows = command(['systemctl', '--user', 'show', unit, *[item for key in properties for item in ('-p', key)]])
    return dict(row.split('=', 1) for row in rows.splitlines())


def verify_service(unit):
    state = unit_state(unit)
    invocation = os.environ.get('INVOCATION_ID')
    proof.require(invocation and re.fullmatch('[0-9a-f]{32}', invocation) and state['InvocationID'] == invocation and
                  int(state['MainPID']) == os.getpid() and state['ActiveState'] in ('active', 'activating') and
                  state['MemoryMax'] == str(CAP) and state['MemorySwapMax'] == '0' and
                  os.getpriority(os.PRIO_PROCESS, 0) >= 19, 'Expected a fresh bounded systemd user service')
    group = Path('/sys/fs/cgroup') / state['ControlGroup'].lstrip('/')
    proof.require((group / 'memory.max').read_text().strip() == str(CAP) and
                  (group / 'memory.swap.max').read_text().strip() == '0', 'Unexpected actual cgroup limits')
    return state


INSIDE = '''
import json
import os
from pathlib import Path
import sys
import npu_isolated_world as world

expected = json.loads(sys.argv[1])
assert all(value != expected['parent_namespaces'][name] for name, value in world.namespaces().items())
assert os.statvfs(world.ROOT).f_flag & os.ST_RDONLY
assert not os.statvfs(expected['output']).f_flag & os.ST_RDONLY
assert world.digest(world.ROOT / 'firmware/source-lock.json') == expected['source_lock_sha256']
os.execv(sys.argv[2], sys.argv[2:])
'''


def size(root):
    amount = 0
    for base, _, names in os.walk(root, followlinks=False):
        for name in names:
            path = Path(base) / name
            if not path.is_symlink():
                try:
                    amount += path.stat().st_size
                except FileNotFoundError:
                    pass
    return amount


def stop_worker(worker):
    if worker.poll() is not None:
        return
    os.killpg(worker.pid, signal.SIGTERM)
    try:
        worker.wait(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(worker.pid, signal.SIGKILL)
        worker.wait(timeout=15)


def execute(control, output, unit, plan, plan_pin, frozen):
    state = verify_service(unit)
    cap_pin, inputs, command_line = plan['capsule_sha256'], plan['inputs'], plan['phases']['full-a']['command']
    prepared = output / 'prepared.json'
    save(prepared, dict(head=plan['head'], plan=plan_pin, invocation=state['InvocationID'], boot=plan['boot'],
        runtime_bindings=330, retained_plan_inputs=len(inputs), command=command_line, from_reset=True,
        earlier_profile_outputs_used=False, capsule_sha256=cap_pin, network_isolated=True))
    need = output / 'retained-inputs'
    for name, pin in inputs.items():
        source = proof.path_under(frozen, name)
        proof.require(not source.stat().st_mode & 0o222 and proof.digest(source) == pin, f'Replay input changed: {name}')
        target = need / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        proof.require(proof.digest(target) == pin and not target.stat().st_mode & 0o222, f'Retained bytes differ: {name}')
    (output / 'runs').mkdir()
    runner = proof.path_under(frozen, proof.REPLAY_BWRAP)
    proof.require(proof.digest(runner) == plan['bwrap_sha256'], 'Selected isolated launcher differs')
    context = dict(parent_namespaces=world.namespaces(), output=str(output), source_lock_sha256=plan['source_lock_sha256'])
    argv = [runner, '--unshare-all', '--ro-bind', '/', '/', '--ro-bind', frozen, ROOT,
            '--bind', output, output, '--tmpfs', '/tmp', '--proc', '/proc', '--dev', '/dev',
            '--new-session', '--die-with-parent', '--clearenv',
            '--setenv', 'PATH', '/usr/local/bin:/usr/bin:/bin', '--setenv', 'LANG', 'C.UTF-8',
            '--setenv', 'LC_ALL', 'C', '--setenv', 'TZ', 'UTC',
            '--setenv', 'NPU_EMULATION_TIMEOUT_US', '10000000',
            '--setenv', 'PYTHONPATH', ':'.join(str(ROOT / name) for name in
                ('.local/npu-reset/python-lib', 'tests/npu', 'tests', 'tools')),
            '/usr/bin/python3', '-u', '-B', '-c', INSIDE, json.dumps(context), *command_line]
    matrix = output / 'runs/matrix-r1'
    first_rpc = matrix / 'profile-0/rpc.jsonl'
    started = control / 'started.json'
    deadline = time.monotonic() + TIME_LIMIT
    breach = False
    with (output / 'replay.log').open('xb') as log:
        worker = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT,
                                  stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            while worker.poll() is None:
                if time.monotonic() >= deadline or size(output) > MAX_OUTPUT or (control / 'CANCEL').exists():
                    breach = True
                    break
                if not started.exists() and first_rpc.exists() and first_rpc.stat().st_size:
                    live = verify_service(unit)
                    if worker.poll() is None:
                        save(started, dict(source_commit=plan['head'], prior_results_stitched=False,
                            private_plan_input_count=len(inputs), qualified_runtime_input_count=330, capsule_sha256=cap_pin,
                            observation=dict(invocation=live['InvocationID'], boot=plan['boot'], expected_boot=plan['boot'],
                                             status='live', observed_unix_ns=time.time_ns(), unit=live),
                            private_receipts={'plan.json': plan_pin, 'prepared.json': proof.digest(prepared)},
                            systemd_unit=unit, hardware=False))
                        print(json.dumps(dict(active=True, start=str(started), invocation=live['InvocationID'],
                                             start_sha256=proof.digest(started))), flush=True)
                time.sleep(3)
        finally:
            stop_worker(worker)
    result = output / 'result.json'
    if worker.returncode == 0 and not breach and started.is_file():
        matrix_receipt = proof.path_under(matrix, 'result.json')
        completed, matrix_pin = proof.read_receipt(matrix_receipt)
        profiles = []
        for profile in range(3):
            path = proof.path_under(matrix, f'profile-{profile}', directory=True)
            summary, summary_pin = proof.read_receipt(proof.path_under(path, 'summary.json'))
            profiles.append(dict(proof.verify_profile(path, profile, summary), summary_sha256=summary_pin))
        saved = dict(passed=True, invocation=state['InvocationID'], from_reset=True,
                     plan=plan_pin, profiles=profiles, counts=completed['counts'],
                     matrix_sha256=matrix_pin, hardware=False, physical_retirement=False)
        pair = Path(command_line[5])
        pair_names = {key: (pair / name).relative_to(ROOT).as_posix() for key, name in proof.PAIR_FILES.items()}
        proof.verify_matrix(ROOT, matrix, saved, inputs, pair_names, command_line)
        proof.require(all(proof.digest(proof.path_under(root, name)) == pin for name, pin in inputs.items()
                          for root in (need, frozen)), 'Replay bytes changed during execution')
        save(result, saved)
    passed = result.is_file() and not breach and worker.returncode == 0
    save(control / 'full-a-controller.json', dict(passed=passed, phase='full-a', plan=plan_pin,
         invocation=state['InvocationID'], boot=plan['boot'], returncode=worker.returncode, breach=breach,
         output_bytes=size(output), result=proof.digest(result) if passed else None, hardware=False))
    return 0 if passed else 1


def run(name, pin):
    control, output, unit, plan = load_plan(name, pin)
    verify_service(unit)
    with ExitStack() as stack:
        acquire_writers(stack)
        capacity = admission()
        proof.require(not os.path.lexists(output) and not (control / 'CANCEL').exists(),
                      'Replay output already exists or launch was canceled')
        receipt = proof.path_under(capsule.CAPSULES, Path(plan['capsule']))
        record, _ = proof.read_pinned(receipt, plan['capsule_sha256'])
        frozen, _ = world.snapshot(receipt)
        proof.require(record['source_commit'] == plan['head'] and record['tracked_dirty'] is False and
                      record['producer_sha256'] == plan['producer_sha256'] and
                      record['source_contract_sha256'] == plan['source_contract_sha256'] and
                      proof.digest(ROOT / proof.REPLAY_LAUNCHER) == plan['launcher_sha256'] and
                      proof.digest(ROOT / proof.REPLAY_CHECKER) == plan['checker_sha256'] and
                      proof.digest(ROOT / proof.SOURCE_LOCK) == plan['source_lock_sha256'] and
                      all(record['files'].get(name) == pin for name, pin in plan['inputs'].items()),
                      'The worktree or capsule is not the planned successor cohort')
        placeholder = output.relative_to(ROOT).as_posix()
        proof.require(record['replay_output_mountpoint'] == placeholder and
                      not any(proof.path_under(frozen, placeholder, directory=True).iterdir()),
                      'Replay output mount point is not blank')
        output.mkdir()
        save(control / 'admission-runtime.json', capacity)
        return execute(control, output, unit, plan, pin, frozen)


def terminal(name, pin):
    control, output, _, plan = load_plan(name, pin)
    invocation = os.environ.get('INVOCATION_ID')
    proof.require(invocation and re.fullmatch('[0-9a-f]{32}', invocation), 'Terminal observation requires systemd')
    row = dict(observed_unix_ns=time.time_ns(), boot=plan['boot'], invocation=invocation, plan=pin,
               service_result=os.environ.get('SERVICE_RESULT'), exit_code=os.environ.get('EXIT_CODE'),
               exit_status=os.environ.get('EXIT_STATUS'), passed=False)
    controller, result = control / 'full-a-controller.json', output / 'result.json'
    if controller.is_file():
        linked, controller_pin = proof.read_receipt(controller)
        row['controller_sha256'] = controller_pin
        if result.is_file() and linked['passed']:
            finished, _ = proof.read_pinned(result, linked['result'])
            row['passed'] = (linked['invocation'] == finished['invocation'] == invocation and
                             linked['plan'] == finished['plan'] == pin and finished['passed'] is True and
                             (row['service_result'], row['exit_code'], row['exit_status']) == ('success', 'exited', '0'))
    save(control / 'terminal.json', row)
    print(json.dumps(row), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    prep = actions.add_parser('prepare')
    for name in ('authority', 'producer'):
        prep.add_argument('--' + name, type=Path, required=True)
    for name in ('contract', 'producer'):
        prep.add_argument('--' + name + '-sha256', required=True)
    for name in ('run', 'terminal'):
        actions.add_parser(name).add_argument('--plan-sha256', required=True)
    for action in actions.choices.values():
        action.add_argument('--name', required=True)
    args = parser.parse_args()
    try:
        proof.require(os.getuid() == 1000, 'Run as the unprivileged workspace user')
        if args.action == 'prepare':
            prepare(args)
        elif args.action == 'run':
            raise SystemExit(run(args.name, args.plan_sha256))
        else:
            terminal(args.name, args.plan_sha256)
    except (AssertionError, KeyError, OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f'successor replay: {error}\n')


if __name__ == '__main__':
    main()
