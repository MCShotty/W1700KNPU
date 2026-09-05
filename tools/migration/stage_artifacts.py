#!/usr/bin/env python3
"""Copy selected immutable release and vendor-analysis inputs; verify all bytes."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
FW = Path('/mnt/c/Users/captain/Downloads/FW/MessingWstuff')
selected = [
    ('FinalResult/W1700K-Daybreak21-WLAN-DMA-R1-20260905', 'releases/Daybreak21-R1'),
    ('FinalResult/W1700K-V6.87-Corrective-Engineering-20260901', 'releases/V6.87-rollback'),
    ('WXK001-05.00.30.82.bin', 'research/stock/WXK001-05.00.30.82.bin'),
    ('npu_blobs_from_stock.zip', 'research/stock/npu_blobs_from_stock.zip'),
    ('work/ghidra-input', 'research/stock/elf'),
    ('work/extract/stock-rootfs/lib/modules/5.4.55/mt_wifi.ko', 'research/stock/elf/stock_mt_wifi.ko'),
    ('work/stock-kernel.vmlinux.elf', 'research/stock/elf/stock-kernel.vmlinux.elf'),
]
rows = []
for old, new in selected:
    src, dest = FW / old, ROOT / new
    paths = sorted(src.rglob('*')) if src.is_dir() else [src]
    for path in paths:
        if not path.is_file():
            continue
        if any(s in path.name.lower() for s in ['private', 'backup', 'factory', '.pem', '.key']):
            raise RuntimeError(f'Protected data found in selected artifact set: {path.name}')
        out = dest / path.relative_to(src) if src.is_dir() else dest
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, out)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if hashlib.sha256(out.read_bytes()).hexdigest() != sha:
            raise RuntimeError('Copy mismatch')
        rows.append({'path': out.relative_to(ROOT).as_posix(), 'source': str(path),
                     'bytes': out.stat().st_size, 'sha256': sha})
path = ROOT / 'docs/migration/artifact-import.json'
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(rows, indent=2) + '\n')
print(json.dumps({'files': len(rows), 'bytes': sum(r['bytes'] for r in rows)}))
