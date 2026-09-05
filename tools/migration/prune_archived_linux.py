#!/usr/bin/env python3
"""Remove only complete, content-verified old caches retained in local archives."""
import hashlib
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
ALLOWED = Path('/home/captain/w1700k-openwrt-build').resolve()
NAMES = {'v688-provider79-build-20260901/build_dir',
         'v686-release-73a8983-20260901/build-a-upper/build_dir',
         '.v685-build-upper/build_dir'}


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


results = []
for receipt in sorted((ROOT / '.local/archives/build-cache').glob('*.receipt.json')):
    record = json.loads(receipt.read_text())
    source = Path(record['source'])
    if record.get('original_deleted'):
        continue
    if source.is_symlink() or source.resolve().relative_to(ALLOWED).as_posix() not in NAMES:
        raise RuntimeError('Refusing unapproved cache path')
    if os.path.ismount(source):
        raise RuntimeError('Refusing mounted cache')
    archive = Path(record['archive']).resolve(strict=True)
    if not archive.is_relative_to((ROOT / '.local/archives/build-cache').resolve()):
        raise RuntimeError('Archive outside approved destination')
    if not record['verified'] or sha(archive) != record['archive_sha256']:
        raise RuntimeError('Archive verification failed')
    entries = {e['path']: e for e in record['entries']}
    paths = {p.relative_to(source).as_posix(): p for p in source.rglob('*')}
    if set(paths) != set(entries):
        raise RuntimeError('Source inventory changed after archive')
    for rel, p in paths.items():
        entry = entries[rel]
        if entry['type'] == 'file' and (not p.is_file() or p.is_symlink() or sha(p) != entry['sha256']):
            raise RuntimeError(f'Source changed: {rel}')
        if entry['type'] == 'symlink' and (not p.is_symlink() or os.readlink(p) != entry['target']):
            raise RuntimeError(f'Symlink changed: {rel}')
    shutil.rmtree(source)
    record['original_deleted'] = True
    receipt.write_text(json.dumps(record, indent=2) + '\n')
    results.append({k: v for k, v in record.items() if k != 'entries'})
out = ROOT / 'docs/migration/linux-archived-cache-removals.json'
out.parent.mkdir(parents=True, exist_ok=True)
previous = json.loads(out.read_text()) if out.exists() else []
out.write_text(json.dumps(previous + results, indent=2) + '\n')
print(json.dumps(results, indent=2))
