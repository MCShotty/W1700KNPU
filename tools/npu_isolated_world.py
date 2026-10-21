#!/usr/bin/env python3
"""Build/inspect offline in private overlays;never mutate the prepared build."""
import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / '.build/merged-openwrt'
WORK = ROOT / '.local/merge-nonoc-20260923'
STORE = ROOT / '.local/npu-isolated-world'
LINKER_PREFIX = ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21'
CACHE = ROOT / '.build/openwrt/dl'


def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def tree_state(root):
    result = {}
    for base, dirs, files in os.walk(root, followlinks=False):
        paths = [Path(base)] + [Path(base) / name for name in sorted(dirs + files)]
        for path in paths:
            name = str(path.relative_to(root))
            if name in result: continue
            info = path.lstat()
            row = dict(mode=stat.S_IMODE(info.st_mode), uid=info.st_uid, gid=info.st_gid)
            if stat.S_ISLNK(info.st_mode): row.update(kind='link', target=os.readlink(path))
            elif stat.S_ISREG(info.st_mode): row.update(kind='file', sha256=digest(path))
            elif stat.S_ISDIR(info.st_mode): row.update(kind='directory')
            else: raise AssertionError(('special-build-input', name, info.st_mode))
            result[name] = row
    return result


def snapshot(receipt_path):
    receipt_path = receipt_path.resolve()
    assert receipt_path.is_relative_to(ROOT / '.local/npu-validation-capsules')
    record = json.loads(receipt_path.read_bytes())
    assert record['format'] == 'npu-validation-capsule-v1' and record['preservation_verified'] is True
    frozen = Path(record['input_root']).resolve()
    assert frozen == receipt_path.parent / 'root' and record['source_root'] == str(ROOT)
    paths = list(frozen.rglob('*'))
    assert not any(path.is_symlink() for path in paths), 'snapshot-symlink'
    names = {str(path.relative_to(frozen)) for path in paths if path.is_file()}
    assert names == record['files'].keys(), 'unexpected-snapshot-inputs'
    for name, expected in record['files'].items():
        path = frozen / name
        assert path.resolve().is_relative_to(frozen) and not path.is_symlink()
        assert digest(path) == expected and not path.stat().st_mode & 0o222, ('snapshot-input-drift', name)
    assert digest(frozen / 'tools/npu_isolated_world.py') == digest(Path(__file__))
    assert all((frozen / path.relative_to(ROOT)).is_dir() for path in (BUILD,WORK,CACHE))
    return frozen, record


def linker_input(frozen, record):
    name = str((LINKER_PREFIX / 'bin/ld.lld').relative_to(ROOT))
    assert name in record['files'], ('missing-frozen-linker', name)
    path = frozen / name
    assert path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(frozen.resolve())
    mode = path.stat().st_mode
    assert mode & 0o111 and not mode & 0o222, ('linker-not-readonly-executable', name)
    assert digest(path) == record['files'][name], ('frozen-linker-drift', name)
    return dict(path=name, sha256=record['files'][name])


def cache_manifest(directory):
    assert directory.is_dir() and not directory.is_symlink(), ('missing-frozen-download-cache',str(directory))
    files = {}
    for path in sorted(directory.rglob('*')):
        mode = path.lstat().st_mode
        assert stat.S_ISREG(mode) or stat.S_ISDIR(mode), ('unsafe-cache-node',str(path))
        if stat.S_ISREG(mode): files[str(path.relative_to(directory))] = digest(path)
    encoded = json.dumps(files,sort_keys=True,separators=(',',':')).encode()
    return files,hashlib.sha256(encoded).hexdigest()


def download_cache_input(frozen, record):
    files,manifest_sha256 = cache_manifest(frozen / CACHE.relative_to(ROOT))
    prefix = str(CACHE.relative_to(ROOT)) + '/'
    declared = {name.removeprefix(prefix):value for name,value in record['files'].items() if name.startswith(prefix)}
    assert files and files == declared, 'download-cache-input-drift'
    release = json.loads((frozen / 'firmware/source-lock.json').read_bytes())['kernel']
    assert re.fullmatch(r'\d+\.\d+\.\d+',release)
    minor = '.'.join(release.split('.')[:2])
    recipe = str(BUILD.relative_to(ROOT) / ('target/linux/generic/kernel-' + minor))
    assert recipe in record['files'] and digest(frozen / recipe) == record['files'][recipe], 'missing-kernel-hash-recipe'
    hashes = re.findall(r'^LINUX_KERNEL_HASH-' + re.escape(release) + r'[ \t]*=[ \t]*([0-9a-f]{64})[ \t]*$',
        (frozen / recipe).read_text(),re.M)
    archive = 'linux-' + release + '.tar.xz'
    assert len(hashes) == 1 and files.get(archive) == hashes[0], 'kernel-cache-recipe-hash-mismatch'
    return dict(file_count=len(files),manifest_sha256=manifest_sha256,kernel_archive=archive,
        kernel_archive_sha256=hashes[0],kernel_recipe=recipe,kernel_recipe_sha256=record['files'][recipe])


def stage_download_cache(build, cache, expected):
    source,source_sha256 = cache_manifest(cache)
    assert len(source) == expected['file_count'] and source_sha256 == expected['manifest_sha256'], 'cache-stage-source-drift'
    target = build / 'dl'
    assert target.is_symlink() and os.readlink(target) == str(cache), 'unexpected-private-dl-link'
    assert not cache.resolve().is_relative_to(build.resolve()), 'cache-inside-build'
    target.unlink()
    shutil.copytree(cache,target)
    for path in (target,*target.rglob('*')):
        assert not path.is_symlink()
        path.chmod(stat.S_IMODE(path.stat().st_mode) | (0o700 if path.is_dir() else 0o600))
    assert cache_manifest(target) == (source,source_sha256), 'private-download-cache-copy-drift'
    assert cache_manifest(cache) == (source,source_sha256), 'source-download-cache-changed'
    return dict(files_copied=len(source),manifest_sha256=source_sha256,
        private_dl_replaced_symlink=True,source_cache_contents_unchanged=True)


def command(frozen, directory, name, context, probe):
    return ['bwrap', '--unshare-all', '--ro-bind', '/', '/', '--ro-bind', str(frozen), str(ROOT),
        '--overlay-src', str(BUILD), '--overlay', str(directory / 'build-upper'), str(directory / 'build-work'), str(BUILD),
        '--overlay-src', str(frozen / WORK.relative_to(ROOT)), '--overlay', str(directory / 'log-upper'),
        str(directory / 'log-work'), str(WORK), '--bind', str(directory / 'tmp'), '/tmp',
        '--proc', '/proc', '--dev', '/dev', '--new-session', '--die-with-parent', '--clearenv',
        '--setenv', 'PATH', '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
        '--setenv', 'HOME', str(BUILD / '.isolated-home'), '--setenv', 'TMPDIR', '/tmp',
        '--setenv', 'XDG_CACHE_HOME', str(BUILD / '.isolated-home/.cache'),
        '--setenv', 'CCACHE_DIR', str(BUILD / '.isolated-ccache'), '--setenv', 'LANG', 'C',
        '--setenv', 'LC_ALL', 'C', '--setenv', 'TZ', 'UTC', '--setenv', 'PYTHONPATH',
        str(ROOT / '.local/npu-reset/python-lib') + ':' + str(ROOT / 'tools') + ':' + str(ROOT / 'tests/npu'),
        '/usr/bin/python3', '-u', '-B', str(ROOT / 'tools/npu_isolated_world.py'), 'inner',
        '--name', name, '--context', json.dumps(context), *(['--probe-only'] if probe else [])]


def identity(path):
    info = path.stat()
    return [info.st_dev, info.st_ino]


def namespaces():
    return {name:str(Path('/proc/self/ns/' + name).readlink()) for name in ('mnt', 'net', 'pid')}


def run_logged(argv, log, timeout=86400):
    with log.open('x') as stream:
        try:
            process = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=stream,
                stderr=subprocess.STDOUT, timeout=timeout)
        except subprocess.TimeoutExpired:
            return dict(returncode=None, host_timeout=True, host_timeout_seconds=timeout)
    return dict(returncode=process.returncode, host_timeout=False, host_timeout_seconds=timeout)


def producer_context(frozen, record, args, context):
    import npu_world_sources
    module_receipt = getattr(args, 'module_receipt', None)
    if module_receipt is not None:
        assert args.provider_receipt is args.mt76_receipt is None, 'mixed-producer-contracts'
        name = module_receipt.resolve().relative_to(ROOT).as_posix()
        assert name in record['files'] and digest(frozen / name) == record['files'][name]
        combined = npu_world_sources.linked_module_sources(frozen, frozen / name)
        assert combined['source_lock_sha256'] == context['source_lock_sha256']
        for key, expected in {**combined['inputs'], **combined['artifacts']}.items():
            assert record['files'].get(key) == expected, ('undeclared-combined-producer-input', key)
        context['module_receipt'] = name
        return
    for key,path in (('provider_receipt',args.provider_receipt),('mt76_receipt',args.mt76_receipt)):
        assert path is not None, ('missing-current-producer-reference',key)
        name = str(path.resolve().relative_to(ROOT))
        assert name in record['files'] and digest(frozen / name) == record['files'][name]
        reference = json.loads((frozen / name).read_bytes())
        assert reference['passed'] is True and reference['source_lock_sha256'] == context['source_lock_sha256']
        context[key] = name


def inner(args):
    context = json.loads(args.context)
    assert os.getuid() == context['uid'] == 1000
    assert identity(ROOT) == context['frozen_root_identity']
    current = namespaces()
    assert all(current[name] != context['parent_namespaces'][name] for name in current)
    assert not Path('/oldroot').exists(), 'old-root-escape-path'
    mounts = Path('/proc/self/mountinfo').read_text().splitlines()
    for path in (BUILD, WORK):
        rows = [line for line in mounts if line.split()[4] == str(path)]
        assert len(rows) == 1 and ' - overlay ' in rows[0], ('missing-private-overlay', str(path))
    sentinel = ROOT / ('.isolated-readonly-' + args.name)
    assert not sentinel.exists()
    try:
        fd = os.open(sentinel, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except OSError as error:
        assert error.errno == errno.EROFS, error
    else:
        os.close(fd)
        raise AssertionError('snapshot-root-is-writable')
    assert digest(ROOT / 'firmware/source-lock.json') == context['source_lock_sha256']
    output = BUILD / 'bin' / ('isolated-world-' + args.name)
    assert not output.exists()
    output.mkdir(parents=True)
    (BUILD / '.isolated-home').mkdir(exist_ok=True)
    probe_log = WORK / ('namespace-probe-' + args.name + '.json')
    assert not probe_log.exists()
    proof = dict(uid=os.getuid(), namespaces=current, root_readonly=True, overlays=['build', 'logs'],
        hardware=False, router_contact=False, probe_only=args.probe_only)
    with probe_log.open('x') as stream: stream.write(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(dict(isolated_namespace=True, probe_only=args.probe_only)), flush=True)
    if args.probe_only:
        result = dict(passed=True, proof=proof, world_build=False, hardware=False)
    else:
        import npu_world_sources
        module_receipt = context.get('module_receipt')
        if module_receipt is not None:
            producer_path = npu_world_sources.relative_file(ROOT, module_receipt)
            combined = npu_world_sources.linked_module_sources(ROOT, producer_path)
            assert combined['source_lock_sha256'] == context['source_lock_sha256']
            provider = consumer = None
        else:
            provider = json.loads(npu_world_sources.relative_file(ROOT,context['provider_receipt']).read_bytes())
            consumer = json.loads(npu_world_sources.relative_file(ROOT,context['mt76_receipt']).read_bytes())
            assert provider['passed'] is consumer['passed'] is True
            assert provider['source_lock_sha256'] == consumer['source_lock_sha256'] == context['source_lock_sha256']
        linker = ROOT / context['linker']['path']
        assert linker == LINKER_PREFIX / 'bin/ld.lld' and digest(linker) == context['linker']['sha256']
        linker_version = subprocess.check_output([str(linker), '--version'], text=True, timeout=30).strip()
        proof['linker'] = dict(**context['linker'], version=linker_version)
        assert digest(ROOT / context['download_cache']['kernel_recipe']) == context['download_cache']['kernel_recipe_sha256'], 'active-kernel-hash-recipe-drift'
        proof['download_cache'] = stage_download_cache(BUILD,CACHE,context['download_cache'])
        print(json.dumps(dict(phase='clean-critical-outputs-in-private-overlay')),flush=True)
        clean_commands = [
            ['make','-C',str(BUILD),'-j2','target/linux/clean','V=s'],
            ['make','-C',str(ROOT / 'firmware/npu'),'OUT=' + str(BUILD / 'bin/npu'),'clean']]
        for cleanup in clean_commands:
            clean = subprocess.run(cleanup,stdin=subprocess.DEVNULL)
            assert clean.returncode == 0, ('private-clean-failed',cleanup,clean.returncode)
        build_name = 'isolated-' + args.name
        build_env = dict(os.environ,FAKEROOTDONTTRYCHOWN='1')
        proof['fakeroot_no_real_chown'] = True
        print(json.dumps(dict(phase='world-with-fakeroot-emulated-ownership',uid=os.getuid())),flush=True)
        build = subprocess.run([sys.executable, '-u', '-B', str(ROOT / 'tools/build_firmware.py'),
            '--name', build_name, '--jobs', '2', '--target', 'world',
            '--host-tools', str(LINKER_PREFIX)], stdin=subprocess.DEVNULL,env=build_env)
        assert build.returncode == 0, ('world-build-failed', build.returncode)
        lock = json.loads((ROOT / 'firmware/source-lock.json').read_bytes())
        for label, tree in (('openwrt', BUILD), ('luci', BUILD / 'feeds/luci')):
            for row in lock[label]['changed_files']:
                assert digest(tree / row['path']) == row['sha256'], ('world-source-drift', label, row['path'])
        for row in lock['component_sources']:
            assert row['tree'] == 'openwrt' and digest(BUILD / row['destination']) == row['sha256']
        assert digest(BUILD / '.config') == digest(ROOT / 'firmware/build.config'), 'world-config-drift'
        prepared_sources = npu_world_sources.verify(BUILD,ROOT,lock,provider,consumer,
            module_sources=combined if module_receipt is not None else None)
        verify = subprocess.run([sys.executable, '-u', '-B', str(ROOT / 'tools/verify_merged_image.py'),
            '--name', build_name + '-image'], stdin=subprocess.DEVNULL)
        assert verify.returncode == 0, ('world-image-verification-failed', verify.returncode)
        image_path = WORK / (build_name + '-image/result.json')
        image = json.loads(image_path.read_bytes())
        assert image['passed'] is True and image['source_lock_sha256'] == context['source_lock_sha256']
        result = dict(passed=True, proof=proof, world_build=True, image_verification=image,
            critical_kernel_modules_and_RV32_cleaned=True, prepared_sources_verified=prepared_sources,
            image_verification_receipt=str(image_path.relative_to(ROOT)), image_verification_sha256=digest(image_path),
            build_state=str((WORK / ('build-' + build_name + '.json')).relative_to(ROOT)),
            module_loaded=False, native_cold_qualified=False, full_setup=False, hardware=False)
    output.mkdir(parents=True,exist_ok=True)
    with (output / 'result.json').open('x') as stream: stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, world_build=result['world_build'], hardware=False)), flush=True)


def run(args):
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name) and os.getuid() == 1000
    directory = STORE / args.name
    assert not directory.exists()
    frozen, record = snapshot(args.snapshot)
    context = dict(uid=os.getuid(), parent_namespaces=namespaces(), frozen_root_identity=identity(frozen),
        source_lock_sha256=digest(frozen / 'firmware/source-lock.json'))
    if not args.probe_only:
        context['linker'] = linker_input(frozen, record)
        context['download_cache'] = download_cache_input(frozen, record)
        producer_context(frozen, record, args, context)
    directory.mkdir(parents=True)
    for name in ('build-upper', 'build-work', 'log-upper', 'log-work', 'tmp'): (directory / name).mkdir()
    print(json.dumps(dict(phase='inventory-protected-lower-build', probe_only=args.probe_only)), flush=True)
    cache_before = tree_state(CACHE)
    with (directory / 'cache-before.json').open('x') as stream: stream.write(json.dumps(cache_before,sort_keys=True) + '\n')
    before = tree_state(BUILD)
    with (directory / 'lower-before.json').open('x') as stream: stream.write(json.dumps(before, sort_keys=True) + '\n')
    argv = command(frozen, directory, args.name, context, args.probe_only)
    envelope = dict(command=argv, snapshot_receipt_sha256=digest(args.snapshot),
        snapshot_source_commit=record['source_commit'], source_lock_sha256=context['source_lock_sha256'],
        parent_namespaces=context['parent_namespaces'], protected_lower_build=str(BUILD),
        physical_output_root=str(directory), bwrap_sha256=digest(Path('/usr/bin/bwrap')), network_isolated=True)
    with (directory / 'launch.json').open('x') as stream: stream.write(json.dumps(envelope, indent=2) + '\n')
    print(json.dumps(dict(phase='launch-private-offline-world', name=args.name, probe_only=args.probe_only)), flush=True)
    execution = run_logged(argv, directory / 'run.log')
    unchanged = tree_state(BUILD) == before
    cache_unchanged = tree_state(CACHE) == cache_before
    snapshot(args.snapshot)
    assert namespaces() == context['parent_namespaces']
    child_path = directory / 'build-upper/bin' / ('isolated-world-' + args.name) / 'result.json'
    child = json.loads(child_path.read_bytes()) if child_path.exists() else None
    passed = execution['returncode'] == 0 and unchanged and cache_unchanged and child is not None and child['passed'] is True
    result = dict(passed=passed, **execution, original_build_content_modes_ownership_links_unchanged=unchanged,
        original_inventory_entries=len(before), snapshot_unchanged=True, parent_namespaces_unchanged=True,
        original_download_cache_content_modes_ownership_links_unchanged=cache_unchanged,
        original_download_cache_entries=len(cache_before),
        envelope=envelope, child=child, world_build=bool(child and child['world_build']),
        probe_only=args.probe_only, module_loaded=False, native_cold_qualified=False, full_setup=False, hardware=False,
        limits=['An offline overlay build reuses prepared cache inputs;not a fresh rebuild of every dependency.',
                'Declared frozen download inputs are copied byte-exact into private writable build/dl;the original cache is compared separately.',
                'Original regular-file content/modes/ownership and literal symlinks/directories are compared;special input nodes are rejected.',
                'Read-only source snapshot,private mount/network/PID namespaces,writable build/log overlays and private temporary storage.',
                'No native-cold,physical DMA/IRQ/drain,boot,actual-client or complete NPU acceptance follows from a successful world/image check.'])
    if passed and not args.probe_only:
        relative = Path(child['image_verification']['image']).relative_to(BUILD.relative_to(ROOT))
        physical = directory / 'build-upper' / relative
        assert not physical.is_symlink() and digest(physical) == child['image_verification']['sha256']
        result['physical_image'] = str(physical)
        result['physical_image_sha256'] = digest(physical)
    with (directory / 'result.json').open('x') as stream: stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=passed, probe_only=args.probe_only, original_entries=len(before),
        original_unchanged=unchanged, result_sha256=digest(directory / 'result.json'))), flush=True)
    assert passed, ('isolated-world-unqualified', directory / 'run.log')


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='mode', required=True)
    outer = sub.add_parser('run')
    outer.add_argument('--name', required=True)
    outer.add_argument('--snapshot', type=Path, required=True)
    outer.add_argument('--provider-receipt', type=Path)
    outer.add_argument('--mt76-receipt', type=Path)
    outer.add_argument('--module-receipt', type=Path)
    outer.add_argument('--probe-only', action='store_true')
    child = sub.add_parser('inner')
    child.add_argument('--name', required=True)
    child.add_argument('--context', required=True)
    child.add_argument('--probe-only', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name): parser.error('Invalid result name')
    if args.mode == 'run':
        if args.module_receipt is not None and (args.provider_receipt is not None or args.mt76_receipt is not None):
            parser.error('Combined and separate producer receipts cannot be mixed')
        if not args.probe_only and args.module_receipt is None and (args.provider_receipt is None or args.mt76_receipt is None):
            parser.error('Current provider and mt76 producer receipts are required for a world build, or use --module-receipt')
    (run if args.mode == 'run' else inner)(args)


if __name__ == '__main__': main()
