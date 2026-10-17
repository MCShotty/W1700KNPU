#!/usr/bin/env python3
"""Link current mt76 consumers against an isolated current provider;never load."""
import argparse
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

from elftools.elf.elffile import ELFFile

from test_current_provider_module import ROOT, WORK, DRIVER, PUBLIC, digest, inventory, module


def symvers(text):
    rows = {}
    for line in text.splitlines():
        fields = line.split('\t')
        assert len(fields) == 5, ('symvers-fields', line)
        crc, name, owner, kind, namespace = fields
        assert re.fullmatch(r'0x[0-9a-fA-F]{8}', crc)
        assert re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name)
        assert owner and not Path(owner).is_absolute() and '..' not in Path(owner).parts
        assert kind in {'EXPORT_SYMBOL', 'EXPORT_SYMBOL_GPL'}
        assert all(32 <= ord(character) < 127 for character in namespace), ('invalid-namespace-bytes', name)
        assert name not in rows, ('duplicate-export', name)
        rows[name] = fields
    assert rows, 'empty-symbol-index'
    return rows


def checked_union(*indices):
    result = {}
    for index in indices:
        assert not result.keys() & index.keys(), ('overlapping-export-indices', result.keys() & index.keys())
        result.update(index)
    return result


def object_symbols(path):
    binary = ELFFile(io.BytesIO(path.read_bytes()))
    assert binary['e_machine'] == 'EM_AARCH64' and binary['e_type'] == 'ET_REL'
    symbols = list(binary.get_section_by_name('.symtab').iter_symbols())
    exports = set()
    for entry in symbols:
        if entry.name.startswith('__export_symbol_'):
            assert binary.get_section(entry['st_shndx']).name == '.export_symbol'
            exports.add(entry.name.removeprefix('__export_symbol_'))
        elif entry.name.startswith('__ksymtab_') and entry.name != '__ksymtab_strings':
            assert binary.get_section(entry['st_shndx']).name in {'__ksymtab', '__ksymtab_gpl'}
            exports.add(entry.name.removeprefix('__ksymtab_'))
    return dict(exports=exports,
                imports={entry.name for entry in symbols if entry.name and entry['st_shndx'] == 'SHN_UNDEF'},
                defined={entry.name for entry in symbols if entry.name and entry['st_shndx'] != 'SHN_UNDEF'})


def dependency_rows(missing, original):
    assert missing <= original.keys(), ('unknown-compiled-imports', missing - original.keys())
    owners = {original[name][2] for name in missing}
    assert not any(Path(owner).name in {'vmlinux', 'airoha_npu'} for owner in owners), 'stale-provider-or-builtin-index'
    return {name: row for name, row in original.items() if row[2] in owners}


def source_copy(upstream, merged, patch, directory):
    shutil.copytree(upstream, directory, ignore=shutil.ignore_patterns('.git', '*.orig', '*.rej'))
    process = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(patch)],
        cwd=directory, capture_output=True, text=True, timeout=180)
    assert process.returncode == 0 and not list(directory.rglob('*.rej')), process.stdout + process.stderr
    selected = re.findall(r'^\+\+\+ b/([^\n]+)$', patch.read_text(), re.M)
    assert len(selected) == len(set(selected)) and 'mt7996/mmio.c' in selected
    current = inventory(directory)
    expected = inventory(merged)
    for name, identity in current.items():
        assert identity == expected[name], ('mt76-patch-result-drift', name)
    assert set(expected) - set(current) <= {name for name in expected if name.startswith('w1700k/')}, 'unexported-source'
    assert not any('w1700k/' in path.read_text() for path in directory.rglob('*')
                   if path.is_file() and (path.suffix in {'.c', '.h'} or path.name == 'Makefile'))
    return selected, current, process.stdout + process.stderr


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--provider-receipt', type=Path, required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    directory = ROOT / '.local/npu-current-mt76-modules' / args.name
    assert not directory.exists()
    directory.mkdir(parents=True)
    inputs = {}
    def add(path, expected=None):
        path = path.resolve()
        assert path.is_relative_to(ROOT)
        actual = digest(path)
        assert expected is None or actual == expected, ('mt76-link-input-drift', str(path))
        name = str(path.relative_to(ROOT))
        assert name not in inputs or inputs[name] == actual
        inputs[name] = actual
    def save(name, value):
        path = directory / name
        with path.open('x') as stream: stream.write(json.dumps(value, indent=2) + '\n')
        return path

    add(Path(__file__))
    add(Path(__file__).with_name('test_current_provider_module.py'))
    receipt_path = args.provider_receipt.resolve()
    add(receipt_path)
    provider = json.loads(receipt_path.read_bytes())
    assert provider['passed'] is True and provider['module_loaded'] is False
    for name, expected in {**provider['inputs'], **provider['artifacts']}.items(): add(ROOT / name, expected)
    lock_path = ROOT / 'firmware/source-lock.json'
    add(lock_path, provider['source_lock_sha256'])
    lock = json.loads(lock_path.read_bytes())
    release = lock['kernel']
    assert re.fullmatch(r'\d+\.\d+\.\d+', release)
    build = (ROOT / lock['build_directory']).resolve()
    assert build.is_relative_to(ROOT / '.build')
    prepared = build / 'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581'
    kernel = receipt_path.parent / ('linux-' + release)
    assert module(kernel / DRIVER / 'airoha_npu.ko') == provider['module']
    assert '# CONFIG_MODVERSIONS is not set\n' in (kernel / '.config').read_text()
    assert 'CONFIG_NET_AIROHA_NPU=m\n' in (kernel / '.config').read_text()
    original_kernel = prepared / ('linux-' + release)
    original_before = json.loads((receipt_path.parent / 'prepared-before.json').read_bytes())
    assert inventory(original_kernel) == original_before
    original_mt76 = prepared / 'mt76-2026.09.01~01367e60'
    mt76_before = inventory(original_mt76)
    save('prepared-mt76-before.json', mt76_before)
    fit = build / 'bin/targets/airoha/an7581/openwrt-airoha-an7581-gemtek_w1700k-ubi-squashfs-sysupgrade.itb'
    add(fit)
    add(build / '.config')
    openwrt_config = (build / '.config').read_text()
    assert 'CONFIG_MT76_AIROHA_NPU=y\n' in openwrt_config
    assert 'CONFIG_PACKAGE_MAC80211_MESH=y\n' in openwrt_config
    assert '# CONFIG_PACKAGE_CFG80211_TESTMODE is not set\n' in openwrt_config

    patch_relative = 'package/kernel/mt76/patches/900-w1700k-integrated-npu.patch'
    patch = ROOT / 'firmware/overlay/openwrt' / patch_relative
    row = next(row for row in lock['openwrt']['changed_files'] if row['path'] == patch_relative)
    add(patch, row['sha256'])
    add(build / patch_relative, row['sha256'])
    add(build / 'package/kernel/mt76/Makefile')
    source = directory / 'mt76'
    selected, source_before, patch_log = source_copy(WORK / 'mt76-upstream', WORK / 'mt76-merged', patch, source)
    with (directory / 'patch.log').open('x') as stream: stream.write(patch_log)
    save('source-before.json', source_before)
    print(json.dumps(dict(phase='copy-current-linked-kernel', changed_mt76_files=len(selected))), flush=True)
    kernel_before = inventory(kernel)
    save('provider-kernel-before.json', kernel_before)
    shadow = directory / ('linux-' + release)
    shutil.copytree(kernel, shadow, symlinks=True)
    assert inventory(shadow) == kernel_before
    assert (shadow / DRIVER / 'airoha_npu.ko').stat().st_ino != (kernel / DRIVER / 'airoha_npu.ko').stat().st_ino
    assert digest(shadow / PUBLIC) == digest(original_kernel / PUBLIC)

    base_index = symvers((shadow / 'Module.symvers').read_text())
    original_index = symvers((original_kernel / 'Module.symvers').read_text())
    mac_path = prepared / 'symvers/mac80211.symvers'
    add(mac_path)
    mac_index = symvers(mac_path.read_text())
    module_dir = build / ('staging_dir/target-aarch64_cortex-a53_musl/root-airoha/lib/modules/' + release)
    dependencies = {}
    for name in ('mac80211', 'cfg80211', 'compat'):
        path = module_dir / (name + '.ko')
        add(path)
        data = module(path)
        assert data['vermagic'] == provider['module']['vermagic'], ('dependency-vermagic', name)
        rows = {key: row for key, row in mac_index.items() if Path(row[2]).name == name}
        assert set(rows) == set(data['exports']), ('dependency-export-drift', name)
        dependencies[name] = data
    mac_copy = directory / 'mac80211.symvers'
    shutil.copy2(mac_path, mac_copy)
    available = checked_union(base_index, mac_index)
    assert {key for key in base_index if Path(base_index[key][2]).name == 'airoha_npu'} == set(provider['module']['exports'])

    include = build / 'staging_dir/target-aarch64_cortex-a53_musl/usr/include'
    header_before = {}
    headers = directory / 'headers'
    headers.mkdir()
    for name in ('mac80211', 'mac80211-backport'):
        header_before[name] = inventory(include / name)
        shutil.copytree(include / name, headers / name, symlinks=True)
        assert inventory(headers / name) == header_before[name]
    save('backport-headers-before.json', header_before)
    prefix = build / 'staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin/aarch64-openwrt-linux-musl-'
    compiler = Path(str(prefix) + 'gcc')
    add(compiler)
    environment = dict(os.environ, STAGING_DIR=str(build / 'staging_dir/target-aarch64_cortex-a53_musl'),
        PATH=str(compiler.parent) + ':' + str(build / 'staging_dir/host/bin') + ':/usr/bin:/bin',
        LANG='C', LC_ALL='C', TZ='UTC')
    environment.pop('MAKEFLAGS', None)
    environment.pop('MFLAGS', None)
    version = subprocess.check_output([str(compiler), '--version'], env=environment, text=True).splitlines()[0]
    assert version == provider['compiler']
    gcc_include = subprocess.check_output([str(compiler), '-print-file-name=include'], env=environment, text=True).strip()
    flags = ['-nostdinc', '-isystem', gcc_include, '-I' + str(source)]
    for name in ('mac80211-backport/uapi', 'mac80211-backport', 'mac80211/uapi', 'mac80211'):
        flags.append('-I' + str(headers / name))
    flags += ['-include', 'backport/autoconf.h', '-include', 'backport/backport.h',
              '-DCONFIG_MAC80211_MESH', '-DCONFIG_MT76_NPU', '-DCONFIG_MT7996_NPU']
    common = ['make', '-C', str(shadow), '-j2', 'M=' + str(source), 'ARCH=arm64',
        'CROSS_COMPILE=' + str(prefix), 'KERNELRELEASE=' + release, 'KBUILD_BUILD_USER=', 'KBUILD_BUILD_HOST=',
        'KBUILD_BUILD_VERSION=0', next(item for item in provider['command'] if item.startswith('KBUILD_BUILD_TIMESTAMP=')),
        'KBUILD_HAVE_NLS=no', 'KBUILD_HOSTLDFLAGS=-L' + str(build / 'staging_dir/host/lib'),
        'KCFLAGS=-fno-caller-saves -fstack-usage', 'CONFIG_MT76_CONNAC_LIB=m', 'CONFIG_MT7996E=m',
        'CONFIG_MT76_NPU=y', 'CONFIG_MT7996_NPU=y', 'NOSTDINC_FLAGS=' + ' '.join(flags), 'V=0']
    deadline = time.monotonic() + 1800
    def make(command, name):
        with (directory / name).open('x') as stream:
            result = subprocess.run(command, cwd=ROOT, env=environment, stdin=subprocess.DEVNULL,
                stdout=stream, stderr=subprocess.STDOUT, timeout=max(1, deadline - time.monotonic()))
        assert result.returncode == 0, (directory / name).read_text()[-6000:]
    objects = ('mt76.o', 'mt76-connac-lib.o', 'mt7996/mt7996e.o')
    compile_command = common + ['KBUILD_EXTRA_SYMBOLS=' + str(mac_copy), *objects]
    print(json.dumps(dict(phase='compile-current-mt76-consumers', jobs=2)), flush=True)
    make(compile_command, 'compile.log')
    combined = {name: object_symbols(source / name) for name in objects}
    own_exports = set().union(*(data['exports'] for data in combined.values()))
    imports = set().union(*(data['imports'] for data in combined.values()))
    metadata = {'__this_module', '_GLOBAL_OFFSET_TABLE_'}
    modpost = shadow / 'scripts/mod/modpost.c'
    add(modpost)
    assert '__visible struct module __this_module' in modpost.read_text()
    extra = dependency_rows(imports - available.keys() - own_exports - metadata, original_index)
    for owner in sorted({row[2] for row in extra.values()}):
        name = Path(owner).name
        path = module_dir / (name + '.ko')
        add(path)
        data = module(path)
        assert data['vermagic'] == provider['module']['vermagic'], ('kernel-dependency-vermagic', name)
        assert set(data['exports']) == {key for key, row in extra.items() if row[2] == owner}, ('kernel-dependency-exports', name)
        dependencies[name] = data
    extra_path = directory / 'kernel-module-dependencies.symvers'
    with extra_path.open('x') as stream: stream.write(''.join('\t'.join(row) + '\n' for row in extra.values()))
    available = checked_union(available, extra)
    command = common + ['KBUILD_EXTRA_SYMBOLS=' + str(mac_copy) + ' ' + str(extra_path), 'modules']
    print(json.dumps(dict(phase='link-current-mt76-consumers', dependencies=sorted(dependencies), jobs=2)), flush=True)
    make(command, 'build.log')
    linked = {name: module(source / name) for name in ('mt76.ko', 'mt76-connac-lib.ko', 'mt7996/mt7996e.ko')}
    own = symvers((source / 'Module.symvers').read_text())
    available = checked_union(available, own)
    assert set(own) == set().union(*(set(data['exports']) for data in linked.values()))
    for name, data in linked.items():
        assert data['vermagic'] == provider['module']['vermagic']
        assert set(data['imports']) <= available.keys(), ('unavailable-linked-import', name, set(data['imports']) - available.keys())
        assert data['sha256'] != digest(module_dir / Path(name).name), ('old-module-reused', name)
        assert '__this_module' in object_symbols(source / name)['defined']
        assert not set(data['imports']) & metadata, ('unresolved-module-metadata', name)
    assert {'airoha_npu_get', 'airoha_npu_put', 'airoha_ppe_get_dev', 'airoha_ppe_put_dev'} <= set(linked['mt76.ko']['imports'])
    npu_edges = {name for name in linked['mt7996/mt7996e.ko']['imports'] if name.startswith('mt76_npu_')}
    assert npu_edges and npu_edges <= set(linked['mt76.ko']['exports'])
    assert module(shadow / DRIVER / 'airoha_npu.ko') == provider['module']
    assert digest(shadow / 'vmlinux') == kernel_before['vmlinux']['sha256']
    for name in ('.config', 'include/generated/autoconf.h', 'include/generated/utsrelease.h'):
        assert digest(shadow / name) == digest(kernel / name), ('consumer-config-drift', name)
    source_after = inventory(source)
    for name, expected in source_before.items():
        assert source_after.get(name) == expected, ('compiled-source-drift', name)
    assert inventory(kernel) == kernel_before and inventory(original_kernel) == original_before
    assert inventory(original_mt76) == mt76_before
    for name, expected in header_before.items(): assert inventory(include / name) == expected
    for name, expected in inputs.items(): assert digest(ROOT / name) == expected, ('consumer-input-drift', name)
    artifacts = {str(path.relative_to(ROOT)): digest(path) for path in directory.glob('*.json')}
    for path in (directory / 'compile.log', directory / 'build.log', directory / 'patch.log', mac_copy, extra_path, source / 'Module.symvers'):
        artifacts[str(path.relative_to(ROOT))] = digest(path)
    for name in linked: artifacts[str((source / name).relative_to(ROOT))] = linked[name]['sha256']
    result = dict(passed=True, scope='current-provider-mt76-unloaded-module-link-only',
        source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        source_lock_sha256=provider['source_lock_sha256'], inputs=inputs, artifacts=artifacts,
        command=command, compile_command=compile_command,
        provider=provider['module'], modules=linked, dependencies=dependencies, changed_mt76_files=len(selected),
        mt7996e_to_mt76_npu_exports=sorted(npu_edges), symbol_indices_are_actual_build_rows=True,
        kernel_dependency_rows=len(extra), metadata_symbols_resolved_in_final_modules=True,
        original_kernel_entries=len(original_before), original_mt76_entries=len(mt76_before),
        producing_provider_kernel_entries=len(kernel_before), protected_originals_unchanged=True,
        module_loaded=False, vmlinux_relinked=False, world_build=False, image_changed=False,
        native_cold_qualified=False, complete_IRQ_contract=False, hardware=False,
        limits=['Actual final module links with pinned configuration/defines/backports;not a full OpenWrt world build.',
                'Uses prebuilt backport/kernel dependencies and existing vmlinux,not freshly rebuilt dependencies.',
                'Dependencies are selected from actual combined-object imports and original module index;no fabricated CRCs.',
                'Host compiler/runtime and toolchain are external;not a hermetic environment.',
                'Symbol/metadata checks do not establish load,concurrency,physical DMA,IRQ/drain or client behavior.'])
    target = save('result.json', result)
    print(json.dumps(dict(passed=True, modules=3, npu_imports=len(npu_edges), originals_unchanged=True, sha256=digest(target))), flush=True)


if __name__ == '__main__': main()
