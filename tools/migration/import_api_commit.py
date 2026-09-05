#!/usr/bin/env python3
"""Import an unsigned API-created commit only if its raw object hash matches."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
record = json.loads(Path(sys.argv[1]).read_text())
if record.get('verification', {}).get('signature'):
    raise SystemExit('Signed commits require their original raw object')
lines = ['tree ' + record['tree']['sha']]
lines += ['parent ' + p['sha'] for p in record['parents']]
for label in ['author', 'committer']:
    person = record[label]
    timestamp = int(datetime.fromisoformat(person['date'].replace('Z', '+00:00')).timestamp())
    lines.append(f'{label} {person["name"]} <{person["email"]}> {timestamp} +0000')
matched = False
# REST normalizes dates to UTC; the original commit retains its timezone offset.
for minutes in range(-12 * 60, 14 * 60 + 1, 15):
    offset = ('-' if minutes < 0 else '+') + f'{abs(minutes)//60:02d}{abs(minutes)%60:02d}'
    for suffix in ['', '\n']:
        headers = [line[:-5] + offset if line.startswith(('author ', 'committer ')) else line for line in lines]
        raw = ('\n'.join(headers) + '\n\n' + record['message'] + suffix).encode()
        sha = hashlib.sha1(f'commit {len(raw)}\0'.encode() + raw).hexdigest()
        if sha == record['sha']:
            matched = True
            break
    if matched:
        break
if not matched:
    raise SystemExit('Commit byte reconstruction mismatch; local refs unchanged')
sha = subprocess.check_output(['git', 'hash-object', '-w', '-t', 'commit', '--stdin'],
                              input=raw, cwd=ROOT).decode().strip()
for parent in record['parents']:
    if subprocess.run(['git', 'cat-file', '-e', parent['sha']], cwd=ROOT,
                      stderr=subprocess.DEVNULL).returncode:
        shallow = ROOT / '.git/shallow'
        existing = shallow.read_text().splitlines() if shallow.exists() else []
        if sha not in existing:
            shallow.write_text('\n'.join(existing + [sha]) + '\n')
subprocess.run(['git', 'update-ref', 'refs/heads/main', sha], cwd=ROOT, check=True)
subprocess.run(['git', 'update-ref', 'refs/remotes/origin/main', sha], cwd=ROOT, check=True)
subprocess.run(['git', 'branch', '--set-upstream-to=origin/main', 'main'], cwd=ROOT, check=True)
print(sha)
