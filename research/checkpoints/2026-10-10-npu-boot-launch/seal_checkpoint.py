#!/usr/bin/env python3
"""Verify/copy only this checkpoint's source and text evidence, never binaries."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
HERE = ROOT / '.local/npu-boot-launch-20261010'
MERGE = ROOT / '.local/merge-nonoc-20260923'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    assert not (OUT / 'verification.json').exists()
    files = {
        'boot-launch.json': HERE / 'final/result.json',
        'probe-lifetime.json': ROOT / '.local/npu-loader-publish-20261010/boot-final-current/result.json',
        'checked-loader.json': ROOT / '.local/npu-loader-publish-20261010/boot-launch-regression/result.json',
        'dma-lifetime.json': ROOT / '.local/npu-loader-publish-20261010/boot-launch-retention/result.json',
        'request-plan.json': ROOT / '.local/npu-provider-plan-20261010/boot-launch-current/result.json',
        'memory-retry-v2.json': ROOT / '.local/npu-cold-memory-plan/boot-launch-20261010/result.json',
        'pair-loader.json': ROOT / '.local/npu-raw-pair-20261010/boot-launch-pair/result.json',
        'native-published.json': ROOT / '.local/npu-loader-publish-20261010/boot-launch-published/result.json',
        'raw-native.json': ROOT / '.local/npu-raw-pair-20261010/boot-launch-full/result.json',
        'reset-map.json': HERE / 'reset-map-final/result.json',
        'assembly.json': HERE / 'assembly.json',
        'source-replay.json': HERE / 'source-replay-final.json',
        'image.json': MERGE / 'boot-launch-20261010-offline/result.json',
        'build.json': MERGE / 'build-boot-launch-20261010.json',
        'checkpatch.log': HERE / 'checkpatch.log',
        'boot-launch.patch': HERE / 'boot-launch-final.patch',
        'preservation.json': HERE / 'pre-world-image/preservation.json',
        'ghidra-provider.txt': HERE / 'ghidra-final/airoha_npu.ko.txt',
        'ghidra-analysis.log': HERE / 'ghidra-final/analysis.log',
    }
    for phase in ('pre', 'post', 'getter'):
        for kind in ('request', 'result'):
            name = f'jev-{phase}-{kind}.json'
            files[name] = HERE / name
    inputs, host_tools, data = {}, {}, {}

    def remember(name, digest):
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT) and sha(path) == digest, ('changed-input', name)
        if name in inputs:
            assert inputs[name] == digest
        inputs[name] = digest

    def visit(value):
        if isinstance(value, list):
            for row in value:
                visit(row)
        elif isinstance(value, dict):
            if 'path' in value and 'sha256' in value:
                path = Path(value['path'])
                if path.is_absolute() and not path.is_relative_to(ROOT):
                    assert path == Path('/usr/bin/make') and sha(path) == value['sha256']
                    host_tools[str(path)] = value['sha256']
                else:
                    remember(value['path'], value['sha256'])
            for key, row in value.items():
                if key in ('inputs', 'source_inputs') and isinstance(row, dict):
                    for name, digest in row.items():
                        remember(name, digest)
                else:
                    visit(row)

    for name, source in files.items():
        assert source.stat().st_size < 4 * 1024 * 1024
        assert b'\0' not in source.read_bytes()
        if source.suffix == '.json':
            data[name] = json.loads(source.read_bytes())
            visit(data[name])
            if 'passed' in data[name]:
                assert data[name]['passed'] is True
        shutil.copy2(source, OUT / name)
    image = data['image.json']
    remember(image['image'], image['sha256'])
    assert image['sha256'] == 'b0400eaa873beeb309fc10e7376255f89cefb7c1f986096863916f5a4ee222b6'
    assert image['source_lock_sha256'] == sha(ROOT / 'firmware/source-lock.json')
    remember(data['preservation.json']['preserved'], data['preservation.json']['sha256'])
    assert data['build.json']['exit_code'] == 0
    assert sum(row['changed_files_verified'] for row in data['source-replay.json']) == 62
    probe = data['probe-lifetime.json']
    assert (probe['cases'], probe['rejected_mutants'], probe['original_controls']) == (265, 3, 1)
    module = ROOT / image['selected_modules']['airoha_npu.ko']['path']
    text = (OUT / 'ghidra-provider.txt').read_text()
    assert 'sha256=' + sha(module) in text and 'decompiled=false' not in text
    assert 'exported_functions=1' in text and 'failed_decompilations=0' in text
    for marker in ('0x30c168', '0x30c16c', '0x30c170', '0x30c194', '0x306004', '0x306000', 'local_44 != 0x457'):
        assert marker in text
    assert 'Analysis succeeded for file:' in (OUT / 'ghidra-analysis.log').read_text()
    assert 'Analysis timed out' not in (OUT / 'ghidra-analysis.log').read_text()
    ghidra = dict(passed=True, module_sha256=sha(module), analyzed_executable_functions=33,
                  selected_functions=1, decompile_failures=0, inlined_launch_block=True,
                  limits=['Ghidra code/assembly cross-check of exact packaged probe; no physical execution.'])
    (OUT / 'ghidra.json').write_text(json.dumps(ghidra, indent=2) + '\n')
    # Check the compiled board node, not only the source label.
    dtb_name = next(row['name'] for row in image['components'] if row['type'] == 'flat_dt')
    dtb = MERGE / 'boot-launch-20261010-offline' / (dtb_name + '.bin')
    done = subprocess.run(['fdtget', '-t', 'x', str(dtb), '/soc/npu@1e900000', 'resets'], capture_output=True, text=True)
    assert done.returncode != 0 and 'FDT_ERR_NOTFOUND' in done.stderr
    remember(str(dtb.relative_to(ROOT)), sha(dtb))
    prior_map = json.loads((ROOT / 'research/checkpoints/2026-09-23-npu-reset-control/reset-native.json').read_bytes())
    assert data['reset-map.json']['maps'] == prior_map['maps']
    # Preserve the executable unit-suite logs and their actual source identities.
    units = []
    for name, command, count in (
        ('builder', [sys.executable, 'tests/test_build_firmware_host_tools.py'], 13),
        ('source-verifier', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_verify_source_export.py', '-v'], 4)):
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                   env={'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin', 'PYTHONDONTWRITEBYTECODE': '1'})
        log = OUT / (name + '.log')
        log.write_text(completed.stdout + completed.stderr)
        assert completed.returncode == 0 and f'Ran {count} tests' in log.read_text() and '\nOK\n' in log.read_text()
        units.append(dict(name=name, tests=count, passed=True, log_sha256=sha(log)))
    (OUT / 'units.json').write_text(json.dumps(units, indent=2) + '\n')
    for name in ('tools/build_firmware.py', 'tools/verify_merged_image.py', 'tools/export_merged_sources.py',
                 'tools/migration/verify_source_export.py', 'tests/test_build_firmware_host_tools.py', 'tests/test_verify_source_export.py',
                 'tools/ghidra/ExportMailboxContract.java', 'firmware/source-lock.json'):
        remember(name, sha(ROOT / name))
    result = dict(passed=True, source_commit_before='5dbfae8d65e164281cf4d1e44fa439f47f505734',
                  image_sha256=image['sha256'], provider_module_sha256=sha(module), inputs=inputs, host_tools=host_tools,
                  current_reset_source_reconstructed=True, reset_map_matches_prior=True, npu_reset_binding=False,
                  binary_launch_ghidra=ghidra, early_version_before_discover=True,
                  physical_acceptance=False, full_npu_goal_complete=False,
                  limits=['Actual C, target instruction, source/Ghidra/offline checks with scoped dependencies modeled.',
                          'No physical containment/retirement/reset,full strict setup or client acceptance.'])
    (OUT / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
    manifest = [dict(path=str(path.relative_to(OUT)), bytes=path.stat().st_size, sha256=sha(path))
                for path in sorted(OUT.iterdir()) if path.is_file() and path.name != 'file-manifest.json']
    (OUT / 'file-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(dict(passed=True, inputs=len(inputs), files=len(manifest), image_sha256=image['sha256'])))


if __name__ == '__main__':
    main()
