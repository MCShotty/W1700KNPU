#!/usr/bin/env python3
"""Retain compact, source-bound merge receipts without copying private inputs."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.local/merge-nonoc-20260923'
OUT = ROOT / 'research/checkpoints/2026-09-23-nonoc-merge'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    assert not OUT.exists(), 'Keep existing receipts; do not silently overwrite them.'
    lock = read(ROOT / 'firmware/source-lock.json')
    build = ROOT / lock['build_directory']
    image = read(WORK / 'image-accepted/result.json')
    assert image['passed'] and image['source_lock_sha256'] == sha(ROOT / 'firmware/source-lock.json')
    assert sha(ROOT / image['image']) == image['sha256']
    replay = read(WORK / 'source-replay-accepted/result.json')
    assert replay['passed'] and replay['source_lock_sha256'] == image['source_lock_sha256']
    assert read(WORK / 'build-versioned-apk.json')['exit_code'] == 0
    prepared = read(WORK / 'tests-prepared-final/result.json')
    for name, digest in prepared['inputs'].items():
        assert sha(ROOT / name) == digest, ('prepared-test-input-drift', name)
    for row in prepared['prepared_source_bindings']:
        assert sha(ROOT / row['prepared']) == row['sha256'] == sha(ROOT / row['staged'])
    helper = read(WORK / 'release-helper-tests.json')
    assert helper['source_sha256'] == sha(build / 'files/usr/libexec/w1700k-release-helper')
    assert helper['test_sha256'] == sha(ROOT / 'tests/router/test_release_helper.py')

    native = {}
    metadata = {'firmware/source-lock.json', 'firmware/build.config',
                'firmware/patches/openwrt.patch', 'firmware/patches/luci.patch'}
    for name in ('bootstrap-results/bootstrap-control-v2.json',
                 'composition-results/bootstrap-composition.json'):
        receipt = read(WORK / 'firmware-tests' / name)
        inputs = receipt.get('inputs', receipt.get('inputs_before_after'))
        assert isinstance(inputs, dict)
        changes = {}
        for path, digest in inputs.items():
            current = sha(ROOT / path)
            if current != digest:
                assert path in metadata, ('native-executable-input-drift', path)
                changes[path] = dict(tested=digest, final=current)
        native[name] = dict(checked_inputs=len(inputs), executable_inputs_unchanged=True,
                            later_host_metadata_changes=changes)

    checks = []
    commands = [
        ['git', 'diff', '--check', '--', '.', ':!firmware/patches/*.patch'],
        ['git', '-C', str(build), 'diff', '--check'],
        ['git', '-C', str(build / 'feeds/luci'), 'diff', '--check'],
        ['shellcheck', str(build / 'files/usr/libexec/w1700k-release-helper'),
         str(build / 'files/www/cgi-bin/github_check'), str(build / 'files/www/cgi-bin/github_fetch')],
        ['node', '--check', str(build / 'feeds/luci/applications/luci-app-attendedsysupgrade/htdocs/luci-static/resources/view/attendedsysupgrade/overview.js')],
        ['node', '--check', str(build / 'feeds/luci/modules/luci-mod-status/htdocs/luci-static/resources/view/status/channel_analysis.js')],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, (command, result.stdout, result.stderr)
        checks.append(dict(command=command, exit_code=0))
    scripts = [*ROOT.glob('tools/*nonoc*.py'), *ROOT.glob('tools/*merged*.py'),
               ROOT / 'tools/prepare_build.py', ROOT / 'tools/build_firmware.py',
               ROOT / 'tests/test_prepared_sources.py', ROOT / 'tests/router/test_release_helper.py',
               ROOT / 'tests/npu/test_nonoc_merge.py', ROOT / 'tests/npu/run_nonoc_bootstrap.py',
               ROOT / 'tests/npu/test_boot_irq_installation.py',
               ROOT / 'tests/npu/test_bootstrap_control_v2.py', ROOT / 'tests/npu/test_bootstrap_v2_composition.py']
    for path in sorted(set(scripts)):
        ast.parse(path.read_text(), filename=str(path))

    copies = {
        'image.json': 'image-accepted/result.json',
        'fit.txt': 'image-accepted/fit.txt',
        'fwtool.json': 'image-accepted/fwtool.json',
        'prepared-driver-tests.json': 'tests-prepared-final/result.json',
        'source-replay.json': 'source-replay-accepted/result.json',
        'bootstrap-control-v2.json': 'firmware-tests/bootstrap-results/bootstrap-control-v2.json',
        'bootstrap-composition.json': 'firmware-tests/composition-results/bootstrap-composition.json',
        'release-helper-tests.json': 'release-helper-tests.json',
        'source-export.json': 'source-export.json',
        'source.json': 'source.json',
        'feed-pins.json': 'feed-pins.json',
        'component-sources.json': 'component-sources.json',
        'jev-final-request.json': 'jev-final-request.json',
        'jev-final-result.json': 'jev-final-result.json',
        'boot-budget-check.json': 'boot-budget-check.json',
    }
    OUT.mkdir(parents=True)
    for destination, source in copies.items():
        path = WORK / source
        assert path.is_file() and path.stat().st_size < 2 * 1024 * 1024
        assert b'PRIVATE KEY-----' not in path.read_bytes()
        shutil.copy2(path, OUT / destination)
    builds = []
    for path in sorted(WORK.glob('build-*.json')):
        state = read(path)
        assert state['exit_code'] is not None, ('unfinished-build', path)
        log = Path(state['log'])
        assert log.resolve().is_relative_to(WORK.resolve())
        state['log_sha256'] = sha(log)
        builds.append(state)
    inputs = sorted(set(scripts) | {ROOT / 'firmware/source-lock.json', ROOT / 'firmware/build.config'} |
                    {p for p in (ROOT / 'firmware/npu').rglob('*') if p.is_file() and p.suffix in ('.c', '.h')} |
                    {ROOT / 'firmware/npu/Makefile'})
    result = dict(passed=True, image_sha256=image['sha256'], native_receipt_rebinding=native,
                  prepared_driver_bindings=len(prepared['prepared_source_bindings']),
                  source_replay_files=len(replay['files']), static_checks=checks,
                  python_syntax_files=len(set(scripts)), builds=builds,
                  inputs={str(p.relative_to(ROOT)): sha(p) for p in inputs},
                  artifacts={p.name: sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
                  limitations=image['limits'],
                  exceptions=['An initial bootstrap run stopped short of a native endpoint; its exact ELF passed an isolated replay. The full suite passed with a recorded 60s wall budget and unchanged 3M instruction/state checks.',
                              'A second bootstrap attempt was canceled after test inputs changed; it is not counted as a pass.',
                              'An intermediate version label was rejected by APK; the accepted revision retains the commit hash suffix.',
                              'Build logs and all failed/intermediate receipts remain local; protected backups and signing keys are excluded.'])
    (OUT / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, checkpoint=str(OUT), image_sha256=image['sha256'],
                         source_files=len(replay['files']), prepared_driver_bindings=len(prepared['prepared_source_bindings']))))


if __name__ == '__main__':
    main()
