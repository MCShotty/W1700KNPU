from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess

root = Path('/home/captain/W1700KNPU')
here = root / '.local/npu-cold-indication-20261010'
out = root / 'research/checkpoints/2026-10-10-npu-cold-indication'
assert not (out / 'verification.json').exists()

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def record(path):
    return dict(path=str(path.relative_to(root)), sha256=sha(path), bytes=path.stat().st_size)

receipts = {
    'indication-core.json': here / 'core-world-sealed/result.json',
    'cold-wire.json': root / '.local/npu-cold-wire-20261010/indication-wire-sealed/result.json',
    'linux-native.json': root / '.local/npu-provider-session-20261010/indication-native-sealed/result.json',
    'endpoint-mutants.json': root / '.local/npu-cold-pages-wire-20261010/indication-endpoint-sealed/result.json',
    'host-caller.json': root / '.local/npu-cold-pages-wire-20261010/indication-host-final/result.json',
    'parser.json': root / '.local/npu-loader-publish-20261010/indication-publish-final/result.json',
    'boot.json': root / '.local/npu-boot-launch-20261010/indication-boot-final/result.json',
    'lease.json': root / '.local/npu-loader-publish-20261010/indication-lease-final/result.json',
    'probe.json': root / '.local/npu-loader-publish-20261010/indication-probe-final/result.json',
    'request.json': root / '.local/npu-provider-plan-20261010/indication-request-final/result.json',
    'memory.json': root / '.local/npu-cold-memory-plan/indication-memory-final/result.json',
    'raw.json': root / '.local/npu-raw-pair-20261010/indication-regression-final/result.json',
    'image.json': root / '.local/merge-nonoc-20260923/cold-indication-20261010-offline/result.json',
    'source-replay.json': here / 'source-replay-final.json',
    'assembly.json': here / 'assembly-final.json',
    'build-state.json': root / '.local/merge-nonoc-20260923/build-npu-cold-indication-20261010.json',
    'static-dispatch.json': here / 'static-dispatch.json',
}
inputs, loaded = {}, {}

def checked_input(path, digest):
    assert not Path(path).is_absolute()
    resolved = (root / path).resolve()
    assert resolved.is_relative_to(root) and sha(resolved) == digest, ('changed-input', path)
    assert path not in inputs or inputs[path] == digest, ('conflicting-input', path)
    inputs[path] = digest

def collect(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ('inputs', 'source_inputs', 'inputs_before_after', 'protected_inputs'):
                if isinstance(item, dict):
                    for path, digest in item.items():
                        if isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest):
                            checked_input(path, digest)
                elif isinstance(item, list):
                    for entry in item:
                        checked_input(entry['path'], entry['sha256'])
            else:
                collect(item)
    elif isinstance(value, list):
        for item in value:
            collect(item)

for name, path in receipts.items():
    value = json.loads(path.read_bytes())
    collect(value)
    loaded[name] = value
    shutil.copy2(path, out / name)
core_test = loaded['indication-core.json']
assert core_test['passed'] and core_test['exact_core_object']
assert core_test['host_rv32_calls'] == 12322 and core_test['controls'] == 3095
assert len(core_test['mutants']) == 7
assert loaded['cold-wire.json']['passed'] and loaded['cold-wire.json']['matrix']['cases'] == 425
assert len(loaded['cold-wire.json']['mutants']) == 13
native = loaded['linux-native.json']
assert native['passed'] and native['complete_cold_native_suite'] and len(native['native']) == 5
assert native['matrix']['cases'] == 545 and len(native['mutants']) == 9
nominal = native['native'][0]
assert nominal['actual_c_txrx_sender'] and not nominal['synthetic_plan_identity_writes']
retained = next(row for row in nominal['cold'] if 'retained_ba_claims' in row)
assert retained['retained_claims'] == 2560 and retained['retained_ba_claims'] == 1792
assert retained['indication_committed'] == retained['indication_published'] == 1536
assert not retained['test_active_writes'] and not retained['test_indication_init']
negative = next(row['indication_native_controls'] for row in nominal['cold'] if 'indication_native_controls' in row)
assert len(negative) == len({row['name'] for row in negative}) == 34
assert sum(row['phase'] == 'late' for row in negative) == 15
assert all(not row['original_record_store'] and row['published'] == 0 for row in negative)
assert any(row.get('next_unsupported') and row['header'] == 0x10 and row['api'] == 19 for row in nominal['cold'])
fault = native['native'][-1]
assert fault['indication_failure'] and fault['passed']
partial = next(row for row in fault['cold'] if row.get('retained_inflight'))
assert partial['indication_committed'] == 1 and partial['indication_published'] == 0
assert partial['retained_packet_claims'] == 2560 and partial['retained_ba_claims'] == 1792
assert partial['retained_active'] == partial['retained_inflight'] == 1
assert loaded['endpoint-mutants.json']['passed'] and len(loaded['endpoint-mutants.json']['mutants']) == 6
assert loaded['host-caller.json']['passed'] and loaded['host-caller.json']['publication_cases'] == 3
assert loaded['raw.json']['passed'] and loaded['raw.json']['full_nominal'] and loaded['raw.json']['txdone']['claimed'] == 3072
assert loaded['raw.json']['independent_pages'][-1]['claimed'] == 1792
assert loaded['image.json']['sha256'] == '8dd1f2f4d62fbc9f8cf8061ead435527e01d85bcf90d0b05f3f6e4da0b1f16d9'
assert loaded['build-state.json']['exit_code'] == 0
assert loaded['assembly.json']['passed'] and loaded['assembly.json']['test_groups'] == 16 and not loaded['assembly.json']['skipped']
assert loaded['static-dispatch.json']['canonical_components'] == 13
assert len(loaded['static-dispatch.json']['nested_source_replay']) == 12
assert sum(row['changed_files_verified'] for row in loaded['source-replay.json']) == 66
for name in ('jev-design.json', 'jev-design-result.json', 'design-jev.py',
             'jev-review.json', 'jev-review-result.json', 'make-jevreview.py',
             'provider-indication.patch', 'checkpatch.log', 'review-delta.py', 'static-dispatch.py',
             'run_ghidra.ps1', 'all.pattern', 'verify-seal.py', 'make-jevfocused.py',
             'jev-focused-hooks.json', 'jev-focused-hooks-result.json',
             'jev-focused-profile.json', 'jev-focused-profile-result.json',
             'jev-focused-ack.json', 'jev-focused-ack-result.json'):
    shutil.copy2(here / name, out / name)
for name in ('airoha_npu.ko.txt', 'analysis.log', 'script.log', 'console.log'):
    shutil.copy2(here / 'ghidra-full' / name, out / ('ghidra-' + name))
text = (out / 'ghidra-airoha_npu.ko.txt').read_text()
provider_hash = loaded['image.json']['selected_modules']['airoha_npu.ko']['sha256']
assert 'sha256=' + provider_hash in text
assert 'total_executable_functions=54' in text and 'exported_functions=54' in text
assert 'failed_decompilations=0' in text and 'decompiled=false' not in text
assert 'total: 0 errors, 0 warnings, 0 checks' in (out / 'checkpatch.log').read_text()
unit_rows = []
for name in ('test_build_firmware_host_tools.py', 'test_verify_source_export.py', 'test_verify_control_ownership.py'):
    command = ['python3', '-m', 'unittest', 'discover', '-s', 'tests', '-p', name, '-v']
    done = subprocess.run(command, cwd=root, capture_output=True, text=True)
    path = out / (name.removesuffix('.py') + '.log')
    path.write_text(done.stdout + done.stderr)
    assert done.returncode == 0
    unit_rows.append(dict(command=command, exit_code=done.returncode, log=record(path)))
for name in ('firmware/source-lock.json', 'firmware/patches/openwrt.patch', 'firmware/patches/luci.patch',
             'firmware/overlay/openwrt/target/linux/airoha/patches-6.18/999-w1700k-integrated-npu.patch',
             'firmware/overlay/openwrt/package/kernel/mt76/patches/900-w1700k-integrated-npu.patch',
             'tools/merge_nonoc_sources.py', 'tools/verify_merged_image.py'):
    inputs[name] = sha(root / name)
core = root / '.build/merged-openwrt/bin/npu/libw1700k-npu.a'
assert sha(core) == 'ee86953a56f524a98353748045b0df0e8e5bcce2253aabb3b9cb45bc7f467ecb'
inputs[str(core.relative_to(root))] = sha(core)
for name, row in loaded['image.json']['selected_modules'].items():
    assert sha(root / row['path']) == row['sha256'], name
    inputs[row['path']] = row['sha256']
backup = here / 'pre-world-image'
old = list(backup.glob('*-sysupgrade.itb'))
assert len(old) == 1 and len(list(backup.iterdir())) == 8
assert sha(old[0]) == '5c94b20d3dbcf37fafa4b2bce129671933cff4d61a582c636223061b69cfb43e'
result = dict(schema=1, passed=True, inputs=inputs, source_files=66, nested_source_files=12,
              canonical_components=13, units=unit_rows, previous_image=record(old[0]), core_archive=record(core),
              build_log=record(root / '.local/merge-nonoc-20260923/build-npu-cold-indication-20261010.log'),
              provider_sha256=provider_hash, image_sha256=loaded['image.json']['sha256'],
              ghidra_functions=54, raw_hooks=63, archive_objects=14,
              checkpatch=dict(errors=0, warnings=0, checks=0, clean=True),
              native_cases=5, native_indication_controls=34,
              native_direct_ownership_init=False, native_test_active_writes=False,
              physical_acceptance=False, flashed=False,
              limits=['Strict RX/page/indication1536/ACK prefix only; actual sender stops at TX0/API19. Complete strict TX/INODE/TXDONE and physical lifecycle/client gates remain open.',
                      'Native grants/backing/delivery/cache/DMA/scheduling remain modeled. Negative memory snapshots include private CODE history and are test-only, not a reset API.',
                      'Separate later/full raw TXDONE still uses a modeled direct lease; it does not complete the missing strict host setup path.'])
(out / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
shutil.copy2(Path(__file__), out / 'seal.py')
files = [record(path) for path in sorted(out.iterdir()) if path.is_file()]
(out / 'file-manifest.json').write_text(json.dumps(dict(schema=1, files=files), indent=2) + '\n')
assert all(sha(root / row['path']) == row['sha256'] for row in files)
print(json.dumps(dict(passed=True, sealed_inputs=len(inputs), sealed_files=len(files),
                      verification_sha256=sha(out / 'verification.json'))))
