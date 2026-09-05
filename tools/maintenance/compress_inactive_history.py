#!/usr/bin/env python3
"""Losslessly compress eligible history files, without altering their contents."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import time

ROOT = Path('C:/Users/captain/.codex')
OUT = Path('//wsl.localhost/Ubuntu/home/captain/W1700KNPU/.local/cleanup-20260905')
ACTIVE_ID = '019ebb9c-6294-7311-a0dd-80df39bd1db8'
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.GetCompressedFileSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel.GetCompressedFileSizeW.restype = wintypes.DWORD


def allocated(path):
    high = wintypes.DWORD()
    ctypes.set_last_error(0)
    low = kernel.GetCompressedFileSizeW(str(path), ctypes.byref(high))
    if low == 0xffffffff and ctypes.get_last_error():
        raise ctypes.WinError(ctypes.get_last_error())
    return (high.value << 32) | low


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
parser.add_argument('--limit', type=int, default=0)
args = parser.parse_args()
receipt = OUT / 'history-compression-results.json'
results = json.loads(receipt.read_text()) if receipt.exists() else []
completed = {r['path']: r for r in results if r.get('exit_code') == 0}
rows = []
for folder in ['sessions', 'archived_sessions']:
    for path in (ROOT / folder).rglob('*.jsonl'):
        info = path.lstat()
        if info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            continue
        actual = allocated(path)
        eligible = (ACTIVE_ID not in path.name and info.st_mtime < time.time() - 7200 and
                    info.st_size > 1024 * 1024 and
                    not info.st_file_attributes & stat.FILE_ATTRIBUTE_COMPRESSED)
        previous = completed.get(str(path))
        if previous and (info.st_size, info.st_mtime_ns) == (previous['logical_bytes'], previous['mtime_ns']):
            eligible = False
        rows.append({'path': str(path), 'logical_bytes': info.st_size,
                     'allocated_before': actual, 'eligible': eligible, 'mtime_ns': info.st_mtime_ns})
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'history-compression-inventory.json').write_text(json.dumps(rows, indent=2) + '\n')
print(json.dumps({'logical_bytes': sum(r['logical_bytes'] for r in rows),
                  'allocated_bytes': sum(r['allocated_before'] for r in rows),
                  'eligible_files': sum(r['eligible'] for r in rows),
                  'eligible_bytes': sum(r['allocated_before'] for r in rows if r['eligible'])}), flush=True)
if not args.apply:
    raise SystemExit(0)
for row in sorted((r for r in rows if r['eligible']), key=lambda r: r['allocated_before'], reverse=True):
    if args.limit and len(results) >= args.limit:
        break
    path = Path(row['path'])
    if not path.resolve().is_relative_to(ROOT.resolve()) or ACTIVE_ID in path.name:
        raise RuntimeError('Outside history compression scope')
    info = path.stat()
    if info.st_size != row['logical_bytes'] or info.st_mtime_ns != row['mtime_ns']:
        continue
    before = sha(path)
    result = subprocess.run(['compact.exe', '/C', '/EXE:LZX', '/Q', str(path)], capture_output=True)
    after = sha(path)
    if after != before:
        raise RuntimeError('File changed during compression; stop and inspect')
    row.update(sha256=before, exit_code=result.returncode, allocated_after=allocated(path),
               contents_unchanged=True)
    results.append(row)
    receipt.write_text(json.dumps(results, indent=2) + '\n')
    if len(results) % 10 == 0 or args.limit:
        print(json.dumps({'processed_files': len(results),
                          'saved_bytes': sum(r['allocated_before'] - r['allocated_after'] for r in results)}), flush=True)
print(json.dumps({'complete': True, 'processed_files': len(results),
                  'saved_bytes': sum(r['allocated_before'] - r['allocated_after'] for r in results)}), flush=True)
