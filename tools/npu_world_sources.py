"""Check actual prepared sources against locked successful producer identities."""
import hashlib
import json
import os
from pathlib import Path
import re

PINNED_MT76_FIRMWARE_LINKS = {
    '01367e60db433534ad0aa3d3b6c886de8cb7d44c': {
        'firmware/mt7662.bin':'mt7662_firmware_e3_v2.3.bin',
        'firmware/mt7662_rom_patch.bin':'mt7662_patch_e3_hdr_v0.0.2_P69.bin',
    }
}


def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def relative_file(base, name):
    relative = Path(name)
    assert name and not relative.is_absolute() and '..' not in relative.parts, ('unsafe-source-path', name)
    target = base / relative
    assert not target.is_symlink() and target.resolve().is_relative_to(base.resolve()), ('source-path-escape', name)
    return target


def mt76_source_file(base, name, revision):
    relative = Path(name)
    assert name and not relative.is_absolute() and '..' not in relative.parts, ('unsafe-source-path',name)
    assert base.is_dir() and not base.is_symlink()
    assert not any((base / parent).is_symlink() for parent in relative.parents), ('source-directory-alias',name)
    target = base / relative
    if target.is_symlink():
        literal = PINNED_MT76_FIRMWARE_LINKS.get(revision,{}).get(name)
        assert literal is not None and os.readlink(target) == literal, ('unlisted-mt76-source-alias',name)
        return relative_file(base,str(relative.parent / literal))
    return relative_file(base,name)


def verify(build, root, lock, provider, consumer):
    source_lock = digest(root / 'firmware/source-lock.json')
    assert provider['passed'] is consumer['passed'] is True
    assert provider['source_lock_sha256'] == consumer['source_lock_sha256'] == source_lock
    release = lock['kernel']
    assert re.fullmatch(r'\d+\.\d+\.\d+', release)
    assert re.fullmatch(r'[0-9a-f]{40}', lock['mt76'])
    minor = '.'.join(release.split('.')[:2])
    prepared = build / 'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581'
    kernel = prepared / ('linux-' + release)
    assert not kernel.is_symlink() and kernel.resolve().is_relative_to(build.resolve())
    patch_name = 'target/linux/airoha/patches-' + minor + '/999-w1700k-integrated-npu.patch'
    patch = relative_file(root / 'firmware/overlay/openwrt', patch_name)
    row = next(row for row in lock['openwrt']['changed_files'] if row['path'] == patch_name)
    assert digest(patch) == row['sha256']
    names = re.findall(r'^\+\+\+ b/([^\n]+)$', patch.read_text(), re.M)
    assert names and len(names) == len(set(names))
    for name in names:
        key = '.local/merge-nonoc-20260923/kernel-merged/' + name
        assert digest(relative_file(kernel, name)) == provider['inputs'][key], ('prepared-kernel-source-drift', name)
    prefix = 'target/linux/airoha/files-' + minor + '/'
    for row in lock['component_sources']:
        assert row['tree'] == 'openwrt' and row['destination'].startswith(prefix)
        name = row['destination'].removeprefix(prefix)
        assert digest(relative_file(kernel, name)) == row['sha256'], ('prepared-component-drift', name)
    manifests = [name for name in consumer['artifacts'] if name.endswith('/source-before.json')]
    assert len(manifests) == 1
    manifest = relative_file(root, manifests[0])
    assert digest(manifest) == consumer['artifacts'][manifests[0]]
    expected = json.loads(manifest.read_bytes())
    candidates = [path for path in prepared.glob('mt76-*') if path.name.endswith('~' + lock['mt76'][:8])]
    assert len(candidates) == 1
    mt76 = candidates[0]
    assert not mt76.is_symlink() and mt76.resolve().is_relative_to(build.resolve())
    for name, identity in expected.items():
        assert set(identity) == {'sha256', 'mode'}, ('unexpected-source-identity', name)
        assert digest(mt76_source_file(mt76,name,lock['mt76'])) == identity['sha256'], ('prepared-mt76-source-drift', name)
    return dict(kernel_patch_files=len(names), component_sources=len(lock['component_sources']), mt76_source_files=len(expected))
