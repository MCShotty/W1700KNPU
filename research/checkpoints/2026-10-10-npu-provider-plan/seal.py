#!/usr/bin/env python3
"""Seal/check scoped provider-plan proof; binary/private inputs remain local."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
WORK = ROOT / '.local/npu-provider-plan-20261010'
MERGE = ROOT / '.local/merge-nonoc-20260923'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(inputs):
    for name, digest in inputs.items():
        assert sha(ROOT / name) == digest, ('input-changed', name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        proof = json.loads((OUT / 'verification.json').read_bytes())
        check(proof['inputs'])
        files = json.loads((OUT / 'file-manifest.json').read_bytes())
        for row in files:
            assert sha(OUT / row['path']) == row['sha256']
        print(json.dumps(dict(passed=True, inputs=len(proof['inputs']), files=len(files))))
        return
    assert not (OUT / 'verification.json').exists()
    sources = {
        WORK / 'host-final/result.json': 'request-result.json',
        WORK / 'native-final/result.json': 'native-result.json',
        ROOT / '.local/npu-cold-memory-plan/request-plan-final/result.json': 'memory-result.json',
        ROOT / '.local/npu-raw-pair-20261010/provider-plan-pair-final/result.json': 'pair-loader-result.json',
        WORK / 'assembly-proof.json': 'assembly-result.json',
        WORK / 'source-world-final.json': 'source-result.json',
        MERGE / 'provider-request-plan-20261010-offline/result.json': 'image-result.json',
        MERGE / 'build-provider-request-plan-20261010.json': 'world-result.json',
        WORK / 'checkpatch-result.json': 'checkpatch-result.json',
        WORK / 'checkpatch.log': 'checkpatch.log',
        WORK / 'provider-delta.patch': 'provider-delta.patch',
        WORK / 'pair-final/manifest.json': 'pair-manifest.json',
        WORK / 'pair-repeat-final/manifest.json': 'repeat-manifest.json',
        WORK / 'pre-world-image/preservation.json': 'preservation.json',
    }
    for name in ('jev-pre-request', 'jev-pre-result', 'jev-post-request', 'jev-post-result',
                 'jev-focus-request', 'jev-focus-result'):
        sources[WORK / (name + '.json')] = name + '.json'
    parsed = {}
    inputs = {}
    for source, name in sources.items():
        if source.suffix == '.json':
            record = json.loads(source.read_bytes())
            parsed[name] = record
            if 'passed' in record:
                assert record['passed'], name
            sealed = record.get('inputs', {}) if isinstance(record, dict) else {}
            if isinstance(sealed, list):
                sealed = {row['path']: row['sha256'] for row in sealed}
            for path, digest in sealed.items():
                assert path not in inputs or inputs[path] == digest, ('inconsistent-seals', path)
                inputs[path] = digest
        shutil.copy2(source, OUT / name)
        inputs[str(source.relative_to(ROOT))] = sha(source)
    request = parsed['request-result.json']
    assert request['matrix']['request_cases'] == 308 and request['matrix']['before_copy_checks'] == 476
    assert len(request['rejected_mutants']) == 9
    native = parsed['native-result.json']
    assert native['raw_pair'] and not native['post_load_elf_injection'] and native['parked'] == [1] * 8
    assert native['request_base'] == '0x83000000' and native['fixed_fixture_rejected']
    assert len(native['address_controls']) == 6 and all(row['flags'] == 3 for row in native['strict_denials'])
    memory = parsed['memory-result.json']
    assert memory['sanitizers']['leak'] and len(memory['rejected_mutants']) == 9
    assert parsed['pair-loader-result.json']['matrix']['cases'] == 273
    assert len(parsed['pair-loader-result.json']['pair_cases']) == 7
    assert parsed['assembly-result.json']['test_groups'] == 15 and parsed['assembly-result.json']['repeat_build']
    assert sum(row['changed_files_verified'] for row in parsed['source-result.json']) == 60
    assert parsed['world-result.json']['exit_code'] == 0
    image = parsed['image-result.json']
    assert image['sha256'] == '8efb19fb491f2446c50a367708c22a6882486c11f7b0ea03d41e99e37df239c5'
    preserved = parsed['preservation.json']
    assert sha(ROOT / preserved['saved']) == preserved['sha256'] == '230e03a7b87cb9e14e0464b53d324bb2c4eb650b3c9a64a63514b30dde4458fe'
    inputs[preserved['saved']] = preserved['sha256']
    inputs[request['plan']['path']] = request['plan']['sha256']
    for suffix, count in (('test_build_firmware_host_tools.py', 8), ('test_verify_source_export.py', 4)):
        done = subprocess.run(['python3', '-m', 'unittest', 'discover', '-s', 'tests', '-p', suffix, '-v'],
                              cwd=ROOT, capture_output=True, text=True, timeout=120)
        assert done.returncode == 0 and f'Ran {count} tests' in done.stderr
        (OUT / (suffix + '.log')).write_text(done.stdout + done.stderr)
        inputs['tests/' + suffix] = sha(ROOT / 'tests' / suffix)
    for name in ('AGENTS.md', 'README.md', 'firmware/npu/README.md', 'firmware/npu/LINUX_CONTROL_CONTRACT.md',
                 'docs/REMAINING_WORK.md', 'docs/W1700K_STOCK_PORT_CURRENT_REFERENCE.md',
                 'docs/W1700K_STOCK_PORT_LEDGER.md', 'docs/W1700K_STOCK_PORT_LOGGING_SESSION_20260625.md',
                 'tools/migration/verify_source_export.py', 'tools/verify_merged_image.py', 'tools/build_firmware.py'):
        inputs[name] = sha(ROOT / name)
    for path in (Path(__file__), OUT / 'REPORT.md', ROOT / image['image'],
                 MERGE / 'build-provider-request-plan-20261010.log'):
        inputs[str(path.relative_to(ROOT))] = sha(path)
    check(inputs)
    proof = dict(passed=True, base_commit='ef29c39a4ba111874267b437c540b711368c6592', inputs=inputs,
                 request_cases=308, precopy_checks=476, request_mutants=9, address_controls=6,
                 native_harts=8, source_files=60, source_verifier_tests=4, build_runner_tests=8,
                 full_world=True, image_sha256=image['sha256'],
                 raw_firmware_packaged=False, real_sram_identity_publication=False, physical_acceptance=False)
    (OUT / 'verification.json').write_text(json.dumps(proof, indent=2) + '\n')
    files = [dict(path=path.relative_to(OUT).as_posix(), bytes=path.stat().st_size, sha256=sha(path))
             for path in sorted(OUT.rglob('*')) if path.is_file() and path.name != 'file-manifest.json']
    (OUT / 'file-manifest.json').write_text(json.dumps(files, indent=2) + '\n')
    print(json.dumps(dict(passed=True, inputs=len(inputs), files=len(files))))


if __name__ == '__main__':
    main()
