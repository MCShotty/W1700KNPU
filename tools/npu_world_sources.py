"""Check actual prepared sources against locked successful producer identities."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
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


def checked_link_record(record):
    assert record['passed'] is True and type(record['returncode']) is int and record['returncode'] == 0
    assert record['originals_unchanged'] is True
    inner = record['inner']
    assert inner['passed'] is True and inner['current_checked_header_compiled'] is True
    assert inner['module_loaded'] is False and inner['image_built'] is False and inner['hardware'] is False
    inputs = record['inputs']
    assert isinstance(inputs, dict) and inputs and all(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value)
                          for value in inputs.values())
    return inner, inputs


def linked_module_sources(root, receipt_path):
    """Read the combined checked-IRQ producer without rewriting its receipt."""
    assert not receipt_path.is_symlink(), 'combined-receipt-alias'
    receipt_path = receipt_path.resolve()
    name = receipt_path.relative_to(root.resolve()).as_posix()
    assert relative_file(root, name) == receipt_path
    record = json.loads(receipt_path.read_bytes())
    inner, inputs = checked_link_record(record)
    source_lock = digest(root / 'firmware/source-lock.json')
    assert inputs['firmware/source-lock.json'] == source_lock, 'combined-source-lock-drift'
    lock = json.loads((root / 'firmware/source-lock.json').read_bytes())
    for input_name, expected in inputs.items():
        path = PurePosixPath(input_name)
        assert input_name and not path.is_absolute() and '..' not in path.parts and '\\' not in input_name
        assert path.as_posix() == input_name
        assert digest(relative_file(root, input_name)) == expected, ('combined-input-drift', input_name)
    prefixes = {'kernel': '.local/merge-nonoc-20260923/kernel-merged/',
                'mt76': '.local/merge-nonoc-20260923/mt76-merged/'}
    sources = {label: {key.removeprefix(prefix): value for key, value in inputs.items() if key.startswith(prefix)}
               for label, prefix in prefixes.items()}
    assert all(sources.values()), 'missing-combined-source-identities'
    names = ('mt76.ko', 'mt76-connac-lib.ko', 'mt7996/mt7996e.ko')
    assert set(inner['modules']) == set(names), 'unexpected-combined-module-set'
    artifacts = {}
    for relative, metadata in [('airoha_npu.ko', inner['provider']),
                               *[('mt76/' + key, inner['modules'][key]) for key in names]]:
        artifact_name = (receipt_path.parent.relative_to(root) / relative).as_posix()
        artifact = relative_file(root, artifact_name)
        assert metadata['vermagic'] == inner['provider']['vermagic']
        assert metadata['vermagic'].split()[0] == lock['kernel'] and 'aarch64' in metadata['vermagic'].split()
        assert artifact.stat().st_size == metadata['bytes'] and digest(artifact) == metadata['sha256'], ('combined-artifact-drift', relative)
        with artifact.open('rb') as stream:
            header = stream.read(20)
        assert header[:6] == b'\x7fELF\x02\x01' and header[16:20] == b'\x01\x00\xb7\x00', ('not-AArch64-module', relative)
        artifacts[artifact_name] = metadata['sha256']
    return dict(receipt=name, receipt_sha256=digest(receipt_path), source_lock_sha256=source_lock,
                inputs=inputs, artifacts=artifacts, **sources)


def stage_locked_overlays(build, root, lock, copy_file):
    """Refresh authoritative files only in the caller's private build overlay."""
    planned = {}

    def add(source, name, expected, mode):
        source = relative_file(root, source)
        target = relative_file(build, name)
        assert source.is_file() and digest(source) == expected, ('overlay-source-drift', str(source))
        assert not target.exists() or target.is_file(), ('overlay-target-not-file', name)
        entry = dict(source=source, target=target, sha256=expected, mode=int(mode, 8))
        if name in planned:
            assert planned[name]['sha256'] == expected and planned[name]['mode'] == entry['mode'], 'conflicting-overlay-authority'
        planned[name] = entry

    for label, prefix in (('openwrt', Path()), ('luci', Path('feeds/luci'))):
        for row in lock[label]['changed_files']:
            authority = Path('firmware/overlay') / label / row['path']
            source = relative_file(root, str(authority))
            if source.exists():
                add(str(authority), str(prefix / row['path']), row['sha256'], row['mode'])
    for row in lock['component_sources']:
        assert row['tree'] == 'openwrt', 'unsupported-component-tree'
        add(row['source'], row['destination'], row['sha256'], row['mode'])
    config = relative_file(root, 'firmware/build.config')
    add('firmware/build.config', '.config', digest(config), '0644')
    copied = []
    for name, row in planned.items():
        target = row['target']
        if target.is_file() and digest(target) == row['sha256'] and target.stat().st_mode & 0o7777 == row['mode']:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()
        copy_file(row['source'], target)
        target.chmod(row['mode'])
        assert digest(target) == row['sha256'], ('staged-overlay-drift', name)
        copied.append(name)
    checked = {}
    for label, tree in (('openwrt', build), ('luci', build / 'feeds/luci')):
        for row in lock[label]['changed_files']:
            target = relative_file(tree, row['path'])
            assert target.is_file() and digest(target) == row['sha256'], ('prebuild-locked-source-drift', label, row['path'])
            assert target.stat().st_mode & 0o7777 == int(row['mode'], 8), ('prebuild-locked-source-mode', label, row['path'])
        checked[label] = len(lock[label]['changed_files'])
    for row in lock['component_sources']:
        target = relative_file(build, row['destination'])
        assert digest(target) == row['sha256'] and target.stat().st_mode & 0o7777 == int(row['mode'], 8), ('prebuild-component-drift', row['destination'])
    assert digest(build / '.config') == digest(config), 'prebuild-config-drift'
    return dict(locked_files_checked=checked, component_sources_checked=len(lock['component_sources']),
                authority_files_checked=len(planned), copied=copied, source_lock_sha256=digest(root / 'firmware/source-lock.json'),
                cumulative_only_files_require_existing_exact_bytes=True, private_overlay_only=True)


def verify(build, root, lock, provider=None, consumer=None, *, module_receipt=None, module_sources=None):
    source_lock = digest(root / 'firmware/source-lock.json')
    if module_receipt is not None or module_sources is not None:
        assert provider is consumer is None, 'mixed-producer-contracts'
        assert module_receipt is None or module_sources is None, 'mixed-combined-source-contracts'
        if module_sources is None:
            combined = linked_module_sources(root, module_receipt)
        else:
            # The private build replaces observed outputs. Keep source expectations
            # pinned to the immutable receipt verified before that build started.
            combined = module_sources
            receipt = relative_file(root, combined['receipt'])
            assert digest(receipt) == combined['receipt_sha256'], 'combined-receipt-drift'
            record = json.loads(receipt.read_bytes())
            checked_link_record(record)
            assert combined['inputs'] == record['inputs'], 'combined-contract-input-drift'
            for label, prefix in (('kernel', '.local/merge-nonoc-20260923/kernel-merged/'),
                                  ('mt76', '.local/merge-nonoc-20260923/mt76-merged/')):
                expected_sources = {key.removeprefix(prefix): value for key,value in record['inputs'].items() if key.startswith(prefix)}
                assert combined[label] == expected_sources and expected_sources, 'combined-contract-source-drift'
            assert combined['source_lock_sha256'] == record['inputs']['firmware/source-lock.json']
        assert combined['source_lock_sha256'] == source_lock
        kernel_inputs = combined['kernel']
        expected = {name: dict(sha256=value) for name, value in combined['mt76'].items()}
    else:
        assert provider['passed'] is consumer['passed'] is True
        assert provider['source_lock_sha256'] == consumer['source_lock_sha256'] == source_lock
        prefix = '.local/merge-nonoc-20260923/kernel-merged/'
        kernel_inputs = {name.removeprefix(prefix): value for name,value in provider['inputs'].items() if name.startswith(prefix)}
        manifests = [name for name in consumer['artifacts'] if name.endswith('/source-before.json')]
        assert len(manifests) == 1
        manifest = relative_file(root, manifests[0])
        assert digest(manifest) == consumer['artifacts'][manifests[0]]
        expected = json.loads(manifest.read_bytes())
        assert all(set(identity) == {'sha256', 'mode'} for identity in expected.values()), 'unexpected-source-identity'
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
    if module_receipt is not None or module_sources is not None:
        assert set(names) == set(kernel_inputs), 'combined-kernel-source-set-drift'
    for name in names:
        assert digest(relative_file(kernel, name)) == kernel_inputs[name], ('prepared-kernel-source-drift', name)
    prefix = 'target/linux/airoha/files-' + minor + '/'
    for row in lock['component_sources']:
        assert row['tree'] == 'openwrt' and row['destination'].startswith(prefix)
        name = row['destination'].removeprefix(prefix)
        assert digest(relative_file(kernel, name)) == row['sha256'], ('prepared-component-drift', name)
    candidates = [path for path in prepared.glob('mt76-*') if path.name.endswith('~' + lock['mt76'][:8])]
    assert len(candidates) == 1
    mt76 = candidates[0]
    assert not mt76.is_symlink() and mt76.resolve().is_relative_to(build.resolve())
    for name, identity in expected.items():
        assert digest(mt76_source_file(mt76,name,lock['mt76'])) == identity['sha256'], ('prepared-mt76-source-drift', name)
    return dict(kernel_patch_files=len(names), component_sources=len(lock['component_sources']), mt76_source_files=len(expected))
