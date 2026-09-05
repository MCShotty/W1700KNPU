#!/usr/bin/env python3
"""Bind worker results to source/ELF/original bytes; not a hardware verifier."""
import json
from pathlib import Path
import re
import subprocess

from test_barrier_protocol import Rv32, BUILD, digest, SOURCE
from test_barrier_workers import ROOT, OUT, SITES, STARTUP_FLAGS, ENTRIES
from test_firmware_stop_counterexample import INPUT, CODE_SHA, DATA_SHA

BASE = '657aad1ab9f44722220a4302ceaf9567fc0b8493'
PRIOR = ROOT / 'research/checkpoints/2026-09-05-npu-barrier'


def main():
    result_path = OUT / 'worker-tests.json'
    report = json.loads(result_path.read_text())
    assert report['passed'] and report['firmware_sha256'] == CODE_SHA
    assert report['data_sha256'] == DATA_SHA
    for name, expected in report['source_sha256'].items():
        assert digest((ROOT / name).read_bytes()) == expected, name
    code = (INPUT / 'en7581_MT7996_npu_rv32.bin').read_bytes()
    data = (INPUT / 'en7581_MT7996_npu_data.bin').read_bytes()
    assert digest(code) == CODE_SHA and digest(data) == DATA_SHA
    binary = BUILD / 'barrier-workers.elf'
    assert digest(binary.read_bytes()) == report['elf_sha256']
    rv = Rv32(binary)
    sections = [{'name': section.name, 'start': int(section['sh_addr']),
                 'end': int(section['sh_addr']) + int(section['sh_size'])}
                for section in rv.elf.iter_sections() if section['sh_flags'] & 2 and section['sh_size']]
    assert all(0x84040000 <= section['start'] < section['end'] < 0x84048000 for section in sections)
    assert len(report['stop_resume']) == 16
    assert {int(row['site'], 16) for row in report['stop_resume']} == set(SITES)
    assert len(report['register_mstatus_differential']) == 96
    assert {(int(row['site'], 16), row['value'], row['mie'])
            for row in report['register_mstatus_differential']} == {
                (site, value, mie) for site in SITES for value in (0, 1, 3) for mie in (False, True)}
    assert {(row['hart'], int(row['missing_flag'], 16) - 0x3e900000)
            for row in report['missing_startup_dependencies']} == {
                (hart, flag) for hart, flags in STARTUP_FLAGS.items() for flag in flags}
    assert {row['hart'] for row in report['inflight']} == set(ENTRIES)
    assert {row['hart'] for row in report['actual_adapter_refresh_interrupted']} == set(ENTRIES)
    assert len(report['mutation_controls']) == 19
    assert all(row['rejected'] for row in report['mutation_controls'].values())
    for row in report['mutation_controls'].values():
        if 'elf_sha256' in row:
            assert len(row['elf_sha256']) == 64 and row['elf_sha256'] != report['elf_sha256']
    for cycle in report['seven_shared_workers']['cycles']:
        assert set(cycle['actual_worker_ack_order']) == set(range(1, 8))
        assert set(cycle['actual_worker_refresh_order']) == set(range(1, 8))
        assert cycle['missing_coordinator_rejected']
    assert [cycle['resource_base'] for cycle in report['seven_shared_workers']['cycles']] == [
        '0x3e931000', '0x3e930000', '0x3e931000']
    assert len(report['core5_combined_elf_regression']['cases']) == 4
    assert len(report['core5_combined_elf_regression']['preservation']) == 10

    export = PRIOR / 'ghidra-irq/en7581_MT7996_npu_rv32.bin.txt'
    prior = json.loads((PRIOR / 'evidence-verification.json').read_text())
    assert digest(export.read_bytes()) == prior['ghidra_export_sha256']
    assembly = {int(address, 16): instruction for address, instruction in
                re.findall(r'^ram:([0-9a-f]+) (.+)$', export.read_text(), re.M)}
    evidence = []
    assert len(report['new_detours']) == len(SITES)
    for patch in report['new_detours']:
        address, target = int(patch['address'], 16), int(patch['target'], 16)
        assert target == rv.symbols[patch['symbol']]
        assert patch['preimage'] == code[address - 0x84000000:address - 0x84000000 + 4].hex()
        assert patch['preimage'] == SITES[address][2]
        encoded = int.from_bytes(bytes.fromhex(patch['postimage']), 'little')
        assert encoded & 0xfff == 0x6f  # JAL x0, not a link-register clobber.
        offset = ((encoded >> 31 & 1) << 20 | (encoded >> 21 & 0x3ff) << 1 |
                  (encoded >> 20 & 1) << 11 | (encoded >> 12 & 0xff) << 12)
        offset -= (1 << 21) if offset & (1 << 20) else 0
        assert address + offset == target
        instructions = [assembly[pc] for pc in (address, address + 2) if pc in assembly]
        assert instructions
        evidence.append({**patch, 'original_assembly': instructions})

    lock = ROOT / 'firmware/source-lock.json'
    assert subprocess.check_output(['git', 'show', BASE + ':firmware/source-lock.json'], cwd=ROOT) == lock.read_bytes()
    changed = subprocess.check_output(['git', 'diff', '--name-only', BASE, '--',
                                       'firmware/source-lock.json', 'firmware/patches',
                                       'firmware/overlay', 'firmware/build.config',
                                       'firmware/feeds.conf.default'], cwd=ROOT, text=True)
    assert not changed, changed
    output = {'passed': True, 'packaged_source_unchanged_from': BASE,
              'source_lock_sha256': digest(lock.read_bytes()),
              'worker_results_sha256': digest(result_path.read_bytes()),
              'verifier_sha256': digest(Path(__file__).read_bytes()),
              'ghidra_export_sha256': digest(export.read_bytes()),
              'elf_sha256': report['elf_sha256'], 'elf_allocated_sections': sections,
              'detour_original_bytes_and_assembly': evidence,
              'scope': 'Artifact/source/preimage binding and recorded case inventory. Not independent all-path validation, production placement, hardware completion or actual-client proof.'}
    (OUT / 'evidence-verification.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'passed': True, 'detours_bound': len(evidence),
                      'elf_sections': sections, 'packaged_source_unchanged': True}))


if __name__ == '__main__':
    main()
