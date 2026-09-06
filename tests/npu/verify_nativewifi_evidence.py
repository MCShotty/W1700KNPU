#!/usr/bin/env python3
"""Bind native bootstrap and separate host traces without broadening their proof."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
from test_mt7996_bootstrap_sequence import sources, exports

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/checkpoints/2026-09-06-npu-nativewifi'
BASE = 'f8402e98db0e8e0b2b2896a0dcd694cfc3c78ee0'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((OUT / name).read_text())


def check_hashes(entries):
    for name, expected in entries.items():
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT) and sha(path) == expected, name


def main():
    native = read('native-wifi-probe.json')
    assert native['passed'] and len(native['cases']) == 5
    check_hashes(native['source_sha256'])
    old_path = ROOT / 'research/checkpoints/2026-09-06-npu-bootstrap/bootstrap-native.json'
    old = json.loads(old_path.read_text())
    assert native['elf_sha256'] == old['elf_sha256'] == sha(ROOT / old['elf'])
    assert native['dtb_sha256'] == sha(ROOT / '.local/npu-bootmem/candidate/an7581-w1700k-ubi.dtb')
    for filename, key in (('en7581_MT7996_npu_rv32.bin', 'firmware_sha256'),
                          ('en7581_MT7996_npu_data.bin', 'data_sha256')):
        assert native[key] == sha(ROOT / '.local/npu-quiescence/firmware' / filename)
    assert native['test_sha256'] == sha(ROOT / 'tests/npu/test_native_wifi_boot.py')
    ghidra_path = ROOT / ('research/checkpoints/2026-09-05-npu-admission/ghidra-mailbox/'
                          'en7581_MT7996_npu_rv32.bin.txt')
    assert native['ghidra_sha256'] == sha(ghidra_path)
    text = ghidra_path.read_text()
    assert len(native['source_spans']) == 13
    for row in native['source_spans']:
        match = re.search(r'^FUNCTION [^\n]* @ ram:' + row['address'][2:] +
                          r'\n.*?(?=^FUNCTION |\Z)', text, re.M | re.S)
        assert match and 'decompiled=true' in match.group()
        assert row['first_line'] == text[:match.start()].count('\n')+1
        assert row['last_line'] == text[:match.end()].count('\n')
        assert row['normalized_text_sha256'] == hashlib.sha256(match.group().encode()).hexdigest()
    for index, row in enumerate(native['cases']):
        assert row['core0_native_return'] and row['coordinator_idle_ack'] == 1
        assert row['other_workers_parked'] == row['physical_domains_drained'] == 0
        assert row['l2_clear_bytes'] == row['footprints']['whole_l2_compared_bytes'] == 262144
        assert row['l2_clear_pcs'] == ['0x840103c2', '0x840103c4', '0x840103c6', '0x840103c8']
        assert row['delayed_api23_and_host_rx'] == (index == 1)
        assert row['malformed_host_registers'] == (index == 2)
        assert row['missing_tx1_wait_checked'] == (index in (0, 3, 4))
        assert row['exhausted_skb_fixture'] == (index == 3)
        assert row['footprints']['allocation_failures'] == (2048 if index == 3 else 0)
        assert row['footprints']['tx_packet_pointers']['valid_entries'] == (0 if index == 3 else 2048)
        assert not row['footprints']['tx_packet_pointers']['backing_packet_memory_accessed']
        assert len(row['patches']) == 5
        assert {p['site'] for p in row['patches']} == {
            '0x84000074', '0x840000f0', '0x840030b2', '0x84000188', '0x84003f2e'}
        assert row['native_entry_counts']['0x84004c16'] == 2048
        assert row['native_entry_counts']['0x8400d1d4'] == row['native_entry_counts']['0x84009fc8'] == 1
        assert len(row['allocations']) == 11
        assert set(row['stub_counts']) <= {'0x840048f4', '0x84004212', '0x84004130',
                                          '0x8400452a', 'mhartid-csr'}
    assert len(native['model_controls']) == 3
    assert [row['missing_register'] for row in native['model_controls']] == [
        '0x1ec0f200', '0x1fb50a04', '0x1ec0d0b0']

    host = read('host-sequence.json')
    assert host['passed'] and host['mt76_revision'] == 'be5ce7910521492d4a2e4ce7ee3843680a46c047'
    check_hashes(host['inputs'])
    members = sources()
    for name, expected in host['mt76_archive_members'].items():
        assert hashlib.sha256(members[name]).hexdigest() == expected
    for row in host['host_adapter_source']['source_refs'].values():
        if 'path' in row:
            check_hashes({row['path']: row['sha256']})
        else:
            assert hashlib.sha256(members[row['archive_member']]).hexdigest() == row['sha256']
    original = exports()
    for address, row in host['static_ghidra_dependencies'].items():
        source = original[int(address, 16)]
        assert row['name'] == source['name'] and row['line'] == source['line']
        assert row['decompiled_sha256'] == hashlib.sha256(source['text'].encode()).hexdigest()
    assert host['host']['case_count'] == len(host['host']['cases']) == 164
    assert host['native']['case_count'] == len(host['native']['cases']) == 149
    assert len(host['host']['success_profiles']) == 4
    for profile in host['host']['success_profiles']:
        assert sum(row['kind'] == 'message' for row in profile['trace']) == 38
    assert len(host['host']['mutation_controls']) == 3
    pending = [row for row in host['native']['cases'] if row['halted_at']]
    assert len(pending) == 13 and all(row['flags'] == 1 for row in pending)
    assert sum(row['flags'] == 7 for row in host['native']['cases']) == 132
    assert sum(row['flags'] == 3 for row in host['native']['cases']) == 4
    scratch = ROOT / '.local/npu-nativewifi/host'
    assert sha(scratch / 'host-sequence') == host['host']['executable_sha256']
    assert sha(scratch / 'host-sequence.c') == host['host']['generated_c_sha256']

    protected = ['firmware', 'tests/npu/admission-platform-emulation.c',
                 'tests/npu/bootstrap-platform-emulation.c', 'tests/npu/startup-platform-emulation.c']
    subprocess.run(['git', 'diff', '--quiet', BASE, '--', *protected], cwd=ROOT, check=True)
    assert not subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard',
                                        '--', *protected], cwd=ROOT)
    for name in ('REPORT.md', 'HOST_SEQUENCE.md', 'NATIVE_REVIEW.md'):
        assert (OUT / name).is_file(), name
    result = {'passed': True, 'base_commit': BASE, 'native_core0_cases': 5,
              'missing_register_controls': 3, 'host_c_cases': 164,
              'native_callback_cases': 149, 'pending_callback_boundaries': 13,
              'host_mutants': 3, 'firmware_and_bindings_unchanged': True,
              'all_worker_boot': False, 'full_mt76_attach': False,
              'physical_containment': False, 'router_actions': False,
              'verifier_sha256': sha(Path(__file__)),
              'scope': 'Input/result binding of bounded software experiments, not hardware acceptance.'}
    files = [path for path in sorted(OUT.rglob('*')) if path.is_file() and
             path.name not in ('file-manifest.json', 'evidence-verification.json')]
    (OUT / 'file-manifest.json').write_text(json.dumps(
        {str(path.relative_to(ROOT)): sha(path) for path in files}, indent=2)+'\n')
    (OUT / 'evidence-verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
