#!/usr/bin/env python3
"""Index reviewed repository files and prepare content-addressed API upload."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
subprocess.run(['git', 'add', '--all'], cwd=ROOT, check=True)
entries = subprocess.check_output(['git', 'ls-files', '--stage', '-z'], cwd=ROOT).decode().split('\0')
plan = []
for entry in filter(None, entries):
    metadata, path = entry.split('\t', 1)
    mode, sha, stage = metadata.split()
    if stage != '0' or mode not in {'100644', '100755'}:
        raise RuntimeError(f'Unexpected staged entry: {path}')
    if path.split('/')[0] in {'.local', '.build', '.migration'}:
        raise RuntimeError('Private/generated workspace entered upload index')
    data = (ROOT / path).read_bytes()
    try:
        text = data.decode('utf-8')
        binary = '\0' in text
    except UnicodeError:
        binary = True
    if len(data) > 20 * 1024 * 1024:
        raise RuntimeError(f'Split large artifact before upload: {path}')
    plan.append({'path': path, 'mode': mode, 'sha': sha, 'bytes': len(data), 'binary': binary})
out = ROOT / '.migration/upload-plan.json'
out.write_text(json.dumps(plan, indent=2) + '\n')
tree = subprocess.check_output(['git', 'write-tree'], cwd=ROOT, text=True).strip()
print(json.dumps({'files': len(plan), 'bytes': sum(e['bytes'] for e in plan),
                  'binary_files': sum(e['binary'] for e in plan), 'tree': tree}))
