#!/usr/bin/env python3
"""Bind module variants to ELF symbols and executable sections, not filenames."""
import hashlib
import json
from pathlib import Path
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/checkpoints/2026-09-05-npu-attach'
ARTIFACTS = ROOT / '.local/npu-attach/artifacts'
BASELINE = json.loads((ROOT / 'tests/npu/fixtures/wlan-dma-r1-code.json').read_text())['modules']


def inspect(path):
    with path.open('rb') as f:
        elf = ELFFile(f)
        if elf['e_machine'] != 'EM_AARCH64':
            raise RuntimeError('Wrong architecture: ' + str(path))
        sections = {s.name: hashlib.sha256(s.data()).hexdigest() for s in elf.iter_sections()
                    if s['sh_flags'] & 4 and s['sh_size']}
        symbols = {s.name for s in elf.get_section_by_name('.symtab').iter_symbols()
                   if s['st_shndx'] != 'SHN_UNDEF'}
    return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'bytes': path.stat().st_size, 'executable_sections': sections}, symbols


reports = {}
for variant in ['npu-enabled', 'wlan-dma']:
    reports[variant] = {}
    for module in ['mt76.ko', 'mt76-connac-lib.ko', 'mt7996e.ko']:
        report, symbols = inspect(ARTIFACTS / variant / module)
        if module == 'mt7996e.ko':
            required = {'mt7996_npu_hw_init', '__mt7996_npu_hw_init', 'mt7996_npu_hw_stop'}
            if variant == 'npu-enabled' and not required <= symbols:
                raise RuntimeError('Enabled module missing NPU initializer/stop')
            if variant == 'wlan-dma' and required & symbols:
                raise RuntimeError('WLAN-DMA module still contains NPU lifecycle functions')
            report['defined_npu_lifecycle_symbols'] = sorted(required & symbols)
        if variant == 'wlan-dma':
            original = BASELINE[module]
            if not report['executable_sections'] or report['executable_sections'] != original['executable_sections']:
                raise RuntimeError('Baseline executable sections changed: ' + module)
            report['all_executable_sections_match_retained_baseline'] = True
            report['baseline_elf_sha256'] = original['original_elf_sha256']
        reports[variant][module] = report
config = (ROOT / '.build/openwrt/.config').read_bytes()
if config != (ROOT / 'firmware/build.config').read_bytes():
    raise RuntimeError('Default build configuration changed')
result = {'passed': True, 'default_config_unchanged': True, 'variants': reports,
          'scope': 'component builds only; no new image, live load or active-NPU runtime test'}
(OUT / 'module-verification.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
