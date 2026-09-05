#!/usr/bin/env python3
"""Compile all affected profiles and compare complete decoded device trees."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import shutil

ROOT = Path(__file__).resolve().parents[2]
OPENWRT = ROOT / '.build/openwrt'
DTS = OPENWRT / 'target/linux/airoha/dts'
KERNEL = OPENWRT / 'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/linux-6.18.44'
BUILD = ROOT / '.local/npu-bootmem'
OUT = ROOT / 'research/checkpoints/2026-09-06-npu-bootmem'
PROFILES = ('an7581-w1700k-ubi', 'an7581-nokia-valyrian', 'an7581-evb-emmc-eagle', 'an7581-evb')
OLD_BA, NEW_BA = '/reserved-memory/npu-ba@90c06800', '/reserved-memory/npu-ba@90c0e000'
TX = '/reserved-memory/npu-txbufid@90c00000'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_dtb(profile, folder, sources=DTS):
    target = folder / (profile + '.dtb')
    preprocessed = subprocess.check_output(['cpp', '-nostdinc', '-undef', '-D__DTS__',
        '-x', 'assembler-with-cpp', '-I', str(KERNEL / 'include'), '-I', str(sources), str(sources / (profile + '.dts'))])
    result = subprocess.run([str(KERNEL / 'scripts/dtc/dtc'), '-@', '-I', 'dts', '-O', 'dtb', '-o', str(target)],
                            input=preprocessed, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    (folder / (profile + '.dtc.log')).write_bytes(result.stderr)
    return target


def properties(dtb):
    pending, nodes, pairs = ['/'], {}, []
    while pending:
        node = pending.pop()
        children = subprocess.check_output(['fdtget', '-l', str(dtb), node], text=True).splitlines()
        pending.extend(node.rstrip('/') + '/' + child for child in children)
        names = subprocess.check_output(['fdtget', '-p', str(dtb), node], text=True).splitlines()
        nodes[node] = {}
        pairs.extend((node, name) for name in names)
    values = subprocess.check_output(['fdtget', '-t', 'bx', str(dtb),
                                     *[value for pair in pairs for value in pair]], text=True).splitlines()
    assert len(values) == len(pairs)
    for (node, name), value in zip(pairs, values):
        nodes[node][name] = bytes(int(word, 16) for word in value.split()).hex()
    return nodes


def expected_tree(before, affected):
    expected = copy.deepcopy(before)
    if affected:
        expected[TX]['reg'] = struct.pack('>4I', 0, 0x90c00000, 0, 0xe000).hex()
        expected[NEW_BA] = expected.pop(OLD_BA)
        expected[NEW_BA]['reg'] = struct.pack('>4I', 0, 0x90c0e000, 0, 0x200000).hex()
        expected['/__symbols__']['npu_ba'] = (NEW_BA.encode() + b'\0').hex()
    return expected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    folder = BUILD / ('baseline' if args.baseline else 'candidate')
    folder.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    sources = DTS
    if args.baseline:
        sources = BUILD / 'baseline-source'
        shutil.copytree(DTS, sources, dirs_exist_ok=True)
        lock = json.loads((ROOT / 'firmware/source-lock.json').read_text())
        original = subprocess.check_output(['git', 'show', lock['openwrt']['base'] +
            ':target/linux/airoha/dts/an7581-npu-mt7996.dtsi'], cwd=OPENWRT)
        (sources / 'an7581-npu-mt7996.dtsi').write_bytes(original)
    rows = []
    for profile in PROFILES:
        path = compile_dtb(profile, folder, sources)
        current = properties(path)
        if not args.baseline:
            old = BUILD / 'baseline' / (profile + '.dtb')
            expected = expected_tree(properties(old), profile != 'an7581-evb')
            changed = sorted(node for node in expected.keys() | current.keys() if expected.get(node) != current.get(node))
            assert not changed, (profile, changed)
        rows.append({'profile': profile, 'dtb_sha256': digest(path),
                     'nodes': len(current), 'properties': sum(len(p) for p in current.values()),
                     'only_intended_reservation_changes': not args.baseline})
    report = {'passed': True, 'baseline': args.baseline, 'profiles': rows,
              'scope': 'Whole decoded DTB comparison for three MT7996 profiles and one unchanged generic control; no image build or flash.'}
    name = 'baseline-dtbs.json' if args.baseline else 'candidate-dtbs.json'
    (OUT / name).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
