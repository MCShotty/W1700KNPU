#!/usr/bin/env python3
"""Export the reviewed merged checkout using an explicit source-only allowlist."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.local/merge-nonoc-20260923'
DEST = ROOT / '.build/merged-openwrt'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(tree, *args):
    return subprocess.check_output(['git', '-C', str(tree), *args])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    before = json.loads((WORK / 'before/source-lock.json').read_text())
    old_export = WORK / 'source-export.json'
    protected = [ROOT / 'firmware/source-lock.json', ROOT / 'firmware/patches/openwrt.patch',
                 ROOT / 'firmware/patches/luci.patch', ROOT / 'firmware/build.config']
    if args.refresh:
        previous = json.loads(old_export.read_text())
        for path in protected:
            assert sha(path) == previous['authority'][str(path.relative_to(ROOT))], path
    else:
        assert not old_export.exists()
        assert sha(protected[0]) == sha(WORK / 'before/source-lock.json')
        for name in ('openwrt.patch', 'luci.patch'):
            assert sha(ROOT / 'firmware/patches' / name) == sha(WORK / 'before/patches' / name)
    components = json.loads((WORK / 'component-sources.json').read_text())
    source = json.loads((WORK / 'source.json').read_text())
    feeds = json.loads((WORK / 'feed-pins.json').read_text())
    rows, tracked_patches = {}, {}
    for label, tree in (('openwrt', DEST), ('luci', DEST / 'feeds/luci')):
        changed = {p for p in git(tree, 'diff', '--name-only', '-z').decode().split('\0') if p}
        allowed = changed | {row['path'] for row in before[label]['changed_files']}
        if label == 'openwrt':
            allowed |= {'package/kernel/mt76/patches/900-w1700k-integrated-npu.patch',
                        'target/linux/airoha/patches-6.18/999-w1700k-integrated-npu.patch',
                        'files/usr/libexec/w1700k-release-helper', 'version'}
            origin = WORK / 'builder/user/default/files'
            allowed |= {'files/' + str(p.relative_to(origin)) for p in origin.rglob('*')
                        if p.is_file() and p.relative_to(origin).parts[0] in ('etc', 'www')}
            allowed |= {c['destination'] for c in components}
        patch = ROOT / 'firmware/patches' / (label + '.patch')
        tracked_patches[label] = git(tree, 'diff', '--binary', 'HEAD', '--', *sorted(changed))
        patch.write_bytes(tracked_patches[label])
        fresh = WORK / ('overlay-' + label + '-new')
        if fresh.exists():
            raise RuntimeError('Unexpected temporary export directory: ' + str(fresh))
        fresh.mkdir()
        entries = []
        for name in sorted(allowed):
            path = tree / name
            if not path.exists():
                continue
            assert path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(tree.resolve()), name
            assert path.stat().st_size < 4 * 1024 * 1024, name
            contents = path.read_bytes()
            assert b'\0' not in contents, ('Only source text may be exported', name)
            assert b'PRIVATE KEY-----' not in contents, name
            assert not any(line.startswith((b'<<<<<<< ', b'||||||| ', b'>>>>>>> ')) for line in contents.splitlines()), name
            entries.append(dict(path=name, sha256=sha(path), mode=oct(path.stat().st_mode & 0o777)))
            is_component = any(c['tree'] == label and c['destination'] == name for c in components)
            tracked = subprocess.run(['git', '-C', str(tree), 'ls-files', '--error-unmatch', '--', name],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
            if not tracked and not is_component:
                target = fresh / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
        overlay = ROOT / 'firmware/overlay' / label
        if overlay.exists():
            archive = WORK / ('overlay-' + label + '-previous-' + str(len(list(WORK.glob('overlay-' + label + '-previous-*')))))
            assert not archive.exists()
            shutil.move(overlay, archive)
        shutil.move(fresh, overlay)
        rows[label] = entries
    for component in components:
        assert sha(ROOT / component['source']) == component['sha256']
        assert sha(DEST / component['destination']) == component['sha256']
    luci_head = git(DEST / 'feeds/luci', 'rev-parse', 'HEAD').decode().strip()
    lock = dict(schema=2, snapshot='nonoc-merged-experimental-20260923',
                last_router_tested_snapshot=before['last_router_tested_snapshot'],
                build_directory='.build/merged-openwrt',
                openwrt=dict(url=source['url'], base=source['commit'], local_head=source['commit'], changed_files=rows['openwrt']),
                luci=dict(url='https://github.com/openwrt/luci.git', base=luci_head,
                          local_head=luci_head, changed_files=rows['luci']),
                feeds=feeds, component_sources=components,
                mt76='01367e60db433534ad0aa3d3b6c886de8cb7d44c', kernel='6.18.52',
                board='gemtek,w1700k-ubi',
                wlan_npu='enabled in unified experimental build; physical recovery and full parity remain unverified',
                upstream_release=source['release'], builder_commit='9449e4ca242ab30278df20940d6654ddc1c102e8',
                firmware_core='firmware/npu/Makefile builds the RV32 components; platform loader and postgate execution remain incomplete')
    (ROOT / 'firmware/source-lock.json').write_text(json.dumps(lock, indent=2) + '\n')
    shutil.copy2(DEST / '.config', ROOT / 'firmware/build.config')
    record = dict(authority={str(p.relative_to(ROOT)): sha(p) for p in protected},
                  source_files={label: len(entries) for label, entries in rows.items()},
                  old_snapshot=before['snapshot'], snapshot=lock['snapshot'],
                  kernel=lock['kernel'], mt76=lock['mt76'], board=lock['board'])
    old_export.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
