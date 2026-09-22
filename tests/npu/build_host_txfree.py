#!/usr/bin/env python3
"""Compile isolated AArch64 TXFREE candidates without changing shared sources."""
import argparse
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

sys.dont_write_bytecode = True
import build_host_tx_topology as kernel
import test_host_txfree as txfree

ROOT, OUT = txfree.ROOT, txfree.OUT
BUILD = txfree.BUILD/'kernel-objects'


def bindings():
    result = txfree.input_bindings()
    paths = [Path(__file__), Path(kernel.__file__), kernel.OPENWRT/'.config',
             kernel.KERNEL/'.config', kernel.KERNEL/'Module.symvers',
             kernel.KERNEL/'include/generated/autoconf.h',
             kernel.KERNEL/'include/generated/utsrelease.h']
    return {**result, **{str(p.relative_to(ROOT)): kernel.sha(p) for p in paths}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    inputs = bindings()
    lock = json.loads((ROOT/'firmware/source-lock.json').read_text())
    assert '"6.18.44"' in (kernel.KERNEL/'include/generated/utsrelease.h').read_text()
    assert kernel.sha(txfree.q.ARCHIVE) == txfree.q.ARCHIVE_SHA
    patches = sorted((ROOT/'firmware/overlay/openwrt/package/kernel/mt76/patches').glob('*.patch'))
    assert len(patches) == 3
    for path in patches:
        name = str(path.relative_to(ROOT/'firmware/overlay/openwrt'))
        entry = next(row for row in lock['openwrt']['changed_files'] if row['path'] == name)
        assert kernel.sha(path) == entry['sha256']
    zstd = kernel.STAGING/'host/bin/zstd'
    raw = subprocess.check_output([str(zstd), '-dc', str(txfree.q.ARCHIVE)], timeout=30)
    compiler = str(kernel.PREFIX)+'gcc'
    gcc_include = kernel.execute([compiler, '-print-file-name=include']).strip()
    original = txfree.host.sources()
    topology = txfree.host.patched(original)
    fixed = txfree.patched(original)
    variants = []
    for phase in ('before', 'after'):
        for enabled in (False, True):
            destination = (BUILD/f'{phase}-npu-{int(enabled)}').resolve()
            assert destination.is_relative_to(BUILD.resolve()) and destination != BUILD.resolve()
            if destination.exists():
                shutil.rmtree(destination)
            destination.mkdir(parents=True)
            with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
                for member in archive.getmembers():
                    assert (destination/member.name).resolve().is_relative_to(destination)
                archive.extractall(destination, filter='data')
            source = destination/'mt76-2026.09.01~be5ce791'
            patch_log = []
            candidates = [txfree.host.PATCH, *([txfree.PATCH] if phase == 'after' else [])]
            for patch in [*patches, *candidates]:
                output = kernel.execute(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)], source)
                if patch in candidates:
                    assert 'offset' not in output and 'fuzz' not in output
                patch_log.append(dict(path=str(patch.relative_to(ROOT)), sha256=kernel.sha(patch), output=output))
            for name in ('mt7996/dma.c', 'mt7996/init.c'):
                assert (source/name).read_text() == topology[name]
            expected = fixed if phase == 'after' else original
            selected = ['mt7996_npu_rx_event_init', '__mt7996_npu_hw_init']
            if phase == 'after':
                selected.append('mt7996_npu_rx_event_validate')
            spans = {}
            for name in selected:
                actual = txfree.q.function((source/'mt7996/npu.c').read_text(), name)
                assert actual == txfree.q.function(expected['mt7996/npu.c'], name)
                spans[name] = txfree.sha(actual.encode())
            includes = ['-nostdinc', '-isystem', gcc_include, '-I'+str(source)]
            includes += ['-I'+str(kernel.TARGET_INCLUDE/name) for name in
                         ('mac80211-backport/uapi', 'mac80211-backport', 'mac80211/uapi', 'mac80211')]
            includes += ['-include', 'backport/autoconf.h', '-include', 'backport/backport.h', '-DCONFIG_MAC80211_MESH']
            config = ['CONFIG_MT76_CONNAC_LIB=m', 'CONFIG_MT7996E=m']
            targets = ['mt7996/init.o', 'mt7996/dma.o']
            if enabled:
                includes += ['-DCONFIG_MT76_NPU', '-DCONFIG_MT7996_NPU']
                config += ['CONFIG_MT76_NPU=y', 'CONFIG_MT7996_NPU=y']
                targets.append('mt7996/npu.o')
            command = ['make', '-C', str(kernel.KERNEL), '-j2', 'ARCH=arm64',
                       'CROSS_COMPILE='+str(kernel.PREFIX), 'CC='+compiler,
                       'KERNELRELEASE=6.18.44', 'KBUILD_BUILD_USER=', 'KBUILD_BUILD_HOST=',
                       'KBUILD_BUILD_TIMESTAMP=Fri Sep 4 16:17:19 2026', 'KBUILD_BUILD_VERSION=0',
                       'V=1', 'M='+str(source), 'NOSTDINC_FLAGS='+' '.join(includes), *config, *targets]
            log_path = OUT/f'objects-{phase}-npu-{int(enabled)}.log'
            env = {**os.environ, 'PATH': str(kernel.TOOLCHAIN/'bin')+':'+str(kernel.STAGING/'host/bin')+':/usr/bin:/bin'}
            with log_path.open('w') as log:
                result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env, timeout=600)
            assert result.returncode == 0 and 'error:' not in log_path.read_text(), log_path
            objects = []
            for name in targets:
                obj = source/name
                header = kernel.execute([str(kernel.PREFIX)+'readelf', '-h', str(obj)])
                assert 'AArch64' in header and 'REL (Relocatable file)' in header
                text = obj.with_suffix('.text')
                kernel.execute([str(kernel.PREFIX)+'objcopy', '--dump-section', '.text='+str(text), str(obj)])
                objects.append(dict(path=str(obj.relative_to(ROOT)), sha256=kernel.sha(obj), size=obj.stat().st_size,
                                    text_sha256=kernel.sha(text), text_bytes=text.stat().st_size))
            variants.append(dict(phase=phase, npu_enabled=enabled, command=command,
                                 patch_application=patch_log, selected_function_sha256=spans,
                                 objects=objects, log=str(log_path.relative_to(ROOT))))
            print(json.dumps(dict(phase=phase, npu_enabled=enabled, objects=len(objects))), flush=True)
    for enabled in (False, True):
        pair = [v for v in variants if v['npu_enabled'] == enabled]
        for index in (0, 1):
            assert pair[0]['objects'][index]['text_sha256'] == pair[1]['objects'][index]['text_sha256']
        if enabled:
            assert pair[0]['objects'][2]['text_sha256'] != pair[1]['objects'][2]['text_sha256']
    checkpatch = kernel.execute(['perl', str(kernel.KERNEL/'scripts/checkpatch.pl'), '--strict',
                                 '--no-tree', '--no-signoff', str(txfree.PATCH)])
    assert '0 errors, 0 warnings, 0 checks' in checkpatch
    assert bindings() == inputs, 'bound inputs changed during execution'
    result = dict(schema=1, inputs_before_after=inputs, variants=variants, checkpatch=checkpatch,
                  compiler=kernel.execute([compiler, '--version']).splitlines()[0],
                  limits=['Ten real AArch64 objects; no module link, package, image or physical execution.',
                          'Prior topology candidate layered identically in both phases, plus three promoted mt76 patches.',
                          'Selected NPU functions equal the host-test source; NPU-disabled builds omit npu.o.',
                          'Shared kernel/configuration/provider, firmware overlay and source lock remain unchanged.',
                          'Build logs retain compiler output; parallel log ordering is not a reproducibility claim.'])
    output = OUT/'kernel-objects.json'
    encoded = (json.dumps(result, indent=2)+'\n').encode()
    if args.check:
        assert output.read_bytes() == encoded
    else:
        output.write_bytes(encoded)
    print(json.dumps(dict(objects=10, evidence_sha256=txfree.sha(encoded))))


if __name__ == '__main__':
    main()
