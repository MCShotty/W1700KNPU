#!/usr/bin/env python3
"""Verify cumulative patches using temporary Git indexes, without source edits."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path('/home/captain/w1700k-openwrt-build/openwrt-w1700k-daybreak20-20260904')
lock = json.loads((ROOT / 'firmware/source-lock.json').read_text())
results = []
for label, source in [('openwrt', SOURCE), ('luci', SOURCE / 'feeds/luci')]:
    with tempfile.TemporaryDirectory(prefix='export-check-', dir=ROOT / '.migration') as tmp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / 'index'))
        def git(*args):
            return subprocess.check_output(['git', '-C', str(source), *args], env=env)
        git('read-tree', lock[label]['base'])
        git('apply', '--cached', str(ROOT / 'firmware/patches' / f'{label}.patch'))
        for entry in lock[label]['changed_files']:
            name = entry['path']
            extra = ROOT / 'firmware/overlay' / label / name
            data = extra.read_bytes() if extra.is_file() else git('show', ':' + name)
            if hashlib.sha256(data).hexdigest() != entry['sha256']:
                raise RuntimeError(f'Export mismatch: {label}/{name}')
        results.append({'component': label, 'base': lock[label]['base'],
                        'tracked_patched_tree': git('write-tree').decode().strip(),
                        'changed_files_verified': len(lock[label]['changed_files']), 'passed': True})
path = ROOT / 'docs/migration/source-export-verification.json'
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps(results, indent=2))
