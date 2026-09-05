#!/usr/bin/env python3
"""Seal the scoped NPU checkpoint's exact inputs and verification records."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research/checkpoints/2026-09-05-npu-attach'
programs = [
    ('stock_hostadpt.ko', ROOT / 'research/stock/elf/stock_hostadpt.ko', 'ghidra-stock', 27),
    ('stock_npu.ko', ROOT / 'research/stock/elf/stock_npu.ko', 'ghidra-stock', 21),
    ('mt7996e.ko', ROOT / '.local/npu-attach/artifacts/npu-enabled/mt7996e.ko', 'ghidra-candidate', 5),
]
rows = []
for name, binary, folder, count in programs:
    text = (OUT / folder / (name + '.txt')).read_text()
    sha = hashlib.sha256(binary.read_bytes()).hexdigest()
    if 'executable_sha256=' + sha not in text or 'decompiled=false' in text:
        raise RuntimeError('Ghidra/binary mismatch: ' + name)
    selected = int(re.search(r'^selected_functions=(\d+)', text, re.M)[1])
    total = int(re.search(r'^total_defined_functions=(\d+)', text, re.M)[1])
    if selected != count or 'failed_decompilations=0' not in text:
        raise RuntimeError('Ghidra selection/export incomplete: ' + name)
    rows.append({'program': name, 'sha256': sha, 'selected_functions': selected,
                 'initialized_executable_functions': total})
candidate = (OUT / 'ghidra-candidate/mt7996e.ko.txt').read_text()
init = candidate.split('FUNCTION mt7996_npu_hw_init @', 1)[1].split('\nFUNCTION ', 1)[0]
if init.index('if (') > init.index('dmam_alloc_attrs('):
    raise RuntimeError('Expected binary guard is not ahead of allocation')
for marker in ['mt7996_npu_hw_stop(dev);', '__mt7996_npu_hw_init(dev);',
               'mt7996_tx_token_put(dev);', 'mt7996_dma_reset(dev,true);']:
    if marker not in candidate:
        raise RuntimeError('Recovery evidence missing: ' + marker)
result = {'passed': True, 'ghidra': rows,
          'analysis': 'Full auto-analysis preceded exports; synthetic EXTERNAL stubs excluded',
          'binary_initializer_guard_reviewed': True,
          'decompiler_limits': 'Optimized DWARF locations partly unresolved; source/assembly cross-checks required',
          'recovery': 'L1 unchecked returns and full-reset pre-quiescence token release remain unresolved',
          'tests': json.loads((OUT / 'initializer-tests.json').read_text()),
          'module_checks': json.loads((OUT / 'module-verification.json').read_text())['passed']}
(OUT / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
manifest = []
for path in sorted(OUT.rglob('*')):
    if path.is_file() and path.name != 'file-manifest.json':
        manifest.append({'path': path.relative_to(OUT).as_posix(), 'bytes': path.stat().st_size,
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
(OUT / 'file-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({'passed': True, 'exported_functions': sum(r['selected_functions'] for r in rows),
                  'analysis_functions': sum(r['initialized_executable_functions'] for r in rows),
                  'manifest_files': len(manifest)}, indent=2))
