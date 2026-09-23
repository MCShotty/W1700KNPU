#!/usr/bin/env python3
"""Build the firmware components and OpenWrt together; never contact a router."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', type=Path, default=ROOT / '.build/merged-openwrt')
    parser.add_argument('--target', default='world')
    parser.add_argument('--jobs', type=int, default=8)
    parser.add_argument('--name', default='world')
    args = parser.parse_args()
    dest = args.destination.resolve()
    assert dest.is_relative_to((ROOT / '.build').resolve()) and (dest / '.config').is_file()
    assert 1 <= args.jobs <= 32 and re.fullmatch('[a-z0-9/-]+', args.target)
    assert re.fullmatch('[a-z][a-z0-9-]*', args.name)
    logs = ROOT / '.local/merge-nonoc-20260923'
    logs.mkdir(parents=True, exist_ok=True)
    log, state = logs / ('build-' + args.name + '.log'), logs / ('build-' + args.name + '.json')
    assert not log.exists(), 'Use a fresh log name for an incremental retry.'
    env = dict(os.environ, PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
               GIT_TERMINAL_PROMPT='0')
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
                    command=command, cwd=str(dest), log=str(log), started=time.time(), exit_code=None)
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
