#!/usr/bin/env python3
"""Publish a local offline FIT only after binding it to a complete RV32 replay."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

import npu_ethernet_fit
import npu_image
from npu_replay_proof import (ROOT, SOURCE_LOCK, QualificationError, bind_world_replay, digest, is_digest, path_under,
                              read_pinned, read_receipt, require, verify_replay)
import npu_world_sources
import verify_merged_image as fit_tools

if not __debug__:
    raise RuntimeError('Sealing requires Python assertions enabled')

QUALIFIED = '.local/npu-qualified-images'
IMAGE_PATH = 'bin/targets/airoha/an7581/openwrt-airoha-an7581-gemtek_w1700k-ubi-squashfs-sysupgrade.itb'
BUILD = '.build/merged-openwrt'
LOGS = '.local/merge-nonoc-20260923'
MAX_FIT = 128 << 20
FIT_PAIR_FILES = {
    'code': 'lib/firmware/airoha/en7581_MT7996_npu_rv32.bin',
    'data': 'lib/firmware/airoha/en7581_MT7996_npu_data.bin',
    'manifest': 'lib/firmware/airoha/w1700k-npu-pair.json',
}


def verify_world(root, result_path, result_pin, snapshot_path, *, recover_rv32_roster=False):
    result_path = path_under(root / '.local', root / result_path)
    directory = result_path.parent
    world, _ = read_pinned(result_path, result_pin)
    require(result_path.name == 'result.json', 'Not a world result receipt')
    if not recover_rv32_roster:
        require(world['returncode'] == 0 and
                all(world[k] is True for k in ('passed', 'world_build', 'snapshot_unchanged', 'parent_namespaces_unchanged',
                    'original_build_content_modes_ownership_links_unchanged',
                    'original_download_cache_content_modes_ownership_links_unchanged')) and
                all(world[k] is False for k in ('host_timeout', 'probe_only', 'hardware', 'module_loaded')),
                'Not a passing isolated world build')
    envelope = world['envelope']
    require(envelope['network_isolated'] is True and envelope['physical_output_root'] == str(directory) and
            envelope['protected_lower_build'] == str(root / BUILD), 'World output directory does not match its envelope')
    snapshot_path = path_under(root / '.local/npu-validation-capsules', root / snapshot_path)
    capsule, capsule_pin = read_pinned(snapshot_path, envelope['snapshot_receipt_sha256'])
    frozen = path_under(snapshot_path.parent, 'root', directory=True)
    require(capsule['format'] == 'npu-validation-capsule-v1' and capsule['preservation_verified'] is True and
            capsule['sources_read_only'] is True and capsule['tracked_dirty'] is False and
            capsule['input_root'] == str(frozen) and capsule['source_root'] == str(root) and
            capsule['source_commit'] == envelope['snapshot_source_commit'], 'Not the selected clean world snapshot')
    lock, lock_pin = read_pinned(path_under(frozen, SOURCE_LOCK), envelope['source_lock_sha256'])
    require(lock_pin == capsule['files'][SOURCE_LOCK] == digest(path_under(root, SOURCE_LOCK)),
            'World does not use the current source lock')
    release = lock['kernel']
    require(isinstance(release, str) and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', release), 'Unknown module path')
    physical = path_under(directory, f'build-upper/{IMAGE_PATH}')
    child = world['child']
    verification = {}
    if recover_rv32_roster:
        require(not npu_world_sources.has_late_module_patches(lock), 'RV32 roster recovery is for the pinned baseline only')
        from npu_world_postflight import recheck
        image, image_receipt_pin, postflight = recheck(
            root, directory, world, result_pin, frozen, capsule['files'], lock_pin, physical)
        verification['world_postflight'] = postflight
    else:
        require(child['world_build'] is True and child['passed'] is True and child['hardware'] is False and
                child['critical_kernel_modules_and_RV32_cleaned'] is True and child['proof']['root_readonly'] is True and
                child['proof']['producer_view_readonly'] is True, 'No clean combined world proof')
        name = Path(child['image_verification_receipt'])
        require(not name.is_absolute() and name.is_relative_to(LOGS) and name.name == 'result.json',
                'Missing independent image-verification receipt')
        image, image_receipt_pin = read_pinned(path_under(directory, Path('log-upper') / name.relative_to(LOGS)),
                                               child['image_verification_sha256'])
        require(image == child['image_verification'], 'World and image receipts differ')
        require(str(physical) == world['physical_image'] and image['sha256'] == world['physical_image_sha256'],
                'World FIT path or digest mismatch')
    require(image['passed'] is True and image['source_lock_sha256'] == lock_pin and
            image['image'] == f'{BUILD}/{IMAGE_PATH}' and image['pinned_module_bytes_verified'] is True,
            'Not the verified image from this world')
    if fit_tools.expects_coherent_pool(lock):
        pools = image.get('board_configuration', {}).get('coherent_dma_pool', {})
        selected_dtb = image['fit_configuration']['fdt']
        dtb_pins = [row['sha256'] for row in image['components'] if row['name'] == selected_dtb and
                    row['type'] == 'flat_dt']
        require(is_digest(pools.get('dtb_sha256')) and dtb_pins == [pools['dtb_sha256']],
                'Missing coherent DMA pool proof for the selected world DTB')
    require(is_digest(image['sha256']) and image['bytes'] == physical.stat().st_size and
            0 < image['bytes'] <= MAX_FIT, 'World FIT path, size or digest mismatch')
    binding = image['packaged_module_provenance']
    producer_name, producer_pin = binding['producer'], binding['producer_sha256']
    require(binding['matches'] is True and binding['mismatches'] == [] and binding['source_lock_sha256'] == lock_pin and
            is_digest(producer_pin) and capsule['files'].get(producer_name) == producer_pin, 'Wrong pinned module producer')
    producer = npu_world_sources.linked_module_sources(frozen, path_under(frozen, producer_name))
    require(producer['receipt_sha256'] == producer_pin and producer['source_lock_sha256'] == lock_pin and
            all(capsule['files'].get(n) == h for n, h in (producer['inputs'] | producer['artifacts']).items()),
            'Module producer does not match its snapshot')
    successor = {}
    if npu_world_sources.has_late_module_patches(lock):
        from npu_successor_sources import world_contract
        contract, proof = world_contract(frozen, lock, producer)
        require(child.get('prepared_sources_verified') == proof,
                'World lacks the exact successor prepared-source proof')
        successor = dict(source_contract_sha256=proof['source_contract_sha256'],
                         staged_bundle_sha256=contract['staged_bundle_sha256'])
    linked = {Path(n).name: h for n, h in producer['artifacts'].items()}
    rows, selected = binding['modules'], image['selected_modules']
    require(set(fit_tools.MODULE_NAMES) == linked.keys() == rows.keys() == selected.keys(),
            'Expected exactly the four combined modules')
    modules = {}
    for name, row in rows.items():
        actual = selected[name]['sha256']
        require(row['matches'] is True and row['linked_sha256'] == linked[name] and is_digest(actual) and
                row['actual_packaged_sha256'] == row['expected_packaged_sha256'] == actual,
                f'Incomplete packaged module binding: {name}')
        modules[name] = actual
    return dict(frozen=frozen, declarations=capsule['files'], world_sha256=result_pin, snapshot_sha256=capsule_pin,
                source_lock_sha256=lock_pin, producer_sha256=producer_pin, image_receipt_sha256=image_receipt_pin,
                fit=physical, image=image, module_sha256=modules, kernel=release, source_lock=lock,
                build_upper=path_under(directory, 'build-upper', directory=True)) | successor | verification


def inspect_fit_pair(image_path, scratch, kernel, replay_pair, module_names=fit_tools.MODULE_NAMES):
    selected, components, paths = fit_tools.extract_fit_components(image_path, scratch)
    model, compatible = fit_tools.board_identity(paths['fdt'])
    modules = {name: f'lib/modules/{kernel}/{name}' for name in module_names}
    rootfs = scratch / 'selected-rootfs'
    fit_tools.run(['unsquashfs', '-processors', '1', '-mem', '16M', '-no-xattrs', '-no-progress', '-no-wildcards',
                   '-strict-errors', '-d', rootfs, paths['rootfs'], *FIT_PAIR_FILES.values(), *modules.values()])
    blobs = {key: path_under(rootfs, p) for key, p in FIT_PAIR_FILES.items()}
    manifest, manifest_pin = read_receipt(blobs['manifest'])
    payload = {}
    for role, limit in (('code', npu_image.CODE_LIMIT), ('data', npu_image.DATA_LIMIT)):
        with blobs[role].open('rb') as stream:
            data = stream.read(limit + 1)
        require(0 < len(data) <= limit and npu_image.sha(data) == replay_pair[role],
                f'Packaged RV32 {role.upper()} differs from the replay')
        payload[role] = data
    npu_image.validate(payload['code'], payload['data'], manifest)
    return dict(fit_configuration=selected, components=components, model=model, compatible=compatible,
                pair={key: manifest[key] for key in ('code', 'data')} | dict(manifest_sha256=manifest_pin),
                module_sha256={name: digest(path_under(rootfs, path)) for name, path in modules.items()})

def bind_packaged(packed, world, replay, ethernet=None):
    inspected = world['image']
    for k in ('fit_configuration', 'components', 'model', 'compatible'):
        require(packed[k] == inspected[k], f'Selected FIT {k} differs from the world receipt')
    modules = packed['module_sha256']
    eth_name = npu_ethernet_fit.ETH_MODULE
    if ethernet is not None:
        require(modules.get(eth_name) == ethernet['expected_packaged_sha256'],
                'Selected FIT Ethernet module differs from the linked world module')
        modules = {name: pin for name, pin in modules.items() if name != eth_name}
    require(modules == world['module_sha256'], 'Packaged files differ from the four qualified modules')
    pair, image_pair = packed['pair'], inspected['checked_npu_pair']
    require(all(pair[k] == image_pair[k] for k in ('code', 'data', 'manifest_sha256')),
            'Packaged RV32 pair differs from the world receipt')
    for role in ('code', 'data'):
        require(pair[role]['sha256'] == replay['pair'][role], f'Packaged RV32 {role.upper()} differs from the replay')


def stage_fit(source, staged, expected_bytes, expected_pin):
    remaining = expected_bytes
    h = hashlib.sha256()
    with source.open('rb') as reader, staged.open('xb') as writer:
        while remaining:
            block = reader.read(min(remaining, 262144))
            require(bool(block), 'World FIT shortened during copy')
            h.update(block)
            writer.write(block)
            remaining -= len(block)
        require(not reader.read(1) and h.hexdigest() == expected_pin, 'World FIT bytes differ from the pinned image')
        writer.flush()
        os.fchmod(writer.fileno(), 0o444)
        os.fsync(writer.fileno())


def fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def seal(root, args):
    require(re.fullmatch(r'[a-z][a-z0-9-]{0,39}', args.name), 'Invalid new candidate name')
    # A missing terminal result must stop an attempted release even when a FIT exists.
    if not (root / args.terminal).exists():
        raise QualificationError('The selected replay has no terminal receipt; no candidate was published')
    store = path_under(root, QUALIFIED, directory=True)
    output = store / args.name
    require(not os.path.lexists(output), 'Candidate name already exists')
    recovery = {'recover_rv32_roster': True} if getattr(args, 'recover_rv32_roster', False) else {}
    world = verify_world(root, args.world_result, args.world_sha256, args.snapshot, **recovery)
    replay = verify_replay(root, args.start, args.start_sha256, args.terminal, args.terminal_sha256,
                           world['frozen'], world['declarations'])
    bind_world_replay(replay, world['source_lock_sha256'], world['producer_sha256'],
                      world.get('source_contract_sha256'))
    fit = world['image']
    filename = fit['sha256'] + '.itb'
    with tempfile.TemporaryDirectory(prefix='.seal-', dir=store) as temp:
        scratch = Path(temp)
        ethernet = npu_ethernet_fit.bind_linked(root, world, args, scratch)
        staged = scratch / filename
        stage_fit(world['fit'], staged, fit['bytes'], fit['sha256'])
        inspect_dir = scratch / 'inspection'
        inspect_dir.mkdir()
        if ethernet is None:
            packed = inspect_fit_pair(staged, inspect_dir, world['kernel'], replay['pair'])
        else:
            names = (*fit_tools.MODULE_NAMES, npu_ethernet_fit.ETH_MODULE)
            packed = inspect_fit_pair(staged, inspect_dir, world['kernel'], replay['pair'], names)
        bind_packaged(packed, world, replay, ethernet)
        require(digest(staged) == fit['sha256'], 'Inspected FIT changed before publication')
        receipt = {k: world[k] for k in ('world_sha256', 'snapshot_sha256', 'source_lock_sha256', 'producer_sha256',
                                          'image_receipt_sha256')}
        if 'source_contract_sha256' in world:
            receipt['source_contract_sha256'] = world['source_contract_sha256']
        if 'world_postflight' in world:
            receipt['world_postflight'] = world['world_postflight']
        receipt.update(format='w1700k-offline-sealed-fit-v1', image=filename, image_sha256=fit['sha256'], bytes=fit['bytes'],
                       replay=replay, packaged=packed, rv32_emulator_replay_bound=True,
                       scope='Exact inspected local FIT and emulator payload binding only',
                       boot_verified=False, physical_retirement=False, hardware=False, flash_authorized=False)
        if ethernet is not None:
            receipt['ethernet'] = {**ethernet, 'matches': True,
                                   'actual_packaged_sha256': packed['module_sha256'][npu_ethernet_fit.ETH_MODULE]}
        publication = scratch / 'receipt.json'
        with publication.open('x') as stream:
            json.dump(receipt, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fchmod(stream.fileno(), 0o444)
            os.fsync(stream.fileno())
        output.mkdir(mode=0o700, exist_ok=False)
        fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.link(staged, filename, dst_dir_fd=fd, follow_symlinks=False)
            os.fsync(fd)
            # The receipt is the completion marker; an interrupted copy is not a candidate.
            os.link(publication, 'receipt.json', dst_dir_fd=fd, follow_symlinks=False)
            os.fsync(fd)
            require(os.path.samestat(os.lstat(output), os.fstat(fd)), 'Candidate directory moved during sealing')
        finally:
            os.close(fd)
        fsync_dir(store)
    return output / 'receipt.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--snapshot', required=True, type=Path)
    parser.add_argument('--recover-rv32-roster', action='store_true',
                        help='explicitly recheck the pinned baseline RV32 roster failure read-only')
    parser.add_argument('--ethernet-bundle', type=Path, help='Verified source bundle receipt for the staged Ethernet lock')
    parser.add_argument('--ethernet-bundle-sha256', help='Independently pinned Ethernet bundle receipt SHA-256')
    parser.add_argument('--ethernet-linked-sha256', help='SHA-256 of the raw module from the same passing world')
    for flag in ('world-result', 'start', 'terminal'):
        parser.add_argument('--' + flag, required=True, type=Path)
        parser.add_argument('--' + ('world' if flag == 'world-result' else flag) + '-sha256', required=True)
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error('Run offline FIT sealing as the unprivileged workspace user')
    try:
        saved = seal(ROOT, args)
    except (ValueError, AssertionError, KeyError, TypeError, OSError) as error:
        parser.error(str(error))
    print(saved)


if __name__ == '__main__':
    main()
