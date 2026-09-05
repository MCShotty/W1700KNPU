#!/usr/bin/env python3
"""Bind native copy-guard evidence without promoting a hardware drain claim."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

from elftools.elf.elffile import ELFFile
from run_layout_regressions import SUITES

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/checkpoints/2026-09-06-npu-copy'
BASE = 'f48c25da94f4d1d33fdc509b3e22a209267ca1b4'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads((OUT / path).read_text())


def main():
    run = read('copy-regressions.json')
    layout = read('layout-regressions.json')
    assert run['passed'] and layout['passed']
    expected = list(SUITES) + ['test_gdma_owner_routes', 'test_gdma_copy_guard']
    assert run['suites'] == [row['suite'] for row in layout['runs']] == expected
    for row in layout['runs']:
        assert row['passed']
        for path, expected_sha in row['evidence'].items():
            assert sha(ROOT / path) == expected_sha, path
    for path, expected_sha in layout['source_sha256'].items():
        assert sha(ROOT / path) == expected_sha, path
    assert layout['rejected_linker_addresses'] == ['0x3e920000', '0x3e904740', '0x3e907ec0', '0x3e906001']
    assert run['both_compiles_reproduced_byte_for_byte']
    assert sha(ROOT / run['combined_test_elf']) == run['combined_test_elf_sha256'] == layout['combined_elf_sha256']
    assert sha(ROOT / run['default_elf']) == run['default_elf_sha256']
    assert run['default_poll_limit'] == 65536 and run['test_poll_limit'] == 64
    assert len(run['default_poll_fault_cases']) == 2
    assert all(row['retained_after_late_completion'] for row in run['default_poll_fault_cases'])
    assert run['default_poll_fault_cases'][0]['device']['pre_control_reads'] == 65536
    assert run['default_poll_fault_cases'][1]['device']['post_done_reads'] == 65536
    copy = read('test_gdma_copy_guard/copy-guard-tests.json')
    assert copy['passed'] and copy['elf_sha256'] == run['combined_test_elf_sha256']
    assert len(copy['normal_cases']) == 48
    assert len(copy['rejected_owners_and_limits']) == 65
    assert len(copy['failure_retention']) == 9 and len(copy['abi_cases']) == 6
    assert len(copy['other_native_callers']) == 14
    assert len(copy['mutation_controls']) == 8
    assert all(row['rejected'] and row['assertion'] for row in copy['mutation_controls'].values())
    assert copy['stop_inflight']['no_ack_from_copy_helper']
    assert copy['coordinator_fault_observation']['status_reports_shared_fault']
    assert copy['coordinator_fault_observation']['coordinator_owned_state_unchanged_by_worker']
    routes = read('test_gdma_owner_routes/known-gdma-owners.json')
    assert {(row['hart'], row['immediate_caller']) for row in routes['known_root_routes']} == {
        (2, '0x8400e87a'), (3, '0x8400f0c4'), (3, '0x8400f528')}
    adapter = read('test_admission_native/admission-native-tests.json')
    assert adapter['elf_sha256'] == run['combined_test_elf_sha256']
    assert adapter['eight_shared_contexts']['all_acks_via_actual_code']
    assert adapter['eight_shared_contexts']['no_drain_witnesses']
    assert adapter['eight_shared_contexts']['wire_status_parked_mask'] == 255
    export = OUT / 'ghidra-default/admission-platform-gdma-gdma-65536.elf.txt'
    text = export.read_text()
    assert 'sha256=' + run['default_elf_sha256'] in text
    assert 'failed_decompilations=0' in text and 'decompiled=false' not in text
    assert len(re.findall(r'^FUNCTION ', text, re.M)) == 3
    assert 'total_executable_functions=50' in text
    assert 'ram:840423c4 lw a0,-0x1fc(t1)' in text
    assert 'ram:840423ca c.bnez a0,0x840423b6' in text
    assert 'ram:84042404 csrrci s4,0x0300,0x8' in text
    assert 'ram:840400ae c.sw a1,0x10(a0)' in text
    assert 'ram:84042452 c.j 0x84042450' in text
    assert 'ram:84042454 csrw 0x0300,s4' in text
    log = (OUT / 'ghidra-default/analysis.log').read_text()
    assert all(marker in log for marker in ('Analysis succeeded', 'Save succeeded',
               'COPY_CANDIDATE_VOLATILE_MAP_PASS', 'MAILBOX_CONTRACT_PASS functions=3 analyzed=50'))
    assert 'Analysis timed out' not in log
    with (ROOT / run['default_elf']).open('rb') as stream:
        elf = ELFFile(stream)
        sections = [{'name': section.name, 'start': section['sh_addr'],
                     'end': section['sh_addr'] + section['sh_size']}
                    for section in elf.iter_sections() if section['sh_flags'] & 2 and section['sh_size']]
    assert all(0x84040000 <= row['start'] < row['end'] <= 0x84048000 for row in sections)
    assert not subprocess.check_output(['git', 'diff', '--name-only', BASE, '--', 'firmware/source-lock.json',
        'firmware/overlay', 'firmware/patches', 'firmware/build.config', 'firmware/feeds.conf.default'], cwd=ROOT)
    live = read('router-readonly.json')
    assert live['ethernet_bound'] and live['strict_host_key_checking']
    assert live['board'] == 'gemtek,w1700k-ubi' and live['wlan_npu_runtime'] == 'compiled-out'
    assert not live['raw_mmio_read_performed'] and not live['configuration_changes']
    assert not live['module_changes'] and not live['flash_performed']
    result = {'passed': True, 'suites': len(expected), 'mutation_controls': 8,
              'packaged_source_unchanged_from': BASE, 'default_elf_sha256': run['default_elf_sha256'],
              'ghidra_export_sha256': sha(export), 'ghidra_functions': 3, 'ghidra_discovered_functions': 50,
              'elf_sections': sections, 'source_lock_sha256': sha(ROOT / 'firmware/source-lock.json'),
              'helpers': {name: sha(ROOT / 'tools/ghidra' / name) for name in
                          ('ExportMailboxContract.java', 'SetupCopyCandidateMap.java', 'copy-candidate.pattern')},
              'verifier_sha256': sha(Path(__file__)),
              'scope': 'Exact software/binary/test inputs and scoped read-only identity; not full hardware drain, boot, cache, host recovery or client acceptance.'}
    (OUT / 'evidence-verification.json').write_text(json.dumps(result, indent=2) + '\n')
    manifest = [{'path': str(path.relative_to(OUT)), 'bytes': path.stat().st_size, 'sha256': sha(path)}
                for path in sorted(OUT.rglob('*')) if path.is_file() and path.name != 'file-manifest.json']
    (OUT / 'file-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'passed': True, 'suites': len(expected), 'manifest_files': len(manifest),
                      'ghidra_functions': 3, 'negative_controls': 8}))


if __name__ == '__main__':
    main()
