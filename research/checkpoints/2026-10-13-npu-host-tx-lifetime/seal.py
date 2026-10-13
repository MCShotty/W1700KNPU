from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import sys

ROOT = Path('/home/captain/W1700KNPU')
HERE = ROOT / '.local/npu-host-tx-lifetime-20261011'
OUT = ROOT / 'research/checkpoints/2026-10-13-npu-host-tx-lifetime'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
receipts = {
    'host-lifetime.json': HERE / 'host-tx-final-style-20261013/result.json',
    'old-host-counterexample.json': HERE / 'old-caller-style-20261013/result.json',
    'old-alias-counterexample.json': HERE / 'alias-before-style-20261013/result.json',
    'linux-session.json': ROOT / '.local/npu-provider-session-20261010/host-tx-session-fixed-20261013/result.json',
    'native-status.json': HERE / 'native-status-qualified-20261013/result.json',
    'host-prefix.json': ROOT / '.local/npu-cold-pages-wire-20261010/host-tx-prefix-qualified-20261013/result.json',
    'endpoint.json': ROOT / '.local/npu-cold-pages-wire-20261010/host-tx-endpoint-final-20261013-seal/result.json',
    'lease.json': ROOT / '.local/npu-loader-publish-20261010/host-tx-lease-style-20261013/result.json',
    'request.json': ROOT / '.local/npu-provider-plan-20261010/host-tx-request-final-20261013-seal/result.json',
    'probe.json': ROOT / '.local/npu-loader-publish-20261010/host-tx-probe-final-20261013-seal/result.json',
    'boot.json': ROOT / '.local/npu-boot-launch-20261010/host-tx-boot-final-20261013-seal/result.json',
    'memory.json': ROOT / '.local/npu-cold-memory-plan/host-tx-memory-final-20261013-seal/result.json',
    'regressions.json': HERE / 'regressions-final-20261013-seal.json',
    'source-replay.json': HERE / 'source-replay-20261013-seal.json',
    'nested-replay.json': HERE / 'nested-replay-20261013-style.json',
    'original-tx-records.json': HERE / 'tx-records-original-qualified-20261013.json',
    'rea-reuse.json': HERE / 'rea-reuse-20261013.json',
    'image.json': ROOT / '.local/merge-nonoc-20260923/host-tx-final-offline-20261013/result.json',
    'build-state.json': ROOT / '.local/merge-nonoc-20260923/build-npu-host-tx-final-20261013.json',
    'raw-pair-manifest.json': ROOT / '.build/merged-openwrt/bin/npu-pair-npu-host-tx-final-20261013/manifest.json',
    'preserved-image.json': HERE / 'preserved-image.json',
    'preserved-final-image.json': HERE / 'preserved-final-image-20261013.json',
}
inputs = {}


def checked(name, digest):
    path = (ROOT / name).resolve()
    assert not Path(name).is_absolute() and path.is_relative_to(ROOT), name
    assert sha(path) == digest, ('changed-input', name)
    assert name not in inputs or inputs[name] == digest, ('conflicting-input', name)
    inputs[name] = digest


def collect(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ('inputs', 'source_inputs', 'inputs_before_after', 'protected_inputs', 'host_inputs'):
                if isinstance(item, dict):
                    for name, digest in item.items():
                        if isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest):
                            checked(name, digest)
                elif isinstance(item, list):
                    for entry in item:
                        checked(entry['path'], entry['sha256'])
            else:
                collect(item)
    elif isinstance(value, list):
        for item in value:
            collect(item)


loaded = {}
audit_errors = []
for name, path in receipts.items():
    value = json.loads(path.read_bytes())
    try:
        collect(value)
    except AssertionError as error:
        if '--audit-only' not in sys.argv:
            raise
        audit_errors.append(dict(receipt=name, error=str(error)))
    loaded[name] = value
    if 'passed' in value and 'counterexample' not in name:
        assert value['passed'], name
if audit_errors:
    print(json.dumps(dict(passed=False, errors=audit_errors)), flush=True)
    raise SystemExit(1)
host = loaded['host-lifetime.json']
assert host['matrix']['cases'] == 76 and len(host['mutants']) == 7
assert host['matrix']['exposed_tx_frees'] == 0
for name in ('old-host-counterexample.json', 'old-alias-counterexample.json'):
    assert loaded[name]['counterexample'] and not loaded[name]['passed']
assert loaded['old-host-counterexample.json']['matrix']['managed_tx_frees'] == 6
session = loaded['linux-session.json']
assert session['matrix']['cases'] == 609 and len(session['mutants']) == 9
assert session['matrix']['endpoint_geometry_cases'] == 272
assert len(loaded['endpoint.json']['mutants']) == 7
assert loaded['regressions.json']['unit_tests'] == 21
assert all(group['tests'] and group['passed'] for group in loaded['regressions.json']['unit_groups'])
native = loaded['native-status.json']
assert native['native']['passed'] and native['native']['result'] == 0
assert native['allocations'] == [dict(allocations=6, published=True)] and len(native['native']['frames']) == 38
assert native['native']['actual_c_linux_setup'] and native['native']['actual_c_txrx_sender']
assert not native['native']['synthetic_plan_identity_writes'] and not native['native']['post_load_elf_injection']
trace = loaded['original-tx-records.json']
assert len(trace['cases']) == 8
assert all(row['record_count'] == 512 and row['record_stores'] == 2048 for row in trace['cases'][:5])
assert all(row['memory_fault'] and row['record_count'] == 0 for row in trace['cases'][5:7])
assert trace['cases'][7]['wait_call_observed'] and not trace['cases'][7]['completed']
assert all(row['untouched_tail_bytes'] and row['exact_other_bytes'] and not row['dynamic_allocator_called'] for row in trace['cases'])
assert sum(row['changed_files_verified'] for row in loaded['source-replay.json']) == 67
assert len(loaded['nested-replay.json']['files']) == 4 and loaded['nested-replay.json']['strict_checkpatch']
assert loaded['build-state.json']['exit_code'] == 0
image = loaded['image.json']
assert image['sha256'] == '6efaa878524140439aaced592c219a925f200dcc9a3f55b00f29bb7e1148dfa7'
assert len(image['packages']) == 218 and image['all_module_abi_checks'] == 78
assert len(image['rv32_core']['objects']) == 16
provider = image['selected_modules']['airoha_npu.ko']
assert provider['sha256'] == '42ec4f37cfc06439292289c71e6523839d5cd0e527d9037e9b8d336750f44293'
pair = loaded['raw-pair-manifest.json']
assert len(pair['components']) == 14 and len(pair['hooks']) == 77
assert pair['code']['sha256'] == '11151179c3bad61b563d1c14703fb886945de036669edf589f376880bcc872e0'
assert pair['data']['sha256'] == '20e416709d1534c72752626e15fa67f75cb99ef7c16cce4256d117e376e9a619'
ghidra = HERE / 'ghidra-provider'
text = (ghidra / 'airoha_npu.ko.txt').read_text()
assert 'sha256=' + provider['sha256'] in text and 'exported_functions=59' in text
assert 'failed_decompilations=0' in text and 'decompiled=false' not in text
assert 'Analysis timed out' not in (ghidra / 'analysis.log').read_text()
assert 'total: 0 errors, 0 warnings, 0 checks' in (HERE / 'checkpatch-final-20261013-style.log').read_text()
for key, folder in [('preserved-image.json', 'pre-world-image'), ('preserved-final-image.json', 'pre-final-image-20261013')]:
    backup = HERE / folder
    assert len(list(backup.iterdir())) == 8
    subprocess.run(['sha256sum', '--check', '--strict', 'sha256sums'], cwd=backup, capture_output=True, check=True)
    for row in loaded[key]['files']:
        checked(row['path'], row['sha256'])
for name in ('firmware/source-lock.json', 'firmware/npu/Makefile', 'tests/npu/test_tx_buffer_records.py'):
    inputs[name] = sha(ROOT / name)
checked(image['image'], image['sha256'])
checked(provider['path'], provider['sha256'])
print(json.dumps(dict(passed=True, audited_inputs=len(inputs), receipts=len(receipts), image_sha256=image['sha256'])), flush=True)
if '--audit-only' in sys.argv:
    raise SystemExit(0)
assert OUT.is_dir() and not (OUT / 'verification.json').exists()
for name, path in receipts.items():
    shutil.copy2(path, OUT / name)
for name in ('jev-existing.json', 'jev-existing-result.json', 'jev-final-20261013.json', 'jev-final-20261013-result.json',
             'jev-scope-followup-20261013.json', 'jev-scope-followup-20261013-result.json',
             'host-tx-lifetime-20261013-style.patch', 'checkpatch-final-20261013-style.log'):
    shutil.copy2(HERE / name, OUT / name)
for name in ('airoha_npu.ko.txt', 'analysis.log', 'script.log', 'console.log'):
    shutil.copy2(ghidra / name, OUT / ('ghidra-' + name))
for name in ('README.md', 'AGENTS.md', 'docs/REMAINING_WORK.md', 'docs/W1700K_STOCK_PORT_CURRENT_REFERENCE.md',
             'docs/W1700K_STOCK_PORT_LEDGER.md', 'docs/W1700K_STOCK_PORT_LOGGING_SESSION_20260625.md'):
    inputs[name] = sha(ROOT / name)
shutil.copy2(Path(__file__), OUT / 'seal.py')
files = [dict(path=str(path.relative_to(ROOT)), sha256=sha(path), bytes=path.stat().st_size)
         for path in sorted(OUT.iterdir()) if path.is_file() and path.name not in ('verification.json', 'CHECKSUMS.sha256')]
verification = dict(schema=1, passed=True,
                    scope='Host coherent TX lifetime and original fixed-record trace; full NPU goal remains open.',
                    image_sha256=image['sha256'], provider_sha256=provider['sha256'],
                    source_files=67, changed_nested_files=4, canonical_components=14,
                    archive_objects=16, raw_components=14, hooks=77, ghidra_functions=59,
                    host_cases=76, provider_cases=609, native_allocator_status_cases=1, original_record_cases=8,
                    physical_acceptance=False, flashed=False, inputs=inputs, files=files)
with (OUT / 'verification.json').open('x') as stream:
    json.dump(verification, stream, indent=2)
    stream.write('\n')
with (OUT / 'CHECKSUMS.sha256').open('x') as stream:
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != 'CHECKSUMS.sha256':
            stream.write(f'{sha(path)}  {path.name}\n')
print(json.dumps(dict(passed=True, sealed_inputs=len(inputs), sealed_files=len(files))), flush=True)
