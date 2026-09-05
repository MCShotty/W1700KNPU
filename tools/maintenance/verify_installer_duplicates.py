#!/usr/bin/env python3
"""Find clearly named installer duplicates in an existing personal backup ZIP."""
import hashlib
import json
from pathlib import Path
import re
import stat
import time
import zipfile

ROOT = Path('C:/Users/captain/Downloads')
ARCHIVE = ROOT / 'Downloads.zip'
OUT = Path('//wsl.localhost/Ubuntu/home/captain/W1700KNPU/.local/cleanup-20260905')


def sha(stream):
    return hashlib.file_digest(stream, 'sha256').hexdigest()


installer = re.compile(r'(?i)(setup|installer|^git-\d|^python-\d|^gfx_win_|^jdk-\d)')
candidates = [p for p in ROOT.iterdir() if p.is_file() and
              ((p.suffix.lower() == '.exe' and installer.search(p.name)) or p.suffix.lower() in {'.msi', '.msu'})]
candidates += [ROOT / 'ghidra_12.1.2_PUBLIC_20260605.zip']
bundle = ROOT / 'DaVinci.Resolve.Studio.v20.0.0.49.KpoJIuK'
if bundle.is_dir():
    candidates += [p for p in bundle.iterdir() if p.name in {
        'DaVinci.Resolve.Studio.v20.0.0.49.part1.exe',
        'DaVinci.Resolve.Studio.v20.0.0.49.part2.rar'}]
before = ARCHIVE.stat()
rows = []
with zipfile.ZipFile(ARCHIVE) as archive:
    names = archive.namelist()
    for path in candidates:
        if not path.exists() or path.is_symlink():
            continue
        info = path.lstat()
        if info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT or info.st_mtime > time.time() - 7 * 86400:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if names.count(relative) != 1:
            continue
        member = archive.getinfo(relative)
        if member.file_size != info.st_size or member.flag_bits & 1:
            continue
        with path.open('rb') as stream:
            digest = sha(stream)
        with archive.open(member) as stream:
            archived_digest = sha(stream)
        if digest != archived_digest:
            continue
        after = path.stat()
        if (after.st_size, after.st_mtime_ns) != (info.st_size, info.st_mtime_ns):
            raise RuntimeError('Installer changed while verifying')
        rows.append({'path': str(path), 'member': relative, 'bytes': info.st_size,
                     'sha256': digest, 'mtime_ns': info.st_mtime_ns})
with ARCHIVE.open('rb') as stream:
    archive_sha = sha(stream)
after = ARCHIVE.stat()
if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
    raise RuntimeError('Backup archive changed during verification')
result = {'archive': str(ARCHIVE), 'archive_bytes': before.st_size, 'archive_sha256': archive_sha,
          'verified_duplicates': rows, 'total_bytes': sum(r['bytes'] for r in rows),
          'policy': 'Preserve archive, portable programs, media, project sources and personal documents'}
(OUT / 'installer-duplicates.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'verified_files': len(rows), 'duplicate_bytes': result['total_bytes'],
                  'archive_preserved': True}), flush=True)
