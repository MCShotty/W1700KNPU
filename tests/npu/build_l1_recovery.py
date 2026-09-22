#!/usr/bin/env python3
"""Compile every MT7996 unit for the unpromoted L1 candidate, offline only."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

sys.dont_write_bytecode = True
from elftools.elf.elffile import ELFFile
import build_host_tx_topology as kernel
import test_l1_recovery as l1

ROOT, OUT = l1.ROOT, l1.OUT
BUILD = l1.BUILD/'kernel-objects'


def inputs():
    paths = [Path(__file__), Path(kernel.__file__), kernel.OPENWRT/'.config',
             kernel.KERNEL/'.config', kernel.KERNEL/'Module.symvers',
             kernel.KERNEL/'include/generated/autoconf.h',
             kernel.KERNEL/'include/generated/utsrelease.h']
    return {**l1.inputs(), **{str(p.relative_to(ROOT)): kernel.sha(p) for p in paths}}


def main():
    before = inputs()
    assert '"6.18.44"' in (kernel.KERNEL/'include/generated/utsrelease.h').read_text()
    checkpatch = kernel.execute(['perl', str(kernel.KERNEL/'scripts/checkpatch.pl'),
                                 '--strict', '--no-tree', '--no-signoff', str(l1.PATCH)])
    assert '0 errors, 0 warnings, 0 checks' in checkpatch
    original, _ = l1.sources()
    fixed, _ = l1.patched(original)
    zstd = kernel.STAGING/'host/bin/zstd'
    raw = subprocess.check_output([str(zstd), '-dc', str(l1.q.ARCHIVE)], timeout=30)
    compiler = str(kernel.PREFIX)+'gcc'
    env = {**os.environ, 'STAGING_DIR': str(kernel.TARGET_INCLUDE.parent.parent),
           'PATH': str(kernel.TOOLCHAIN/'bin')+':'+str(kernel.STAGING/'host/bin')+':/usr/bin:/bin'}
    gcc_include = subprocess.check_output([compiler, '-print-file-name=include'], env=env, text=True, timeout=30).strip()
    promoted = sorted((ROOT/'firmware/overlay/openwrt/package/kernel/mt76/patches').glob('*.patch'))
    variants = []
    for phase, expected in (('before', original), ('after', fixed)):
        for enabled in (False, True):
            destination = (BUILD/f'{phase}-npu-{int(enabled)}').resolve()
            assert destination.is_relative_to(BUILD.resolve())
            destination.mkdir(parents=True, exist_ok=True)
            with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
                for member in archive.getmembers():
                    assert (destination/member.name).resolve().is_relative_to(destination)
                archive.extractall(destination, filter='data')
            source = destination/'mt76-2026.09.01~be5ce791'
            logs = []
            patches = [*promoted, l1.txfree.host.PATCH, l1.txfree.PATCH]
            if phase == 'after':
                patches.append(l1.PATCH)
            for patch in patches:
                output = kernel.execute(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)], source)
                if patch == l1.PATCH:
                    assert 'offset' not in output and 'fuzz' not in output
                logs.append(dict(path=str(patch.relative_to(ROOT)), sha256=kernel.sha(patch), output=output))
            assert all((source/name).read_text() == data for name, data in expected.items())
            includes = ['-nostdinc', '-isystem', gcc_include, '-I'+str(source)]
            includes += ['-I'+str(kernel.TARGET_INCLUDE/name) for name in
                         ('mac80211-backport/uapi', 'mac80211-backport', 'mac80211/uapi', 'mac80211')]
            includes += ['-include', 'backport/autoconf.h', '-include', 'backport/backport.h', '-DCONFIG_MAC80211_MESH']
            config = ['CONFIG_MT76_CONNAC_LIB=m', 'CONFIG_MT7996E=m']
            if enabled:
                includes += ['-DCONFIG_MT76_NPU', '-DCONFIG_MT7996_NPU']
                config += ['CONFIG_MT76_NPU=y', 'CONFIG_MT7996_NPU=y']
            command = ['make', '-C', str(kernel.KERNEL), '-j2', 'ARCH=arm64',
                       'CROSS_COMPILE='+str(kernel.PREFIX), 'CC='+compiler,
                       'KERNELRELEASE=6.18.44', 'KBUILD_BUILD_USER=', 'KBUILD_BUILD_HOST=',
                       'KBUILD_BUILD_TIMESTAMP=Mon Sep 14 00:00:00 2026', 'KBUILD_BUILD_VERSION=0',
                       'V=1', 'M='+str(source), 'NOSTDINC_FLAGS='+' '.join(includes),
                       *config, 'mt7996/mt7996e.o']
            log_path = OUT/f'objects-{phase}-npu-{int(enabled)}.log'
            with log_path.open('w') as log:
                result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env, timeout=900)
            assert result.returncode == 0 and 'error:' not in log_path.read_text(), log_path
            assert 'warning:' not in log_path.read_text(), log_path
            required = {'pci.o', 'init.o', 'dma.o', 'eeprom.o', 'main.o', 'mcu.o', 'mac.o', 'debugfs.o', 'mmio.o', 'mt7996e.o'}
            if enabled:
                required.add('npu.o')
            objects = []
            for obj in sorted((source/'mt7996').glob('*.o')):
                with obj.open('rb') as stream:
                    elf = ELFFile(stream)
                    assert elf['e_machine'] == 'EM_AARCH64' and elf['e_type'] == 'ET_REL'
                    symbols = {s.name for s in elf.get_section_by_name('.symtab').iter_symbols()}
                if obj.name == 'mt7996e.o':
                    assert 'mt7996_mac_reset_work' in symbols and 'mt7996_dma_start' in symbols
                    assert ('mt7996_npu_hw_stop' in symbols) == enabled
                objects.append(dict(name=obj.name, path=str(obj.relative_to(ROOT)),
                                    sha256=kernel.sha(obj), bytes=obj.stat().st_size))
            assert required <= {obj['name'] for obj in objects}
            variants.append(dict(phase=phase, npu_enabled=enabled, command=command, patch_application=logs,
                                 objects=objects, log=str(log_path.relative_to(ROOT))))
            print(json.dumps(dict(phase=phase, npu_enabled=enabled, objects=len(objects))), flush=True)
    assert inputs() == before
    result = dict(schema=1, inputs_before_after=before, variants=variants, checkpatch=checkpatch,
                  staging_dir=env['STAGING_DIR'],
                  compiler=subprocess.check_output([compiler, '--version'], env=env, text=True, timeout=30).splitlines()[0],
                  limits=['All MT7996 compilation units and relocatable aggregation are compiled; this is not module load, runtime or an NPU-active image.',
                          'Linux/framework concurrency and independent NPU containment/drains remain unproved.',
                          'The source-lock, firmware overlays, kernel build configuration and existing images are unchanged.'])
    encoded = (json.dumps(result, indent=2)+'\n').encode()
    (OUT/'kernel-objects.json').write_bytes(encoded)
    print(json.dumps(dict(variants=len(variants), objects=sum(len(row['objects']) for row in variants),
                          evidence_sha256=l1.sha(encoded))))


if __name__ == '__main__':
    main()
