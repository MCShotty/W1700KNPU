#!/usr/bin/env python3
"""Hash-preserved validation inputs at their original path in a private mount."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
CAPSULES = ROOT / '.local/npu-validation-capsules'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_file(root, name):
    relative = Path(name)
    assert name and not relative.is_absolute() and '..' not in relative.parts, ('unsafe-capsule-path', name)
    source = (root / relative).resolve()
    assert source.is_relative_to(root) and source.is_file(), ('capsule-source-path', name)
    return source


def add_file(root, files, name, expected=None):
    source = source_file(root, name)
    actual = digest(source)
    assert expected is None or actual == expected, ('capsule-source-drift', name)
    assert name not in files or files[name] == actual, ('capsule-source-conflict', name)
    files[name] = actual


def receipt_inputs(record):
    if isinstance(record, dict):
        for key, value in record.items():
            if key in ('inputs', 'artifacts', 'host_inputs') and isinstance(value, dict) and value and all(
                    isinstance(item, str) and re.fullmatch('[0-9a-f]{64}', item) for item in value.values()):
                yield value
            else:
                yield from receipt_inputs(value)
    elif isinstance(record, list):
        for value in record: yield from receipt_inputs(value)


def copy_files(root, target, files):
    assert not target.exists() and target.resolve().is_relative_to(root)
    for name, expected in files.items():
        assert digest(source_file(root, name)) == expected, ('capsule-pre-copy-drift', name)
    target.mkdir(parents=True)
    total = 0
    for name, expected in sorted(files.items()):
        source, output = source_file(root, name), target / name
        assert output.resolve().is_relative_to(target) and not source.is_relative_to(target)
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, output)
        assert digest(output) == digest(source) == expected, ('capsule-copy-drift', name)
        output.chmod(stat.S_IMODE(output.stat().st_mode) & ~0o222)
        total += output.stat().st_size
    return total


def create(args):
    destination = CAPSULES / args.name
    assert not destination.exists()
    files, queue, expanded = {}, [], set()
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    for name in filter(None, tracked): add_file(ROOT, files, name)
    add_file(ROOT, files, str(Path(__file__).relative_to(ROOT)))
    for path in args.receipt:
        path = path.resolve()
        name = str(path.relative_to(ROOT))
        record = json.loads(path.read_bytes())
        assert record.get('passed') is True, ('capsule-receipt-not-passed', name)
        add_file(ROOT, files, name)
        queue.append(path)
    for snapshot in args.snapshot:
        snapshot = snapshot.resolve()
        record = json.loads(snapshot.read_bytes())
        assert record['format'] == 'npu-native-prefix-diagnostic-v1'
        assert record['fresh_loader_allocator_caller_proof'] is False
        add_file(ROOT, files, str(snapshot.relative_to(ROOT)))
        for item in [*record['regions'], record['context']]:
            assert Path(item['file']).name == item['file']
            add_file(ROOT, files, str((snapshot.parent / item['file']).relative_to(ROOT)), item['sha256'])
        queue.append(snapshot)
    for path in [*args.include, ROOT / '.local/npu-reset/python-lib']:
        path = path.resolve()
        assert path.is_relative_to(ROOT)
        for item in path.rglob('*') if path.is_dir() else [path]:
            if item.is_file(): add_file(ROOT, files, str(item.relative_to(ROOT)))
    while queue:
        path = queue.pop()
        if path in expanded: continue
        expanded.add(path)
        for mapping in receipt_inputs(json.loads(path.read_bytes())):
            for name, expected in mapping.items():
                add_file(ROOT, files, name, expected)
                if Path(name).suffix == '.json': queue.append(ROOT / name)
    total = copy_files(ROOT, destination / 'root', files)
    owner = pwd.getpwuid(ROOT.stat().st_uid)
    environment = {key: os.environ[key] for key in
        ('PATH', 'LANG', 'LC_ALL', 'TZ', 'ASAN_OPTIONS', 'UBSAN_OPTIONS', 'UNICORN_LIB_PATH') if key in os.environ}
    record = dict(format='npu-validation-capsule-v1', preservation_verified=True, source_root=str(ROOT),
        input_root=str(destination / 'root'), files=files, file_count=len(files), bytes=total,
        source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        tracked_dirty=subprocess.run(['git', 'diff', '--quiet', 'HEAD'], cwd=ROOT).returncode != 0,
        uid=owner.pw_uid, gid=owner.pw_gid, user=owner.pw_name, home=owner.pw_dir, environment=environment,
        sources_read_only=True, original_receipts_rewritten=False, complete_executable_environment=False,
        replay_verified=False, full_setup=False, full_npu_goal_complete=False, hardware=False,
        limits=['Copies tracked source, declared receipt inputs/artifacts, selected captures and the existing Python dependency directory.',
                'Host interpreter, compiler and system libraries remain external; this is not a complete portable environment.',
                'A separate private-namespace replay must pass before this is considered an execution copy.',
                'Only the named older candidate is validated; this never qualifies later changes on main.'])
    output = destination / 'receipt.json'
    with output.open('x') as stream: stream.write(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(preservation_verified=True, files=len(files), bytes=total,
        receipt=str(output.relative_to(ROOT)), sha256=digest(output))), flush=True)


def inner(args):
    assert os.geteuid() == 0
    current = os.readlink('/proc/self/ns/mnt')
    assert current != args.parent_ns, 'refusing-mount-without-new-namespace'
    record = json.loads(args.receipt.read_bytes())
    canonical, frozen = Path(record['source_root']), Path(record['input_root'])
    assert canonical == ROOT and frozen.is_relative_to(CAPSULES)
    source_inode = (frozen.stat().st_dev, frozen.stat().st_ino)
    with args.proof.open('x') as stream:
        subprocess.run(['mount', '--make-rprivate', '/'], check=True)
        subprocess.run(['mount', '--bind', str(frozen), str(canonical)], check=True)
        os.chdir(canonical)
        assert (canonical.stat().st_dev, canonical.stat().st_ino) == source_inode
        stream.write(json.dumps(dict(private_mount_namespace=current, parent_mount_namespace=args.parent_ns,
            source_inode=source_inode, canonical_path_bound_to_capsule=True, uid=record['uid'])) + '\n')
        stream.flush()
    environment = dict(record['environment'], HOME=record['home'], USER=record['user'], LOGNAME=record['user'])
    environment['PYTHONPATH'] = ':'.join(str(canonical / name) for name in
        ('.local/npu-reset/python-lib', 'tests/npu', 'tools'))
    environment['NPU_EMULATION_TIMEOUT_US'] = str(args.timeout_us)
    os.setgroups([])
    os.setgid(record['gid'])
    os.setuid(record['uid'])
    os.execve(sys.executable, [sys.executable, '-u', '-B', str(canonical / args.script), *args.arguments], environment)


def run(args):
    assert os.geteuid() == 0, 'invoke the namespace runner through the WSL root user'
    directory = CAPSULES / args.name
    receipt = directory / 'receipt.json'
    record = json.loads(receipt.read_bytes())
    assert record['preservation_verified'] and record['source_root'] == str(ROOT)
    frozen = Path(record['input_root'])
    for name, expected in record['files'].items():
        assert digest(source_file(frozen, name)) == expected, ('capsule-input-drift', name)
    source_file(frozen, args.script)
    proof = directory / (args.tag + '.mount.json')
    output = directory / (args.tag + '.execution.json')
    assert not proof.exists() and not output.exists()
    namespace = os.readlink('/proc/self/ns/mnt')
    original_inode = (ROOT.stat().st_dev, ROOT.stat().st_ino)
    command = ['unshare', '--mount', '--fork', '--', sys.executable, str(Path(__file__)), '_inner',
        '--receipt', str(receipt), '--proof', str(proof), '--parent-ns', namespace,
        '--script', args.script, '--timeout-us', str(args.timeout_us), '--', *args.arguments]
    started = time.time()
    completed = subprocess.run(command, cwd=ROOT)
    assert os.readlink('/proc/self/ns/mnt') == namespace
    assert (ROOT.stat().st_dev, ROOT.stat().st_ino) == original_inode, 'host-worktree-mount-changed'
    result = dict(returncode=completed.returncode, capsule_sha256=digest(receipt), command=command,
        bootstrap_sha256=digest(Path(__file__)), parent_mount_namespace=namespace,
        host_project_mount_unchanged=True, elapsed_seconds=time.time() - started,
        proof_sha256=digest(proof) if proof.exists() else None, full_npu_goal_complete=False, hardware=False)
    with output.open('x') as stream: stream.write(json.dumps(result, indent=2) + '\n')
    raise SystemExit(completed.returncode)


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='mode', required=True)
    copy = commands.add_parser('create')
    copy.add_argument('--name', required=True)
    copy.add_argument('--receipt', type=Path, action='append', default=[])
    copy.add_argument('--snapshot', type=Path, action='append', default=[])
    copy.add_argument('--include', type=Path, action='append', default=[])
    launch = commands.add_parser('run')
    launch.add_argument('--name', required=True)
    launch.add_argument('--tag', required=True)
    launch.add_argument('--script', required=True)
    launch.add_argument('--timeout-us', type=int, default=60000000)
    private = commands.add_parser('_inner')
    for flag in ('receipt', 'proof'): private.add_argument('--' + flag, type=Path, required=True)
    private.add_argument('--parent-ns', required=True)
    private.add_argument('--script', required=True)
    private.add_argument('--timeout-us', type=int, required=True)
    for part in (launch, private): part.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    for field in ('name', 'tag'):
        if hasattr(args, field): assert re.fullmatch('[a-z][a-z0-9-]{0,39}', getattr(args, field))
    if hasattr(args, 'timeout_us'): assert 1000000 <= args.timeout_us <= 120000000
    if hasattr(args, 'arguments') and args.arguments[:1] == ['--']: args.arguments = args.arguments[1:]
    {'create': create, 'run': run, '_inner': inner}[args.mode](args)


if __name__ == '__main__': main()
