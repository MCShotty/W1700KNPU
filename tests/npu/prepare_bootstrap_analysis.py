#!/usr/bin/env python3
"""Bind headless seed spans to the currently tested extension ELF symbols."""
import hashlib
import json
from pathlib import Path

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/checkpoints/2026-09-06-npu-bootstrap'


def main():
    native = json.loads((OUT / 'bootstrap-native.json').read_text())
    path = ROOT / native['elf']
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == native['elf_sha256']
    with path.open('rb') as stream:
        elf = ELFFile(stream)
        symbols = {symbol.name: (int(symbol['st_value']), int(symbol['st_size']))
                   for symbol in elf.get_section_by_name('.symtab').iter_symbols()
                   if symbol['st_shndx'] != 'SHN_UNDEF'}
        sections = [{'name': section.name, 'address': hex(section['sh_addr']),
                     'bytes': int(section['sh_size'])} for section in elf.iter_sections()
                    if section['sh_flags'] & 2]
    names = ['npu_emulation_admission_init', 'npu_emulation_mailbox',
             'npu_bootstrap_init', 'npu_bootstrap_transport', 'npu_bootstrap_begin',
             'npu_bootstrap_finish', 'npu_emulation_bootstrap_mailbox',
             'npu_emulation_mailbox_register', 'npu_emulation_cold_start',
             'npu_emulation_before_bss', 'npu_emulation_reset_gate']
    seeds = []
    for name in names:
        start, size = symbols[name]
        if name == 'npu_emulation_before_bss':
            size = symbols['npu_emulation_reset_gate'][0] - start
        elif name == 'npu_emulation_reset_gate':
            size = symbols['npu_gdma_copy'][0] - start
        assert size > 0 and 0x84040000 <= start < start+size <= 0x84048000
        seeds.append({'name': name, 'start': f'{start:08x}', 'end': f'{start+size-1:08x}', 'bytes': size})
    result = {'elf': native['elf'], 'elf_sha256': digest, 'sections': sections, 'seeds': seeds}
    (OUT / 'analysis-input.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
