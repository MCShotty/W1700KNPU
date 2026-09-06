#!/usr/bin/env python3
"""Bind first-gate parking and separate RX callback proofs to current inputs."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
from elftools.elf.elffile import ELFFile

from test_bootstrap_native import ROOT, sha
from test_barrier_core5 import jump
from test_mt7996_bootstrap_sequence import exports, GHIDRA, INPUT, CODE_SHA, DATA_SHA

OUT = ROOT / 'research/checkpoints/2026-09-06-npu-allhart'
RX = ROOT / 'research/checkpoints/2026-09-06-npu-attachrx'
BASE = 'bc82345173efec5049e4cfc6e399966ab82b08f5'
ELF = ROOT / '.local/npu-barrier/admission-platform-bootstrap-bootstrap-startup-gdma-gdma-65536.elf'


def hashes(entries):
    for name, value in entries.items():
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT) and sha(path) == value, name


def main():
    native = json.loads((OUT / 'allhart-native.json').read_text())
    assert native['passed'] and len(native['cases']) == 14
    assert len(native['missing_gates']) == 7 and len(native['input_controls']) == 6
    hashes(native['source_sha256'])
    assert sha(ELF) == native['elf_sha256'] == 'bdb64d12d738bdef85a747d0b638e6b148c1c534410fd893348fbaf5908e2931'
    with ELF.open('rb') as stream:
        symbols = {symbol.name: int(symbol['st_value'])
                   for symbol in ELFFile(stream).get_section_by_name('.symtab').iter_symbols()}
    code_path = INPUT / 'en7581_MT7996_npu_rv32.bin'
    assert sha(code_path) == CODE_SHA
    assert sha(INPUT / 'en7581_MT7996_npu_data.bin') == DATA_SHA
    code = code_path.read_bytes()
    patches = native['patches']
    assert len(patches) == len({row['site'] for row in patches}) == 26
    for row in patches:
        site, target = int(row['site'], 16), int(row['target'], 16)
        assert code[site-0x84000000:site-0x84000000+4].hex() == row['before']
        assert symbols[row['name']] == target and jump(site, target).hex() == row['after']
    for index, row in enumerate(native['cases']):
        order = row['order']
        assert sorted(order) == list(range(8))
        early = order[:order.index(0)]
        assert row['early_waiting_harts'] == early
        assert [worker['hart'] for worker in row['workers']] == order[order.index(0)+1:]+early[::-1]
        assert row['final_parked'] == [1]*8 and row['ready_and_drained'] == [0]*13
        assert row['released'] == row['armed'] == 0 and row['idempotent_stop_repoll_passes'] == 2
        assert row['parked_write_counts_by_owner'] == {str(hart): 3 for hart in range(8)}
        initializers = row['candidate_initializers']
        assert len(initializers) == 2 and all(event['hart'] == 0 for event in initializers)
        assert {int(event['pc'], 16) for event in initializers} == {
            symbols['npu_barrier_init'], symbols['npu_emulation_admission_init']}
        assert row['coordinator_footprint']['whole_l2_compared_bytes'] == 262144
        mask = 0
        for event in row['status_progress']:
            mask |= 1 << event['hart']
            assert event['epoch'] == 1 and event['parked_mask'] == mask
        assert mask == 255
        if row['plic_model'] == 'flat':
            assert len(row['plic_enable_word0']) == 1
            assert not int(row['plic_enable_word0'][0], 16) & (1 << 9)
        else:
            assert row['plic_model'] == 'banked' and len(row['plic_enable_word0']) == 8
            assert int(row['plic_enable_word0'][0], 16) & (1 << 9)
        if index < 8:
            assert order == list(range(index, 8))+list(range(index))
    assert {row['hart'] for row in native['missing_gates']} == set(range(1, 8))
    assert all(row['missing_ack'] for row in native['missing_gates'])

    rx = json.loads((RX / 'rx-callbacks.json').read_text())
    hashes(rx['sources'])
    counts = rx['counts']
    assert counts['new_callback_closures'] == counts['valid_callbacks'] == 2
    assert counts['negative_controls'] == len(rx['negative_controls']) == 21
    assert counts['remaining_original_pending_paths'] == len(rx['remaining_original_pending_cases']) == 11
    assert counts['remaining_separately_allocator_modeled_cases'] == 2
    assert counts['nominal_rx_descriptors'] == counts['nominal_software_ids'] == 2560
    assert not rx['strict_bootstrap']['api1_admitted']
    assert all(row['flags'] == 3 and not row['callbacks'] for row in rx['strict_bootstrap']['replies'])
    assert [(row['selector'], row['requested_count']) for row in rx['valid_sequence']] == [(0, 1536), (2, 1024)]
    for row in rx['valid_sequence']:
        assert row['callback_return'] == row['ready_flag'] == row['mailbox_flags_untouched'] == 1
        assert row['stopped_access'] is None and row['whole_ram_compared_bytes'] == 786432
        assert row['exact_memory_write_footprint'] and row['ready_publication_after_other_memory_writes']
    original = exports()
    for address, row in rx['ghidra_functions'].items():
        function = original[int(address, 16)]
        assert row['name'] == function['name'] and row['line'] == function['line']
        assert row['export_sha256'] == hashlib.sha256((function['text']+function['assembly']).encode()).hexdigest()

    text = GHIDRA.read_text()
    spans = []
    for address in (0x84000104, 0x84000164, 0x84000190, 0x840001a0, 0x840001c0,
                    0x8400099c, 0x840009bc, 0x84000a82, 0x84000aa6, 0x84000aca,
                    0x84000aee, 0x84003106, 0x84003200, 0x84003254, 0x8400326a,
                    0x840032e2, 0x84004348, 0x8400585c, 0x84005a00,
                    0x8400cb0e, 0x8400cd1a, 0x8400cdc6, 0x8400d0ae,
                    0x8400e3fc, 0x8400ec48):
        match = re.search(r'^FUNCTION [^\n]* @ ram:' + f'{address:08x}' + r'\n.*?(?=^FUNCTION |\Z)', text, re.M | re.S)
        assert match and 'decompiled=true' in match.group(), hex(address)
        spans.append({'address': hex(address), 'first_line': text[:match.start()].count('\n')+1,
                      'last_line': text[:match.end()].count('\n'),
                      'normalized_sha256': hashlib.sha256(match.group().encode()).hexdigest()})
    assembly = subprocess.check_output(['riscv64-linux-gnu-objdump', '-D', '-b', 'binary',
        '-m', 'riscv:rv32', '--adjust-vma=0x84000000', '--start-address=0x84000982',
        '--stop-address=0x8400099c', str(code_path)], text=True)
    assert code[0x982:0x99c].hex() == 'b7b7a51f23a007468280b7c7a51f23a00746828009456f40506c'
    for instruction in ('0x1fa5b460', '0x1fa5c460', '0x8400585c'):
        assert instruction in assembly
    protected = ['firmware', 'research/checkpoints/2026-09-06-npu-nativewifi',
                 'tests/npu/admission-platform-emulation.c', 'tests/npu/startup-platform-emulation.c',
                 'tests/npu/bootstrap-platform-emulation.c']
    subprocess.run(['git', 'diff', '--quiet', BASE, '--', *protected], cwd=ROOT, check=True)
    assert not subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--', *protected], cwd=ROOT)
    review = (OUT / 'ALLHART_REVIEW.md').read_text()
    assert 'No actionable findings' in review
    assert native['source_sha256']['tests/npu/test_multihart_cold_boot.py'] in review
    assert sha(OUT / 'allhart-native.json') in review
    for name in ('REPORT.md',):
        assert (OUT / name).is_file()
    assert (RX / 'RX_CALLBACKS.md').is_file()
    (OUT / 'module-fallback-assembly.txt').write_text(assembly)
    (OUT / 'original-boot-sources.json').write_text(json.dumps({
        'code_sha256': CODE_SHA, 'data_sha256': DATA_SHA,
        'ghidra_sha256': sha(GHIDRA), 'spans': spans,
        'tiny_entries': ['0x84000982', '0x8400098c', '0x84000996'],
        'tiny_assembly_sha256': hashlib.sha256(assembly.encode()).hexdigest()}, indent=2)+'\n')
    result = {'passed': True, 'base_commit': BASE, 'allhart_scenarios': 14,
              'missing_gate_controls': 7, 'input_controls': 6, 'source_functions': len(spans),
              'new_rx_callback_paths': 2, 'rx_negative_controls': 21, 'strict_rx_rejections': 2,
              'remaining_original_callback_cases': 11, 'separate_allocator_modeled_cases': 2,
              'firmware_and_bindings_unchanged': True, 'full_attach': False,
              'post_gate_initialization': False, 'physical_containment': False, 'router_actions': False,
              'verifier_sha256': sha(Path(__file__)),
              'scope': 'Current-input binding of bounded software proofs, not a release certificate.'}
    files = [path for directory in (OUT, RX) for path in sorted(directory.iterdir())
             if path.is_file() and path.name not in ('file-manifest.json', 'evidence-verification.json')]
    (OUT / 'file-manifest.json').write_text(json.dumps({str(path.relative_to(ROOT)): sha(path)
                                                    for path in files}, indent=2)+'\n')
    (OUT / 'evidence-verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
