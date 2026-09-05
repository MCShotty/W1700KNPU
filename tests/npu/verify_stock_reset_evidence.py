#!/usr/bin/env python3
"""Verify reset checkpoint identities, table relocations and export coverage."""
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import subprocess

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/checkpoints/2026-09-05-npu-reset'
INPUTS = ROOT / '.local/npu-reset/inputs'
IDENTITIES = {
    'mt_wifi.ko': '40c8f974ad7317776f602c069c009d1f0d5d939d622ccdee275423fad1e35cb0',
    'mt7990.ko': '502cd4b1ddab60b5a23a0d4d904f49ddae795dfa09154d70b63f933add323f81',
    'mtk_hwifi.ko': '6d82ba02d96d638da9e80592a63e31c09d2f8603620066b604c1702d1171c8f7',
    'mtk_pci.ko': 'c71b2073eeb2498c05c5e42bb5ceaf3df664cff42bf0b0740eb6152458e0857b',
    'connac_if.ko': '52f5c19cacf0febddc73a72247250a7c067039c80b8bbd744f5283a5492e0d28',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_export(relative, expected_sha, total, exported, targets=None):
    path = OUT / relative
    text = path.read_text()
    assert f'sha256={expected_sha}\n' in text, relative
    assert f'total_executable_functions={total}\n' in text, relative
    assert f'exported_functions={exported}\n' in text, relative
    assert len(re.findall(r'^FUNCTION ', text, re.M)) == exported, relative
    assert len(re.findall(r'^decompiled=true$', text, re.M)) == exported, relative
    assert 'failed_decompilations=0' in text and 'decompiled=false' not in text, relative
    if targets is not None:
        assert f'inventory_targets_exported={targets}' in text, relative
    return {'file': relative, 'sha256': sha(path), 'analyzed_functions': total,
            'exported_functions': exported, 'inventory_targets': targets}


def main():
    elfs = {}
    for name, expected in IDENTITIES.items():
        path = INPUTS / name
        assert sha(path) == expected, name
        elfs[name] = ELFFile(io.BytesIO(path.read_bytes()))
    bindings = []
    for name, section, offset, target_section, target in [
        ('connac_if.ko', '.data', 0x90, '.text', 0xc80),
        ('mtk_hwifi.ko', '.rodata', 0x700, '.text', 0xce90),
        ('mtk_hwifi.ko', '.rodata', 0x708, '.text', 0xcec4),
        ('mtk_hwifi.ko', '.rodata', 0x6a0, '.text', 0xcf00),
        ('mtk_hwifi.ko', '.rodata', 0x6b0, '.text', 0xd020),
        ('mtk_pci.ko', '.data', 0x1e0, '.text.unlikely', 0x50),
        ('mtk_pci.ko', '.data', 0x1e8, '.text.unlikely', 0),
        ('mtk_pci.ko', '.data', 0x128, '.text', 0x1c14),
        ('mtk_pci.ko', '.data', 0x1f0, '.text', 0x580),
        ('mtk_pci.ko', '.data', 0x1f8, '.text', 0x5a0),
        ('mt7990.ko', '.data', 0x80, '.text', 0xcc4),
        ('mt7990.ko', '.data', 0x420, '.text', 0x140),
    ]:
        elf = elfs[name]
        relocations = elf.get_section_by_name('.rela' + section)
        table = elf.get_section(relocations['sh_link'])
        matches = [r for r in relocations.iter_relocations() if r['r_offset'] == offset]
        assert len(matches) == 1, (name, hex(offset))
        reloc = matches[0]
        symbol = table.get_symbol(reloc['r_info_sym'])
        assert reloc['r_info_type'] == 257
        assert elf.get_section(symbol['st_shndx']).name == target_section
        assert symbol['st_value'] + reloc['r_addend'] == target
        bindings.append({'file': name, 'source': section + '+' + hex(offset),
                         'target': target_section + '+' + hex(target), 'relocation': 'R_AARCH64_ABS64'})
    pci = elfs['mtk_pci.ko']
    relocs = {r['r_offset'] for r in pci.get_section_by_name('.rela.data').iter_relocations()}
    for offset in (0x130, 0x138):
        assert offset not in relocs
        assert pci.get_section_by_name('.data').data()[offset:offset + 8] == bytes(8)

    exports = []
    for name, total, exported, targets in [('mtk_pci.ko', 143, 26, 6), ('mtk_hwifi.ko', 351, 4, 4),
                                            ('mt7990.ko', 29, 2, 2), ('mt_wifi.ko', 11264, 363, 7)]:
        exports.append(verify_export('ghidra-modules/' + name + '.txt', IDENTITIES[name], total, exported, targets))
        log = (OUT / 'ghidra-modules' / (name + '.analysis.log')).read_text()
        assert 'Analysis succeeded' in log and 'Analysis timed out' not in log
    for name, total in [('mtk_pci.ko', 143), ('mtk_hwifi.ko', 351)]:
        exports.append(verify_export('ghidra-modules-all/' + name + '.txt', IDENTITIES[name], total, total))
    exports.append(verify_export('ghidra-connac/connac_if.ko.txt', IDENTITIES['connac_if.ko'], 59, 59))
    exports.append(verify_export('ghidra-bindings/mt_wifi.ko.txt', IDENTITIES['mt_wifi.ko'], 11264, 32))
    exports.append(verify_export('ghidra-kernel/stock-kernel.vmlinux.elf.txt',
                                'a51e6d0a6deee620a5f715c9469f193906cdf3fcea28b97ce01cf88383aa704e', 33676, 251))
    firmware = ROOT / '.local/npu-quiescence/firmware/en7581_MT7996_npu_rv32.bin'
    firmware_sha = 'e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643'
    assert sha(firmware) == firmware_sha
    final_export = 'ghidra-current-rv32-concurrent-final/en7581_MT7996_npu_rv32.bin.txt'
    exports.append(verify_export(final_export, firmware_sha, 424, 424))
    text = (OUT / final_export).read_text()
    for marker in ['DAT_ram_3e9046e8 = 0;', 'DAT_ram_3e9046f6 = 1;', 'DAT_ram_3e9046f7 = 1;',
                   'FUNCTION worker_8400ec48', 'FUNCTION worker_8400e3fc']:
        assert marker in text, marker
    for name in ('stock-dispatch-emulation.json', 'firmware-stop-counterexample.json'):
        assert json.loads((OUT / name).read_text())['passed']

    baseline_lock = subprocess.check_output(['git', 'show', '068832a6811c3dc04cd323873c0330a083863a68:firmware/source-lock.json'], cwd=ROOT)
    assert baseline_lock == (ROOT / 'firmware/source-lock.json').read_bytes(), 'Firmware source lock changed'
    pointer = struct.pack('<I', 0x8400c9b0)
    data = (ROOT / '.local/npu-quiescence/firmware/en7581_MT7996_npu_data.bin').read_bytes()
    report = {'passed': True, 'scope': 'input/export identities, relocation-defined tables, analysis visibility and recorded model results; not runtime binding or physical DMA containment',
              'inputs': IDENTITIES, 'bindings': bindings, 'exports': exports,
              'static_pci_traffic_slots': 'NULL at pci_dma_ops +0x78/+0x80; dynamic overrides are not excluded',
              'standalone_page_loop': {'address': '0x8400c9b0', 'absolute_code_pointer_offset': firmware.read_bytes().find(pointer),
                                       'absolute_data_pointer_offset': data.find(pointer), 'reachability': 'not established; not required for core5 counterexample'},
              'firmware_source_lock_unchanged': True}
    (OUT / 'evidence-verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'table_bindings': len(bindings), 'exports': len(exports),
                      'inventory_targets': 19, 'firmware_source_lock_unchanged': True}))


if __name__ == '__main__':
    main()
