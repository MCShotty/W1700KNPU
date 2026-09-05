#!/usr/bin/env python3
"""Verify candidate provenance and collect direct-call evidence, not DMA proof."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/checkpoints/2026-09-05-npu-barrier'
BASE = '364b0932749a435705bfa2d0e3ddfc93635d0108'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    lock = (ROOT / 'firmware/source-lock.json').read_bytes()
    prior = subprocess.check_output(['git', '-C', str(ROOT), 'show', BASE + ':firmware/source-lock.json'])
    assert lock == prior, 'Packaged firmware source changed during candidate work'
    protocols = json.loads((OUT / 'protocol-tests.json').read_text())
    core5 = json.loads((OUT / 'core5-detour-tests.json').read_text())
    irqs = json.loads((OUT / 'irq-stop-counterexamples.json').read_text())
    assert all(report['passed'] for report in (protocols, core5, irqs))
    assert protocols['source_sha256'] == sha((ROOT / 'firmware/npu/barrier.c').read_bytes())
    assert protocols['rv32_elf_sha256'] == sha((ROOT / '.local/npu-barrier/barrier.elf').read_bytes())
    assert protocols['native_elf_sha256'] == sha((ROOT / '.local/npu-barrier/barrier.so').read_bytes())
    assert core5['detour_elf_sha256'] == sha((ROOT / '.local/npu-barrier/barrier-core5.elf').read_bytes())
    assert len(core5['cases']) == 4 and len(core5['register_mie_preservation_cases']) == 10
    assert core5['missing_detour_control']['rejected']

    export = OUT / 'ghidra-irq/en7581_MT7996_npu_rv32.bin.txt'
    text = export.read_text()
    assert 'failed_decompilations=0' in text and 'decompiled=false' not in text
    starts = list(re.finditer(r'^FUNCTION (\S+) @ ram:([0-9a-f]+)$', text, re.M))
    assert len(starts) == 425
    blocks = {int(start[2], 16): text[start.end():starts[index + 1].start() if index + 1 < len(starts) else len(text)]
              for index, start in enumerate(starts)}
    assert 'ram:840047d0 c.j 0x84004604' in blocks[0x840047a0]
    assert 'ram:840046dc' in blocks[0x84004604]
    direct = {0x840053a6: [], 0x84003254: []}
    for entry, block in blocks.items():
        for site, target in re.findall(r'^ram:([0-9a-f]+) (?:jal ra,|c\.jal )0x([0-9a-f]+)$', block, re.M):
            if int(target, 16) in direct:
                direct[int(target, 16)].append({'function': hex(entry), 'call': '0x' + site})
    assert {row['call'] for row in direct[0x840053a6]} == {'0x8400eb32', '0x8400f198', '0x8400f58e'}
    assert len(direct[0x84003254]) == 5
    sources = ['firmware/npu/barrier.c', 'firmware/npu/barrier.h',
               'tests/npu/barrier-core5-emulation.S', 'tests/npu/barrier-emulation.ld',
               'tests/npu/test_barrier_protocol.py', 'tests/npu/test_barrier_core5.py',
               'tests/npu/test_firmware_stop_irqs.py', 'tests/npu/verify_barrier_evidence.py',
               'tools/ghidra/SeedNpuUartIrq.java', 'tools/ghidra/run_barrier_irq.ps1']
    report = {'passed': True, 'packaged_source_unchanged_from': BASE,
              'source_lock_sha256': sha(lock), 'ghidra_export_sha256': sha(export.read_bytes()),
              'source_files': {path: sha((ROOT / path).read_bytes()) for path in sources},
              'discovered_functions': 425, 'failed_decompilations': 0,
              'direct_copy_helper_calls': direct[0x840053a6],
              'direct_irq_registration_calls': direct[0x84003254],
              'scope': 'Exact current artifacts and discovered direct calls only. Counts are not whole-program coverage; indirect calls and hardware ownership remain open. Candidate code is not packaged.'}
    (OUT / 'evidence-verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
