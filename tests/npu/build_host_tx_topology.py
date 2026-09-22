#!/usr/bin/env python3
"""Compile the two changed mt7996 units without modifying the shared build."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

sys.dont_write_bytecode = True
import test_host_tx_topology as host

ROOT, OUT, KERNEL = host.ROOT, host.OUT, host.KERNEL
BUILD = host.SCRATCH / 'kernel-objects'
OPENWRT = ROOT / '.build/openwrt'
STAGING = OPENWRT / 'staging_dir'
TOOLCHAIN = STAGING / 'toolchain-aarch64_cortex-a53_gcc-14.4.0_musl'
TARGET_INCLUDE = STAGING / 'target-aarch64_cortex-a53_musl/usr/include'
PREFIX = TOOLCHAIN / 'bin/aarch64-openwrt-linux-musl-'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(command, cwd=None):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def main():
    lock_path = ROOT / 'firmware/source-lock.json'
    lock = json.loads(lock_path.read_text())
    protected = [lock_path, ROOT / 'firmware/patches/openwrt.patch',
                 ROOT / 'firmware/build.config', OPENWRT / '.config',
                 KERNEL / '.config', KERNEL / 'Module.symvers',
                 KERNEL / 'include/generated/autoconf.h',
                 KERNEL / 'include/generated/utsrelease.h']
    before = {str(path.relative_to(ROOT)): sha(path) for path in protected}
    assert '"6.18.44"' in (KERNEL / 'include/generated/utsrelease.h').read_text()
    assert sha(host.queues.ARCHIVE) == host.queues.ARCHIVE_SHA
    patches = sorted((ROOT / 'firmware/overlay/openwrt/package/kernel/mt76/patches').glob('*.patch'))
    assert len(patches) == 3
    for path in patches:
        name = str(path.relative_to(ROOT / 'firmware/overlay/openwrt'))
        entry = next(row for row in lock['openwrt']['changed_files'] if row['path'] == name)
        assert sha(path) == entry['sha256']
    zstd = STAGING / 'host/bin/zstd'
    raw = subprocess.check_output([str(zstd), '-dc', str(host.queues.ARCHIVE)], timeout=30)
    compiler = str(PREFIX) + 'gcc'
    gcc_include = execute([compiler, '-print-file-name=include']).strip()
    original = host.sources()
    fixed = host.patched(original)
    variants = []
    for phase in ('before', 'after'):
        for enabled in (False, True):
            destination = BUILD / f'{phase}-npu-{int(enabled)}'
            destination.mkdir(parents=True, exist_ok=True)
            with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
                for member in archive.getmembers():
                    path = (destination / member.name).resolve()
                    assert path.is_relative_to(destination.resolve())
                archive.extractall(destination, filter='data')
            source = destination / 'mt76-2026.09.01~be5ce791'
            patch_log = []
            for patch in [*patches, *([host.PATCH] if phase == 'after' else [])]:
                output = execute(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)], source)
                if patch == host.PATCH:
                    assert 'offset' not in output and 'fuzz' not in output
                patch_log.append(dict(path=str(patch.relative_to(ROOT)), sha256=sha(patch), output=output))
            expected = fixed if phase == 'after' else original
            for name in ('mt7996/dma.c', 'mt7996/init.c'):
                assert (source / name).read_text() == expected[name]
            includes = ['-nostdinc', '-isystem', gcc_include, '-I' + str(source)]
            includes += ['-I' + str(TARGET_INCLUDE / name) for name in
                         ('mac80211-backport/uapi', 'mac80211-backport', 'mac80211/uapi', 'mac80211')]
            includes += ['-include', 'backport/autoconf.h', '-include', 'backport/backport.h', '-DCONFIG_MAC80211_MESH']
            config = ['CONFIG_MT76_CONNAC_LIB=m', 'CONFIG_MT7996E=m']
            if enabled:
                includes += ['-DCONFIG_MT76_NPU', '-DCONFIG_MT7996_NPU']
                config += ['CONFIG_MT76_NPU=y', 'CONFIG_MT7996_NPU=y']
            command = ['make', '-C', str(KERNEL), '-j2', 'ARCH=arm64',
                       'CROSS_COMPILE=' + str(PREFIX), 'CC=' + compiler,
                       'KERNELRELEASE=6.18.44', 'KBUILD_BUILD_USER=', 'KBUILD_BUILD_HOST=',
                       'KBUILD_BUILD_TIMESTAMP=Fri Sep 4 16:17:19 2026', 'KBUILD_BUILD_VERSION=0',
                       'V=1', 'M=' + str(source), 'NOSTDINC_FLAGS=' + ' '.join(includes),
                       *config, 'mt7996/init.o', 'mt7996/dma.o']
            log_path = OUT / f'objects-{phase}-npu-{int(enabled)}.log'
            env = {**os.environ, 'PATH': str(TOOLCHAIN / 'bin') + ':' + str(STAGING / 'host/bin') + ':/usr/bin:/bin'}
            with log_path.open('w') as log:
                result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env, timeout=600)
            assert result.returncode == 0, log_path
            assert 'error:' not in log_path.read_text()
            objects = []
            for name in ('mt7996/init.o', 'mt7996/dma.o'):
                obj = source / name
                elf_header = execute([str(PREFIX) + 'readelf', '-h', str(obj)])
                assert 'AArch64' in elf_header and 'REL (Relocatable file)' in elf_header
                objects.append(dict(path=str(obj.relative_to(ROOT)), sha256=sha(obj), size=obj.stat().st_size))
            variants.append(dict(phase=phase, npu_enabled=enabled, command=command,
                                 patch_application=patch_log, objects=objects,
                                 log=str(log_path.relative_to(ROOT)), log_sha256=sha(log_path)))
            print(json.dumps(dict(phase=phase, npu_enabled=enabled, compiled_objects=len(objects))), flush=True)
    assert {str(path.relative_to(ROOT)): sha(path) for path in protected} == before
    result = dict(schema=1, test_sha256=sha(Path(__file__)), archive_sha256=host.queues.ARCHIVE_SHA,
                  patch_sha256=sha(host.PATCH), compiler=execute([compiler, '--version']).splitlines()[0],
                  protected_inputs_before_after=before, variants=variants,
                  limits=['Eight real AArch64 kernel translation-unit objects, not linked modules or an image.',
                          'Shared kernel configuration, release configuration, source lock and cumulative patch are unchanged.',
                          'Existing staged mac80211/backport headers used; module symbol-version link not tested.',
                          'No NPU firmware/native callback execution, router access, image or flash operation.'])
    receipt = OUT / 'kernel-objects.json'
    receipt.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(variants=len(variants), objects=8, evidence_sha256=sha(receipt))))


if __name__ == '__main__':
    main()
