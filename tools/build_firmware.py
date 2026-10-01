#!/usr/bin/env python3
"""Build the firmware components and OpenWrt together; never contact a router."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
SYSTEM_PATH = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'


def build_environment(host_tools):
    """Opt in to workspace tool prefixes without inheriting the caller's PATH."""
    selected = []
    allowed = (ROOT / '.local', ROOT / '.build')
    for requested in host_tools:
        try:
            prefix = requested.resolve(strict=True)
            binary_dir = (prefix / 'bin').resolve(strict=True)
        except (OSError, RuntimeError, ValueError) as error:
            raise ValueError(f'Invalid host-tools prefix {requested}: {error}') from error
        for path in (prefix, binary_dir):
            if (not path.is_dir() or os.pathsep in str(path) or
                    not any(path != root and path.is_relative_to(root) for root in allowed)):
                raise ValueError('Host-tools prefix and bin must be existing directories strictly '
                                 f'inside {ROOT}/.local or {ROOT}/.build: {path}')
        selected.append(dict(prefix=str(prefix), bin=str(binary_dir)))
    path = os.pathsep.join([entry['bin'] for entry in selected] + [SYSTEM_PATH])
    env = dict(os.environ, PATH=path, GIT_TERMINAL_PROMPT='0')
    make = shutil.which('make', path=path)
    if make is None:
        raise ValueError('make is unavailable in the selected fixed build PATH')
    make = Path(make).resolve(strict=True)
    provenance = dict(host_tools=selected, path=path,
                      make=dict(path=str(make), sha256=hashlib.sha256(make.read_bytes()).hexdigest()))
    return env, provenance


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', type=Path, default=ROOT / '.build/merged-openwrt')
    parser.add_argument('--target', default='world')
    parser.add_argument('--jobs', type=int, default=8)
    parser.add_argument('--name', default='world')
    parser.add_argument('--host-tools', type=Path, action='append', default=[], metavar='PREFIX',
                        help='Prepend PREFIX/bin to both build stages; repeatable, workspace .local/.build only')
    args = parser.parse_args()
    dest = args.destination.resolve()
    assert dest.is_relative_to((ROOT / '.build').resolve()) and (dest / '.config').is_file()
    assert 1 <= args.jobs <= 32 and re.fullmatch('[a-z0-9/-]+', args.target)
    assert re.fullmatch('[a-z][a-z0-9-]*', args.name)
    try:
        env, tool_provenance = build_environment(args.host_tools)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    logs = ROOT / '.local/merge-nonoc-20260923'
    logs.mkdir(parents=True, exist_ok=True)
    log, state = logs / ('build-' + args.name + '.log'), logs / ('build-' + args.name + '.json')
    assert not log.exists(), 'Use a fresh log name for an incremental retry.'
    lock = (dest / '.codex-build.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with log.open('w') as stream:
        subprocess.run(['make', '-C', str(ROOT / 'firmware/npu'),
                        'OUT=' + str(dest / 'bin/npu')], env=env, stdout=stream,
                       stderr=subprocess.STDOUT, check=True)
        command = ['make', '-j' + str(args.jobs), args.target, 'V=s']
        child = subprocess.Popen(command, cwd=dest, env=env, stdout=stream,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        info = dict(pid=child.pid, process_group=child.pid, wrapper_pid=os.getpid(),
                    command=command, cwd=str(dest), log=str(log), started=time.time(), exit_code=None,
                    tool_provenance=tool_provenance)
        state.write_text(json.dumps(info, indent=2) + '\n')
        print(json.dumps(info), flush=True)

        def stop(_signum, _frame):
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        code = child.wait()
        info.update(exit_code=code, finished=time.time())
        state.write_text(json.dumps(info, indent=2) + '\n')
        print(json.dumps(dict(target=args.target, exit_code=code, log=str(log))), flush=True)
        raise SystemExit(code)


if __name__ == '__main__':
    main()
