#!/usr/bin/env python3
"""Seal/check this raw-pair checkpoint without publishing private binary inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
WORK = ROOT / '.local/npu-raw-pair-20261010'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(inputs):
    for name, digest in inputs.items():
        assert sha(ROOT / name) == digest, ('input-changed', name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        proof = json.loads((OUT / 'verification.json').read_bytes())
        verify(proof['inputs'])
        files = json.loads((OUT / 'file-manifest.json').read_bytes())
        for row in files:
            assert sha(OUT / row['path']) == row['sha256']
        print(json.dumps(dict(passed=True, inputs=len(proof['inputs']), files=len(files))))
        return
    assert not (OUT / 'verification.json').exists()
    raw_path = WORK / 'full-final/result.json'
    assembly_path = WORK / 'assembly-final.json'
    provider_path = WORK / 'loader-final-v2/result.json'
    image_path = ROOT / '.local/merge-nonoc-20260923/raw-pair-20261010-offline/result.json'
    raw, assembly, provider, image = [json.loads(path.read_bytes()) for path in
                                     (raw_path, assembly_path, provider_path, image_path)]
    assert raw['passed'] and raw['full_nominal'] and raw['raw_pair'] and not raw['post_load_elf_injection']
    assert raw['txdone']['claimed'] == 3072 and raw['independent_pages'][-1]['claimed'] == 1792
    assert len(raw['boot_controls']) == 6 and len(raw['controls']) == 8 and raw['hooks'] == 61
    assert assembly['passed'] and assembly['test_groups'] == 15 and assembly['repeat_build'] and not assembly['skipped']
    assert provider['passed'] and provider['matrix']['cases'] == 273 and len(provider['pair_cases']) == 7
    assert image['passed'] and image['sha256'] == '230e03a7b87cb9e14e0464b53d324bb2c4eb650b3c9a64a63514b30dde4458fe'
    inputs = {}
    for rows in (raw['inputs'], assembly['source_inputs'], provider['inputs']):
        for name, digest in rows.items():
            assert name not in inputs or inputs[name] == digest, ('conflicting-seal', name)
            inputs[name] = digest
    verify(inputs)
    receipts = {raw_path: 'raw-result.json', assembly_path: 'assembly-result.json',
                provider_path: 'provider-result.json', image_path: 'image-result.json',
                WORK / 'checked-pair/manifest.json': 'pair-manifest.json',
                WORK / 'repeat-pair/manifest.json': 'repeat-manifest.json'}
    for name in ('jev-pre-request', 'jev-pre-result', 'jev-post-request', 'jev-post-result'):
        receipts[WORK / (name + '.json')] = name + '.json'
    for source, name in receipts.items():
        shutil.copyfile(source, OUT / name)
        inputs[str(source.relative_to(ROOT))] = sha(source)
    log = WORK / 'build-runner-final.log'
    result = subprocess.run(['python3', '-m', 'unittest', 'discover', '-s', 'tests',
                             '-p', 'test_build_firmware_host_tools.py', '-v'], cwd=ROOT,
                            capture_output=True, text=True, timeout=120)
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and 'Ran 8 tests' in log.read_text()
    shutil.copyfile(log, OUT / log.name)
    archives, members = {}, {}
    for name, folder in (('fresh', WORK / 'normal-core'), ('packaged', ROOT / '.build/merged-openwrt/bin/npu')):
        archive = folder / 'libw1700k-npu.a'
        order = subprocess.check_output(['ar', 't', archive], text=True).splitlines()
        assert len(order) == len(set(order)) == 12
        contents = {member: hashlib.sha256(subprocess.check_output(['ar', 'p', archive, member])).hexdigest()
                    for member in order}
        members[name] = contents
        archives[name] = dict(sha256=sha(archive), member_order=order, members=contents)
        inputs[str(archive.relative_to(ROOT))] = sha(archive)
    assert members['fresh'] == members['packaged']
    documents = ['AGENTS.md', 'README.md', 'firmware/npu/README.md', 'firmware/npu/Makefile',
                 'docs/REMAINING_WORK.md', 'docs/W1700K_STOCK_PORT_CURRENT_REFERENCE.md',
                 'docs/W1700K_STOCK_PORT_LEDGER.md', 'docs/W1700K_STOCK_PORT_LOGGING_SESSION_20260625.md',
                 'tools/verify_merged_image.py', 'tests/test_build_firmware_host_tools.py']
    for path in [ROOT / name for name in documents] + [Path(__file__), OUT / 'REPORT.md']:
        inputs[str(path.relative_to(ROOT))] = sha(path)
    verify(inputs)
    proof = dict(passed=True, base_commit='629a65037e460e647a363aeadf274bc9279c62db',
                 raw_hooks=61, raw_packet_claims=3072, raw_page_claims=1792,
                 assembly_groups=15, loader_matrix=273, exact_pair_loader_cases=7, build_runner_tests=8,
                 boot_controls=6, txdone_controls=8, repeat_pair_byte_identical=True,
                 archive_members_identical=True, archives=archives, inputs=inputs,
                 firmware_packaged=False, physical_acceptance=False, fresh_world_build=False)
    (OUT / 'verification.json').write_text(json.dumps(proof, indent=2) + '\n')
    files = [dict(path=path.relative_to(OUT).as_posix(), bytes=path.stat().st_size, sha256=sha(path))
             for path in sorted(OUT.rglob('*')) if path.is_file() and path.name != 'file-manifest.json']
    (OUT / 'file-manifest.json').write_text(json.dumps(files, indent=2) + '\n')
    print(json.dumps(dict(passed=True, inputs=len(inputs), files=len(files))))


if __name__ == '__main__':
    main()
