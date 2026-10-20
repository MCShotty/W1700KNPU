#!/usr/bin/env python3
"""Check guest AND Windows backing-volume capacity before private WSL work."""
import argparse
import base64
import fcntl
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ('snapshot', 'cache', 'overlay', 'output', 'margin')


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(('invalid-byte-count', name))
    return value


def windows_query(distro):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', distro):
        raise ValueError('unsupported-WSL-distribution-name')
    script = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$rows = @(Get-ChildItem -LiteralPath 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' |
    ForEach-Object { Get-ItemProperty -LiteralPath $_.PSPath } |
    Where-Object { $_.DistributionName -ceq '__DISTRO__' })
if ($rows.Count -ne 1 -or $rows[0].Version -ne 2) { throw 'WSL2 identity is not unique' }
$row = $rows[0]
$base = [Environment]::ExpandEnvironmentVariables($row.BasePath)
$name = if ($row.VhdFileName) { $row.VhdFileName } else { 'ext4.vhdx' }
if ([IO.Path]::GetFileName($name) -cne $name) { throw 'Unexpected VHD filename' }
$vhd = Get-Item -LiteralPath (Join-Path $base $name)
if ($vhd.PSIsContainer -or $vhd.Extension -ine '.vhdx' -or $vhd.Length -le 0) {
    throw 'Missing WSL backing disk'
}
$path = $vhd.FullName -replace '^\\\?\\', ''
if ($path -notmatch '^[A-Za-z]:\\') { throw 'Unsupported backing-volume path' }
$drive = $path.Substring(0,1).ToUpperInvariant()
$volume = Get-Volume -DriveLetter $drive
if ($volume.HealthStatus -ne 'Healthy') { throw 'Backing volume is not healthy' }
[ordered]@{ distro=$row.DistributionName; vhd_path=$path; vhd_bytes=[long]$vhd.Length;
    drive=$drive; free_bytes=[long]$volume.SizeRemaining; total_bytes=[long]$volume.Size } |
    ConvertTo-Json -Compress
'''.replace('__DISTRO__', distro)
    encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    result = subprocess.run(['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive',
        '-EncodedCommand', encoded], stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError('Windows-backing-volume-query-failed')
    return json.loads(result.stdout.decode('utf-8-sig'))


def observe(root):
    root = root.resolve(strict=True)
    if root.stat().st_dev != Path('/').stat().st_dev:
        raise ValueError('project-not-on-WSL-root-filesystem')
    filesystem = subprocess.check_output(['findmnt', '-n', '-o', 'FSTYPE', '--target', str(root)],
        text=True, timeout=10).strip()
    if filesystem != 'ext4' or os.statvfs(root).f_flag & os.ST_RDONLY:
        raise ValueError('project-requires-writable-native-ext4')
    distro = os.environ.get('WSL_DISTRO_NAME', '')
    host = windows_query(distro)
    if host.get('distro') != distro:
        raise ValueError('backing-distribution-mismatch')
    path = PureWindowsPath(host['vhd_path'])
    if not path.is_absolute() or not re.fullmatch(r'[A-Z]:', path.drive.upper()):
        raise ValueError('unsupported-backing-path')
    if host.get('drive') != path.drive[0].upper():
        raise ValueError('backing-drive-mismatch')
    integer(host['vhd_bytes'], 'vhd', 1)
    usage = shutil.disk_usage(root)
    return dict(observed_unix_ns=time.time_ns(), project=str(root), filesystem=filesystem,
        distro=distro, host=host, guest=dict(free_bytes=usage.free, total_bytes=usage.total),
        writable_ext4=True)


def evaluate(observation, budgets):
    if budgets.keys() != set(COMPONENTS):
        raise ValueError('all-five-budget-components-required')
    for name, value in budgets.items():
        integer(value, name, 1 if name == 'margin' else 0)
    required = sum(budgets.values())
    remaining = {}
    for name in ('host', 'guest'):
        space = observation[name]
        free = integer(space['free_bytes'], name + '-free')
        total = integer(space['total_bytes'], name + '-total', 1)
        if free > total:
            raise ValueError(('invalid-space-observation', name))
        remaining[name] = free - required
    return dict(format='npu-storage-budget-v1', passed=all(value >= 0 for value in remaining.values()),
        observation=observation, budget_bytes=budgets, required_bytes=required,
        remaining_after_budget_bytes=remaining, space_reserved=False,
        full_npu_goal_complete=False, hardware=False,
        limits=['Point-in-time check and explicit estimates, not a reservation or a world/native result.',
                'Both guest and actual Windows backing volume must cover the entire budget, including margin.',
                'An advisory lock serializes only cooperating launches; other applications can still consume space.',
                'Budget VHD growth conservatively without relying on guest free blocks being host-allocated.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in COMPONENTS:
        parser.add_argument('--' + name + '-bytes', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    budgets = {name: getattr(args, name + '_bytes') for name in COMPONENTS}
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / '.local') or output.exists() or not output.parent.is_dir():
        parser.error('Use a new receipt in an existing project .local directory')
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    with (ROOT / '.local/npu-storage-budget.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('Another cooperating budgeted launch holds the storage lock')
        try:
            result = evaluate(observe(ROOT), budgets)
        except (KeyError, OSError, ValueError, subprocess.SubprocessError) as error:
            parser.error(str(error))
        result['command'] = command
        with output.open('x') as stream:
            stream.write(json.dumps(result, indent=2) + '\n')
        print(json.dumps(dict(passed=result['passed'], required_bytes=result['required_bytes'],
            remaining_after_budget_bytes=result['remaining_after_budget_bytes'], receipt=str(output))), flush=True)
        if not result['passed']:
            raise SystemExit(2)
        if command:
            raise SystemExit(subprocess.run(command, stdin=subprocess.DEVNULL).returncode)


if __name__ == '__main__':
    main()
