#!/usr/bin/env python3
"""Link checked IRQ modules in a private kernel overlay;never load or flash."""
import argparse
import errno
import json
import os
from pathlib import Path
import re
import resource
import shutil
import subprocess
import sys
import time

from test_current_provider_module import ROOT, WORK, DRIVER, PUBLIC, digest, inventory, module
from test_current_mt76_modules import source_copy, symvers, checked_union, object_symbols, dependency_rows

sys.path.insert(0, str(ROOT / 'tools'))
import npu_storage_budget as storage


def save(path, value):
    with path.open('x') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')


def guard(pid):
    proc = Path('/proc') / str(pid)
    matches = []
    for fd in proc.joinpath('fd').iterdir():
        if str(fd.readlink()) == str(ROOT / '.local/npu-storage-budget.lock'):
            matches += [line for line in proc.joinpath('fdinfo', fd.name).read_text().splitlines()
                if ' FLOCK ' in line and (' WRITE ' + str(pid) + ' ') in line]
    assert len(matches) == 1, 'original-native-guard-not-held'
    return dict(pid=pid, start_ticks=proc.joinpath('stat').read_text().split()[21], lock=matches[0])


def inner(directory):
    assert os.getuid() == 1000
    context = json.loads((directory / 'context.json').read_text())
    kernel, build = (Path(context[name]) for name in ('kernel', 'build'))
    mounts = Path('/proc/self/mountinfo').read_text().splitlines()
    assert any(line.split()[4] == str(kernel) and ' - overlay ' in line for line in mounts)
    try:
        fd = os.open(ROOT / '.checked-irq-write-probe', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except OSError as error:
        assert error.errno == errno.EROFS
    else:
        os.close(fd)
        raise AssertionError('original-workspace-is-writable')
    lock = json.loads((ROOT / 'firmware/source-lock.json').read_text())
    release = lock['kernel']
    patchroot = directory / 'provider-source'
    for name in context['provider_files']:
        target = kernel / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(patchroot / name, target)
    for row in lock['component_sources']:
        name = row['destination'].removeprefix('target/linux/airoha/files-6.18/')
        target = kernel / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / row['source'], target)
    prefix = build / 'staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin/aarch64-openwrt-linux-musl-'
    compiler = Path(str(prefix) + 'gcc')
    environment = dict(os.environ, STAGING_DIR=str(build / 'staging_dir/target-aarch64_cortex-a53_musl'),
        PATH=str(compiler.parent) + ':' + str(build / 'staging_dir/host/bin') + ':/usr/bin:/bin',
        LANG='C', LC_ALL='C', TZ='UTC', KCONFIG_NOSILENTUPDATE='1')
    environment.pop('MAKEFLAGS', None)
    environment.pop('MFLAGS', None)
    version = subprocess.check_output([str(compiler), '--version'], env=environment, text=True).splitlines()[0]
    assert 'CONFIG_CC_VERSION_TEXT="' + version + '"' in (kernel / '.config').read_text()
    deadline = time.monotonic() + 1800
    def make(command, name):
        print(json.dumps(dict(phase=name, jobs=1)), flush=True)
        with (directory / (name + '.log')).open('x') as stream:
            result = subprocess.run(command, env=environment, stdin=subprocess.DEVNULL,
                stdout=stream, stderr=subprocess.STDOUT, timeout=max(1, deadline - time.monotonic()))
        assert result.returncode == 0, (directory / (name + '.log')).read_text()[-5000:]
    common = ['make', '-C', str(kernel), '-j1', 'ARCH=arm64', 'CROSS_COMPILE=' + str(prefix),
        'KERNELRELEASE=' + release, 'KBUILD_BUILD_USER=', 'KBUILD_BUILD_HOST=', 'KBUILD_BUILD_VERSION=0',
        'KBUILD_BUILD_TIMESTAMP=' + context['timestamp'], 'KBUILD_HAVE_NLS=no',
        'KBUILD_HOSTLDFLAGS=-L' + str(build / 'staging_dir/host/lib'),
        'KCFLAGS=-fno-caller-saves -fstack-usage', 'V=0']
    make(common + [DRIVER + '/airoha_npu.ko'], 'provider')
    provider = module(kernel / DRIVER / 'airoha_npu.ko')
    exports = set(re.findall(r'EXPORT_SYMBOL(?:_GPL)?\(\s*(\w+)\s*\)', (patchroot / DRIVER / 'airoha_npu.c').read_text()))
    assert set(provider['exports']) == exports
    assert provider['sha256'] != context['old_provider_sha256']
    shutil.copy2(kernel / DRIVER / 'airoha_npu.ko', directory / 'airoha_npu.ko')
    base = symvers((kernel / 'Module.symvers').read_text())
    assert set(provider['imports']) <= base.keys()
    assert {key for key, row in base.items() if Path(row[2]).name == 'airoha_npu'} == exports
    source = directory / 'mt76'
    prepared = kernel.parent
    mac = prepared / 'symvers/mac80211.symvers'
    original = symvers((directory / 'original-kernel.symvers').read_text())
    mac_index = symvers(mac.read_text())
    available = checked_union(base, mac_index)
    include = build / 'staging_dir/target-aarch64_cortex-a53_musl/usr/include'
    gcc_include = subprocess.check_output([str(compiler), '-print-file-name=include'], env=environment, text=True).strip()
    flags = ['-nostdinc', '-isystem', gcc_include, '-I' + str(source)]
    for name in ('mac80211-backport/uapi', 'mac80211-backport', 'mac80211/uapi', 'mac80211'):
        flags.append('-I' + str(include / name))
    flags += ['-include', 'backport/autoconf.h', '-include', 'backport/backport.h',
        '-DCONFIG_MAC80211_MESH', '-DCONFIG_MT76_NPU', '-DCONFIG_MT7996_NPU']
    mtcommon = common + ['M=' + str(source), 'CONFIG_MT76_CONNAC_LIB=m', 'CONFIG_MT7996E=m',
        'CONFIG_MT76_NPU=y', 'CONFIG_MT7996_NPU=y', 'NOSTDINC_FLAGS=' + ' '.join(flags)]
    make(mtcommon + ['KBUILD_EXTRA_SYMBOLS=' + str(mac), 'mt76.o', 'mt76-connac-lib.o', 'mt7996/mt7996e.o'], 'consumers-compile')
    combined = [object_symbols(source / name) for name in ('mt76.o', 'mt76-connac-lib.o', 'mt7996/mt7996e.o')]
    own = set().union(*(data['exports'] for data in combined))
    imports = set().union(*(data['imports'] for data in combined))
    extra = dependency_rows(imports - available.keys() - own - {'__this_module', '_GLOBAL_OFFSET_TABLE_'}, original)
    module_dir = build / ('staging_dir/target-aarch64_cortex-a53_musl/root-airoha/lib/modules/' + release)
    dependencies = {}
    for owner in sorted({row[2] for row in extra.values()} | {mac_index[name][2] for name in imports & mac_index.keys()}):
        name = Path(owner).name
        data = module(module_dir / (name + '.ko'))
        assert data['vermagic'] == provider['vermagic']
        expected = {key for key, row in {**extra, **mac_index}.items() if row[2] == owner}
        assert set(data['exports']) == expected
        dependencies[name] = data
    extra_path = directory / 'dependencies.symvers'
    with extra_path.open('x') as stream:
        stream.write(''.join('\t'.join(row) + '\n' for row in extra.values()))
    make(mtcommon + ['KBUILD_EXTRA_SYMBOLS=' + str(mac) + ' ' + str(extra_path), 'modules'], 'consumers-link')
    linked = {name: module(source / name) for name in ('mt76.ko', 'mt76-connac-lib.ko', 'mt7996/mt7996e.ko')}
    available = checked_union(available, extra, symvers((source / 'Module.symvers').read_text()))
    for name, data in linked.items():
        assert data['vermagic'] == provider['vermagic'] and set(data['imports']) <= available.keys()
        assert '__this_module' in object_symbols(source / name)['defined']
    checked = {'mt76_npu_start_irqs', 'mt76_npu_rearm_irq', 'mt76_npu_io_admit', 'mt76_npu_irq_error', 'mt76_npu_disable_irqs'}
    assert checked <= set(linked['mt76.ko']['exports'])
    assert (checked - {'mt76_npu_io_admit'}) <= set(linked['mt7996/mt7996e.ko']['imports'])
    for name, expected in context['kernel_configs'].items():
        assert digest(kernel / name) == expected
    for name in context['provider_files']:
        assert digest(kernel / name) == digest(patchroot / name)
    for row in lock['component_sources']:
        name = row['destination'].removeprefix('target/linux/airoha/files-6.18/')
        assert digest(kernel / name) == row['sha256']
    source_after = inventory(source)
    for name, expected in context['mt76_sources'].items():
        assert source_after[name] == expected
    save(directory / 'inner-result.json', dict(passed=True, compiler=version, provider=provider,
        modules=linked, dependencies=dependencies, checked_edges=sorted(checked), jobs=1,
        current_checked_header_compiled=True, module_loaded=False, image_built=False, hardware=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--shared-guard-pid', type=int)
    parser.add_argument('--inner', action='store_true')
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    directory = ROOT / '.local/npu-checked-irq-modules' / args.name
    if args.inner:
        inner(directory)
        return
    assert os.getuid() == 0 and args.shared_guard_pid and not directory.exists()
    before_guard = guard(args.shared_guard_pid)
    errors = []
    for attempt in range(3):
        try:
            observation = storage.observe(ROOT)
            break
        except ValueError as error:
            if str(error) != 'Windows-backing-volume-query-failed' or attempt == 2:
                raise
            errors.append(str(error))
            time.sleep(1)
    capacity = storage.evaluate(observation, dict(snapshot=0, cache=0, overlay=268435456,
        output=1073741824, margin=2147483648))
    assert capacity['passed']
    directory.mkdir(parents=True)
    save(directory / 'capacity.json', dict(capacity=capacity, errors=errors, existing_guard=before_guard,
        original_native_future_output_fully_rebudgeted=True, independent_lock_owner=False))
    lock = json.loads((ROOT / 'firmware/source-lock.json').read_text())
    build = ROOT / lock['build_directory']
    kernel = build / 'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581' / ('linux-' + lock['kernel'])
    print(json.dumps(dict(phase='hash-protected-kernel', capacity_passed=True)), flush=True)
    before = inventory(kernel)
    save(directory / 'kernel-before.json', before)
    mtold = kernel.parent / 'mt76-2026.09.01~01367e60'
    mtbefore = inventory(mtold)
    save(directory / 'mt76-before.json', mtbefore)
    tracked = [ROOT / 'firmware/source-lock.json', Path(__file__).resolve(),
        Path(__file__).with_name('test_current_provider_module.py'), Path(__file__).with_name('test_current_mt76_modules.py')]
    provider_files = []
    for label, relative in (('kernel', 'target/linux/airoha/patches-6.18/999-w1700k-integrated-npu.patch'),
                            ('mt76', 'package/kernel/mt76/patches/900-w1700k-integrated-npu.patch')):
        path = ROOT / 'firmware/overlay/openwrt' / relative
        assert digest(path) == next(row['sha256'] for row in lock['openwrt']['changed_files'] if row['path'] == relative)
        tracked.append(path)
        if label == 'kernel':
            target = directory / 'provider-source'
            shutil.copytree(WORK / 'kernel-upstream', target)
            result = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(path)],
                cwd=target, capture_output=True, text=True)
            (directory / 'provider-patch.log').write_text(result.stdout + result.stderr)
            assert result.returncode == 0 and 'fuzz' not in result.stdout.lower()
            provider_files = re.findall(r'^\+\+\+ b/([^\n]+)$', path.read_text(), re.M)
            for name in provider_files:
                assert digest(target / name) == digest(WORK / 'kernel-merged' / name)
                tracked.append(WORK / 'kernel-merged' / name)
        else:
            _, source_before, log = source_copy(WORK / 'mt76-upstream', WORK / 'mt76-merged', path, directory / 'mt76')
            (directory / 'mt76-patch.log').write_text(log)
            assert 'fuzz' not in log.lower()
            tracked.extend(WORK / 'mt76-merged' / name for name in source_before)
    tracked += [build / '.config', build / 'bin/targets/airoha/an7581/openwrt-airoha-an7581-gemtek_w1700k-ubi-squashfs-sysupgrade.itb']
    inputs = {str(path.relative_to(ROOT)): digest(path) for path in tracked}
    for row in lock['component_sources']:
        assert digest(ROOT / row['source']) == row['sha256']
        inputs[row['source']] = row['sha256']
    for name in ('kernel-upper', 'kernel-work', 'tmp'):
        (directory / name).mkdir()
    shutil.copy2(kernel / 'Module.symvers', directory / 'original-kernel.symvers')
    timestamp = subprocess.check_output(['runuser', '-u', 'captain', '--', 'git', '-C', str(ROOT),
        'show', '-s', '--format=%cI', 'HEAD'], text=True).strip()
    save(directory / 'context.json', dict(kernel=str(kernel), build=str(build), provider_files=provider_files,
        old_provider_sha256=digest(kernel / DRIVER / 'airoha_npu.ko'), mt76_sources=source_before,
        kernel_configs={name: digest(kernel / name) for name in ('.config', 'include/generated/autoconf.h',
            'include/generated/utsrelease.h')}, timestamp=timestamp))
    for path in (directory, *directory.rglob('*')):
        os.chown(path, 1000, 1000, follow_symlinks=False)
    command = ['runuser', '-u', 'captain', '--', 'bwrap', '--unshare-all', '--ro-bind', '/', '/',
        '--bind', str(directory), str(directory), '--overlay-src', str(kernel),
        '--overlay', str(directory / 'kernel-upper'), str(directory / 'kernel-work'), str(kernel),
        '--bind', str(directory / 'tmp'), '/tmp', '--proc', '/proc', '--dev', '/dev',
        '--new-session', '--die-with-parent', '/usr/bin/python3', '-u', '-B', str(Path(__file__).resolve()),
        '--name', args.name, '--inner']
    environment = dict(os.environ, PYTHONPATH=str(ROOT / '.local/npu-reset/python-lib') + ':' + str(ROOT / 'tests/npu'))
    def limits():
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_FSIZE, (268435456, 268435456))
    with (directory / 'controller.log').open('x') as stream:
        result = subprocess.run(command, env=environment, stdout=stream, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, timeout=2100, preexec_fn=limits)
    print(json.dumps(dict(inner_returncode=result.returncode, phase='verify-protected-kernel')), flush=True)
    assert inventory(kernel) == before and inventory(mtold) == mtbefore
    assert all(digest(ROOT / name) == expected for name, expected in inputs.items())
    after_guard = guard(args.shared_guard_pid)
    assert after_guard['start_ticks'] == before_guard['start_ticks']
    written = sum(path.stat().st_size for path in directory.rglob('*') if path.is_file())
    assert written < 268435456, ('overlay-budget-exceeded', written)
    save(directory / 'result.json', dict(passed=result.returncode == 0, returncode=result.returncode,
        inputs=inputs, inner=json.loads((directory / 'inner-result.json').read_text()) if result.returncode == 0 else None,
        original_kernel_entries=len(before), original_mt76_entries=len(mtbefore), originals_unchanged=True,
        original_native_jobs_modified_or_paused=False, guard_before=before_guard, guard_after=after_guard,
        actual_output_bytes=written, budget=capacity, command=command,
        limits=['Actual pinned AArch64 final links,not module load or fresh dependencies/vmlinux/world/image.',
            'Read-only original workspace with a writable private kernel overlay and mt76 source copy.',
            'No physical IRQ,DMA drain,ownership retirement,router/radio/client or performance qualification.']))
    print(json.dumps(dict(passed=result.returncode == 0, output_bytes=written,
        receipt_sha256=digest(directory / 'result.json'))), flush=True)
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
