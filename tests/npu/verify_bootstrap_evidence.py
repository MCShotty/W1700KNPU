#!/usr/bin/env python3
"""Bind this candidate's receipts to current sources, inputs and compiled code."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/checkpoints/2026-09-06-npu-bootstrap'
BASE = '452d420f24b1afbdcfd4adaf8067bba477059784'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((OUT / name).read_text())


def check_hashes(entries):
    for name, expected in entries.items():
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT) and sha(path) == expected, name


def main():
    native = read('bootstrap-native.json')
    assert native['passed'] and native['cold_data_bytes'] == 25392
    check_hashes(native['source_sha256'])
    assert sha(ROOT / native['elf']) == native['elf_sha256']
    assert sha(ROOT / '.local/npu-bootstrap/bootstrap-cold-sram-test-input.bin') == native['cold_data_sha256']
    assert sha(ROOT / '.local/npu-bootmem/candidate/an7581-w1700k-ubi.dtb') == native['dtb_sha256']
    integrated = native['integrated']
    assert integrated['early_version']['words'] == [0x30, 10, 0x457]
    assert integrated['early_version']['flags'] == 7
    assert [row['words'][1] for row in integrated['provider_replies']] == [18, 32, 8, 23, 7, 12]
    assert all(row['flags'] == 7 for row in integrated['provider_replies'])
    assert integrated['cleared_bytes'] == 57344 and integrated['retained_mask'] == 0x1e
    assert integrated['control_capabilities'] == 7 and integrated['core0_boundary'] == '0x8400e330'
    assert len(native['rejected']['invalid_requests']) == 35 and len(native['controls']) == 7
    assert native['rejected']['duplicate_commands_rejected'] == 6
    assert native['rejected']['post_reservation_mt76_commands_still_closed'] == 4
    for name, expected in [('en7581_MT7996_npu_rv32.bin', native['firmware_sha256']),
                           ('en7581_MT7996_npu_data.bin', native['data_sha256'])]:
        assert sha(ROOT / '.local/npu-quiescence/firmware' / name) == expected

    policy = read('bootstrap-protocol.json')
    assert policy['passed'] and policy['scenarios'] == 228
    assert policy['native_rv32_call_pairs'] == 5935 and policy['bootstrap_oracle_call_pairs'] == 5286
    assert policy['mutants_compiled_and_killed'] == len(policy['mutation_controls']) == 14
    assert all(row['compiled_native_and_rv32'] and row['rejected'] for row in policy['mutation_controls'].values())
    check_hashes(policy['inputs_sha256'])
    for name, key in [('bootstrap.so', 'native_elf_sha256'), ('bootstrap.elf', 'rv32_elf_sha256')]:
        assert sha(ROOT / '.local/npu-bootstrap/protocol' / name) == policy[key]

    late = read('startup-late-hart.json')
    assert late['passed'] and len(late['fixed_cases']) == len(late['preimage_cases']) == 16
    assert sum('falsely_rejected_late_hart' in row for row in late['preimage_cases']) == 14
    assert late['binding_sha256'] == sha(ROOT / 'tests/npu/startup-platform-emulation.c')
    assert late['test_sha256'] == sha(ROOT / 'tests/npu/test_startup_late_hart.py')

    irq = read('irq-installation.json')
    assert irq['passed'] and len(irq['ordering_cases']) == 4 and len(irq['interception_cases']) == 2
    assert len(irq['binding_controls']) == 7
    assert irq['test_sha256'] == sha(ROOT / 'tests/npu/test_boot_irq_installation.py')
    check_hashes({'tests/npu/' + name: digest for name, digest in irq['unchanged_helpers'].items()})
    original = irq['source_evidence']
    assert sha(ROOT / original['provider_path']) == original['provider_sha256']
    assert sha(ROOT / original['header_path']) == original['header_sha256']
    assert sha(ROOT / 'research/checkpoints/2026-09-05-npu-admission/ghidra-mailbox/en7581_MT7996_npu_rv32.bin.txt') == original['ghidra_sha256']

    regressions = read('regressions/bootstrap-regressions.json')
    assert regressions['passed'] and len(regressions['runs']) == 4
    for run in regressions['runs']:
        assert run['passed']
        check_hashes(run['evidence'])
    prefix = 'regressions/run_startup_regressions/'
    layout = read(prefix + 'regressions/layout-regressions.json')
    assert layout['passed'] and len(layout['runs']) == 12
    check_hashes(layout['source_sha256'])
    prior = read(prefix + 'startup-regressions.json')
    assert prior['passed'] and prior['reproducible_both_builds']
    assert prior['default_late_completion_holds'] == 2
    start = read('regressions/test_startup_native/startup-native-tests.json')
    assert start['passed'] and len(start['reset_orders']) == start['register_cases'] == 32
    assert len(start['rejection_cases']) == 30

    analysis = read('analysis-input.json')
    assert analysis['elf_sha256'] == native['elf_sha256'] and len(analysis['seeds']) == 11
    export = (OUT / 'ghidra' / (Path(native['elf']).name + '.txt')).read_text()
    assert 'sha256=' + native['elf_sha256'] in export
    assert 'exported_functions=11' in export and 'total_executable_functions=62' in export
    assert 'failed_decompilations=0' in export and 'decompiled=false' not in export
    assert len(re.findall(r'^FUNCTION ', export, re.M)) == 11
    log = (OUT / 'ghidra/script.log').read_text()
    for seed in analysis['seeds']:
        assert f"BOOTSTRAP_SEEDED {seed['name']} ram:{seed['start']} ram:{seed['end']}" in log
        assert f"FUNCTION {seed['name']} @ ram:{seed['start']}" in export
    for instruction in (
        '84042178 jalr ra,ra,0x2b8', '8404255e c.sw a1,0x10(a0)',
        '840425c2 c.sw a3,0x4(a0)', '84042736 bne a0,ra,0x84042742',
        '8404273e addi a1,a1,-0x648', '84042746 addi ra,ra,-0xce',
        '8404274a j 0x84003254', '84042ac4 c.beqz a0,0x84042aca',
        '84042aca lui a0,0x1ec0c', '84042bf0 j 0x84000078', '84042cc4 j 0x840000f4'):
        assert 'ram:' + instruction in export, instruction
    assert 'Analysis timed out' not in (OUT / 'ghidra/analysis.log').read_text()

    packaged = ['firmware/source-lock.json', 'firmware/build.config', 'firmware/feeds.conf.default',
                'firmware/patches', 'firmware/overlay']
    subprocess.run(['git', 'diff', '--quiet', BASE, '--', *packaged], cwd=ROOT, check=True)
    assert not subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--', *packaged], cwd=ROOT)
    review = OUT / 'BOOTSTRAP_REVIEW.md'
    assert review.exists() and 'No actionable' in review.read_text()
    report = {'passed': True, 'base_commit': BASE, 'packaged_source_unchanged': True,
              'elf_sha256': native['elf_sha256'], 'policy_call_pairs': 5935,
              'mutants_killed': 14, 'native_invalid_requests': 35, 'native_controls': 7,
              'prior_suites': 12, 'ghidra_selected_functions': 11,
              'complete_boot': False, 'physical_containment': False, 'router_actions': False,
              'scope': 'Current-source binding of the stated software proofs, not production release acceptance.'}
    files = [p for p in sorted(OUT.rglob('*')) if p.is_file() and
             p.name not in ('file-manifest.json', 'evidence-verification.json')]
    manifest = {str(p.relative_to(ROOT)): sha(p) for p in files}
    (OUT / 'file-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (OUT / 'evidence-verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({**report, 'manifest_files': len(manifest)}))


if __name__ == '__main__':
    main()
