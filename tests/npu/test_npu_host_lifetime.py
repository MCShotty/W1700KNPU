#!/usr/bin/env python3
"""Actual provider probe/IRQ/work and mt76 detach C with explicit lifetime models."""
import argparse
import difflib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

sys.dont_write_bytecode = True
from elftools.elf.elffile import ELFFile
import build_control_v2_provider as provider
import test_l1_recovery as l1

ROOT, KERNEL, SOURCE, HEADER = provider.ROOT, provider.KERNEL, provider.SOURCE, provider.HEADER
BUILD = ROOT / '.local/npu-host-lifetime'
OUT = ROOT / 'research/checkpoints/2026-09-16-npu-host-lifetime'
INIT = OUT / 'provider-core-init.c'
DEINIT = OUT / 'mt76-deinit.c'
HELPERS = KERNEL / 'include/linux/devm-helpers.h'
PROVIDER_HARNESS = ROOT / 'tests/npu/provider-lifetime-harness.c'
RCU_HARNESS = ROOT / 'tests/npu/npu-rcu-lifetime-harness.c'
q, preflight, kernel = provider.extract, provider.preflight, provider.kernel_build
sha, execute = provider.sha, provider.execute


def once(source, old, new):
    assert source.count(old) == 1, old
    return source.replace(old, new)


def function(source, name):
    return preflight.block(source, r'^(?:static\s+(?:inline\s+)?)?(?:int|void|u32|irqreturn_t)\s+' +
                           re.escape(name) + r'\([^;{]*?\)\s*\{')


def stage():
    receipt = json.loads((provider.OUT / 'control-v2-provider.json').read_text())
    assert sha(SOURCE) == receipt['inputs'][str(SOURCE.relative_to(ROOT))]
    assert sha(HEADER) == receipt['inputs'][str(HEADER.relative_to(ROOT))]
    original = SOURCE.read_text()
    control_patch = provider.OUT / '928-net-airoha-npu-bidirectional-control.patch'
    assert sha(control_patch) == receipt['patch_sha256']
    control_root = BUILD / 'control-base'
    for relative, source in (('drivers/net/ethernet/airoha/airoha_npu.c', SOURCE),
                             ('include/linux/soc/airoha/airoha_offload.h', HEADER)):
        target = control_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    applied = subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(control_patch)],
                             cwd=control_root, capture_output=True, text=True, timeout=30)
    assert applied.returncode == 0 and 'offset' not in applied.stdout and 'fuzz' not in applied.stdout
    original = (control_root / 'drivers/net/ethernet/airoha/airoha_npu.c').read_text()
    changed = once(original, '#include <linux/devcoredump.h>\n',
                   '#include <linux/devcoredump.h>\n#include <linux/devm-helpers.h>\n')
    probe = function(changed, 'airoha_npu_probe')
    fixed = once(probe, '\t\tspin_lock_init(&core->lock);\n\t\tcore->npu = npu;\n\n', '')
    fixed = once(fixed, '\n\t\tINIT_WORK(&core->wdt_work, airoha_npu_wdt_work);\n', '')
    fixed = once(fixed, '\tirq = platform_get_irq(pdev, 0);\n',
                 INIT.read_text() + '\tirq = platform_get_irq(pdev, 0);\n')
    changed = once(changed, probe, fixed)
    changed = once(changed, function(changed, 'airoha_npu_remove') + '\n\n', '')
    changed = once(changed, '\t.remove = airoha_npu_remove,\n', '')
    mt76, _ = l1.sources()
    before_mt = mt76['npu.c']
    after_mt = once(before_mt, function(before_mt, 'mt76_npu_deinit'), DEINIT.read_text().rstrip())
    rows = []
    for name, relative, before, after, subject in (
        ('929-net-airoha-npu-irq-work-lifetime.patch', 'drivers/net/ethernet/airoha/airoha_npu.c',
         original, changed, 'net: airoha: order managed NPU watchdog work and IRQ lifetime'),
        ('007-mt76-npu-rcu-reader-lifetime.patch', 'npu.c', before_mt, after_mt,
         'wifi: mt76: drain NPU and PPE RCU readers before dropping references')):
        path = OUT / name
        description = ('From: W1700KNPU development <noreply@example.invalid>\n'
                       f'Subject: [CANDIDATE] {subject}\n\n'
                       'Unpromoted CPU callback/reference lifetime correction. Hardware\n'
                       'DMA containment and safe buffer reclamation remain separate gates.\n\n---\n')
        patch = description + ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                      fromfile='a/' + relative, tofile='b/' + relative))
        path.write_text(patch)
        directory = BUILD / name.removesuffix('.patch')
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(before)
        done = subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(path)],
                              cwd=directory, capture_output=True, text=True, timeout=30)
        assert done.returncode == 0 and 'offset' not in done.stdout and 'fuzz' not in done.stdout, done.stdout + done.stderr
        assert target.read_text() == after
        rows.append(dict(path=str(path.relative_to(ROOT)), sha256=sha(path), application=done.stdout))
    return (original, changed), (before_mt, after_mt), rows


def provider_include(source, directory):
    header = HEADER.read_text()
    macros = ('AIROHA_NPU_MBOX_SIZE', 'NPU_DUMP_SIZE', 'NPU_EN7581_FIRMWARE_RV32_MAX_SIZE',
              'NPU_SRAM_BACKUP_SIZE', 'NPU_CLUSTER_BASE_ADDR', 'REG_CR_BOOT_TRIGGER',
              'REG_CR_BOOT_CONFIG', 'REG_CR_BOOT_BASE', 'NPU_MBOX_BASE_ADDR',
              'REG_CR_MBOX_INT_STATUS', 'MBOX_INT_STATUS_MASK', 'REG_CR_MBQ8_CTRL',
              'REG_CR_NPU_MIB', 'REG_PC_DBG', 'NPU_TIMER_BASE_ADDR', 'REG_WDT_TIMER_CTRL',
              'WDT_EN_MASK', 'WDT_INTR_MASK', 'MBOX_MSG_STATUS', 'MBOX_MSG_DONE')
    (directory / 'constants.inc').write_text('\n'.join(q.macro(source, n) for n in macros) + '\n')
    enums = [q.declaration(header, 'enum', n) for n in ('airoha_npu_wlan_set_cmd', 'airoha_npu_wlan_get_cmd')]
    types = [q.declaration(header, 'struct', 'airoha_npu'), q.declaration(source, 'struct', 'airoha_npu_priv')]
    (directory / 'types.inc').write_text('\n'.join(enums + types) + '\n')
    functions = ['airoha_npu_mbox_handler', 'airoha_npu_wdt_work', 'airoha_npu_wdt_handler']
    helper = HELPERS.read_text()
    parts = [function(helper, 'devm_work_drop'), function(helper, 'devm_work_autocancel')]
    parts += [function(source, n) for n in functions]
    probe = function(source, 'airoha_npu_probe')
    names = re.findall(r'npu->ops\.\w+ = (\w+);', probe)
    stubs = []
    for name in names:
        signature = function(source, name).split('{', 1)[0]
        stubs.append(signature + '{ ' + ('' if re.match(r'(?:static\s+)?void\s', signature) else 'return 0; ') + '}')
    stubs.append('static int airoha_npu_run_firmware(struct airoha_npu_priv *priv, void *base, struct resource *res)\n'
                 '{ return model_firmware(); }')
    parts += stubs + [probe]
    if 'static void airoha_npu_remove(' in source:
        parts.append(function(source, 'airoha_npu_remove'))
    else:
        parts.append('static void airoha_npu_remove(struct platform_device *pdev) { (void)pdev; }')
    parts.append('static void model_remove(struct platform_device *pdev) { airoha_npu_remove(pdev); }')
    (directory / 'driver.inc').write_text('\n\n'.join(parts) + '\n')


def build_harness(directory, harness):
    binary = directory / 'lifetime'
    command = [shutil.which('clang'), '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
               '-Wno-unused-parameter', '-Wno-unused-function', '-Wno-sign-compare',
               '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-pthread',
               '-I', str(directory), str(harness), '-o', str(binary)]
    execute(command)
    return binary, dict(command=command, binary=str(binary.relative_to(ROOT)), sha256=sha(binary))


def provider_cases(sources):
    rows = []
    for phase, source in zip(('before', 'after'), sources):
        directory = BUILD / ('provider-' + phase)
        directory.mkdir(parents=True, exist_ok=True)
        provider_include(source, directory)
        binary, build = build_harness(directory, PROVIDER_HARNESS)
        result = json.loads(execute([binary, phase]))
        rows.append(dict(phase=phase, build=build, result=result))
    assert rows[0]['result']['cases'][0]['uninitialized_queue'] == 8
    assert rows[0]['result']['cases'][0]['pending_at_free'] == 8
    return rows


def rcu_cases(sources):
    rows = []
    for phase, source in zip(('before', 'after'), sources):
        directory = BUILD / ('rcu-' + phase)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'deinit.inc').write_text(function(source, 'mt76_npu_deinit') + '\n')
        binary, build = build_harness(directory, RCU_HARNESS)
        result = json.loads(execute([binary, phase]))
        rows.append(dict(phase=phase, build=build, result=result))
    return rows


def mutants(provider_source, mt76_source):
    rows = []
    mt76_source = function(mt76_source, 'mt76_npu_deinit')
    untracked = once(provider_source, '\t\terr = devm_work_autocancel(dev, &core->wdt_work,\n'
                                     '\t\t\t\t\t   airoha_npu_wdt_work);',
                     '\t\tINIT_WORK(&core->wdt_work, airoha_npu_wdt_work);\n\t\terr = 0;')
    variants = [('missing-managed-cancel', untracked, PROVIDER_HARNESS)]
    no_wait = once(mt76_source, '\tif (npu || ppe_dev)\n\t\tsynchronize_rcu();\n', '')
    variants.append(('missing-rcu-grace', no_wait, RCU_HARNESS))
    put = '\tif (npu)\n\t\tairoha_npu_put(npu);\n'
    early_put = once(once(mt76_source, put, ''), '\tif (npu || ppe_dev)\n', put + '\tif (npu || ppe_dev)\n')
    variants.append(('npu-put-before-grace', early_put, RCU_HARNESS))
    early_cleanup = once(once(mt76_source, put, ''), '\tmutex_unlock(&dev->mutex);\n',
                         put + '\tmutex_unlock(&dev->mutex);\n')
    variants.append(('npu-put-before-cleanup', early_cleanup, RCU_HARNESS))
    for name, source, harness in variants:
        directory = BUILD / ('mutant-' + name)
        directory.mkdir(parents=True, exist_ok=True)
        if harness == PROVIDER_HARNESS:
            provider_include(source, directory)
        else:
            (directory / 'deinit.inc').write_text(function(source, 'mt76_npu_deinit') + '\n')
        binary, build = build_harness(directory, harness)
        completed = subprocess.run([str(binary), 'after'], capture_output=True, text=True, timeout=30)
        oracle = {'missing-managed-cancel': 'irq-work-lifetime',
                  'missing-rcu-grace': 'missing-reader-grace',
                  'npu-put-before-grace': 'put-before-reader-grace',
                  'npu-put-before-cleanup': 'cleanup-after-provider-put'}[name]
        assert completed.returncode != 0 and oracle in completed.stderr, (name, completed.stderr)
        assert 'AddressSanitizer' not in completed.stderr and 'runtime error:' not in completed.stderr
        rows.append(dict(name=name, build=build, oracle=oracle, oracle_failure=completed.stderr.strip()))
    return rows


def object_info(path, deinit=False):
    obj = ELFFile(io.BytesIO(path.read_bytes()))
    assert obj['e_machine'] == 'EM_AARCH64' and obj['e_type'] == 'ET_REL'
    row = dict(path=str(path.relative_to(ROOT)), sha256=sha(path), bytes=path.stat().st_size)
    if deinit:
        table = obj.get_section_by_name('.symtab')
        target = table.get_symbol_by_name('mt76_npu_deinit')[0]
        calls = []
        for section in obj.iter_sections():
            if section['sh_type'] != 'SHT_RELA' or section['sh_info'] != target['st_shndx']:
                continue
            for relocation in section.iter_relocations():
                if target['st_value'] <= relocation['r_offset'] < target['st_value'] + target['st_size']:
                    symbol = table.get_symbol(relocation['r_info_sym']).name
                    if symbol:
                        calls.append(symbol)
        row['deinit_relocations'] = calls
    return row


def kernel_objects(provider_sources, mt76_sources, patches):
    env = dict(os.environ, STAGING_DIR=str(kernel.TARGET_INCLUDE.parent.parent),
               PATH=str(kernel.TOOLCHAIN / 'bin') + ':' + str(kernel.STAGING / 'host/bin') + ':/usr/bin:/bin')
    rows = []
    public = BUILD / 'control-base/include/linux/soc/airoha/airoha_offload.h'
    for phase, contents in zip(('before', 'after'), provider_sources):
        directory = BUILD / ('kernel-provider-' + phase)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'airoha_npu.c').write_text(contents)
        (directory / 'public.h').write_bytes(public.read_bytes())
        for path in SOURCE.parent.glob('*.h'):
            shutil.copy2(path, directory / path.name)
        for enabled in (0, 1):
            prefix = '#define TEST_CONTROL_DECL\n' + ('#define TEST_NPU_ON\n' if enabled else '')
            (directory / f'probe-{enabled}.c').write_text(prefix + provider.PROBE)
        (directory / 'Makefile').write_text('obj-m += airoha_npu.o probe-0.o probe-1.o\n'
                                           'CFLAGS_airoha_npu.o += -include $(src)/public.h\n')
        command = ['make', '-C', str(KERNEL), f'M={directory}', 'ARCH=arm64',
                   f'CROSS_COMPILE={kernel.PREFIX}', 'airoha_npu.o', 'probe-0.o', 'probe-1.o']
        done = subprocess.run(command, env=env, capture_output=True, text=True, timeout=180)
        log = done.stdout + done.stderr
        log_path = OUT / f'kernel-provider-{phase}.log'
        log_path.write_text(log)
        assert done.returncode == 0 and not re.search(r'\b(?:warning|error):', log, re.I), log
        layouts = {}
        for enabled in (0, 1):
            obj = ELFFile(io.BytesIO((directory / f'probe-{enabled}.o').read_bytes()))
            layouts[str(enabled)] = obj.get_section_by_name('.npu_layout').data().hex()
        rows.append(dict(kind='provider', phase=phase, command=command, public_layout=layouts,
                         log=str(log_path.relative_to(ROOT)), log_sha256=sha(log_path),
                         objects=[object_info(directory / name) for name in ('airoha_npu.o', 'probe-0.o', 'probe-1.o')]))
        print(json.dumps(dict(stage='kernel-provider', phase=phase)), flush=True)
    assert rows[0]['public_layout'] == rows[1]['public_layout']

    raw = subprocess.check_output([str(kernel.STAGING / 'host/bin/zstd'), '-dc', str(l1.q.ARCHIVE)], timeout=30)
    compiler = str(kernel.PREFIX) + 'gcc'
    gcc_include = subprocess.check_output([compiler, '-print-file-name=include'], env=env, text=True, timeout=30).strip()
    promoted = sorted((ROOT / 'firmware/overlay/openwrt/package/kernel/mt76/patches').glob('*.patch'))
    for phase, expected in zip(('before', 'after'), mt76_sources):
        for enabled in (0, 1):
            destination = BUILD / f'kernel-mt76-{phase}-{enabled}'
            destination.mkdir(parents=True, exist_ok=True)
            with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
                for member in archive.getmembers():
                    assert (destination / member.name).resolve().is_relative_to(destination.resolve())
                archive.extractall(destination, filter='data')
            source = destination / 'mt76-2026.09.01~be5ce791'
            selected = [*promoted, l1.txfree.host.PATCH, l1.txfree.PATCH, l1.PATCH]
            if phase == 'after':
                selected.append(ROOT / patches[1]['path'])
            for patch in selected:
                done = subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)],
                                      cwd=source, capture_output=True, text=True, timeout=30)
                assert done.returncode == 0, done.stdout + done.stderr
                if patch == ROOT / patches[1]['path']:
                    assert 'offset' not in done.stdout and 'fuzz' not in done.stdout
            assert (source / 'npu.c').read_text() == expected
            includes = ['-nostdinc', '-isystem', gcc_include, '-I' + str(source)]
            includes += ['-I' + str(kernel.TARGET_INCLUDE / name) for name in
                         ('mac80211-backport/uapi', 'mac80211-backport', 'mac80211/uapi', 'mac80211')]
            includes += ['-include', 'backport/autoconf.h', '-include', 'backport/backport.h', '-DCONFIG_MAC80211_MESH']
            config = ['CONFIG_MT76_CONNAC_LIB=m', 'CONFIG_MT7996E=m']
            objects = ['mac80211.o']
            if enabled:
                includes += ['-DCONFIG_MT76_NPU', '-DCONFIG_MT7996_NPU']
                config += ['CONFIG_MT76_NPU=y', 'CONFIG_MT7996_NPU=y']
                objects.append('npu.o')
            command = ['make', '-C', str(KERNEL), '-j2', 'ARCH=arm64', f'CROSS_COMPILE={kernel.PREFIX}',
                       'CC=' + compiler, 'KERNELRELEASE=6.18.44', 'KBUILD_BUILD_USER=', 'KBUILD_BUILD_HOST=',
                       'KBUILD_BUILD_TIMESTAMP=Wed Sep 16 00:00:00 2026', 'KBUILD_BUILD_VERSION=0',
                       'M=' + str(source), 'NOSTDINC_FLAGS=' + ' '.join(includes), *config, *objects]
            done = subprocess.run(command, capture_output=True, text=True, env=env, timeout=300)
            log_path = OUT / f'kernel-mt76-{phase}-{enabled}.log'
            log = done.stdout + done.stderr
            log_path.write_text(log)
            assert done.returncode == 0 and not re.search(r'\b(?:warning|error):', log, re.I), log
            compiled = [object_info(source / name, name == 'npu.o') for name in objects]
            if enabled:
                assert ('synchronize_rcu' in compiled[-1]['deinit_relocations']) == (phase == 'after')
            rows.append(dict(kind='mt76', phase=phase, npu_enabled=enabled, command=command,
                             log=str(log_path.relative_to(ROOT)), log_sha256=sha(log_path), objects=compiled))
            print(json.dumps(dict(stage='kernel-mt76', phase=phase, npu_enabled=enabled)), flush=True)
    return rows


def fingerprints():
    paths = [Path(__file__), INIT, DEINIT, PROVIDER_HARNESS, RCU_HARNESS, SOURCE, HEADER, HELPERS,
             provider.OUT / 'control-v2-provider.json', provider.OUT / '928-net-airoha-npu-bidirectional-control.patch',
             kernel.OPENWRT / '.config', KERNEL / '.config', KERNEL / 'Module.symvers',
             KERNEL / 'include/generated/autoconf.h', KERNEL / 'include/generated/utsrelease.h',
             KERNEL / 'drivers/base/devres.c', KERNEL / 'kernel/irq/devres.c', KERNEL / 'kernel/irq/manage.c',
             KERNEL / 'include/linux/rcupdate.h', KERNEL / 'kernel/rcu/tree.c', KERNEL / 'kernel/workqueue.c']
    paths += list(SOURCE.parent.glob('*.h'))
    for module in (provider, preflight, kernel, q):
        paths.append(Path(module.__file__))
    return {**l1.inputs(), **{str(path.relative_to(ROOT)): sha(path) for path in paths}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-kernel', action='store_true')
    args = parser.parse_args()
    BUILD.mkdir(parents=True, exist_ok=True)
    before = fingerprints()
    p, m, patches = stage()
    result, readers = provider_cases(p), rcu_cases(m)
    mutations = mutants(p[1], m[1])
    checks = []
    for patch in patches:
        done = subprocess.run(['perl', str(KERNEL / 'scripts/checkpatch.pl'), '--strict', '--no-tree',
                              '--no-signoff', str(ROOT / patch['path'])], capture_output=True, text=True, timeout=30)
        check = done.stdout + done.stderr
        (OUT / (Path(patch['path']).stem + '-checkpatch.log')).write_text(check)
        assert done.returncode == 0 and '0 errors, 0 warnings, 0 checks' in check, check
        checks.append(check)
    compiled = [] if args.skip_kernel else kernel_objects(p, m, patches)
    assert fingerprints() == before
    derived_paths = list(BUILD.rglob('*.inc'))
    for row in compiled:
        if row['kind'] == 'provider':
            directory = BUILD / ('kernel-provider-' + row['phase'])
            derived_paths += [directory / name for name in ('airoha_npu.c', 'public.h', 'probe-0.c', 'probe-1.c', 'Makefile')]
        else:
            directory = BUILD / f"kernel-mt76-{row['phase']}-{row['npu_enabled']}" / 'mt76-2026.09.01~be5ce791'
            derived_paths += [directory / name for name in ('npu.c', 'mac80211.c', 'mt76.h', 'airoha_offload.h')]
    derived = {str(path.relative_to(ROOT)): sha(path) for path in derived_paths}
    output = OUT / ('host-lifetime-models.json' if args.skip_kernel else 'host-lifetime.json')
    output.write_text(json.dumps(dict(schema=1, inputs_before_after=before, derived=derived,
                        provider=result, rcu=readers, mutants=mutations, patches=patches, checkpatch=checks,
                        kernel_objects=compiled,
                        compilers=dict(native=execute(['clang', '--version']).splitlines()[0],
                                       kernel=execute([str(kernel.PREFIX) + 'gcc', '--version']).splitlines()[0]),
                        limits=['Framework IRQ/devres/work and RCU semantics are explicit models, not a loaded kernel or hardware race test.',
                                'No physical DMA drain is provided: queue cleanup still occurs with the independent DMA actor alive.',
                                'No provider/client V2 integration, source-lock/overlay, image, router, Wi-Fi or restricted-lane change.']), indent=2) + '\n')
    print(json.dumps(dict(provider_cases=[len(row['result']['cases']) for row in result],
                          rcu_cases=[len(row['result']['cases']) for row in readers], mutants=len(mutations),
                          objects=sum(len(row['objects']) for row in compiled), receipt_sha256=sha(output))))


if __name__ == '__main__':
    main()
