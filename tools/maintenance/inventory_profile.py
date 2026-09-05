#!/usr/bin/env python3
"""Metadata-only Windows storage inventory; skip junctions/cloud reparse data."""
import heapq
import json
import os
from pathlib import Path
import stat
import time

REPO = Path('//wsl.localhost/Ubuntu/home/captain/W1700KNPU')
OUT = REPO / '.local/cleanup-20260905'
OUT.mkdir(parents=True, exist_ok=True)


def inventory(root):
    groups, errors, skipped = {}, [], 0
    largest = []
    stack = [root]
    files = 0
    while stack:
        directory = stack.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    try:
                        info = entry.stat(follow_symlinks=False)
                        if info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                            skipped += 1
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        rel = Path(entry.path).relative_to(root)
                        files += 1
                        for depth in [1, 2, 3, 4]:
                            key = '/'.join(rel.parts[:depth])
                            row = groups.setdefault(key, {'bytes': 0, 'files': 0, 'depth': depth})
                            # Short paths belong once to a bucket, not once per depth.
                            if row['depth'] != depth:
                                continue
                            row['bytes'] += info.st_size
                            row['files'] += 1
                        item = (info.st_size, str(rel))
                        if len(largest) < 40:
                            heapq.heappush(largest, item)
                        elif item > largest[0]:
                            heapq.heapreplace(largest, item)
                    except OSError as error:
                        errors.append({'path': entry.path, 'error': str(error)})
        except OSError as error:
            errors.append({'path': str(directory), 'error': str(error)})
    return {'root': str(root), 'files': files, 'reparse_entries_skipped': skipped,
            'groups': groups, 'largest': sorted(largest, reverse=True), 'errors': errors,
            'basis': 'logical file sizes, not reclaimable physical bytes; no file contents read'}


for label, root in [('profile', Path('C:/Users/captain')), ('drive-d', Path('D:/'))]:
    started = time.time()
    result = inventory(root)
    result['elapsed_seconds'] = round(time.time() - started, 1)
    (OUT / f'{label}-inventory.json').write_text(json.dumps(result, indent=2) + '\n')
    summary = sorted((dict(path=p, **v) for p, v in result['groups'].items() if v['depth'] == 1),
                     key=lambda x: x['bytes'], reverse=True)[:25]
    print(json.dumps({'root': str(root), 'seconds': result['elapsed_seconds'], 'files': result['files'],
                      'skipped_reparse': result['reparse_entries_skipped'], 'errors': len(result['errors']),
                      'top_level': summary}), flush=True)
