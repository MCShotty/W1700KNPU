#!/usr/bin/env python3
"""Reassemble checksummed large inputs stored in GitHub-API-sized parts."""
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('manifest', type=Path)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
manifest = args.manifest.resolve(strict=True)
data = json.loads(manifest.read_text())
output = args.output.resolve()
if output.exists():
    raise SystemExit(f'Refusing to overwrite {output}')
output.parent.mkdir(parents=True, exist_ok=True)
partial = output.with_name(output.name + '.partial')
total = hashlib.sha256()
size = 0
created = False
try:
    with partial.open('xb') as out:
        created = True
        for part in data['parts']:
            path = (manifest.parent / part['path']).resolve(strict=True)
            if not path.is_relative_to(manifest.parent):
                raise RuntimeError('Part outside manifest directory')
            blob = path.read_bytes()
            if len(blob) != part['bytes'] or hashlib.sha256(blob).hexdigest() != part['sha256']:
                raise RuntimeError(f'Part mismatch: {path.name}')
            out.write(blob)
            total.update(blob)
            size += len(blob)
    if total.hexdigest() != data['sha256'] or size != data['bytes']:
        raise RuntimeError('Reassembled artifact mismatch')
    partial.rename(output)
except BaseException:
    # Remove only the newly created partial, never an existing user artifact.
    if created and partial.exists():
        partial.unlink()
    raise
print(f'{data["sha256"]}  {output}')
