#!/usr/bin/env python3
"""Inspect the built FIT, packages and module ABI without executing firmware."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from elftools.elf.elffile import ELFFile
import npu_image

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / '.build/merged-openwrt'
OUT = ROOT / '.local/merge-nonoc-20260923/image-verification'
CORE_OBJECT_NAMES = frozenset(name + '.o' for name in (
    'barrier', 'admission', 'control-v2', 'bootstrap', 'bootstrap-v2', 'cold-setup',
    'startup', 'allocator', 'cold-page', 'cold-packet', 'cold-indication', 'cold-tx',
    'cold-descriptor', 'cold-tx-buffer', 'cold-rx-event', 'cold-txdone', 'cold-rx-pcie',
    'cold-pcie-tail', 'cold-inode', 'rro-lifetime', 'rro-native', 'rro-wire', 'rro-session',
    'gdma', 'tunnel-header', 'tunnel-packet'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    done = subprocess.run(list(map(str, args)), capture_output=True, timeout=180)
    assert done.returncode == 0, done.stderr.decode(errors='replace')[-4000:]
    return done.stdout


def verify_core_archive(core, objects):
    archive = core / 'libw1700k-npu.a'
    members = run(['ar', 't', archive]).decode().splitlines()
    assert len(members) == len(set(members)), 'Duplicate RV32 archive members'
    assert set(members) == set(objects), 'RV32 archive member set differs from normal objects'
    actual = {name: hashlib.sha256(run(['ar', 'p', archive, name])).hexdigest()
              for name in members}
    assert actual == objects, 'RV32 archive contains stale or different object bytes'
    return actual


def verify_core_objects(core):
    objects = {}
    for path in core.glob('*.o'):
        elf = ELFFile(io.BytesIO(path.read_bytes()))
        assert elf['e_machine'] == 'EM_RISCV' and elf.elfclass == 32
        assert elf.get_section_by_name('.text')['sh_size'] > 0
        objects[path.name] = sha(path)
    assert objects.keys() == CORE_OBJECT_NAMES, (
        'RV32 normal object set differs', sorted(CORE_OBJECT_NAMES - objects.keys()),
        sorted(objects.keys() - CORE_OBJECT_NAMES))
    return objects


def prop(path, node, name, kind='s', optional=False):
    done = subprocess.run(['fdtget', '-t', kind, str(path), node, name], capture_output=True, text=True)
    assert done.returncode == 0 or optional, done.stderr
    return done.stdout.strip() if done.returncode == 0 else None


def select_fit_configuration(image, image_types):
    """Resolve the W1700K sysupgrade profile, not an arbitrary image by type."""
    def reference(node, propname):
        raw = bytes(int(x, 16) for x in prop(image, node, propname, 'bx').split())
        if not re.fullmatch(rb'[A-Za-z0-9_-]+\0', raw):
            raise ValueError(f'{node}/{propname}: expected exactly one FIT node name')
        return raw[:-1].decode('ascii')

    parent = '/configurations'
    default = reference(parent, 'default')
    if default not in run(['fdtget', '-l', image, parent]).decode().splitlines():
        raise ValueError(f'Unknown default FIT configuration: {default}')
    node = parent + '/' + default
    properties = set(run(['fdtget', '-p', image, node]).decode().splitlines())
    if properties - {'description', 'compatible'} != {'kernel', 'fdt', 'loadables'}:
        raise ValueError(f'Unsupported W1700K sysupgrade configuration: {sorted(properties)}')
    selected = {'name': default}
    for key, role, kind in [('kernel', 'kernel', 'kernel'), ('fdt', 'fdt', 'flat_dt'),
                            ('loadables', 'rootfs', 'filesystem')]:
        name = reference(node, key)
        if image_types.get(name) != kind:
            raise ValueError(f'{node}/{key}: {name} does not reference a {kind} image')
        selected[role] = name
    return selected


def extract_fit_components(image, directory):
    names = run(['fdtget', '-l', image, '/images']).decode().splitlines()
    if len(names) != len(set(names)) or any(not re.fullmatch(r'[a-zA-Z0-9_-]+', n) for n in names):
        raise ValueError('Invalid FIT subimage names')
    types = {n: prop(image, '/images/' + n, 'type') for n in names}
    selected = select_fit_configuration(image, types)
    components, paths = [], {}
    for index, name in enumerate(names):
        node, output = '/images/' + name, directory / (name + '.bin')
        if output.exists() or output.is_symlink():
            raise FileExistsError(output)
        run(['dumpimage', '-T', 'flat_dt', '-p', index, '-o', output, image])
        hashes = []
        for child in run(['fdtget', '-l', image, node]).decode().splitlines():
            algorithm = prop(image, node + '/' + child, 'algo', optional=True)
            if algorithm not in ('sha1', 'sha256', 'md5'):
                continue
            expected = bytes(int(b, 16) for b in prop(image, node + '/' + child, 'value', 'bx').split())
            assert hashlib.new(algorithm, output.read_bytes()).digest() == expected
            hashes.append(dict(algorithm=algorithm, value=expected.hex()))
        assert hashes, name
        components.append(dict(name=name, type=types[name], sha256=sha(output), verified_hashes=hashes))
        paths[name] = output
    return selected, components, {role: paths[selected[role]] for role in ('kernel', 'fdt', 'rootfs')}


MODULE_NAMES = ('mt76.ko', 'mt76-connac-lib.ko', 'mt7996e.ko', 'airoha_npu.ko')
# The locked W1700K OpenWrt strip-kmod.sh profile: NO_RENAME=1, no KEEP_BUILD_ID or KEEP_SYMBOLS.
KMOD_OBJCOPY_ARGS = ('-R', '.comment', '-R', '.pdr', '-R', '.mdebug.abi32', '-R', '.gnu.attributes',
                     '-R', '.reginfo', '-R', '.MIPS.abiflags', '-R', '.note.GNU-stack',
                     '-x', '-G', '__this_module', '--strip-unneeded', '-R', '.note.gnu.build-id')


def bound_producer(root, receipt, expected_sha256):
    from npu_world_sources import linked_module_sources
    path = root / receipt
    if (not re.fullmatch(r'[0-9a-f]{64}', expected_sha256) or path.is_symlink()
            or not path.resolve(strict=True).is_relative_to(root.resolve()) or sha(path) != expected_sha256):
        raise ValueError('Module producer path or digest mismatch')
    linked = linked_module_sources(root, path)
    if linked['receipt_sha256'] != expected_sha256:
        raise ValueError('Module producer changed during verification')
    return linked


def producer_input_root(workspace, selected):
    if selected is None:
        return workspace
    # Both mounts name the same snapshot root, but only the workspace has
    # writable build/log overlays. A producer may pin the image being replaced.
    if (selected == workspace.resolve() or selected != selected.resolve(strict=True) or not selected.is_dir()
            or not selected.samefile(workspace) or any(not os.statvfs(path).f_flag & os.ST_RDONLY
                for path in (selected, selected / '.build/merged-openwrt', selected / '.local/merge-nonoc-20260923'))):
        raise ValueError('Producer view must be a read-only mount of the same source snapshot')
    for name in ('firmware/source-lock.json', 'firmware/build.config'):
        if sha(selected / name) != sha(workspace / name):
            raise ValueError(f'Producer view differs from the image workspace: {name}')
    return selected


def compare_packaged_modules(root, build, linked, packaged, scratch):
    from npu_world_sources import relative_file
    build = build.resolve(strict=True)
    config = build / '.config'
    config_hash = sha(root / 'firmware/build.config')
    text = config.read_text()
    lines = set(text.splitlines())
    versions = re.findall(r'^CONFIG_GCC_VERSION="([0-9]+(?:\.[0-9]+)+)"$', text, re.MULTILINE)
    required = {'CONFIG_KERNEL_KALLSYMS=y', 'CONFIG_TARGET_ARCH_PACKAGES="aarch64_cortex-a53"', 'CONFIG_TARGET_SUFFIX="musl"'}
    if (sha(config) != config_hash or len(versions) != 1 or not required <= lines
            or {'CONFIG_NO_STRIP=y', 'CONFIG_KERNEL_PROFILING=y'} & lines):
        raise ValueError('Unsupported or unlocked W1700K module packaging profile')
    staging = (build / 'staging_dir').resolve(strict=True)
    objcopy = (staging / f'toolchain-aarch64_cortex-a53_gcc-{versions[0]}_musl/bin/aarch64-openwrt-linux-musl-objcopy').resolve()
    if not staging.is_relative_to(build) or not objcopy.is_file() or not objcopy.is_relative_to(staging):
        raise ValueError('The configured OpenWrt AArch64 objcopy is required')
    tool_hash = sha(objcopy)
    artifacts = linked['artifacts']
    if (len(artifacts) != len(MODULE_NAMES) or {Path(k).name for k in artifacts} != set(MODULE_NAMES)
            or set(packaged) != set(MODULE_NAMES)):
        raise ValueError('Expected exactly the four selected kernel modules')
    modules = {}
    with tempfile.TemporaryDirectory(prefix='package-compare-', dir=scratch) as tmp:
        for relative, expected in sorted(artifacts.items()):
            source = relative_file(root, relative)
            if sha(source) != expected:
                raise ValueError(f'Producer artifact changed: {relative}')
            dest = Path(tmp) / source.name
            run([objcopy, *KMOD_OBJCOPY_ARGS, source, dest])
            normalized = sha(dest)
            modules[source.name] = dict(linked_sha256=expected, expected_packaged_sha256=normalized,
                                        actual_packaged_sha256=packaged[source.name],
                                        matches=normalized == packaged[source.name])
            if sha(source) != expected:
                raise ValueError(f'Producer artifact changed during comparison: {relative}')
    if sha(config) != config_hash or sha(objcopy) != tool_hash:
        raise ValueError('Packaging configuration or tool changed during comparison')
    mismatches = sorted(name for name, row in modules.items() if not row['matches'])
    return dict(matches=not mismatches, mismatches=mismatches, modules=modules,
                producer=linked['receipt'], producer_sha256=linked['receipt_sha256'],
                source_lock_sha256=linked['source_lock_sha256'], config_sha256=config_hash,
                profile='openwrt-w1700k-no-rename-no-build-id',
                objcopy=str(objcopy.relative_to(build)), objcopy_sha256=tool_hash,
                objcopy_args=list(KMOD_OBJCOPY_ARGS))


def board_identity(dtb):
    model, compatible = prop(dtb, '/', 'model'), prop(dtb, '/', 'compatible')
    assert model == 'Gemtek W1700K (OpenWrt U-Boot layout)'
    assert 'gemtek,w1700k-ubi' in compatible.split()
    return model, compatible


def compare_module_image(image, root, build, linked, scratch):
    """Check packaged bytes in an existing FIT without running a world build or boot."""
    image_hash = sha(image)
    kernel = json.loads((root / 'firmware/source-lock.json').read_bytes())['kernel']
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', kernel):
        raise ValueError('Unsupported target kernel version')
    with tempfile.TemporaryDirectory(prefix='fit-compare-', dir=scratch) as tmp:
        directory = Path(tmp)
        selected, components, paths = extract_fit_components(image, directory)
        model, compatible = board_identity(paths['fdt'])
        packaged = {name: hashlib.sha256(run(['unsquashfs', '-processors', '1', '-mem', '16M', '-cat',
                    paths['rootfs'], f'lib/modules/{kernel}/{name}'])).hexdigest() for name in MODULE_NAMES}
        binding = compare_packaged_modules(root, build, linked, packaged, directory)
    if sha(image) != image_hash:
        raise ValueError('FIT changed during inspection')
    return dict(matches=binding['matches'], image_sha256=image_hash, fit_configuration=selected,
                components=components, model=model, compatible=compatible, packaged_module_provenance=binding,
                full_image_verified=False, module_loaded=False, hardware=False)


def save_comparison(directory, result):
    with (directory / 'module-comparison.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')


def module(path):
    elf = ELFFile(io.BytesIO(path.read_bytes()))
    assert elf['e_machine'] == 'EM_AARCH64'
    info = elf.get_section_by_name('.modinfo').data().split(b'\0')
    assert b'vermagic=6.18.52 SMP mod_unload aarch64' in info
    table = elf.get_section_by_name('.symtab')
    defined = {s.name for s in table.iter_symbols() if s['st_shndx'] != 'SHN_UNDEF'}
    imports = {s.name for s in table.iter_symbols() if s['st_shndx'] == 'SHN_UNDEF'}
    return dict(path=str(path.relative_to(ROOT)), sha256=sha(path),
                info=[s.decode() for s in info if s.startswith((b'vermagic=', b'depends='))],
                npu_definitions=sorted(s for s in defined if 'npu' in s),
                npu_imports=sorted(s for s in imports if 'npu' in s)), defined, imports


def verify_control_ownership(name, defined, imports):
    control = {'npu_linux_control_init', 'npu_linux_control_exchange',
               'npu_linux_control_close', 'npu_linux_control_snapshot',
               'npu_client_v2_request', 'npu_client_v2_complete',
               'npu_linux_control_cold_exchange', 'npu_cold_client_request', 'npu_cold_client_complete'}
    if name == 'mt76.ko':
        assert not control & defined, 'Control state belongs to the provider, not each consumer'
        assert 'airoha_npu_wlan_control' not in imports
    if name == 'airoha_npu.ko':
        assert control | {'airoha_npu_wlan_control'} <= defined
        assert not control & imports, 'The provider must link its own control implementation'


ROOTFS_BOOT_MODES = {
    '':'drwxr-xr-x', 'bin':'drwxr-xr-x', 'etc':'drwxr-xr-x',
    'sbin':'drwxr-xr-x', 'usr':'drwxr-xr-x', 'usr/libexec':'drwxr-xr-x',
    'bin/busybox':'-rwxr-xr-x', 'sbin/init':'-rwxr-xr-x',
    'etc/passwd':'-rw-r--r--', 'etc/group':'-rw-r--r--', 'etc/shadow':'-rw-------',
    'usr/libexec/w1700k-release-helper':'-rwxr-xr-x',
}


def rootfs_owner_table(listing):
    rows = {}
    for line in listing.splitlines():
        match = re.fullmatch(r'([d-][rwxstST-]{9})\s+(\d+)/(\d+)\s+\d+\s+'
            r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+squashfs-root(?:/(\S+))?', line)
        assert match, ('invalid-numeric-rootfs-listing', line)
        mode,uid,gid,name = match[1],int(match[2]),int(match[3]),match[4] or ''
        assert name in ROOTFS_BOOT_MODES and name not in rows, ('unexpected-rootfs-ownership-entry',name)
        assert mode == ROOTFS_BOOT_MODES[name] and (uid,gid) == (0,0), ('rootfs-boot-owner-or-mode',name,mode,uid,gid)
        rows[name] = dict(mode=mode,uid=uid,gid=gid)
    assert rows.keys() == ROOTFS_BOOT_MODES.keys(), ('missing-rootfs-ownership-entry',sorted(ROOTFS_BOOT_MODES.keys() - rows.keys()))
    return rows


def verify_rootfs_ownership(rootfs):
    leaves = [name for name,mode in ROOTFS_BOOT_MODES.items() if mode.startswith('-')]
    listing = run(['unsquashfs','-lln','-UTC',rootfs,*leaves]).decode('utf-8')
    return rootfs_owner_table(listing)


def board_configuration(dtb):
    regions = {'npu-binary@84000000': (0x84000000, 0xa00000),
               'npu-pkt@8a000000': (0x8a000000, 0x2c00000),
               'npu-txpkt@8cc00000': (0x8cc00000, 0x4000000),
               'npu-txbufid@90c00000': (0x90c00000, 0xe000),
               'npu-ba@90c0e000': (0x90c0e000, 0x200000)}
    handles = []
    for name, (address, size) in regions.items():
        node = '/reserved-memory/' + name
        cells = [int(n, 16) for n in prop(dtb, node, 'reg', 'x').split()]
        assert cells == [0, address, 0, size], (name, cells)
        assert prop(dtb, node, 'no-map', 'x') == ''
        handles.append(int(prop(dtb, node, 'phandle', 'x'), 16))
    npu = '/soc/npu@1e900000'
    assert prop(dtb, npu, 'status') == 'okay'
    assert prop(dtb, npu, 'memory-region-names').split() == ['binary', 'pkt', 'tx-pkt', 'tx-bufid', 'ba']
    assert [int(n, 16) for n in prop(dtb, npu, 'memory-region', 'x').split()] == handles
    frequencies = []
    for name in run(['fdtget', '-l', dtb, '/opp-table']).decode().splitlines():
        raw = bytes(int(n, 16) for n in prop(dtb, '/opp-table/' + name, 'opp-hz', 'bx').split())
        assert len(raw) == 8
        frequencies.append(int.from_bytes(raw, 'big'))
    assert sorted(frequencies) == list(range(500000000, 1200000001, 50000000))
    return dict(npu_regions=regions, cpu_opp_hz=sorted(frequencies),
                scope='Device-tree configuration only; not measured CPU clocks or physical memory ownership.')


def main():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', default='image-verification')
    parser.add_argument('--module-receipt', type=Path, help='Source-bound four-module producer')
    parser.add_argument('--expected-producer-sha256', help='Independently pinned SHA256 of --module-receipt')
    parser.add_argument('--frozen-producer-root', type=Path,
                        help='Read producer inputs through a read-only snapshot view outside the build overlays')
    parser.add_argument('--modules-only-image', type=Path, metavar='FIT',
                        help='Compare the named FIT to the producer without requiring a complete world build')
    args = parser.parse_args()
    if not __debug__:
        parser.error('Image verification requires Python assertions enabled (no -O or PYTHONOPTIMIZE)')
    if (args.module_receipt is None) != (args.expected_producer_sha256 is None):
        parser.error('Use --module-receipt and --expected-producer-sha256 together')
    if args.modules_only_image is not None and args.module_receipt is None:
        parser.error('--modules-only-image requires a pinned module producer')
    if args.frozen_producer_root and (not args.module_receipt or args.module_receipt.is_absolute()):
        parser.error('--frozen-producer-root requires a snapshot-relative pinned module receipt')
    producer_root = producer_input_root(ROOT, args.frozen_producer_root)
    linked = bound_producer(producer_root, args.module_receipt, args.expected_producer_sha256) if args.module_receipt else None
    assert re.fullmatch(r'[a-z0-9][a-z0-9-]*', args.name), 'Invalid receipt name'
    OUT = OUT.parent / args.name
    assert not OUT.exists(), 'Keep prior verification; use a fresh result directory for a changed image.'
    OUT.mkdir(parents=True)
    if args.modules_only_image is not None:
        result = compare_module_image(args.modules_only_image, producer_root, BUILD, linked, OUT)
        save_comparison(OUT, result)
        print(json.dumps(dict(matches=result['matches'], mismatches=result['packaged_module_provenance']['mismatches'],
                              receipt=str(OUT / 'module-comparison.json'))))
        return 0 if result['matches'] else 1
    image = BUILD / 'bin/targets/airoha/an7581/openwrt-airoha-an7581-gemtek_w1700k-ubi-squashfs-sysupgrade.itb'
    assert image.is_file()
    image_hash = sha(image)
    (OUT / 'fit.txt').write_bytes(run(['dumpimage', '-l', image]))
    selected, components, paths = extract_fit_components(image, OUT)
    dtb, rootfs, kernel = paths['fdt'], paths['rootfs'], paths['kernel']
    rootfs_owners = verify_rootfs_ownership(rootfs)
    model, compatible = board_identity(dtb)
    board = board_configuration(dtb)
    (OUT / 'board.dts').write_bytes(run(['dtc', '-I', 'dtb', '-O', 'dts', dtb]))
    built_kernel = BUILD / 'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/linux-6.18.52/arch/arm64/boot/Image'
    assert gzip.decompress(kernel.read_bytes()) == built_kernel.read_bytes()
    root = OUT / 'rootfs'
    result = subprocess.run(['unsquashfs', '-no-xattrs', '-no-progress', '-d', str(root), str(rootfs),
                             'etc', 'lib/modules', 'lib/firmware', 'lib/apk', 'usr/libexec',
                             'usr/sbin', 'www/cgi-bin'], capture_output=True, text=True, timeout=180)
    (OUT / 'extract.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    packages = {}
    for block in (root / 'lib/apk/db/installed').read_text().split('\n\n'):
        fields = dict(line.split(':', 1) for line in block.splitlines() if line.startswith(('P:', 'V:')))
        if 'P' in fields:
            assert fields['P'] not in packages
            packages[fields['P']] = fields['V']
    required = ('kmod-airoha-npu', 'kmod-mt7996e', 'wpad-openssl', 'luci-ssl-openssl',
                'sqm-scripts', 'kmod-sched-cake', 'adblock', 'softethervpn5-server',
                'w1700k-npu-status', 'luci-app-w1700k-npu', 'luci-app-sqm',
                'luci-app-w1700k-softether-server', 'luci-app-airoha-flowsense',
                'luci-app-airoha-npu', 'luci-app-w1700k-fancontrol', 'luci-app-mlo', 'luci-app-wifi7')
    assert set(required) <= packages.keys(), sorted(set(required) - packages.keys())
    assert packages['kernel'].startswith('6.18.52')
    modules = {}
    for name in MODULE_NAMES:
        path = root / 'lib/modules/6.18.52' / name
        row, defined, imports = module(path)
        modules[name] = row
        verify_control_ownership(name, defined, imports)
        if name == 'mt7996e.ko':
            assert 'mt76_npu_init' in imports
    binding = None
    if linked is not None:
        binding = compare_packaged_modules(producer_root, BUILD, linked, {n: m['sha256'] for n, m in modules.items()}, OUT)
        if not binding['matches']:
            save_comparison(OUT, dict(matches=False, image_sha256=image_hash, fit_configuration=selected,
                                      packaged_module_provenance=binding, full_image_verified=False, hardware=False))
            raise ValueError(f"Packaged modules differ from the qualified producer: {binding['mismatches']}")
    module_paths = list((root / 'lib/modules').glob('*/*.ko'))
    assert all(p.parent.name == '6.18.52' for p in module_paths)
    for path in module_paths:
        module(path)
    helper = root / 'usr/libexec/w1700k-release-helper'
    assert sha(helper) == sha(BUILD / 'files/usr/libexec/w1700k-release-helper')
    assert helper.stat().st_mode & 0o111 and not helper.stat().st_mode & 0o022
    fw = root / 'lib/firmware/airoha'
    pair_manifest = json.loads((fw / 'w1700k-npu-pair.json').read_bytes())
    npu_image.validate((fw / 'en7581_MT7996_npu_rv32.bin').read_bytes(),
                       (fw / 'en7581_MT7996_npu_data.bin').read_bytes(), pair_manifest)
    staged = BUILD / 'bin/npu-checked'
    for name in ('en7581_MT7996_npu_rv32.bin', 'en7581_MT7996_npu_data.bin', 'w1700k-npu-pair.json'):
        assert sha(fw / name) == sha(staged / name)
    for name, digest in pair_manifest['inputs'].items():
        source = (ROOT / name).resolve()
        assert source.is_relative_to(ROOT) and sha(source) == digest, ('changed-pair-input', name)
    wifi_sources = BUILD / 'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/mt76-2026.09.01~01367e60/firmware/mt7996'
    wifi_firmware = {}
    for path in (root / 'lib/firmware/mediatek/mt7996').glob('*.bin'):
        assert sha(path) == sha(wifi_sources / path.name)
        wifi_firmware[path.name] = sha(path)
    assert {'mt7996_wm.bin', 'mt7996_wa.bin', 'mt7996_dsp.bin', 'mt7996_rom_patch.bin'} <= wifi_firmware.keys()
    core = BUILD / 'bin/npu'
    core_objects = verify_core_objects(core)
    archive = core / 'libw1700k-npu.a'
    archive_members = verify_core_archive(core, core_objects)
    metadata = OUT / 'fwtool.json'
    run([BUILD / 'staging_dir/host/bin/fwtool', '-i', metadata, image])
    data = json.loads(metadata.read_text())
    assert str(data['compat_version']) == '2.0'
    assert 'gemtek,w1700k-ubi' in data['new_supported_devices']
    assert data['version']['revision'] == 'r36536-merged-288d79449f'
    assert (root / 'etc/openwrt_version').read_text().strip() == 'r36536-merged-288d79449f'
    assert sha(image) == image_hash
    receipt = dict(passed=True, image=str(image.relative_to(ROOT)), sha256=image_hash,
                   bytes=image.stat().st_size, components=components, model=model,
                   compatible=compatible, metadata=data, packages=packages, fit_configuration=selected,
                   packaged_module_provenance=binding, pinned_module_bytes_verified=binding is not None,
                   rootfs_numeric_boot_ownership=rootfs_owners,
                   board_configuration=board,
                   wifi_firmware_sha256=wifi_firmware,
                   rv32_core=dict(objects=core_objects, archive_sha256=sha(archive),
                                  archive_members=archive_members,
                                  bootable_replacement=False),
                   checked_npu_pair=dict(code=pair_manifest['code'], data=pair_manifest['data'],
                                         manifest_sha256=sha(fw / 'w1700k-npu-pair.json'),
                                         hooks=len(pair_manifest['hooks']), loader_provisioned=False,
                                         physical_acceptance=False),
                   selected_modules=modules, all_module_abi_checks=len(module_paths),
                   source_lock_sha256=sha(ROOT / 'firmware/source-lock.json'),
                   limits=['Offline image integrity/package/ABI checks only, not boot, throughput or physical recovery.',
                           'The FIT-declared default is inspected, not a bootloader override or signature trust decision.',
                           'Without a pinned producer, module ABI checks do not identify the qualified module bytes.',
                           'Linux V2 client and once-owned initial setup are compiled into the provider; full strict setup and physical cold-lifetime proof remain incomplete.',
                           'The checked experimental raw CODE/DATA pair is packaged; physical cold containment,strict full setup and retirement remain incomplete.'])
    path = OUT / 'result.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(passed=True, image_sha256=image_hash, bytes=receipt['bytes'],
                         packages=len(packages), module_abi_checks=len(module_paths),
                         pinned_module_bytes_verified=receipt['pinned_module_bytes_verified'], receipt=str(path))))


if __name__ == '__main__':
    raise SystemExit(main())
