#!/usr/bin/env python3
"""Materialize the pinned firmware source, without building or flashing."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run(*args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True)


def checkout(url, commit, dest):
    if dest.exists():
        raise RuntimeError(f'Refusing to overwrite {dest}')
    dest.mkdir(parents=True)
    run('git', 'init', str(dest))
    run('git', 'remote', 'add', 'origin', url, cwd=dest)
    run('git', 'fetch', '--depth=1', 'origin', commit, cwd=dest)
    run('git', 'checkout', '--detach', 'FETCH_HEAD', cwd=dest)


def apply(label, dest, lock):
    patch = ROOT / 'firmware/patches' / f'{label}.patch'
    run('git', 'apply', '--check', str(patch), cwd=dest)
    run('git', 'apply', str(patch), cwd=dest)
    overlay = ROOT / 'firmware/overlay' / label
    if overlay.exists():
        shutil.copytree(overlay, dest, dirs_exist_ok=True)
    for component in lock.get('component_sources', []):
        if component['tree'] != label:
            continue
        source = (ROOT / component['source']).resolve()
        target = (dest / component['destination']).resolve()
        if not source.is_relative_to((ROOT / 'firmware/npu').resolve()) or not target.is_relative_to(dest.resolve()):
            raise RuntimeError('Component path escapes its source/build tree')
        if hashlib.sha256(source.read_bytes()).hexdigest() != component['sha256']:
            raise RuntimeError(f'Component source hash mismatch: {component["source"]}')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        target.chmod(int(component['mode'], 8))
    for entry in lock[label]['changed_files']:
        path = dest / entry['path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise RuntimeError(f'Source hash mismatch: {label}/{entry["path"]}')
        path.chmod(int(entry['mode'], 8))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    lock = json.loads((ROOT / 'firmware/source-lock.json').read_text())
    destination = (args.destination or ROOT / lock.get('build_directory', '.build/openwrt')).resolve()
    if not destination.is_relative_to((ROOT / '.build').resolve()):
        raise RuntimeError('Build workspace must remain beneath this repository/.build')
    fs = subprocess.check_output(['stat', '-f', '-c', '%T', str(ROOT)], text=True).strip()
    if fs in {'9p', 'drvfs', 'fuseblk', 'ntfs', 'ntfs3'}:
        raise RuntimeError('OpenWrt build requires native Linux filesystem, not NTFS/DrvFS')
    checkout(lock['openwrt']['url'], lock['openwrt']['base'], destination)
    apply('openwrt', destination, lock)
    # Local LuCI commits are represented in the cumulative patch, not fetchable upstream.
    for name, feed in lock['feeds'].items():
        commit = lock['luci']['base'] if name == 'luci' else feed['commit']
        checkout(feed['url'], commit, destination / 'feeds' / name)
    apply('luci', destination / 'feeds/luci', lock)
    run('./scripts/feeds', 'update', '-i', cwd=destination)
    run('./scripts/feeds', 'install', '-a', cwd=destination)
    shutil.copy2(ROOT / 'firmware/build.config', destination / '.config')
    run('make', 'defconfig', cwd=destination)
    print(f'Prepared and source-hash-verified: {destination}')
    print('Build with a Linux-only PATH; no image has been built or flashed by this tool.')


if __name__ == '__main__':
    main()
