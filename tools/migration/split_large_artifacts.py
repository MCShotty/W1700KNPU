#!/usr/bin/env python3
"""Mechanically package large staged binaries without dropping original bytes."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
rows = []
for parent in ['research', 'releases']:
    for source in sorted((ROOT / parent).rglob('*')):
        if not source.is_file() or source.stat().st_size <= 20 * 1024 * 1024:
            continue
        manifest = source.with_name(source.name + '.parts.json')
        if manifest.exists():
            raise RuntimeError('Existing part manifest; refusing overwrite')
        output = source.with_name(source.name + '.parts')
        output.mkdir()
        parts = []
        total = hashlib.sha256()
        with source.open('rb') as f:
            while blob := f.read(16 * 1024 * 1024):
                part = output / f'{len(parts):04d}'
                part.write_bytes(blob)
                sha = hashlib.sha256(blob).hexdigest()
                if hashlib.sha256(part.read_bytes()).hexdigest() != sha:
                    raise RuntimeError('Part copy mismatch')
                total.update(blob)
                parts.append({'path': part.relative_to(manifest.parent).as_posix(),
                              'bytes': len(blob), 'sha256': sha})
        data = {'filename': source.name, 'bytes': source.stat().st_size,
                'sha256': total.hexdigest(), 'parts': parts}
        manifest.write_text(json.dumps(data, indent=2) + '\n')
        private = ROOT / '.local/large-artifacts' / total.hexdigest() / source.name
        private.parent.mkdir(parents=True, exist_ok=True)
        if private.exists():
            raise RuntimeError('Local original already exists')
        source.rename(private)
        rows.append({'manifest': manifest.relative_to(ROOT).as_posix(),
                     'bytes': data['bytes'], 'sha256': data['sha256'], 'parts': len(parts)})
print(json.dumps(rows, indent=2))
