#!/usr/bin/env python3
"""Clean-link the pinned successor modules in a private, offline kernel overlay."""
import argparse
from contextlib import ExitStack
import fcntl
import json
import os
from pathlib import Path
import re
import resource
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from npu_ethernet_fit import inspect_linked
from npu_replay_proof import digest, path_under, read_pinned, require
from npu_world_stream_host import capture, inventory, save
import npu_storage_budget as storage
import npu_successor_sources as sources

ROOT = sources.ROOT
SCRATCH = ROOT / '.local/npu-build-scratch/native-c2'
STORE = '.local/npu-successor-modules'
BUILD_CONFIG = '.build/merged-openwrt/.config'
DRIVER = 'drivers/net/ethernet/airoha'
MODULES = ('airoha_npu.ko', 'mt76/mt76.ko', 'mt76/mt76-connac-lib.ko', 'mt76/mt7996/mt7996e.ko')
NEW_EDGES = {'airoha_npu_wlan_uses_checked_dma', 'airoha_npu_wlan_alloc_queue_mem'}
BWRAP = '.local/npu-bwrap-xino-20261021/bin/bwrap'
RUNNER_DIR = '.local/npu-rro-reset-target-20261023'
WRAPPER = RUNNER_DIR + '/make_gc_q1.sh'
PHASES = RUNNER_DIR + '/run_phases_q1.sh'
INSPECT = 'tests/npu/test_rro_reset_phased_modules.py'
SYMVERS = 'original-kernel.symvers'
CAP = 1536 << 20
RESERVE = 2 << 30
MAX_WRITTEN = 1 << 30
if not __debug__:
    raise RuntimeError('Linked successor verification requires Python assertions enabled')


def command(argv, *, timeout=45):
    return subprocess.check_output(argv, cwd=ROOT, text=True, timeout=timeout).strip()


def admission(scratch):
    require(scratch == path_under(ROOT / '.local', scratch, directory=True) and
            scratch.stat().st_dev != ROOT.stat().st_dev, 'Expected the native scratch mount')
    mount, = json.loads(command(['findmnt', '--json', '--target', scratch,
                                 '--output', 'source,fstype,uuid,options']))['filesystems']
    require(mount['fstype'] == 'ext4' and mount['uuid'] == 'b0b1bc48-d684-4090-a8cf-1ecb2939c36d'
            and {'rw', 'nosuid', 'nodev'} <= set(mount['options'].split(',')), 'Unexpected scratch mount')
    cgroup = Path('/proc/self/cgroup').read_text().strip().split('::', 1)[1]
    limits = Path('/sys/fs/cgroup') / cgroup.lstrip('/')
    require((limits / 'memory.max').read_text().strip() == str(CAP) and
            (limits / 'memory.swap.max').read_text().strip() == '0' and
            os.getpriority(os.PRIO_PROCESS, 0) >= 19, 'Run with the admitted one-job memory and priority limits')
    guest = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                     if line.startswith('MemAvailable:'))) * 1024
    windows = int(command(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
        '[Math]::Min([long](Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory * 1024,'
        ' [long](Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory).AvailableBytes)']))
    d = storage.observe(ROOT)
    c = storage.windows_query('W1700K-BuildScratch-20261021')
    require(d['host']['drive'] == 'D' and d['host']['vhd_path'] == r'D:\WSL\Ubuntu\ext4.vhdx' and
            c['drive'] == 'C' and c['vhd_path'] ==
            r'C:\Users\captain\W1700K-BuildScratch\2026-10-21-native-wsl-v1\distro\ext4.vhdx',
            'Scratch or source backing volume differs')
    space = shutil.disk_usage(scratch)
    budgets = {
        'C': storage.evaluate(dict(host=c, guest=dict(free_bytes=space.free, total_bytes=space.total)),
            dict(snapshot=0, cache=0, overlay=MAX_WRITTEN, output=128 << 20, margin=RESERVE)),
        'D': storage.evaluate(d, dict(snapshot=0, cache=0, overlay=0, output=128 << 20, margin=RESERVE)),
    }
    require(min(windows, guest) >= CAP + RESERVE and all(row['passed'] for row in budgets.values()),
            'Not enough admitted memory or disk for the clean module link')
    return dict(mount=mount, budgets=budgets, guest_available=guest, windows_available=windows,
                memory_max=CAP, swap_max=0, jobs=1, hardware=False)


def identify(root, path):
    return {'sha256': digest(path_under(root, path)), 'mode': (root / path).stat().st_mode & 0o777}


def stage_inputs(directory, authority, contract):
    for group, target in (('kernel', 'provider-source'), ('mt76', 'mt76')):
        for name, pin in contract['sources'][group].items():
            source = path_under(authority, f'{sources.MERGED}/{group}-merged/{name}')
            require(digest(source) == pin, f'Successor {group} source changed: {name}')
            copied = directory / target / name
            sources.handoff.copy_source(source, copied)
            require(digest(copied) == pin, f'Private {group} copy differs: {name}')
    return {name: identify(directory / 'mt76', name) for name in contract['sources']['mt76']}


def clear_outputs(kernel):
    driver = path_under(kernel, DRIVER, directory=True)
    suffixes = ('.o', '.a', '.ko', '.mod', '.mod.c', '.su', '.cmd', '.o.d')
    removed = []
    for path in sorted(driver.rglob('*')):
        if path.name.endswith(suffixes) or path.name == 'modules.order':
            require(path_under(driver, path) == path, 'Unexpected alias among prior driver objects')
            path.unlink()
            removed.append(path.relative_to(kernel).as_posix())
    require(all(f'{DRIVER}/{name}' in removed for name in (MODULES[0], 'airoha-eth.ko')),
            'Did not clear both retained driver modules')
    return removed


def check_edges(inner):
    require(NEW_EDGES <= set(inner['provider']['exports']) and
            NEW_EDGES <= set(inner['modules']['mt76.ko']['imports']),
            'Two successor queue-ownership edges did not link')


def in_overlay(directory):
    from npu_isolated_world import namespaces
    from test_current_provider_module import module

    context = json.loads((directory / 'successor.json').read_bytes())
    kernel = Path(context['kernel'])
    mounts = Path('/proc/self/mountinfo').read_text().splitlines()
    require(os.statvfs(ROOT).f_flag & os.ST_RDONLY and
            any(row.split()[4] == str(kernel) and ' - overlay ' in row for row in mounts) and
            all(node != context['parent_namespaces'][name] for name, node in namespaces().items()),
            'Kernel and network namespace isolation is required')
    require(digest(ROOT / sources.SOURCE_LOCK) == context['source_lock_sha256'],
            'Isolated compilation did not select the successor lock')
    removed = clear_outputs(kernel)
    print(json.dumps(dict(phase='clean-link-provider-and-mt76', removed_prior_targets=len(removed))), flush=True)
    subprocess.run(['/bin/sh', ROOT / PHASES, ROOT / INSPECT, directory],
                   stdin=subprocess.DEVNULL, check=True, timeout=1860)
    inner = json.loads((directory / 'inner-result.json').read_bytes())
    check_edges(inner)
    spec = json.loads((directory / 'phase-control/provider-command.json').read_bytes())
    require(spec['command'][-1] == f'{DRIVER}/{MODULES[0]}', 'Unexpected provider Kbuild target')
    ethernet = path_under(kernel, DRIVER, directory=True) / 'airoha-eth.ko'
    require(not ethernet.exists(), 'Old Ethernet object was not cleared')
    with (directory / 'ethernet.log').open('x') as log:
        done = subprocess.run([*spec['command'], f'{DRIVER}/{ethernet.name}'], timeout=180,
                              env=spec['environment'], stdout=log, stderr=subprocess.STDOUT,
                              stdin=subprocess.DEVNULL)
    require(done.returncode == 0, 'Ethernet link failed: ' + (directory / 'ethernet.log').read_text()[-2000:])
    eth = module(ethernet)
    bindings = inspect_linked(ethernet.read_bytes(), context['release'], with_qdma=True)
    require(eth['vermagic'] == inner['provider']['vermagic'] and
            digest(kernel / DRIVER / MODULES[0]) == inner['provider']['sha256'], 'Linked kernel modules diverged')
    require(all(digest(path_under(kernel, name)) == expected for name, expected in
                context['kernel_sources'].items()), 'Prepared kernel postimages changed during linking')
    sources.handoff.copy_source(ethernet, directory / ethernet.name)
    save(directory / 'overlay-proof.json', dict(removed_prior_targets=removed, ethernet=eth,
         ethernet_owner_definitions=bindings['definitions'], network_isolated=True, kernel_upper_only=True,
         fresh_provider=True, fresh_mt76=True, fresh_ethernet=True))


def verify_parent(args, contract):
    parent_path = path_under(ROOT / '.local', ROOT / args.parent_producer)
    parent, parent_pin = read_pinned(parent_path, contract['parent_producer_sha256'])
    seal_path = path_under(ROOT / '.local/npu-qualified-images', ROOT / args.baseline_seal)
    seal, seal_pin = read_pinned(seal_path, args.baseline_seal_sha256)
    require(seal['format'] == 'w1700k-offline-sealed-fit-v1' and seal['producer_sha256'] == parent_pin and
            seal['source_lock_sha256'] == contract['parent_lock_sha256'] and
            digest(path_under(seal_path.parent, seal['image'])) == seal['image_sha256'],
            'The sealed baseline does not match the successor parent')
    context, pin = read_pinned(path_under(parent_path.parent, 'context.json'), args.parent_context_sha256)
    checks = (BWRAP, WRAPPER, PHASES, INSPECT, 'tests/npu/test_rro_reset_modules.py',
              'tests/npu/test_current_mt76_modules.py', 'tests/npu/test_current_provider_module.py')
    tools = {name: parent['inputs'][name] for name in checks}
    require(all(digest(path_under(ROOT, name)) == expected for name, expected in tools.items()),
            'Retained linker recipes or launcher differ')
    return context, pin, seal_pin, tools


def output_name(root, name):
    require(re.fullmatch('[a-z][a-z0-9-]{0,39}', name), 'Invalid new successor link name')
    selected = root / name
    require(not os.path.lexists(selected), 'Link output already exists')
    return selected


def publish(authority, destination, directory, record, contract, pin):
    destination.parent.mkdir(exist_ok=True)
    require(path_under(authority, destination.parent, directory=True) == destination.parent,
            'Producer output parent alias')
    names = (*MODULES, 'airoha-eth.ko')
    with TemporaryDirectory(prefix='.link-', dir=destination.parent) as folder:
        stage = Path(folder)
        for name in names:
            src, dst = path_under(directory, name), stage / name
            sources.handoff.copy_source(src, dst)
            dst.chmod(0o444)
        save(stage / 'result.json', record)
        staged_receipt = stage / 'result.json'
        staged_receipt.chmod(0o444)
        receipt_pin = digest(staged_receipt)
        sources.verify_producer(authority, contract, pin, staged_receipt, receipt_pin)
        require(digest(stage / 'airoha-eth.ko') == record['overlay_proof']['ethernet']['sha256'],
                'Linked Ethernet copy drift')
        destination.mkdir(exist_ok=False)
        for name in (*names, 'result.json'):
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(stage / name, target, follow_symlinks=False)
    return destination / 'result.json', receipt_pin


def link(args):
    from npu_isolated_world import namespaces

    require(os.getuid() == 1000, 'Link as the unprivileged workspace user')
    authority = path_under(ROOT / '.local', ROOT / args.authority, directory=True)
    contract, pin, lock = sources.verify_authority(authority, args.contract_sha256)
    previous, previous_pin, seal_pin, tools = verify_parent(args, contract)
    build = path_under(ROOT / '.build', ROOT / lock['build_directory'], directory=True)
    kernel = sources.kernel_path(build, lock['kernel'])
    mt76 = sources.mt76_path(build, lock['mt76'])
    require(Path(previous['kernel']) == kernel and Path(previous['build']) == build and
            digest(path_under(ROOT, BUILD_CONFIG)) == contract['config_sha256'] and
            all(digest(path_under(kernel, k)) == h for k, h in previous['kernel_configs'].items()),
            'Retained prepared kernel or configuration differs')
    original = path_under(kernel, 'Module.symvers')
    require(digest(original) == args.original_symvers_sha256, 'Retained dependency symbols differ')
    directory = output_name(SCRATCH, args.name)
    destination = output_name(authority / STORE, args.name)
    with ExitStack() as held:
        for lock_path in (ROOT / '.local/npu-storage-budget.lock', SCRATCH / '.world-storage.lock'):
            fd = os.open(lock_path, os.O_RDWR | os.O_NOFOLLOW)
            held.callback(os.close, fd)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        capacity = admission(SCRATCH)
        directory.mkdir()
        save(directory / 'admission.json', capacity)
        print(json.dumps(dict(phase='inventory-retained-kernel-and-mt76', admitted=True)), flush=True)
        baseline = {label: capture(path, directory / f'{label}-before.jsonl')
                    for label, path in (('kernel', kernel), ('mt76', mt76))}
        mt76_inputs = stage_inputs(directory, authority, contract)
        sources.handoff.copy_source(original, directory / SYMVERS)
        for name in ('kernel-upper', 'kernel-work', 'tmp'):
            (directory / name).mkdir()
        save(directory / 'context.json', {k: previous[k] for k in
             ('kernel', 'build', 'old_provider_sha256', 'timestamp', 'kernel_configs')} |
             dict(provider_files=list(contract['sources']['kernel']), mt76_sources=mt76_inputs))
        save(directory / 'successor.json', dict(kernel=str(kernel), release=lock['kernel'],
             kernel_sources=contract['sources']['kernel'],
             source_lock_sha256=contract['source_lock_sha256'], parent_namespaces=namespaces()))
        argv = [ROOT / BWRAP, '--unshare-all', '--ro-bind', '/', '/',
                '--bind', directory, directory, '--overlay-src', kernel, '--overlay',
                directory / 'kernel-upper', directory / 'kernel-work', kernel,
                '--ro-bind', authority / sources.SOURCE_LOCK, ROOT / sources.SOURCE_LOCK,
                '--ro-bind', authority / 'firmware/npu', ROOT / 'firmware/npu',
                '--bind', directory / 'tmp', '/tmp', '--ro-bind', '/usr/bin/make', '/tmp/w1700k-original-make',
                '--ro-bind', ROOT / WRAPPER, '/usr/bin/make', '--proc', '/proc', '--dev', '/dev',
                '--new-session', '--die-with-parent', '--clearenv',
                '--setenv', 'PATH', '/usr/local/bin:/usr/bin:/bin',
                '--setenv', 'PYTHONPATH', ':'.join(str(ROOT / p) for p in
                    ('tools', 'tests/npu', '.local/npu-reset/python-lib')),
                '/usr/bin/python3', '-u', '-B', Path(__file__).resolve(), '--inner', directory]
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_FSIZE, (256 << 20, 256 << 20))
        with (directory / 'controller.log').open('x') as log:
            result = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    timeout=2100)
        require(result.returncode == 0, 'Private module link failed: ' +
                (directory / 'controller.log').read_text()[-4500:])
        print(json.dumps(dict(phase='reverify-retained-kernel-and-mt76', linked=True)), flush=True)
        require(inventory(kernel) == baseline['kernel'] and inventory(mt76) == baseline['mt76'] and
                all(digest(path_under(ROOT, key)) == value for key, value in tools.items()),
                'A retained kernel input or build tool changed during the link')
        sources.verify_authority(authority, pin)
        require(sum(p.stat().st_size for p in directory.rglob('*') if p.is_file()) <= MAX_WRITTEN,
                'Module link exceeded its admitted scratch budget')
        inner = json.loads((directory / 'inner-result.json').read_bytes())
        proof = json.loads((directory / 'overlay-proof.json').read_bytes())
        record = dict(passed=True, returncode=0, originals_unchanged=True, inner=inner,
                      inputs=contract['files'] | {sources.CONTRACT: pin}, hardware=False,
                      source_lock_sha256=contract['source_lock_sha256'], source_contract_sha256=pin,
                      parent_context_sha256=previous_pin, baseline_seal_sha256=seal_pin,
                      retained_original_symvers_sha256=args.original_symvers_sha256,
                      lower_inventories=baseline, tools=tools, overlay_proof=proof,
                      module_loaded=False, image_built=False)
        receipt, receipt_pin = publish(authority, destination, directory, record, contract, pin)
    print(json.dumps(dict(receipt=str(receipt), receipt_sha256=receipt_pin,
                         linked_modules=4, scratch_linked_ethernet=True, hardware=False)), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inner', type=Path)
    parser.add_argument('--name')
    for name in ('authority', 'parent-producer', 'baseline-seal'):
        parser.add_argument('--' + name, type=Path)
    for name in ('contract', 'baseline-seal', 'parent-context', 'original-symvers'):
        parser.add_argument('--' + name + '-sha256')
    args = parser.parse_args()
    try:
        if args.inner is not None:
            in_overlay(path_under(SCRATCH, args.inner, directory=True))
        else:
            require(all(value for key, value in vars(args).items() if key != 'inner'),
                    'Link name, authority, exact parent context and baseline seal pins are required')
            link(args)
    except (OSError, AssertionError, KeyError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f'successor module link: {error}\n')


if __name__ == '__main__':
    main()
