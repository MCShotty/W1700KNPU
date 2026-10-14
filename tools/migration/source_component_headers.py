"""Verify quoted header dependencies in the explicit NPU source export."""
from pathlib import Path, PurePosixPath
import posixpath
import re

QUOTED_INCLUDE = re.compile(r'^\s*#\s*include\s*"([^"\n]+)"', re.MULTILINE)


def verify_header_closure(root, components):
    root = Path(root).resolve()
    rows = [row for row in components if row['tree'] == 'openwrt']
    exported = {row['destination'] for row in rows}
    edges = []
    for row in rows:
        if not row['source'].startswith('firmware/npu/') or not row['source'].endswith('.h'):
            continue
        source = (root / row['source']).resolve()
        if not source.is_relative_to(root) or not source.is_file():
            raise RuntimeError('Invalid NPU header source: ' + row['source'])
        destination = PurePosixPath(row['destination'])
        if destination.is_absolute() or '..' in destination.parts:
            raise RuntimeError('Invalid NPU header destination: ' + row['destination'])
        for dependency in QUOTED_INCLUDE.findall(source.read_text()):
            if PurePosixPath(dependency).is_absolute():
                raise RuntimeError('Absolute quoted NPU include: ' + dependency)
            target = posixpath.normpath(str(destination.parent / dependency))
            if target not in exported:
                raise RuntimeError('Missing exported NPU header: ' + row['destination'] + ' -> ' + target)
            edges.append(dict(header=row['destination'], dependency=target))
    return edges
