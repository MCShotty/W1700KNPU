#!/usr/bin/env python3
"""Bind source, component tests, real ARM64 build and Ghidra evidence."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
from test_memory_preflight import HEADER, KERNEL, LOCAL, OUT, PATCH, ROOT, SOURCE

BASE = 'e7b606e58b9c41b4e224a82baf8b7814b77556a0'
CHANGED = 'target/linux/airoha/patches-6.18/927-net-airoha-npu-validate-memory-before-wlan.patch'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((OUT / name).read_text())


def original(path):
    return subprocess.check_output(['git', 'show', BASE + ':' + path], cwd=ROOT)


def main():
    lock = json.loads((ROOT / 'firmware/source-lock.json').read_text())
    old = json.loads(original('firmware/source-lock.json'))
    assert lock['snapshot'] == 'post-Daybreak21-R1-NPU-memory-preflight-20260906'
    old['snapshot'] = lock['snapshot']
    entry = {'path': CHANGED, 'sha256': sha(PATCH), 'mode': '0o644'}
    old['openwrt']['changed_files'].append(entry)
    assert lock == old, 'Unrelated source-lock changes'
    assert sha(ROOT / '.build/openwrt' / CHANGED) == sha(PATCH)
    protected = ['firmware/patches', 'firmware/npu', 'firmware/build.config',
                 'firmware/feeds.conf.default', 'firmware/overlay/openwrt/package',
                 'firmware/overlay/luci']
    assert not subprocess.check_output(['git', 'diff', '--name-only', BASE, '--', *protected], cwd=ROOT)
    assert sha(HEADER) == '9359009a4161de572e7f44b41b172860bb6414b56332f16ed6ff8df972126364'
    source_hash = sha(SOURCE)
    assert source_hash == '8eed02dd963c9d80fcaf4f15368506f4a4720dd7be4f080c394a21bba7e1fe8f'
    reviewed = SOURCE.read_text().replace('\t' * 8 + 'memory[i].name, res);',
                                          '\t' * 7 + '      memory[i].name, res);')
    assert hashlib.sha256(reviewed.encode()).hexdigest() == '4ed450814e021a519cb68072bbb129576b570c3432b58b7d1e6053f6da074b88'
    tests = read('compiled-c-tests.json')
    assert tests['passed'] and tests['cases'] == 109 and len(tests['mutations_killed']) == 6
    assert tests['source_sha256'] == source_hash and tests['header_sha256'] == sha(HEADER)
    assert tests['preimage_sha256'] == '51cd396f8c141bbf6d425088ddbf39e8a59d4874fa529980332509ba3b52e1fa'
    assert len(tests['dtb_cases']) == 8
    assert sum(row['ret'] == 0 for row in tests['dtb_cases']) == 5
    assert all(row['ret'] == 0 or row['wire'] == [] for row in tests['dtb_cases'])
    fixtures = read('dtb-cases.json')
    assert [r['dtb_sha256'] for r in fixtures] == [r['dtb_sha256'] for r in tests['dtb_cases']]
    mailbox = read('mailbox-tests.json')
    assert mailbox['passed'] and mailbox['fixed'] == 'PASS assertions=143'
    assert mailbox['source_sha256'] == source_hash and len(mailbox['negative_controls']) == 2
    build = read('kernel-build.json')
    assert len(build) == 2 and all(row['exit_code'] == 0 for row in build)
    assert 'target/linux/prepare' in build[0]['command'] and 'target/linux/compile' in build[1]['command']
    assert CHANGED in (OUT / 'kernel-prepare.log').read_text()
    compile_log = (OUT / 'kernel-compile.log').read_text()
    assert re.search(r'CC\s+drivers/net/ethernet/airoha/airoha_npu.o', compile_log)
    assert not re.search(r'\b(?:error|warning):', compile_log)
    layout = read('abi-layout.json')
    assert layout['passed'] and layout['public_baseline'] == layout['public_current']
    assert layout['source_sha256'] == source_hash and layout['public_header_sha256'] == sha(HEADER)
    assert layout['private']['public_offset'] == 0
    obj = KERNEL / 'drivers/net/ethernet/airoha/airoha_npu.o'
    assert sha(obj) == sha(LOCAL / 'airoha_npu.o')
    elf = obj.read_bytes()
    assert elf[:6] == b'\x7fELF\x02\x01' and int.from_bytes(elf[18:20], 'little') == 183
    ghidra = (OUT / 'ghidra-provider/airoha_npu.o.txt').read_text()
    assert 'sha256=' + sha(obj) in ghidra and 'language=AARCH64:LE:64:v8A' in ghidra
    assert 'failed_decompilations=0' in ghidra and 'decompiled=false' not in ghidra
    counts = {name: int(re.search(name + r'=(\d+)', ghidra)[1]) for name in
              ['total_executable_functions', 'exported_functions']}
    assert counts['total_executable_functions'] == counts['exported_functions']
    assert 'FUNCTION airoha_npu_wlan_init_memory' in ghidra and 'FUNCTION airoha_npu_probe' in ghidra
    assert 'Analysis timed out' not in (OUT / 'ghidra-provider/analysis.log').read_text()
    export = read('source-export-verification.json')
    assert [r['changed_files_verified'] for r in export] == [36, 3] and all(r['passed'] for r in export)
    checkpatch = subprocess.run(['perl', str(KERNEL / 'scripts/checkpatch.pl'), '--no-tree',
                                '--no-signoff', str(PATCH)], text=True, capture_output=True)
    assert checkpatch.returncode == 0 and '0 errors, 0 warnings, 0 checks' in checkpatch.stdout
    (OUT / 'checkpatch.log').write_text(checkpatch.stdout + checkpatch.stderr)
    inputs = ['tests/npu/test_memory_preflight.py', 'tests/npu/preflight_dtb_cases.py',
              'tests/npu/build_preflight_layout.py', 'tests/npu/test_txbuf_dtbs.py',
              'tests/npu/test_mailbox_ownership.py', 'tools/ghidra/run_preflight_provider.ps1',
              'tools/ghidra/ExportMailboxContract.java', 'tools/ghidra/all-functions.pattern',
              'tools/migration/verify_source_export.py', 'firmware/source-lock.json',
              'firmware/patches/openwrt.patch', 'firmware/build.config']
    result = {'passed': True, 'packaged_delta': CHANGED, 'patch_sha256': sha(PATCH),
              'provider_source_sha256': source_hash, 'provider_object_sha256': sha(obj),
              'public_header_sha256': sha(HEADER), 'ghidra_counts': counts,
              'compiled_c_cases': tests['cases'], 'dtb_cases': len(tests['dtb_cases']),
              'mutations_killed': len(tests['mutations_killed']), 'mailbox_assertions': 143,
              'inputs': {name: sha(ROOT / name) for name in inputs},
              'verifier_sha256': sha(Path(__file__)),
              'scope': 'Provider startup preflight: component tests and real ARM64 build/static analysis. No hardware containment, full recovery, new release image, flash or client proof.'}
    (OUT / 'evidence-verification.json').write_text(json.dumps(result, indent=2) + '\n')
    manifest = [{'path': str(p.relative_to(OUT)), 'bytes': p.stat().st_size, 'sha256': sha(p)}
                for p in sorted(OUT.rglob('*')) if p.is_file() and p.name != 'file-manifest.json']
    (OUT / 'file-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['passed', 'compiled_c_cases', 'dtb_cases', 'mutations_killed',
                                           'provider_object_sha256', 'ghidra_counts']}))


if __name__ == '__main__':
    main()
