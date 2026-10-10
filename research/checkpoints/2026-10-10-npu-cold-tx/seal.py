from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess

root = Path('/home/captain/W1700KNPU')
here = root / '.local/npu-cold-tx-20261010'
out = root / 'research/checkpoints/2026-10-10-npu-cold-tx'
assert not (out / 'verification.json').exists()

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def record(path):
    return dict(path=str(path.relative_to(root)), sha256=sha(path), bytes=path.stat().st_size)

receipts = {
    'tx-core.json': here / 'core-world-qualification/result.json',
    'indication-core.json': root / '.local/npu-cold-indication-20261010/tx-indication-core/result.json',
    'cold-wire.json': root / '.local/npu-cold-wire-20261010/tx-wire-qualification/result.json',
    'linux-native.json': root / '.local/npu-provider-session-20261010/tx-native-qualification/result.json',
    'linux-hif2.json': root / '.local/npu-provider-session-20261010/tx-hif2-qualification/result.json',
    'endpoint-mutants.json': root / '.local/npu-cold-pages-wire-20261010/tx-endpoint-qualification/result.json',
    'host-caller.json': root / '.local/npu-cold-pages-wire-20261010/tx-host-qualification/result.json',
    'parser.json': root / '.local/npu-loader-publish-20261010/tx-publish-qualification/result.json',
    'boot.json': root / '.local/npu-boot-launch-20261010/tx-boot-qualification/result.json',
    'lease.json': root / '.local/npu-loader-publish-20261010/tx-lease-qualification/result.json',
    'probe.json': root / '.local/npu-loader-publish-20261010/tx-probe-qualification/result.json',
    'request.json': root / '.local/npu-provider-plan-20261010/tx-request-qualification/result.json',
    'memory.json': root / '.local/npu-cold-memory-plan/tx-memory-qualification/result.json',
    'raw.json': root / '.local/npu-raw-pair-20261010/tx-raw-final/result.json',
    'image.json': root / '.local/merge-nonoc-20260923/cold-tx-20261010-offline/result.json',
    'source-replay.json': here / 'source-replay-final.json',
    'assembly.json': here / 'assembly-final.json',
    'build-state.json': root / '.local/merge-nonoc-20260923/build-npu-cold-tx-20261010.json',
    'static-dispatch.json': here / 'static-dispatch.json',
    'next-setup-inputs.json': here / 'next-setup-inputs.json',
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
core_test = loaded['tx-core.json']
assert core_test['passed'] and core_test['exact_core_object']
assert core_test['host_rv32_calls'] == 525 and core_test['controls'] == 205
assert len(core_test['mutants']) == 6
indication = loaded['indication-core.json']
assert indication['passed'] and indication['exact_core_object']
assert indication['host_rv32_calls'] == 12322 and indication['controls'] == 3095 and len(indication['mutants']) == 7
assert loaded['cold-wire.json']['passed'] and loaded['cold-wire.json']['matrix']['cases'] == 459
assert len(loaded['cold-wire.json']['mutants']) == 16
assert loaded['cold-wire.json']['matrix']['tx_geometry_cases'] == 16
native = loaded['linux-native.json']
assert native['passed'] and native['complete_cold_native_suite'] and len(native['native']) == 7
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
assert any(row.get('next_unsupported') and row['header'] == 0x30 and row['api'] == 4 for row in nominal['cold'])
tx_negative = next(row['tx_native_controls'] for row in nominal['cold'] if 'tx_native_controls' in row)
assert len(tx_negative) == len({row['name'] for row in tx_negative}) == 27
assert sum(row['phase'] == 'late' for row in tx_negative) == 12
assert all(row['register_stores'] == 0 and row['retained_active'] == row['retained_inflight'] == 1 for row in tx_negative)
assert all(row['committed'] == row['published'] == (3 if row['phase'] == 'late' else 0) for row in tx_negative)
fault = native['native'][4]
assert fault['indication_failure'] and fault['passed']
partial = next(row for row in fault['cold'] if row.get('retained_inflight'))
assert partial['indication_committed'] == 1 and partial['indication_published'] == 0
assert partial['retained_packet_claims'] == 2560 and partial['retained_ba_claims'] == 1792
assert partial['retained_active'] == partial['retained_inflight'] == 1
for index, flag, committed, published in (
    (5, 'tx_failure', 4, 3), (6, 'token_failure', 11, 10)):
    fault = native['native'][index]
    assert fault[flag] and fault['passed']
    partial = next(row for row in fault['cold'] if 'tx_committed' in row)
    assert partial['tx_committed'] == committed and partial['tx_published'] == published
    assert partial['retained_active'] == partial['retained_inflight'] == 1
    assert partial['retained_packet_claims'] == 2560 and partial['retained_ba_claims'] == 1792
    assert partial['reply']['reply']['words'][14] == 7
hif2 = loaded['linux-hif2.json']
assert hif2['passed'] and hif2['native_case'] == 'nominal' and len(hif2['native']) == 1
peer = hif2['native'][0]
assert peer['hif2'] and peer['actual_c_txrx_sender']
assert any(row.get('header') == 0x12 and row.get('api') == 19 and row['value'] == 0x200d8450 for row in peer['cold'])
assert loaded['endpoint-mutants.json']['passed'] and len(loaded['endpoint-mutants.json']['mutants']) == 6
assert loaded['host-caller.json']['passed'] and loaded['host-caller.json']['publication_cases'] == 3
assert loaded['raw.json']['passed'] and loaded['raw.json']['full_nominal'] and loaded['raw.json']['txdone']['claimed'] == 3072
assert loaded['raw.json']['independent_pages'][-1]['claimed'] == 1792
assert loaded['raw.json']['hooks'] == 74 and len(loaded['raw.json']['authenticated_cold_prefix']) == 18
assert not loaded['raw.json']['initial_test_active_writes'] and not loaded['raw.json']['initial_direct_owner_init']
assert loaded['raw.json']['later_txdone_lease_modeled']
assert loaded['image.json']['sha256'] == '4da01cfe0136b72014b71f3220323a38ee9e5b3987396b69f55fba6cf8afae84'
assert loaded['build-state.json']['exit_code'] == 0
assert loaded['assembly.json']['passed'] and loaded['assembly.json']['test_groups'] == 16 and not loaded['assembly.json']['skipped']
assert loaded['static-dispatch.json']['canonical_components'] == 13
assert len(loaded['static-dispatch.json']['nested_source_replay']) == 12
assert sum(row['changed_files_verified'] for row in loaded['source-replay.json']) == 66
for name in ('jev-design.json', 'jev-design-result.json', 'make-design.py',
             'jev-review.json', 'jev-review-result.json', 'make-review.py',
             'original-token-body.txt', 'provider-tx.patch', 'checkpatch.log',
             'review-delta.py', 'static-dispatch.py', 'run-regressions.py', 'regressions.json',
             'run_ghidra.ps1', 'all.pattern', 'verify-seal.py', 'make-next-review.py',
             'jev-next-setup.json', 'jev-next-setup-result.json'):
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
assert sha(core) == '413cdd509fac32b91087896dde38acc384848614b4d6849ff4d587be6995db1e'
assert len(subprocess.check_output(['ar', 't', core], text=True).splitlines()) == 15
inputs[str(core.relative_to(root))] = sha(core)
for name, row in loaded['image.json']['selected_modules'].items():
    assert sha(root / row['path']) == row['sha256'], name
    inputs[row['path']] = row['sha256']
mapping = root / '.build/merged-openwrt/build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/linux-6.18.52/kernel/dma/mapping.c'
inputs[str(mapping.relative_to(root))] = sha(mapping)
backup = here / 'pre-world-image'
old = list(backup.glob('*-sysupgrade.itb'))
assert len(old) == 1 and len(list(backup.iterdir())) == 8
assert sha(old[0]) == '8dd1f2f4d62fbc9f8cf8061ead435527e01d85bcf90d0b05f3f6e4da0b1f16d9'
subprocess.run(['sha256sum', '--check', '--strict', 'sha256sums'], cwd=backup, check=True, capture_output=True)
previous_files = [record(path) for path in sorted(backup.iterdir())]
for row in previous_files:
    checked_input(row['path'], row['sha256'])
for name in ('README.md', 'AGENTS.md', 'docs/REMAINING_WORK.md',
             'docs/W1700K_STOCK_PORT_CURRENT_REFERENCE.md', 'docs/W1700K_STOCK_PORT_LEDGER.md',
             'docs/W1700K_STOCK_PORT_LOGGING_SESSION_20260625.md', 'firmware/npu/Makefile'):
    inputs[name] = sha(root / name)
pair = here / 'pair-qualification'
repeat = here / 'pair-repeat'
world_pair = root / loaded['build-state.json']['checked_npu_pair']['directory']
manifests = [json.loads((path / 'manifest.json').read_bytes()) for path in (pair, repeat, world_pair)]
assert all(item['inputs'] == manifests[0]['inputs'] for item in manifests)
assert all(len(item['components']) == 13 and len(item['hooks']) == 74 for item in manifests)
for path in (repeat, world_pair):
    for name in ('CODE.bin', 'DATA.bin'):
        assert (path / name).read_bytes() == (pair / name).read_bytes()
result = dict(schema=1, passed=True, inputs=inputs, source_files=66, nested_source_files=12,
              canonical_components=13, units=unit_rows, previous_image=record(old[0]),
              previous_files=previous_files, core_archive=record(core),
              build_log=record(root / '.local/merge-nonoc-20260923/build-npu-cold-tx-20261010.log'),
              provider_sha256=provider_hash, image_sha256=loaded['image.json']['sha256'],
              ghidra_functions=54, raw_hooks=74, archive_objects=15, raw_components=13,
              checkpatch=dict(errors=0, warnings=0, checks=0, clean=True),
              native_cases=7, native_indication_controls=34, native_tx_controls=27, hif2=True,
              native_direct_ownership_init=False, native_test_active_writes=False,
              physical_acceptance=False, flashed=False,
              limits=['Strict RX/page/indication1536/ACK/TX0/TX2/token prefix; actual offload C completes and next RXDESC-base GET remains denied. Remaining host/INODE/TXDONE/final IRQ and physical lifecycle/client gates remain open.',
                      'Native grants/backing/delivery/cache/DMA/scheduling remain modeled. Negative memory snapshots include private CODE history and are test-only, not a reset API.',
                      'Separate later/full raw TXDONE still uses a modeled direct lease; it does not complete the missing strict host setup path.'])
(out / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
shutil.copy2(Path(__file__), out / 'seal.py')
files = [record(path) for path in sorted(out.iterdir()) if path.is_file()]
(out / 'file-manifest.json').write_text(json.dumps(dict(schema=1, files=files), indent=2) + '\n')
assert all(sha(root / row['path']) == row['sha256'] for row in files)
print(json.dumps(dict(passed=True, sealed_inputs=len(inputs), sealed_files=len(files),
                      verification_sha256=sha(out / 'verification.json'))))
