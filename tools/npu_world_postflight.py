"""Recheck the pinned baseline's RV32 roster failure without rerunning the build."""
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from npu_replay_proof import digest, path_under, read_pinned, require

CHECKPOINT = 'research/checkpoints/2026-11-18-npu-successor-source-gate/EVIDENCE.json'
BUILD = '.build/merged-openwrt'
LOGS = '.local/merge-nonoc-20260923'
NAME = 'baseline-a-image'
PRODUCER_VIEW = '/tmp/w1700k-frozen-producer'
VERIFIER = 'tools/verify_merged_image.py'

RECHECK = '''
import json
import os
from pathlib import Path
import sys

from npu_isolated_world import namespaces
from npu_world_sources import linked_module_sources, verify as verify_sources
import verify_merged_image as image

context = json.loads(sys.argv.pop(1))
root, build = image.ROOT, image.BUILD
assert all(os.statvfs(p).f_flag & os.ST_RDONLY for p in (root, build, context['producer_view']))
assert all(node != context['parent_namespaces'][name] for name, node in namespaces().items())
assert image.sha(Path(image.__file__)) == context['verifier']
fits = list((build / 'bin/targets/airoha/an7581').glob('*sysupgrade.itb'))
assert len(fits) == 1 and image.sha(fits[0]) == context['image']
source_lock = root / 'firmware/source-lock.json'
assert image.sha(source_lock) == context['lock']
lock = json.loads(source_lock.read_bytes())
for label, tree in (('openwrt', build), ('luci', build / 'feeds/luci')):
    for row in lock[label]['changed_files']:
        assert image.sha(tree / row['path']) == row['sha256'], ('prepared-overlay', row['path'])
for row in lock['component_sources']:
    assert row['tree'] == 'openwrt' and image.sha(build / row['destination']) == row['sha256']
assert image.sha(build / '.config') == image.sha(root / 'firmware/build.config')
producer_root = Path(context['producer_view'])
producer = linked_module_sources(producer_root, producer_root / context['producer'])
assert producer['receipt_sha256'] == context['producer_sha256']
proof = verify_sources(build, producer_root, lock, module_sources=producer)
with (image.OUT.parent / 'prepared.json').open('x') as output:
    json.dump(proof, output)
raise SystemExit(image.main())
'''


def check_failure(world, pin, evidence, launch, state, build, log):
    require(pin == evidence['terminal_world_sha256'] and world['returncode'] == 1 and
            world['world_build'] is world['passed'] is False and world['child'] is None,
            'Not the pinned RV32 roster failure')
    require(world['envelope'] == launch and launch['network_isolated'] is True and
            launch['source_lock_sha256'] == evidence['source_lock_sha256'] and
            launch['producer_sha256'] == evidence['producer_sha256'],
            'Frozen launch differs from the failed world')
    require(all(world[key] is True for key in ('snapshot_unchanged', 'parent_namespaces_unchanged',
                'original_build_content_modes_ownership_links_unchanged',
                'original_download_cache_content_modes_ownership_links_unchanged')) and
            all(world[key] is False for key in ('host_timeout', 'probe_only', 'hardware', 'module_loaded')),
            'Original world did not preserve its inputs')
    inventories = launch['streamed_inventories']
    require(inventories == world['streamed_inventories_after'] and set(inventories) == {'lower', 'cache'}
            and all(row['entries'] > 0 for row in inventories.values()),
            'Protected build or download cache inventory changed')
    require(state['exit_code'] == 0 and state['finished'] > state['started'] and
            state['command'] == ['make', '-j2', 'world', 'V=s'] and state['cwd'] == str(build) and
            state['log'] == str(log), 'No completed make world for the failed verification')


def recheck(root, directory, world, world_pin, frozen, declarations, lock_pin, fit):
    checkpoint = path_under(root, CHECKPOINT)
    evidence = json.loads(checkpoint.read_bytes())['baseline']
    launch, launch_pin = read_pinned(path_under(directory, 'launch.json'), evidence['launch_sha256'])
    name = 'build-isolated-' + directory.name
    state, state_pin = read_pinned(path_under(directory, f'log-upper/{name}.json'),
                                   evidence['build_state_sha256'])
    build, logs = root / BUILD, root / LOGS
    check_failure(world, world_pin, evidence, launch, state, build, logs / f'{name}.log')
    require(digest(path_under(directory, 'run.log')) == evidence['run_log_sha256'] and
            digest(fit) == evidence['fit_sha256'] and fit.stat().st_size == evidence['fit_bytes'],
            'Original verifier output or produced FIT changed')
    verifier = path_under(root, VERIFIER)
    verifier_pin = evidence['recheck_verifier_sha256']
    require(digest(verifier) == verifier_pin and
            digest(path_under(frozen, VERIFIER)) == declarations[VERIFIER] == evidence['frozen_verifier_sha256'],
            'Unexpected frozen or corrected image verifier')
    original, original_pin = read_pinned(path_under(root / '.local', root / evidence['image_recheck_path']),
                                         evidence['image_recheck_sha256'])
    launcher = launch['bubblewrap']
    executable = path_under(frozen, launcher['path'])
    require(launcher['frozen'] is True and digest(executable) == launcher['sha256'] ==
            declarations[launcher['path']] == launch['bwrap_sha256'] and str(executable) == launch['command'][0],
            'Wrong read-only overlay launcher')
    producer = json.loads(launch['command'][-1])['module_receipt']
    require(declarations[producer] == evidence['producer_sha256'] and lock_pin == evidence['source_lock_sha256'],
            'The recovered world does not use the pinned baseline producer and lock')

    with TemporaryDirectory(prefix='.world-postflight-', dir=root / '.local') as folder:
        scratch = Path(folder)
        reports, tmp = scratch / 'reports', scratch / 'tmp'
        reports.mkdir()
        tmp.mkdir()
        upper = path_under(directory, 'build-upper', directory=True)
        context = dict(parent_namespaces={name: str(Path(f'/proc/self/ns/{name}').readlink())
                                         for name in ('mnt', 'net', 'pid')},
                       producer=producer, producer_sha256=evidence['producer_sha256'],
                       image=evidence['fit_sha256'], verifier=verifier_pin,
                       lock=lock_pin, producer_view=PRODUCER_VIEW)
        argv = ['nice', '-n', '19', executable, '--unshare-all', '--ro-bind', '/', '/',
                '--ro-bind', frozen, root, '--overlay-src', build, '--overlay-src', upper,
                '--ro-overlay', build, '--ro-bind', verifier, verifier, '--bind', reports, logs,
                '--bind', tmp, '/tmp', '--ro-bind', frozen, PRODUCER_VIEW,
                '--proc', '/proc', '--dev', '/dev', '--new-session', '--die-with-parent',
                '--clearenv', '--setenv', 'PATH', '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
                '--setenv', 'LC_ALL', 'C', '--setenv', 'PYTHONPATH',
                ':'.join(str(root / p) for p in ('.local/npu-reset/python-lib', 'tools', 'tests/npu')),
                '/usr/bin/python3', '-u', '-B', '-c', RECHECK, json.dumps(context),
                '--name', NAME, '--frozen-producer-root', PRODUCER_VIEW, '--module-receipt', producer,
                '--expected-producer-sha256', evidence['producer_sha256']]
        try:
            done = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=180, text=True)
        except subprocess.TimeoutExpired as error:
            raise ValueError('Read-only FIT postflight exceeded 180 seconds') from error
        require(done.returncode == 0, 'Read-only FIT postflight failed: ' + done.stderr[-1800:])
        image, pin = read_pinned(path_under(reports, f'{NAME}/result.json'), original_pin)
        proof = json.loads(path_under(reports, 'prepared.json').read_bytes())
    require(image == original and digest(verifier) == verifier_pin and digest(fit) == evidence['fit_sha256'],
            'Corrected verification or FIT changed during postflight')
    return image, pin, dict(format='w1700k-baseline-rv32-roster-recheck-v1',
                           original_wrapper_passed=False, original_wrapper_returncode=world['returncode'],
                           original_terminal_sha256=world_pin, original_launch_sha256=launch_pin,
                           original_build_state_sha256=state_pin, source_lock_sha256=lock_pin,
                           reconstructed_build_readonly=True, prepared_sources_verified=proof,
                           corrected_image_verifier_sha256=verifier_pin,
                           corrected_image_receipt_sha256=pin)
