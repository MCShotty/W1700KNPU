#!/usr/bin/env python3
"""Verify the scoped MT7996 reservation correction and native boot evidence."""
import hashlib
import json
from pathlib import Path
import subprocess

from test_txbuf_dtbs import BUILD, DTS, OUT, PROFILES, ROOT, expected_tree, properties

BASE = '0c1ed498946d19b7280e01a66094754c3d90a6e3'
CHANGED = 'target/linux/airoha/dts/an7581-npu-mt7996.dtsi'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_file(path):
    return subprocess.check_output(['git', 'show', BASE + ':' + path], cwd=ROOT)


def main():
    native = json.loads((OUT / 'native-txbuf-extent.json').read_text())
    assert native['passed']
    old, new = native['retained_r1'], native['candidate']
    assert old['reserved_bytes'] == 26624 and new['reserved_bytes'] == 57344
    assert old['native_cleared_bytes'] == new['native_cleared_bytes'] == 57344
    assert old['out_of_reservation_bytes'] == old['ba_overlap_bytes'] == 30720
    assert old['first_outside_pc'] == '0x84004f1e'
    assert new['out_of_reservation_bytes'] == new['ba_overlap_bytes'] == 0
    assert old['waited_for_host_before_clear'] and new['waited_for_host_before_clear']
    assert old['mailbox_flags'] == new['mailbox_flags'] == 7
    assert new['relocated_ba_address_accepted_by_native_api7']
    controls = native['partial_fix_controls']
    assert controls == {
        'short_table': {'rejected': True, 'out_of_reservation_bytes': 30720, 'ba_overlap_bytes': 0},
        'unmoved_ba': {'rejected': True, 'out_of_reservation_bytes': 0, 'ba_overlap_bytes': 30720}}
    staged = ROOT / '.build/openwrt/staging_dir/target-aarch64_cortex-a53_musl/root-airoha/lib/firmware/airoha'
    assert sha(staged / 'en7581_MT7996_npu_rv32.bin') == native['firmware_sha256']
    assert sha(staged / 'en7581_MT7996_npu_data.bin') == native['data_sha256']
    baseline = json.loads((OUT / 'baseline-dtbs.json').read_text())
    candidate = json.loads((OUT / 'candidate-dtbs.json').read_text())
    assert baseline['passed'] and candidate['passed']
    assert [row['profile'] for row in candidate['profiles']] == list(PROFILES)
    for before, after in zip(baseline['profiles'], candidate['profiles']):
        profile = after['profile']
        old_dtb, new_dtb = [BUILD / kind / (profile + '.dtb') for kind in ('baseline', 'candidate')]
        assert sha(old_dtb) == before['dtb_sha256'] and sha(new_dtb) == after['dtb_sha256']
        assert expected_tree(properties(old_dtb), profile != 'an7581-evb') == properties(new_dtb)
        assert after['only_intended_reservation_changes']
    assert baseline['profiles'][-1]['dtb_sha256'] == candidate['profiles'][-1]['dtb_sha256']
    assert candidate['profiles'][0]['dtb_sha256'] == new['dtb_sha256']
    old_lock = json.loads(git_file('firmware/source-lock.json'))
    lock = json.loads((ROOT / 'firmware/source-lock.json').read_text())
    assert lock['last_router_tested_snapshot'] == old_lock['last_router_tested_snapshot']
    assert lock['snapshot'] == 'post-Daybreak21-R1-NPU-txbuf-reservation-20260906'
    before = {row['path']: row for row in old_lock['openwrt']['changed_files']}
    after = {row['path']: row for row in lock['openwrt']['changed_files']}
    assert after.keys() - before.keys() == {CHANGED} and not before.keys() - after.keys()
    assert all(after[name] == value for name, value in before.items())
    assert after[CHANGED]['sha256'] == sha(DTS / 'an7581-npu-mt7996.dtsi')
    assert lock['luci'] == old_lock['luci'] and lock['feeds'] == old_lock['feeds']
    old_patch = git_file('firmware/patches/openwrt.patch')
    patch = (ROOT / 'firmware/patches/openwrt.patch').read_bytes()
    assert patch.endswith(old_patch)
    prefix = patch[:-len(old_patch)]
    assert prefix.count(b'diff --git ') == 1
    assert prefix.startswith(('diff --git a/' + CHANGED + ' b/' + CHANGED + '\n').encode())
    assert not subprocess.check_output(['git', 'diff', '--name-only', BASE, '--', 'firmware/overlay',
        'firmware/npu', 'firmware/build.config', 'firmware/feeds.conf.default', 'firmware/patches/luci.patch'], cwd=ROOT)
    reconstructed = json.loads((OUT / 'source-export-verification.json').read_text())
    assert [row['changed_files_verified'] for row in reconstructed] == [35, 3]
    assert all(row['passed'] for row in reconstructed)
    result = {'passed': True, 'affected_profiles': 3, 'unchanged_generic_control': True,
              'old_overlap_bytes': 30720, 'corrected_overlap_bytes': 0, 'partial_fix_controls': 2,
              'packaged_source_delta': CHANGED, 'source_lock_sha256': sha(ROOT / 'firmware/source-lock.json'),
              'cumulative_patch_sha256': sha(ROOT / 'firmware/patches/openwrt.patch'),
              'inputs': {name: sha(ROOT / name) for name in (
                  'tests/npu/test_boot_txbuf_extent.py', 'tests/npu/test_txbuf_dtbs.py',
                  'tests/npu/test_firmware_mailbox_dispatch.py', 'tests/npu/test_firmware_stop_irqs.py',
                  'tests/npu/test_firmware_stop_counterexample.py', 'tests/npu/test_firmware_memory_layout.py',
                  'tests/npu/emulation_layout.py', 'tools/migration/verify_source_export.py')},
              'verifier_sha256': sha(Path(__file__)),
              'scope': 'Native instruction/DTB/source reconstruction proof. No full image, flash, active-NPU hardware or client Wi-Fi acceptance.'}
    (OUT / 'evidence-verification.json').write_text(json.dumps(result, indent=2) + '\n')
    manifest = [{'path': str(path.relative_to(OUT)), 'bytes': path.stat().st_size, 'sha256': sha(path)}
                for path in sorted(OUT.rglob('*')) if path.is_file() and path.name != 'file-manifest.json']
    (OUT / 'file-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'passed': True, 'affected_profiles': 3, 'unchanged_control': 1,
                      'native_overlap_bytes': [30720, 0], 'manifest_files': len(manifest)}))


if __name__ == '__main__':
    main()
