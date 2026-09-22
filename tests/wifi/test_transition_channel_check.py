#!/usr/bin/env python3
"""Verify that the live-test oracle only permits an evidenced same-pair swap."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / 'tests/wifi/transition_channel_check.uc'
UCODE = ROOT / '.build/openwrt/staging_dir/hostpkg/bin/ucode'
EXPECTED = '1 2412 20 2412\n44 5220 80 5210\n53 6215 80 6225\n'
SWAP = EXPECTED.replace('44 5220', '48 5240')
CASES = [
    ('exact', EXPECTED, 'none', True, True),
    ('evidenced-swap', SWAP, 'current', True, False),
    ('swap-without-message', SWAP, 'none', False, False),
    ('swap-with-stale-marker', SWAP, 'previous', False, False),
    ('swap-message-before-marker', SWAP, 'before', False, False),
    ('wrong-partner-same-80-block', EXPECTED.replace('44 5220', '40 5200'), 'current', False, False),
    ('wrong-width', SWAP.replace('80 5210', '40 5230'), 'current', False, False),
    ('wrong-center', SWAP.replace('80 5210', '80 5290'), 'current', False, False),
    ('wrong-frequency', SWAP.replace('48 5240', '48 5230'), 'current', False, False),
    ('unchanged-primary-wrong-frequency', EXPECTED.replace('44 5220', '44 5230'), 'current', False, False),
    ('2g-swap-not-permitted', EXPECTED.replace('1 2412', '5 2432'), 'current', False, False),
    ('6g-swap-not-permitted', EXPECTED.replace('53 6215', '57 6235'), 'current', False, False),
    ('missing-radio', EXPECTED.replace('53 6215 80 6225\n', ''), 'current', False, False),
    ('extra-radio', EXPECTED + '36 5180 80 5210\n', 'current', False, False),
    ('duplicate-band', EXPECTED.replace('53 6215 80 6225', '36 5180 80 5210'), 'current', False, False),
    ('empty-readback', '', 'current', False, False),
]


def main():
    results = []
    with tempfile.TemporaryDirectory(prefix='w1700k-wifi-transitions-20260907-', dir='/tmp') as directory:
        root = Path(directory)
        for name, actual, log_kind, valid, exact in CASES:
            stage = '03-channels'
            marker = f'W1700K-TRANSITION {root} {stage} BEGIN'
            message = 'daemon.notice hostapd: Switch own primary and secondary channel to get secondary channel with no Beacons from other BSSes'
            logs = {'none': marker, 'current': marker + '\n' + message,
                    'previous': marker.replace(stage, '02-add6g') + '\n' + message,
                    'before': message + '\n' + marker}
            (root / f'{stage}.expected-channels.txt').write_text(EXPECTED)
            (root / f'{stage}.actual-channels.txt').write_text(actual)
            (root / f'{stage}.current.system.private.log').write_text(logs[log_kind])
            run = subprocess.run([str(UCODE), str(CHECKER), str(root), stage],
                                 capture_output=True, text=True, timeout=10)
            assert (run.returncode == 0) == valid, (name, run.stdout, run.stderr)
            if run.stdout:
                result = json.loads(run.stdout)
                assert bool(result['valid']) == valid
                assert bool(result['exact_primary_match']) == exact
            results.append(dict(name=name, passed=True, valid=valid, exact=exact))
    report = dict(scope='Test-oracle controls only; no production or router execution',
                  checker_sha256=hashlib.sha256(CHECKER.read_bytes()).hexdigest(),
                  harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  cases=results, passed=len(results))
    output = ROOT / 'research/checkpoints/2026-09-07-wifi-transitions/channel-oracle-tests.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': len(results)}))


if __name__ == '__main__':
    main()
