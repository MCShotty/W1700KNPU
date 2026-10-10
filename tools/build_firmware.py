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
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SYSTEM_PATH = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'


def pair_required(target):
    return target == 'world' or target.startswith(('package/', 'target/install', 'target/linux/install'))


def original_pair_directory(dest, requested=None):
    import npu_image as image
    candidates = [requested.resolve()] if requested else sorted(
        (dest / 'build_dir/target-aarch64_cortex-a53_musl').glob('linux-firmware-*/airoha'))
    matches = []
    for directory in candidates:
        if not directory.is_relative_to(ROOT):
            raise ValueError('Original NPU pair must be inside the workspace')
        files = [directory / name for name in ('en7581_MT7996_npu_rv32.bin', 'en7581_MT7996_npu_data.bin')]
        if all(path.is_file() for path in files) and [image.sha(path.read_bytes()) for path in files] == [image.CODE_SHA, image.DATA_SHA]:
            matches.append(directory)
    if len(matches) != 1:
        raise ValueError('A unique hash-pinned original NPU pair is required. Prepare linux-firmware '
                         'first or supply --npu-firmware-directory.')
    return matches[0]


def stage_checked_pair(dest, pair, name):
    import npu_image as image
    pair = pair.resolve()
    if not pair.is_relative_to(dest / 'bin'):
        raise ValueError('Checked pair must be in this build destination')
    manifest = json.loads((pair / 'manifest.json').read_bytes())
    code, data = [(pair / name).read_bytes() for name in ('CODE.bin', 'DATA.bin')]
    image.validate(code, data, manifest)
    for path, digest in manifest['inputs'].items():
        source = (ROOT / path).resolve()
        if not source.is_relative_to(ROOT) or image.sha(source.read_bytes()) != digest:
            raise ValueError('Checked-pair input has changed: ' + path)
    package = pair / 'package'
    package.mkdir()
    for source, target in (('CODE.bin', 'en7581_MT7996_npu_rv32.bin'),
                           ('DATA.bin', 'en7581_MT7996_npu_data.bin'),
                           ('manifest.json', 'w1700k-npu-pair.json')):
        shutil.copy2(pair / source, package / target)
        if (package / target).read_bytes() != (pair / source).read_bytes():
            raise ValueError('Staged pair differs: ' + target)
    link = dest / 'bin/npu-checked'
    if link.exists() and not link.is_symlink():
        raise ValueError('Refusing to replace unmanaged npu-checked directory')
    temporary = dest / 'bin' / ('.npu-checked-' + name)
    temporary.symlink_to(os.path.relpath(package, temporary.parent), target_is_directory=True)
    os.replace(temporary, link)
    return dict(directory=str(pair.relative_to(ROOT)), manifest_sha256=image.sha((pair / 'manifest.json').read_bytes()),
                code=manifest['code'], data=manifest['data'], loader_provisioned=False,
                physical_acceptance=False)


def build_checked_pair(dest, name, env, stream, firmware_directory=None):
    original = original_pair_directory(dest, firmware_directory)
    pair = dest / 'bin' / ('npu-pair-' + name)
    subprocess.run([sys.executable, str(ROOT / 'tools/build_npu_pair.py'), '--output', str(pair),
                    '--firmware-directory', str(original)], env=env, stdout=stream,
                   stderr=subprocess.STDOUT, check=True)
    return stage_checked_pair(dest, pair, name)


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
    parser.add_argument('--npu-firmware-directory', type=Path,
                        help='Pinned original MT7996 pair directory; otherwise use prepared linux-firmware')
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
        checked_pair = build_checked_pair(dest, args.name, env, stream, args.npu_firmware_directory) if pair_required(args.target) else None
        command = ['make', '-j' + str(args.jobs), args.target, 'V=s']
        child = subprocess.Popen(command, cwd=dest, env=env, stdout=stream,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        info = dict(pid=child.pid, process_group=child.pid, wrapper_pid=os.getpid(),
                    command=command, cwd=str(dest), log=str(log), started=time.time(), exit_code=None,
                    tool_provenance=tool_provenance, checked_npu_pair=checked_pair)
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
