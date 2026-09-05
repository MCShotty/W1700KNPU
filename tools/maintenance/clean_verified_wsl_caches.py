#!/usr/bin/env python3
"""Delete audited duplicate downloads and regenerable apt caches only."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '.local/cleanup-20260905'
audit = json.loads((OUT / 'wsl-readonly-audit.json').read_text())
allowed = {Path('/home/captain/w1700k-openwrt-build') / name / 'dl' for name in
           ['v688-provider79-build-20260901', 'v689-build-full-20260902',
            'fanboy-source-recovered-20260831']}
candidates = {}
for group in audit['duplicate_download_groups']:
    parent = Path(group['path'])
    if group['duplicates'] and parent not in allowed:
        raise RuntimeError('Unapproved download directory')
    for entry in group['duplicates']:
        path = parent / entry['name']
        if path.parent != parent or path.is_symlink():
            raise RuntimeError('Invalid duplicate filename')
        candidates[path] = entry


def digest(path):
    if not stat.S_ISREG(path.lstat().st_mode):
        raise RuntimeError('Nonregular cache file')
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


deletions = []
for path, entry in candidates.items():
    keeper = Path(entry['keep'])
    visited = {path}
    while keeper in candidates:
        if keeper in visited:
            raise RuntimeError('Duplicate keeper cycle')
        visited.add(keeper)
        keeper = Path(candidates[keeper]['keep'])
    if not keeper.is_relative_to(ROOT / '.build/openwrt/dl') and keeper.parent not in allowed:
        raise RuntimeError('Unapproved keeper')
    if path.resolve().parent != path.parent.resolve() or path.parent.is_symlink():
        raise RuntimeError('Unexpected source indirection')
    if digest(path) != entry['sha256'] or digest(keeper) != entry['sha256']:
        raise RuntimeError('Duplicate content changed')
    info = path.stat()
    path.unlink()
    deletions.append({'category': 'duplicate-source-download', 'path': str(path),
                      'keeper': str(keeper), 'sha256': entry['sha256'],
                      'logical_bytes': info.st_size, 'allocated_bytes': info.st_blocks * 512})

with Path('/var/cache/apt/archives/lock').open('a') as lock:
    fcntl.lockf(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    apt_paths = [(Path(audit['apt_archives_root']) / e['name'], e) for e in audit['apt_deb_files']]
    apt_paths += [(Path(e['path']), e) for e in audit['apt_index_caches']]
    for path, entry in apt_paths:
        permitted = (path.parent == Path('/var/cache/apt/archives') and path.suffix == '.deb') or \
                    path in {Path('/var/cache/apt/pkgcache.bin'), Path('/var/cache/apt/srcpkgcache.bin')}
        if not permitted or path.is_symlink():
            raise RuntimeError('Unapproved apt cache path')
        info = path.stat()
        if info.st_size != entry['logical_bytes'] or info.st_mtime_ns != int(entry['mtime_ns']):
            continue
        path.unlink()
        deletions.append({'category': 'apt-cache', 'path': str(path), 'logical_bytes': info.st_size,
                          'allocated_bytes': info.st_blocks * 512})
    fcntl.lockf(lock, fcntl.LOCK_UN)

result = {'removed_files': len(deletions), 'allocated_bytes': sum(r['allocated_bytes'] for r in deletions),
          'deletions': deletions, 'preserved': 'sources, unique downloads, apt locks/partial and installed packages'}
output = OUT / 'wsl-cache-removals.json'
output.write_text(json.dumps(result, indent=2) + '\n')
os.chown(output, ROOT.stat().st_uid, ROOT.stat().st_gid)
print(json.dumps({k: v for k, v in result.items() if k != 'deletions'}, indent=2))
