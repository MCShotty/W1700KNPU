#!/usr/bin/env python3
"""Test the merged updater with synthetic API/session/image fixtures, no network."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '.local/merge-nonoc-20260923'
SOURCE = ROOT / '.build/merged-openwrt/files/usr/libexec/w1700k-release-helper'
TAG = 'ubi2_2026.09.23_r36536-288d79449f'
SESSION = 'a' * 32  # Synthetic fixture, not a real authenticated session.
PAYLOAD = b'SYNTHETIC firmware fixture: never flash this file.\n'

MOCK = r'''#!/usr/bin/python3
import hashlib, json, os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
root = Path(os.environ['FIXTURE_ROOT'])
mode = os.environ['FIXTURE_MODE']
payload = b'SYNTHETIC firmware fixture: never flash this file.\n'
tag = 'ubi2_2026.09.23_r36536-288d79449f'
asset = 'openwrt-airoha-an7581-gemtek_w1700k-ubi-squashfs-sysupgrade.itb'
url = 'https://github.com/w1700k/builds/releases/download/' + tag + '/' + asset
with (root / 'calls.jsonl').open('a') as stream:
    stream.write(json.dumps({'tool': name, 'operation': sys.argv[1:3]}) + '\n')
if name == 'ubus':
    if sys.argv[1:4] == ['call', 'session', 'access']:
        request = json.loads(sys.argv[4])
        assert request['ubus_rpc_session'] == 'a' * 32
        assert request['scope'] == 'access-group'
        assert request['object'] == 'luci-app-attendedsysupgrade'
        assert request['function'] == os.environ['FIXTURE_PERMISSION']
        print(json.dumps({'access': mode != 'denied'}))
    else:
        assert sys.argv[1:] == ['call', 'system', 'board']
        print(json.dumps({'board_name': 'unrelated,board' if mode == 'wrong-board' else 'gemtek,w1700k-ubi'}))
elif name == 'curl':
    request = sys.argv[-1]
    if mode == 'network-failure': sys.exit(22)
    entry = {'name': asset, 'browser_download_url': url,
             'digest': 'sha256:' + hashlib.sha256(payload).hexdigest()}
    if mode == 'missing-digest': entry.pop('digest')
    if mode == 'wrong-origin': entry['browser_download_url'] = 'https://example.invalid/image.itb'
    release = {'tag_name': tag, 'draft': False, 'prerelease': False,
               'assets': [entry, dict(entry)] if mode == 'duplicate-asset' else [entry]}
    if request.endswith('?per_page=10'):
        assert request == 'https://api.github.com/repos/w1700k/builds/releases?per_page=10'
        oc = dict(release, tag_name='ubi2-oc_example')
        draft = dict(release, draft=True)
        print(json.dumps([release, oc, draft]))
    else:
        assert '-o' in sys.argv
        output = Path(sys.argv[sys.argv.index('-o') + 1])
        assert output.resolve().is_relative_to((root / 'tmp').resolve())
        if '/releases/tags/' in request:
            assert request == 'https://api.github.com/repos/w1700k/builds/releases/tags/' + tag
            output.write_text(json.dumps(release))
        else:
            assert request == url
            assert '--max-filesize' in sys.argv and '--max-time' in sys.argv
            output.write_bytes(b'corrupt' if mode == 'bad-digest' else payload)
elif name == 'sysupgrade':
    assert len(sys.argv) == 3 and sys.argv[1] == '-T'
    assert Path(sys.argv[2]).read_bytes() == payload
    sys.exit(1 if mode == 'incompatible' else 0)
else:
    raise AssertionError(name)
'''


def main():
    original = SOURCE.read_text()
    results = []
    cases = [
        ('missing-session', 'fetch', 'POST', '', 'tag=' + TAG, 403),
        ('anonymous', 'fetch', 'POST', '0' * 32, 'tag=' + TAG, 403),
        ('bad-session', 'fetch', 'POST', 'z' * 32, 'tag=' + TAG, 403),
        ('denied', 'fetch', 'POST', SESSION, 'tag=' + TAG, 403),
        ('wrong-method', 'fetch', 'GET', SESSION, 'tag=' + TAG, 405),
        ('bad-tag', 'fetch', 'POST', SESSION, 'tag=ubi2_x&extra=value', 400),
        ('oc-tag', 'fetch', 'POST', SESSION, 'tag=ubi2-oc_x', 400),
        ('wrong-board', 'fetch', 'POST', SESSION, 'tag=' + TAG, 409),
        ('locked', 'fetch', 'POST', SESSION, 'tag=' + TAG, 409),
        ('network-failure', 'fetch', 'POST', SESSION, 'tag=' + TAG, 502),
        ('duplicate-asset', 'fetch', 'POST', SESSION, 'tag=' + TAG, 502),
        ('missing-digest', 'fetch', 'POST', SESSION, 'tag=' + TAG, 502),
        ('wrong-origin', 'fetch', 'POST', SESSION, 'tag=' + TAG, 502),
        ('bad-digest', 'fetch', 'POST', SESSION, 'tag=' + TAG, 502),
        ('incompatible', 'fetch', 'POST', SESSION, 'tag=' + TAG, 409),
        ('success', 'fetch', 'POST', SESSION, 'tag=' + TAG, 200),
        ('list', 'check', 'GET', SESSION, '', 200),
        ('denied', 'check', 'GET', SESSION, '', 403),
    ]
    for mode, action, method, session, query, expected in cases:
        with tempfile.TemporaryDirectory(prefix='release-fixture-', dir=WORK) as temp:
            root = Path(temp)
            (root / 'tmp').mkdir()
            (root / 'bin').mkdir()
            helper = root / 'helper'
            # Filesystem-only mapping: isolate fixed router /tmp paths from the host.
            helper.write_text(original.replace('/tmp/', str(root / 'tmp') + '/'))
            for name in ('ubus', 'curl', 'sysupgrade'):
                path = root / 'bin' / name
                path.write_text(MOCK)
                path.chmod(0o755)
            prior = b'Existing staging file must survive a rejected request.\n'
            staged = root / 'tmp/firmware.bin'
            staged.write_bytes(prior)
            lock = root / 'tmp/w1700k-github-fetch.lock'
            if mode == 'locked': lock.mkdir()
            env = dict(os.environ, PATH=str(root / 'bin') + ':/usr/bin:/bin',
                       FIXTURE_ROOT=str(root), FIXTURE_MODE=mode,
                       FIXTURE_PERMISSION='read' if action == 'check' else 'write',
                       REQUEST_METHOD=method, HTTP_X_LUCI_SESSION=session, QUERY_STRING=query)
            result = subprocess.run(['sh', str(helper), action], env=env,
                                    capture_output=True, text=True, timeout=20)
            assert SESSION not in result.stdout + result.stderr
            head, body = result.stdout.split('\n\n', 1)
            status = int(head.split()[1]) if head.startswith('Status:') else 200
            assert status == expected, (mode, result.stdout, result.stderr)
            data = json.loads(body)
            assert result.returncode == (0 if expected == 200 else 1)
            assert staged.read_bytes() == (PAYLOAD if mode == 'success' else prior)
            calls = [json.loads(line) for line in (root / 'calls.jsonl').read_text().splitlines()] if (root / 'calls.jsonl').exists() else []
            if expected in (403, 405) or mode in ('bad-tag', 'oc-tag', 'wrong-board', 'locked'):
                assert not any(row['tool'] == 'curl' for row in calls), mode
            if mode == 'success':
                assert data['success'] and data['sha256'] == hashlib.sha256(PAYLOAD).hexdigest()
                assert any(row['tool'] == 'sysupgrade' for row in calls)
            if mode == 'list':
                assert len(data) == 1 and data[0]['tag'] == TAG
            assert not list((root / 'tmp').glob('w1700k-github.*'))
            assert lock.exists() == (mode == 'locked')
            results.append(dict(mode=mode, action=action, status=status, calls=len(calls)))
    output = WORK / 'release-helper-tests.json'
    output.write_text(json.dumps(dict(source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                                      test_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                      cases=results, network=False, flashed=False,
                                      limits='Synthetic ubus, GitHub and compatibility-check responses; fixed /tmp paths mapped into private fixtures.'), indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=len(results), network=False, flashed=False)))


if __name__ == '__main__':
    main()
