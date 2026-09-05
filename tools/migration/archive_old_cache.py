#!/usr/bin/env python3
"""Losslessly archive named old caches; never delete originals in this step."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import tarfile
import time

ROOT = Path(__file__).resolve().parents[2]
WINDOWS_ROOT = Path('/mnt/c/Users/captain/Documents/Codex/2026-06-12/i-need-help-wiping-the-nand/work')
LINUX_ROOT = Path('/home/captain/w1700k-openwrt-build')
WINDOWS_ARCHIVES = Path('/mnt/c/Users/captain/Downloads/FW/W1700KNPU-LocalArchives')
if os.name == 'nt':
    WINDOWS_ROOT = Path('C:/Users/captain/Documents/Codex/2026-06-12/i-need-help-wiping-the-nand/work')
    WINDOWS_ARCHIVES = Path('C:/Users/captain/Downloads/FW/W1700KNPU-LocalArchives')
WINDOWS = [
    'ghidra-v619-ownership-20260717', 'ghidra-v629-fasttx-direct-20260718',
    'ghidra-v626-fasttx-reason22-20260718', 'ghidra-v641-airoha-ownership-20260805',
    'ghidra-v646-rro-session-teardown-20260806', 'ghidra-v662-mib-ring-accounting-20260829',
    'ghidra-v642-hostadpt-tx-headroom-20260805', 'ghidra-final-20260710',
]
LINUX = ['v688-provider79-build-20260901/build_dir',
         'v686-release-73a8983-20260901/build-a-upper/build_dir',
         'v689-build-full-20260902/build_dir']


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def archive_one(source, allowed, destination, label):
    source = source.resolve(strict=True)
    if not source.is_relative_to(allowed.resolve()) or source == allowed.resolve():
        raise RuntimeError('Unsafe source boundary')
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / (label.replace('/', '__') + '.tar.gz')
    receipt = output.with_suffix('.receipt.json')
    if output.exists() and receipt.exists():
        saved = json.loads(receipt.read_text())
        if saved['verified'] and sha(output) == saved['archive_sha256']:
            print(f'Already verified: {label}', flush=True)
            return
        raise RuntimeError(f'Archive receipt mismatch: {output}')
    if output.exists() or receipt.exists():
        raise RuntimeError(f'Incomplete final archive: {output}')
    entries = []
    before = {}
    for p in sorted(source.rglob('*')):
        rel = p.relative_to(source).as_posix()
        st = p.lstat()
        if p.is_symlink():
            entries.append({'path': rel, 'type': 'symlink', 'target': os.readlink(p)})
        elif p.is_file():
            entries.append({'path': rel, 'type': 'file', 'bytes': st.st_size, 'sha256': sha(p)})
            before[rel] = (st.st_size, st.st_mtime_ns)
        elif p.is_dir():
            entries.append({'path': rel, 'type': 'directory'})
        else:
            raise RuntimeError(f'Unsupported special file: {p}')
    partial = output.with_suffix('.partial')
    if not partial.exists():
        with partial.open('wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', compresslevel=1, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode='w|', dereference=False) as tar:
                for entry in entries:
                    tar.add(source / entry['path'], arcname=entry['path'], recursive=False)
    expected = {e['path']: e for e in entries}
    seen = set()
    with tarfile.open(partial, 'r|gz') as tar:
        for member in tar:
            e = expected[member.name]
            if member.name in seen:
                raise RuntimeError('Duplicate archive member')
            seen.add(member.name)
            if e['type'] == 'file':
                # tarfile can encode identical inode data as hardlinks.
                if member.islnk():
                    if expected[member.linkname]['sha256'] != e['sha256']:
                        raise RuntimeError('Hardlink target mismatch')
                elif hashlib.file_digest(tar.extractfile(member), 'sha256').hexdigest() != e['sha256']:
                    raise RuntimeError(f'Archive content mismatch: {member.name}')
            elif e['type'] == 'symlink' and (not member.issym() or member.linkname != e['target']):
                raise RuntimeError('Symlink mismatch')
            elif e['type'] == 'directory' and not member.isdir():
                raise RuntimeError('Directory mismatch')
    if seen != set(expected):
        raise RuntimeError('Archive inventory mismatch')
    for rel, state in before.items():
        st = (source / rel).stat()
        if (st.st_size, st.st_mtime_ns) != state:
            raise RuntimeError(f'Source changed during archive: {rel}')
    partial.rename(output)
    result = {'source': str(source), 'archive': str(output), 'archive_sha256': sha(output),
              'archive_bytes': output.stat().st_size, 'source_bytes': sum(e.get('bytes', 0) for e in entries),
              'verified': True, 'original_deleted': False, 'created_unix': time.time(), 'entries': entries}
    receipt.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'entries'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('surface', choices=['windows', 'linux'])
    parser.add_argument('--name', help='One exact entry from the approved surface list')
    args = parser.parse_args()
    if args.surface == 'windows':
        if args.name and args.name not in WINDOWS:
            raise RuntimeError('Unapproved archive name')
        for name in ([args.name] if args.name else WINDOWS):
            archive_one(WINDOWS_ROOT / name, WINDOWS_ROOT, WINDOWS_ARCHIVES / 'ghidra', name)
    else:
        if args.name and args.name not in LINUX:
            raise RuntimeError('Unapproved archive name')
        for name in ([args.name] if args.name else LINUX):
            archive_one(LINUX_ROOT / name, LINUX_ROOT, ROOT / '.local/archives/build-cache', name)
