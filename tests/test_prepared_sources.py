#!/usr/bin/env python3
"""Reconstruct every locked modified source file in clean upstream worktrees."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from prepare_build import apply


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', default='source-replay')
    args = parser.parse_args()
    assert re.fullmatch(r'[a-z0-9][a-z0-9-]*', args.name), 'Invalid receipt name'
    lock = json.loads((ROOT / 'firmware/source-lock.json').read_text())
    source = ROOT / lock['build_directory']
    work = ROOT / '.local/merge-nonoc-20260923' / args.name
    assert not work.exists()
    work.mkdir()
    checked = []
    for label, tree in (('openwrt', source), ('luci', source / 'feeds/luci')):
        dest = work / label
        subprocess.run(['git', '-C', str(tree), 'worktree', 'add', '--detach', str(dest),
                        lock[label]['base']], check=True)
        apply(label, dest, lock)
        subprocess.run(['git', '-C', str(dest), 'diff', '--check'], check=True)
        for item in lock[label]['changed_files']:
            path = dest / item['path']
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assert digest == item['sha256']
            assert os.stat(path).st_mode & 0o777 == int(item['mode'], 8)
            checked.append(dict(tree=label, path=item['path'], sha256=digest))
    output = work / 'result.json'
    output.write_text(json.dumps(dict(passed=True, files=checked,
                                      source_lock_sha256=hashlib.sha256((ROOT / 'firmware/source-lock.json').read_bytes()).hexdigest()), indent=2) + '\n')
    print(json.dumps(dict(passed=True, verified_files=len(checked), receipt=str(output))))


if __name__ == '__main__':
    main()
