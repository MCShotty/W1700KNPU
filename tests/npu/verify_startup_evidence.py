#!/usr/bin/env python3
"""Bind the unpromoted startup candidate, races, regressions and snapshot evidence."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
from elftools.elf.elffile import ELFFile
from test_startup_native import ROOT, OUT, BUILD, STARTUP, cold_data

BASE = '3e1f435d4e98e13e6230c94419073e69acb87698'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((OUT / name).read_text())


def main():
    run, native, protocol, race = [read(n) for n in ('startup-regressions.json', 'startup-native-tests.json',
                                                    'startup-protocol-tests.json', 'startup-race-tests.json')]
    assert all(r['passed'] for r in [run, native, protocol, race])
    assert len(native['reset_orders']) == native['register_cases'] == 32
    assert len(native['rejection_cases']) == 30 and len(native['negative_controls']) == 2
    assert native['fault_during_initialization_retained'] and native['template_preserves_original_prefix']
    assert native['cold_data_bytes'] == 25024 and native['cold_data_sha256'] == hashlib.sha256(cold_data()).hexdigest()
    assert sha(BUILD / 'cold-sram-test-input.bin') == native['cold_data_sha256']
    assert protocol['cases'] == 173 and protocol['differential_calls'] == 2126
    assert len(protocol['mutations_killed']) == 6 and all(protocol['mutations_killed'].values())
    source_sha = sha(ROOT / 'firmware/npu/startup.c')
    assert protocol['source_sha256'] == race['source_sha256'] == source_sha
    assert race['preimage']['publication']['publish_result'] == 1
    assert race['preimage']['publication']['poll_result'] == race['preimage']['fault_after_ready_acquire'] == 2
    assert race['fixed']['publication'] == {'phase_when_fault_latched': 3, 'publish_result': 0, 'poll_result': 3}
    assert race['fixed']['fault_after_ready_acquire'] == 3
    review = (OUT / 'STARTUP_REVIEW.md').read_text()
    assert source_sha in review and sha(ROOT / 'tests/npu/startup-emulation.S') in review
    assert 'Original P2 addressed at source level' in review
    assert run['reproducible_both_builds'] and run['default_late_completion_holds'] == 2
    assert run['default_poll_limit'] == 65536 and run['test_poll_limit'] == 64
    layout = read('regressions/layout-regressions.json')
    assert layout['passed'] and len(run['suites']) == len(layout['runs']) == 12
    assert [row['suite'] for row in layout['runs']] == run['suites']
    for row in layout['runs']:
        assert row['passed']
        for name, expected in row['evidence'].items():
            assert sha(ROOT / name) == expected, name
    for name, expected in layout['source_sha256'].items():
        assert sha(ROOT / name) == expected, name
    for key in ['default_elf', 'combined_elf']:
        assert sha(ROOT / run[key]) == run[key+'_sha256']
    assert native['elf_sha256'] == run['default_elf_sha256']
    assert read('combined-copy-tests.json')['elf_sha256'] == run['combined_elf_sha256']
    with (ROOT / run['default_elf']).open('rb') as stream:
        elf = ELFFile(stream)
        symbols = {s.name: int(s['st_value']) for s in elf.get_section_by_name('.symtab').iter_symbols()}
        assert symbols['npu_emulation_startup_state'] == STARTUP
        sections = [{'name': s.name, 'start': int(s['sh_addr']), 'end': int(s['sh_addr']+s['sh_size'])}
                    for s in elf.iter_sections() if s['sh_flags'] & 2 and s['sh_size']]
        assert all(0x84040000 <= s['start'] < s['end'] <= 0x84048000 for s in sections)
    exported = OUT / 'ghidra-default/admission-platform-startup-gdma-gdma-65536.elf.txt'
    text = exported.read_text()
    assert 'sha256='+run['default_elf_sha256'] in text and 'failed_decompilations=0' in text
    assert 'exported_functions=6' in text and 'total_executable_functions=56' in text
    for instruction in ['840427da sw t1,0xc(t0)', '840427e6 sw t1,0x10(t0)',
                        '8404266e lr.w.aq', '84042676 sc.w.rl',
                        '840427c6 j 0x84000078', '8404289a j 0x840000f4']:
        assert instruction in text, instruction
    log = (OUT / 'ghidra-default/analysis.log').read_text()
    assert 'STARTUP_SEEDED npu_emulation_before_bss' in log
    assert 'STARTUP_SEEDED npu_emulation_cold_start' in log and 'Analysis timed out' not in log
    assert 'MAILBOX_CONTRACT_PASS functions=6 analyzed=56' in log
    callbacks = read('bootstrap-callbacks.json')
    assert callbacks['passed'] and callbacks['counts']['total'] == 218
    snapshot = read('snapshot-comparison.json')
    assert snapshot['current_snapshot']['revision'] == 'r36060-d6933d6aed'
    assert snapshot['current_snapshot']['mt76_commit'] == 'be5ce7910521492d4a2e4ce7ee3843680a46c047'
    assert snapshot['validation']['openwrt_file_hash_matches'] == 18
    assert snapshot['validation']['npu_payloads_match_canonical_input']
    assert snapshot['reconstruction']['prepared_source_matches']
    assert snapshot['canonical']['source_lock_sha256'] == sha(ROOT / 'firmware/source-lock.json')
    artifact_root = Path(snapshot['artifact_root']).resolve()
    assert artifact_root == (ROOT / '.local/npu-startup/snapshot-audit').resolve()
    assert len(snapshot['artifacts']) == 58
    for row in snapshot['artifacts']:
        path = (artifact_root / row['path']).resolve()
        assert path.is_relative_to(artifact_root)
        assert path.stat().st_size == row['bytes'] and sha(path) == row['sha256'], row['path']
    protected = ['firmware/source-lock.json', 'firmware/overlay', 'firmware/patches',
                 'firmware/build.config', 'firmware/feeds.conf.default']
    assert not subprocess.check_output(['git', 'diff', '--name-only', BASE, '--', *protected], cwd=ROOT)
    helpers = ['SetupStartupCandidateMap.java', 'SeedStartupCandidate.java', 'startup-candidate.pattern',
               'run_startup_candidate.ps1', 'ExportMailboxContract.java']
    result = {'passed': True, 'base': BASE, 'packaged_source_unchanged': True,
              'startup_source_sha256': source_sha, 'default_elf_sha256': run['default_elf_sha256'],
              'elf_sections': sections, 'cold_data_bytes': 25024, 'native_reset_orders': 32,
              'native_register_cases': 32, 'rejected_entries': 30, 'protocol_cases': 173,
              'differential_calls': 2126, 'source_mutants': 6, 'race_controls': 2,
              'callback_cases': 218, 'regression_suites': 12, 'snapshot_artifacts': 58,
              'ghidra_functions': 6, 'ghidra_export_sha256': sha(exported),
              'helpers': {n: sha(ROOT / 'tools/ghidra' / n) for n in helpers},
              'verifier_sha256': sha(Path(__file__)),
              'scope': 'Unpromoted reset/software contract and exact snapshot comparison. Not complete bootstrap, physical loader/cache/drain, Linux recovery, image acceptance or client proof.'}
    (OUT / 'evidence-verification.json').write_text(json.dumps(result, indent=2) + '\n')
    manifest = [{'path': str(p.relative_to(OUT)), 'bytes': p.stat().st_size, 'sha256': sha(p)}
                for p in sorted(OUT.rglob('*')) if p.is_file() and p.name != 'file-manifest.json']
    (OUT / 'file-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'passed': True, 'manifest_files': len(manifest), 'protocol_cases': 173,
                      'differential_calls': 2126, 'race_controls': 2, 'snapshot_artifacts': 58}))


if __name__ == '__main__':
    main()
