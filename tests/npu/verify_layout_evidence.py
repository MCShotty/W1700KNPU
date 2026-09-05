#!/usr/bin/env python3
"""Verify current bounded-map receipts and provenance, not hardware quiescence."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

from run_layout_regressions import ROOT, OUT, SUITES

BASE = 'b9cff2bc40a67feafd1c94c522f8cbd81888d16c'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(suite, name):
    return json.loads((OUT / suite / name).read_text())


def main():
    report = json.loads((OUT / 'layout-regressions.json').read_text())
    assert report['passed'] and [row['suite'] for row in report['runs']] == list(SUITES)
    for row in report['runs']:
        assert row['passed'] and row['evidence']
        for name, expected in row['evidence'].items():
            assert digest(ROOT / name) == expected, name
    for name, expected in report['source_sha256'].items():
        assert digest(ROOT / name) == expected, name
    assert report['rejected_linker_addresses'] == ['0x3e920000', '0x3e904740', '0x3e907ec0', '0x3e906001']
    assert report['state'] == '0x3e906000' and report['local_sram_test_bytes'] == 0x8000
    assert digest(ROOT / '.local/npu-barrier/admission-platform.elf') == report['combined_elf_sha256']
    memory = read('test_firmware_memory_layout', 'native-memory-layout.json')
    assert memory['status'] == 'PASS' and len(memory['reset_cases']) == 16
    assert sum(row['bss_cleared'] for row in memory['reset_cases']) == 1
    assert memory['lookup']['table_entries_checked'] == 36
    assert memory['lookup']['old_virtual_state_unmapped']
    assert memory['board']['native_bss'] == ['0x3e900c10', '0x3e904754']
    assert memory['board']['candidate_state'] == ['0x3e906000', '0x3e906158']
    gdma = read('test_firmware_gdma', 'native-gdma.json')
    assert gdma['passed'] and len(gdma['kernel_cases']) == 4 and len(gdma['rv32_cases']) == 12
    assert gdma['conditional_stale_done']['control_enable_at_return_or_bound']
    assert gdma['conditional_stale_done']['done_reads'] == 1
    assert gdma['alternative_start_clears_done']['done_reads'] == 7
    assert gdma['rv32_stalled']['done_reads'] > 50 and not gdma['rv32_stalled']['returned']
    protocol = read('test_admission_protocol', 'admission-protocol-tests.json')
    adapter = read('test_admission_native', 'admission-native-tests.json')
    assert protocol['native_rv32_call_pairs'] == 1667 and len(protocol['mutation_controls']) == 6
    assert all(row['rejected'] for row in protocol['mutation_controls'].values())
    assert adapter['eight_shared_contexts']['wire_status_parked_mask'] == 255
    assert adapter['eight_shared_contexts']['all_acks_via_actual_code']
    assert adapter['eight_shared_contexts']['no_drain_witnesses']
    assert adapter['combined_elf_worker_regressions'] == {
        'new_worker_register_cases': 96, 'new_worker_stop_resume': 16,
        'new_worker_inflight': 6, 'new_worker_interrupted_refresh': 6,
        'core5_stop_resume': 4, 'core5_register_cases': 10, 'core5_inflight': True}
    exports = {}
    for folder, expected in (('ghidra-kernel-dma', 63), ('ghidra-kernel-dma-callers', 67)):
        path = OUT / folder / 'stock-kernel.vmlinux.elf.txt'
        text = path.read_text()
        assert 'sha256=' + gdma['kernel_sha256'] in text
        assert 'failed_decompilations=0' in text and 'decompiled=false' not in text
        assert len(re.findall(r'^FUNCTION ', text, re.M)) == expected
        assert 'ffffffc0100cc150 tbnz w0,#0x1,0xffffffc0100cc130' in text
        assert 'total_executable_functions=33676' in text
        assert f'MAILBOX_CONTRACT_PASS functions={expected} analyzed=33676' in (OUT / folder / 'reexport.log').read_text()
        exports[folder] = {'functions': expected, 'sha256': digest(path)}
    protected = ['firmware/source-lock.json', 'firmware/overlay', 'firmware/patches',
                 'firmware/build.config', 'firmware/feeds.conf.default', 'firmware/npu']
    assert not subprocess.check_output(['git', 'diff', '--name-only', BASE, '--', *protected], cwd=ROOT)
    result = {'passed': True, 'suites': len(SUITES), 'packaged_source_and_protocol_unchanged_from': BASE,
              'combined_elf_sha256': report['combined_elf_sha256'], 'ghidra': exports,
              'source_lock_sha256': digest(ROOT / 'firmware/source-lock.json'),
              'helpers': {name: digest(ROOT / 'tools/ghidra' / name)
                          for name in ('ExportMailboxContract.java', 'kernel-dma.pattern')},
              'verifier_sha256': digest(Path(__file__)),
              'scope': 'Exact inputs, result inventory and machine-code facts; physical ownership/cache/drain and full boot remain unproved.'}
    (OUT / 'evidence-verification.json').write_text(json.dumps(result, indent=2) + '\n')
    manifest = [{'path': str(path.relative_to(OUT)), 'bytes': path.stat().st_size, 'sha256': digest(path)}
                for path in sorted(OUT.rglob('*')) if path.is_file() and path.name != 'file-manifest.json']
    (OUT / 'file-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'passed': True, 'suites': len(SUITES), 'manifest_files': len(manifest),
                      'ghidra_exported_functions': [row['functions'] for row in exports.values()]}))


if __name__ == '__main__':
    main()
