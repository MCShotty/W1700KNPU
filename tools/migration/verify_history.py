#!/usr/bin/env python3
"""Check every historical archive member and credential-quarantine exclusion."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

ROOT = Path(__file__).resolve().parents[2]
expected = {r['path']: r for r in json.loads((ROOT / 'research/history-manifest.json').read_text())}
original = {r['path'].replace('\\', '/'): r for r in json.loads((ROOT / '.migration/history-inventory.json').read_text())}
flagged = {f['File'].removeprefix('.migration/history/') for f in
           json.loads((ROOT / '.migration/gitleaks-history.json').read_text())}
if set(expected) & flagged:
    raise RuntimeError('Credential-quarantined file entered archive')
seen = {}
archive = ROOT / 'research/history-20260905.tar.gz'
with tarfile.open(archive, 'r|gz') as tar:
    for member in tar:
        path = PurePosixPath(member.name)
        if path.is_absolute() or '..' in path.parts or member.name in seen:
            raise RuntimeError('Unsafe/duplicate archive path')
        if member.islnk():
            sha = seen[member.linkname]
        elif member.isfile():
            sha = hashlib.file_digest(tar.extractfile(member), 'sha256').hexdigest()
        else:
            raise RuntimeError('Unexpected archive member type')
        if sha != expected[member.name]['sha256'] or sha != original[member.name]['sha256']:
            raise RuntimeError(f'Historical content mismatch: {member.name}')
        seen[member.name] = sha
if set(seen) != set(expected):
    raise RuntimeError('Archive member set mismatch')
result = {'passed': True, 'members_verified': len(seen), 'unique_contents': len(set(seen.values())),
          'quarantined_files_excluded': len(flagged), 'all_archived_bytes_match_screened_originals': True,
          'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}
out = ROOT / 'docs/migration/history-verification.json'
out.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
