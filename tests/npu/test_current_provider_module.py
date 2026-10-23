#!/usr/bin/env python3
"""Link the current provider in an independent pinned kernel;never load it."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '.local/merge-nonoc-20260923'
DRIVER = 'drivers/net/ethernet/airoha'
PROVIDER = DRIVER + '/airoha_npu.c'
PUBLIC = 'include/linux/soc/airoha/airoha_offload.h'


def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(directory):
    files = {}
    for base, dirs, names in os.walk(directory, followlinks=False):
        for name in sorted(dirs + names):
            path = Path(base) / name
            relative = str(path.relative_to(directory))
            if path.is_symlink():
                target = os.readlink(path)
                assert not os.path.isabs(target) and path.resolve().is_relative_to(directory), ('external-kernel-symlink', relative)
                files[relative] = dict(link=target)
            elif path.is_file():
                files[relative] = dict(sha256=digest(path), mode=stat.S_IMODE(path.stat().st_mode))
    return files


def module(path):
    binary = ELFFile(io.BytesIO(path.read_bytes()))
    assert binary['e_machine'] == 'EM_AARCH64' and binary['e_type'] == 'ET_REL'
    info = binary.get_section_by_name('.modinfo').data().split(b'\0')
    magic = [item.decode().split('=', 1)[1] for item in info if item.startswith(b'vermagic=')]
    assert len(magic) == 1
    symbols = list(binary.get_section_by_name('.symtab').iter_symbols())
    exported = {item.name.removeprefix('__ksymtab_') for item in symbols
                if item.name.startswith('__ksymtab_') and item.name != '__ksymtab_strings'}
    undefined = {item.name for item in symbols if item.name and item['st_shndx'] == 'SHN_UNDEF'}
    return dict(sha256=digest(path), bytes=path.stat().st_size, vermagic=magic[0],
                exports=sorted(exported), imports=sorted(undefined))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    directory = ROOT / '.local/npu-current-provider-module' / args.name
    assert not directory.exists()
    directory.mkdir(parents=True)
    lock_path = ROOT / 'firmware/source-lock.json'
    lock = json.loads(lock_path.read_bytes())
    release = lock['kernel']
    assert re.fullmatch(r'\d+\.\d+\.\d+', release)
    build = (ROOT / lock['build_directory']).resolve()
    assert build.is_relative_to(ROOT / '.build')
    kernel = build / 'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581' / ('linux-' + release)
    config = (kernel / '.config').read_text()
    assert 'CONFIG_NET_AIROHA_NPU=m\n' in config and '# CONFIG_MODVERSIONS is not set\n' in config
    assert digest(kernel / PUBLIC) == digest(WORK / 'kernel-merged' / PUBLIC), 'public-header-drift'
    expected_release = '#define UTS_RELEASE "' + release + '"'
    assert (kernel / 'include/generated/utsrelease.h').read_text().strip() == expected_release
    inputs = {str(path.relative_to(ROOT)): digest(path) for path in (Path(__file__), lock_path)}
    def add(path, expected=None):
        value = digest(path)
        assert expected is None or value == expected, ('module-source-drift', str(path))
        name = str(path.relative_to(ROOT))
        assert name not in inputs or inputs[name] == value
        inputs[name] = value

    patch_relative = 'target/linux/airoha/patches-6.18/999-w1700k-integrated-npu.patch'
    patch = ROOT / 'firmware/overlay/openwrt' / patch_relative
    patch_row = next(row for row in lock['openwrt']['changed_files'] if row['path'] == patch_relative)
    add(patch, patch_row['sha256'])
    applied = directory / 'patched-reference'
    shutil.copytree(WORK / 'kernel-upstream', applied)
    result = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(patch)],
        cwd=applied, capture_output=True, text=True, timeout=180)
    with (directory / 'patch.log').open('x') as stream: stream.write(result.stdout + result.stderr)
    assert result.returncode == 0 and not list(applied.rglob('*.rej')), result.stdout + result.stderr
    selected = re.findall(r'^\+\+\+ b/([^\n]+)$', patch.read_text(), re.M)
    assert len(selected) == len(set(selected)) and {PROVIDER, PUBLIC, DRIVER + '/Makefile'} <= set(selected)
    for name in selected:
        assert (applied / name).resolve().is_relative_to(applied)
        add(applied / name)
        add(WORK / 'kernel-merged' / name, digest(applied / name))
    components = lock['component_sources']
    assert len(components) == 24
    for row in components:
        assert row['tree'] == 'openwrt' and row['destination'].startswith('target/linux/airoha/files-6.18/' + DRIVER + '/w1700k/')
        add(ROOT / row['source'], row['sha256'])
        add(build / row['destination'], row['sha256'])

    print(json.dumps(dict(phase='hash-and-copy-independent-prepared-kernel', release=release)), flush=True)
    before = inventory(kernel)
    before_path = directory / 'prepared-before.json'
    with before_path.open('x') as stream: stream.write(json.dumps(before, sort_keys=True) + '\n')
    shadow = directory / ('linux-' + release)
    shutil.copytree(kernel, shadow, symlinks=True)
    assert inventory(shadow) == before, 'kernel-copy-drift'
    assert (shadow / PROVIDER).stat().st_ino != (kernel / PROVIDER).stat().st_ino
    for name in selected:
        output = shadow / name
        if output.exists() and digest(output) == digest(applied / name): continue
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(applied / name, output)
    for row in components:
        name = row['destination'].removeprefix('target/linux/airoha/files-6.18/')
        output = shadow / name
        if output.exists() and digest(output) == row['sha256']: continue
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / row['source'], output)
    toolchain = build / 'staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl'
    prefix = toolchain / 'bin/aarch64-openwrt-linux-musl-'
    compiler = Path(str(prefix) + 'gcc')
    add(compiler)
    environment = dict(os.environ, STAGING_DIR=str(build / 'staging_dir/target-aarch64_cortex-a53_musl'),
        PATH=str(compiler.parent) + ':' + str(build / 'staging_dir/host/bin') + ':/usr/bin:/bin',
        LANG='C', LC_ALL='C', TZ='UTC')
    environment.pop('MAKEFLAGS', None)
    environment.pop('MFLAGS', None)
    version = subprocess.check_output([str(compiler), '--version'], env=environment, text=True).splitlines()[0]
    assert 'CONFIG_CC_VERSION_TEXT="' + version + '"' in config
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    timestamp = subprocess.check_output(['git', 'show', '-s', '--format=%cI', 'HEAD'], cwd=ROOT, text=True).strip()
    command = ['make', '-C', str(shadow), '-j2', 'ARCH=arm64', 'CROSS_COMPILE=' + str(prefix),
        'KERNELRELEASE=' + release, 'KBUILD_BUILD_USER=', 'KBUILD_BUILD_HOST=', 'KBUILD_BUILD_VERSION=0',
        'KBUILD_BUILD_TIMESTAMP=' + timestamp, 'KBUILD_HAVE_NLS=no',
        'KBUILD_HOSTLDFLAGS=-L' + str(build / 'staging_dir/host/lib'),
        'KCFLAGS=-fno-caller-saves -fstack-usage', 'V=0', DRIVER + '/airoha_npu.ko']
    print(json.dumps(dict(phase='link-current-provider-module', source_commit=commit, jobs=2)), flush=True)
    with (directory / 'build.log').open('x') as stream:
        result = subprocess.run(command, cwd=ROOT, env=environment, stdin=subprocess.DEVNULL,
            stdout=stream, stderr=subprocess.STDOUT, timeout=1800)
    assert result.returncode == 0, (directory / 'build.log').read_text()[-6000:]
    for name in ('.config', 'include/generated/autoconf.h', 'include/generated/utsrelease.h'):
        assert digest(shadow / name) == digest(kernel / name), ('configuration-drift', name)
    for name in selected: assert digest(shadow / name) == digest(applied / name)
    for row in components:
        assert digest(shadow / row['destination'].removeprefix('target/linux/airoha/files-6.18/')) == row['sha256']
    linked = module(shadow / DRIVER / 'airoha_npu.ko')
    previous = module(kernel / DRIVER / 'airoha_npu.ko')
    assert linked['vermagic'] == previous['vermagic'] and linked['vermagic'].startswith(release + ' ')
    assert linked['sha256'] != previous['sha256'], 'old-provider-module-reused'
    exports = set(re.findall(r'EXPORT_SYMBOL(?:_GPL)?\(\s*(\w+)\s*\)', (applied / PROVIDER).read_text()))
    assert set(linked['exports']) == exports and {'airoha_npu_get', 'airoha_npu_put', 'airoha_npu_wlan_control'} <= exports
    available = {words[1] for line in (shadow / 'Module.symvers').read_text().splitlines()
                 if len(words := line.split()) >= 4}
    assert set(linked['imports']) <= available, ('unresolved-module-imports', set(linked['imports']) - available)
    for name, expected in inputs.items(): assert digest(ROOT / name) == expected, ('module-input-drift', name)
    assert inventory(kernel) == before, 'prepared-kernel-changed'
    artifacts = {str(path.relative_to(ROOT)): digest(path) for path in
        (shadow / DRIVER / 'airoha_npu.ko', directory / 'build.log', directory / 'patch.log', before_path)}
    record = dict(passed=True, scope='isolated-current-provider-module-link-only', source_commit=commit,
        source_lock_sha256=inputs[str(lock_path.relative_to(ROOT))], inputs=inputs, artifacts=artifacts,
        module=linked, prior_module=previous, command=command, compiler=version,
        prepared_kernel_inventory_files=len(before), prepared_kernel_content_and_modes_unchanged=True,
        current_provider_components=6, source_components_verified=24,
        module_loaded=False, vmlinux_relinked=False, world_build=False, image_changed=False,
        native_cold_qualified=False, full_setup=False, hardware=False,
        limits=['Independent complete kernel copy;all original file content/modes/relative links are verified unchanged.',
                'Current tracked kernel patch/24 component sources;normal pinned kernel/module configuration and real final module link.',
                'Host compiler/runtime and toolchain remain external;this is not a complete portable execution environment.',
                'Module metadata/exports/import availability are offline checks,not module load,IRQ,drain,client or physical acceptance.'])
    target = directory / 'result.json'
    with target.open('x') as stream: stream.write(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(passed=True, vermagic=linked['vermagic'], exports=len(exports),
        imports=len(linked['imports']), prepared_unchanged=True, sha256=digest(target))), flush=True)


if __name__ == '__main__': main()
