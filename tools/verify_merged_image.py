#!/usr/bin/env python3
"""Inspect the built FIT, packages and module ABI without executing firmware."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / '.build/merged-openwrt'
OUT = ROOT / '.local/merge-nonoc-20260923/image-verification'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    done = subprocess.run(list(map(str, args)), capture_output=True, timeout=180)
    assert done.returncode == 0, done.stderr.decode(errors='replace')[-4000:]
    return done.stdout


def prop(path, node, name, kind='s', optional=False):
    done = subprocess.run(['fdtget', '-t', kind, str(path), node, name], capture_output=True, text=True)
    assert done.returncode == 0 or optional, done.stderr
    return done.stdout.strip() if done.returncode == 0 else None


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
    args = parser.parse_args()
    assert re.fullmatch(r'[a-z0-9][a-z0-9-]*', args.name), 'Invalid receipt name'
    OUT = OUT.parent / args.name
    assert not OUT.exists(), 'Keep prior verification; use a fresh result directory for a changed image.'
    OUT.mkdir(parents=True)
    image = BUILD / 'bin/targets/airoha/an7581/openwrt-airoha-an7581-gemtek_w1700k-ubi-squashfs-sysupgrade.itb'
    assert image.is_file()
    image_hash = sha(image)
    (OUT / 'fit.txt').write_bytes(run(['dumpimage', '-l', image]))
    names = run(['fdtget', '-l', image, '/images']).decode().splitlines()
    components = []
    dtb = rootfs = kernel = None
    for index, name in enumerate(names):
        assert re.fullmatch('[a-zA-Z0-9_-]+', name)
        node, output = '/images/' + name, OUT / (name + '.bin')
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
        kind = prop(image, node, 'type')
        components.append(dict(name=name, type=kind, sha256=sha(output), verified_hashes=hashes))
        if kind == 'flat_dt': dtb = output
        if kind == 'filesystem': rootfs = output
        if kind == 'kernel': kernel = output
    assert dtb and rootfs and kernel
    model, compatible = prop(dtb, '/', 'model'), prop(dtb, '/', 'compatible')
    assert model == 'Gemtek W1700K (OpenWrt U-Boot layout)'
    assert 'gemtek,w1700k-ubi' in compatible.split()
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
    for name in ('mt76.ko', 'mt76-connac-lib.ko', 'mt7996e.ko', 'airoha_npu.ko'):
        path = root / 'lib/modules/6.18.52' / name
        row, defined, imports = module(path)
        modules[name] = row
        if name == 'mt76.ko':
            assert {'npu_linux_control_init', 'npu_linux_control_exchange', 'npu_linux_control_close'} <= defined
            assert 'airoha_npu_wlan_control' in imports
        if name == 'airoha_npu.ko':
            assert 'airoha_npu_wlan_control' in defined
        if name == 'mt7996e.ko':
            assert 'mt76_npu_init' in imports
    module_paths = list((root / 'lib/modules').glob('*/*.ko'))
    assert all(p.parent.name == '6.18.52' for p in module_paths)
    for path in module_paths:
        module(path)
    helper = root / 'usr/libexec/w1700k-release-helper'
    assert sha(helper) == sha(BUILD / 'files/usr/libexec/w1700k-release-helper')
    assert helper.stat().st_mode & 0o111 and not helper.stat().st_mode & 0o022
    fw = root / 'lib/firmware/airoha'
    assert sha(fw / 'en7581_MT7996_npu_rv32.bin') == 'e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643'
    assert sha(fw / 'en7581_MT7996_npu_data.bin') == '61a75afb052feed2ceb2f3023e16f50317c05c78f9c8e564bf01924ce39c7ec1'
    wifi_sources = BUILD / 'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/mt76-2026.09.01~01367e60/firmware/mt7996'
    wifi_firmware = {}
    for path in (root / 'lib/firmware/mediatek/mt7996').glob('*.bin'):
        assert sha(path) == sha(wifi_sources / path.name)
        wifi_firmware[path.name] = sha(path)
    assert {'mt7996_wm.bin', 'mt7996_wa.bin', 'mt7996_dsp.bin', 'mt7996_rom_patch.bin'} <= wifi_firmware.keys()
    core = BUILD / 'bin/npu'
    core_objects = {}
    for path in core.glob('*.o'):
        elf = ELFFile(io.BytesIO(path.read_bytes()))
        assert elf['e_machine'] == 'EM_RISCV' and elf.elfclass == 32
        assert elf.get_section_by_name('.text')['sh_size'] > 0
        core_objects[path.name] = sha(path)
    assert set(core_objects) == {name + '.o' for name in (
        'barrier', 'admission', 'control-v2', 'bootstrap', 'bootstrap-v2',
        'startup', 'allocator', 'gdma', 'tunnel-header', 'tunnel-packet')}
    archive = core / 'libw1700k-npu.a'
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
                   compatible=compatible, metadata=data, packages=packages,
                   board_configuration=board,
                   wifi_firmware_sha256=wifi_firmware,
                   rv32_core=dict(objects=core_objects, archive_sha256=sha(archive),
                                  bootable_replacement=False),
                   selected_modules=modules, all_module_abi_checks=len(module_paths),
                   source_lock_sha256=sha(ROOT / 'firmware/source-lock.json'),
                   limits=['Offline image integrity/package/ABI checks only, not boot, throughput or physical recovery.',
                           'Linux V2 client is compiled into mt76, but production caller/cold-loader wiring remains incomplete.',
                           'The supplied NPU firmware remains the inspected legacy binary; no emulator image is substituted.'])
    path = OUT / 'result.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(passed=True, image_sha256=image_hash, bytes=receipt['bytes'],
                         packages=len(packages), module_abi_checks=len(module_paths), receipt=str(path))))


if __name__ == '__main__':
    main()
