from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess

root = Path('/home/captain/W1700KNPU')
here = root / '.local/npu-cold-descriptor-20261010'
out = root / 'research/checkpoints/2026-10-10-npu-cold-descriptor'
assert not (out / 'verification.json').exists()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
def record(path):
    return dict(path=str(path.relative_to(root)),sha256=sha(path),bytes=path.stat().st_size)
receipts = {
    'descriptor-core.json': here / 'core-world-qualification/result.json',
    'cold-wire.json': root / '.local/npu-cold-wire-20261010/descriptor-wire-sealed/result.json',
    'linux-native.json': root / '.local/npu-provider-session-20261010/descriptor-suite-sealed/result.json',
    'linux-hif2.json': root / '.local/npu-provider-session-20261010/descriptor-hif2-sealed/result.json',
    'host-caller.json': root / '.local/npu-cold-pages-wire-20261010/descriptor-host-second/result.json',
    'parser.json': root / '.local/npu-loader-publish-20261010/descriptor-publish-qualification/result.json',
    'endpoint.json': root / '.local/npu-cold-pages-wire-20261010/descriptor-endpoint-sealed/result.json',
    'lease.json': root / '.local/npu-loader-publish-20261010/descriptor-lease-qualification/result.json',
    'request.json': root / '.local/npu-provider-plan-20261010/descriptor-request-qualification/result.json',
    'probe.json': root / '.local/npu-loader-publish-20261010/descriptor-probe-qualification/result.json',
    'boot.json': root / '.local/npu-boot-launch-20261010/descriptor-boot-qualification/result.json',
    'memory.json': root / '.local/npu-cold-memory-plan/descriptor-memory-qualification/result.json',
    'raw.json': root / '.local/npu-raw-pair-20261010/descriptor-raw-qualification/result.json',
    'extra-controls.json': here / 'extra-controls-first/result.json',
    'release-controls.json': here / 'release-controls-sealed/result.json',
    'argument-controls.json': here / 'argument-controls-sealed/result.json',
    'tx-buffer-lookup.json': here / 'tx-buffer-lookup-first/result.json',
    'lock-counterexample.json': here / 'lock-before/result.json',
    'lock-fixed.json': here / 'lock-qualification/result.json',
    'unit-regressions.json': here / 'unit-regressions.json',
    'image.json': root / '.local/merge-nonoc-20260923/cold-descriptor-20261011-offline/result.json',
    'build-state.json': root / '.local/merge-nonoc-20260923/build-npu-cold-descriptor-20261011.json',
    'source-replay.json': here / 'source-replay-final.json',
    'static-dispatch.json': here / 'static-dispatch.json',
    'assembly.json': here / 'assembly-final.json',
    'preserved-image.json': here / 'preserved-image.json',
}
inputs, loaded = {}, {}
def checked(path,digest):
    file = (root / path).resolve()
    assert not Path(path).is_absolute() and file.is_relative_to(root)
    assert sha(file) == digest, ('changed-input',path)
    assert path not in inputs or inputs[path] == digest, ('conflicting-input',path)
    inputs[path] = digest
def collect(value):
    if isinstance(value,dict):
        for key,item in value.items():
            if key in ('inputs','source_inputs','inputs_before_after','protected_inputs'):
                if isinstance(item,dict):
                    for path,digest in item.items():
                        if isinstance(digest,str) and re.fullmatch('[0-9a-f]{64}',digest): checked(path,digest)
                elif isinstance(item,list):
                    for entry in item: checked(entry['path'],entry['sha256'])
            else: collect(item)
    elif isinstance(value,list):
        for item in value: collect(item)
for name,path in receipts.items():
    value = json.loads(path.read_bytes())
    collect(value); loaded[name] = value
    if 'passed' in value and name != 'lock-counterexample.json': assert value['passed'], name
core = loaded['descriptor-core.json']
assert core['exact_core_object'] and core['host_rv32_calls'] == 5732 and core['controls'] == 1592 and len(core['mutants']) == 5
wire = loaded['cold-wire.json']
assert wire['matrix']['cases'] == 657 and len(wire['mutants']) == 23
assert [wire['matrix'][key] for key in ('getter_reply_cases','getter_server_cases','getter_codec_cases')] == [71,47,32]
native = loaded['linux-native.json']
assert native['complete_cold_native_suite'] and len(native['native']) == 9
assert native['matrix']['cases'] == 545 and len(native['mutants']) == 9
nominal = native['native'][0]
assert nominal['actual_c_txrx_sender'] and not nominal['synthetic_plan_identity_writes']
for key,count in (('indication_native_controls',35),('tx_native_controls',28),('descriptor_native_controls',28)):
    rows = next(row[key] for row in nominal['cold'] if key in row)
    assert len(rows) == count
getters = [row for row in nominal['cold'] if row.get('api') == 4 and 'output' in row]
assert [row['header'] for row in getters] == [0x30,0x32,0x3a,0x3b,0x3c,0x38,0x35,0x37]
assert any(row.get('next_unsupported') and row['api'] == 21 for row in nominal['cold'])
for selector,committed,published in ((5,1,0),(7,513,512)):
    case = next(row for row in native['native'] if row.get('descriptor_fault_selector') == selector)
    partial = next(row for row in case['cold'] if 'descriptor_committed' in row)
    assert (partial['descriptor_committed'],partial['descriptor_published']) == (committed,published)
    assert partial['retained_active'] == partial['retained_inflight'] == 1
    assert partial['retained_packet_claims'] == 2560 and partial['retained_ba_claims'] == 1792
hif2 = loaded['linux-hif2.json']
assert hif2['native_case'] == 'nominal' and len(hif2['native']) == 1 and hif2['native'][0]['hif2']
raw = loaded['raw.json']
assert raw['full_nominal'] and raw['hooks'] == 77 and len(raw['authenticated_cold_prefix']) == 26
assert raw['txdone']['claimed'] == 3072 and len(raw['boot_controls']) == 6 and len(raw['controls']) == 8
assert raw['later_txdone_lease_modeled'] and not raw['initial_test_active_writes'] and not raw['initial_direct_owner_init']
assert len(loaded['extra-controls.json']['pointer_controls']) == 40 and len(loaded['extra-controls.json']['tx_caller_controls']) == 9
assert len(loaded['release-controls.json']['release_controls']) == 56
assert loaded['argument-controls.json']['matrix']['argument_cases'] == 9
assert len(loaded['tx-buffer-lookup.json']['cases']) == 6
assert loaded['lock-counterexample.json']['counterexample'] and not loaded['lock-counterexample.json']['passed']
assert len(loaded['lock-fixed.json']['cases']) == 3 and all(row['lock_preserved'] and not row['unlock_writes'] for row in loaded['lock-fixed.json']['cases'])
assert loaded['unit-regressions.json']['tests'] == 21
assert loaded['assembly.json']['test_groups'] == 16 and not loaded['assembly.json']['skipped']
assert sum(row['changed_files_verified'] for row in loaded['source-replay.json']) == 67
assert len(loaded['static-dispatch.json']['nested_source_replay']) == 12 and loaded['static-dispatch.json']['canonical_components'] == 14
assert loaded['build-state.json']['exit_code'] == 0
image = loaded['image.json']
assert image['sha256'] == '3951dc7c9160f5adbde30285c0a70cdf1cd36685b2c7222498977caddad9bdec'
assert len(image['packages']) == 218 and image['all_module_abi_checks'] == 78 and len(image['rv32_core']['objects']) == 16
provider = image['selected_modules']['airoha_npu.ko']
assert provider['sha256'] == '707331d24b659b9b2e68ee92e72d732f97da6dd83d575bae4e6ae9c149933c16'
ghidra = here / 'ghidra-full-second'
text = (ghidra / 'airoha_npu.ko.txt').read_text()
assert 'sha256=' + provider['sha256'] in text and 'exported_functions=54' in text
assert 'failed_decompilations=0' in text and 'decompiled=false' not in text
assert 'Analysis timed out' not in (ghidra / 'analysis.log').read_text()
assert 'total: 0 errors, 0 warnings, 0 checks' in (here / 'checkpatch-final.log').read_text()
pair = here / 'pair-qualification'
for repeat in (here / 'pair-repeat',root / loaded['build-state.json']['checked_npu_pair']['directory']):
    assert json.loads((repeat / 'manifest.json').read_bytes())['inputs'] == json.loads((pair / 'manifest.json').read_bytes())['inputs']
    for name in ('CODE.bin','DATA.bin'): assert (repeat / name).read_bytes() == (pair / name).read_bytes()
backup = here / 'pre-world-image'
assert len(list(backup.iterdir())) == 8
subprocess.run(['sha256sum','--check','--strict','sha256sums'],cwd=backup,check=True,capture_output=True)
for row in loaded['preserved-image.json']['files']: checked(row['path'],row['sha256'])
for name,path in receipts.items(): shutil.copy2(path,out / name)
for name in ('jev-review.json','jev-review-result.json','jev-rejection-review.json','jev-rejection-result.json',
             'jev-native-review.json','jev-native-result.json','jev-focused-next-review.json','jev-focused-next-result.json',
             'jev-branches-review.json','jev-branches-result.json','jev-argument-contract.json','jev-argument-contract-result.json',
             'jev-lookup-review.json','jev-lookup-result.json',
             'provider-descriptor.patch','checkpatch-final.log'):
    shutil.copy2(here / name,out / name)
for name in ('airoha_npu.ko.txt','analysis.log','script.log','console.log'):
    shutil.copy2(ghidra / name,out / ('ghidra-' + name))
for name in ('README.md','AGENTS.md','docs/REMAINING_WORK.md','docs/W1700K_STOCK_PORT_CURRENT_REFERENCE.md',
             'docs/W1700K_STOCK_PORT_LEDGER.md','docs/W1700K_STOCK_PORT_LOGGING_SESSION_20260625.md',
             'firmware/npu/Makefile','firmware/source-lock.json'):
    inputs[name] = sha(root / name)
inputs[image['image']] = sha(root / image['image'])
inputs[provider['path']] = sha(root / provider['path'])
shutil.copy2(Path(__file__),out / 'seal.py')
files = [record(path) for path in sorted(out.iterdir()) if path.is_file() and path.name not in ('verification.json','CHECKSUMS.sha256')]
verification = dict(schema=1,passed=True,scope='Descriptor checkpoint only; full NPU/hardware goal remains open.',
                    image_sha256=image['sha256'],provider_sha256=provider['sha256'],source_files=67,nested_source_files=12,
                    canonical_components=14,archive_objects=16,raw_components=14,hooks=77,native_cases=9,
                    inputs=inputs,files=files,physical_acceptance=False,flashed=False)
(out / 'verification.json').write_text(json.dumps(verification,indent=2) + '\n')
checks = [f'{sha(path)}  {path.name}\n' for path in sorted(out.iterdir()) if path.is_file() and path.name != 'CHECKSUMS.sha256']
(out / 'CHECKSUMS.sha256').write_text(''.join(checks))
print(json.dumps(dict(passed=True,sealed_inputs=len(inputs),sealed_files=len(files),image_sha256=image['sha256'])))
