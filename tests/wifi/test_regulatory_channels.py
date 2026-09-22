#!/usr/bin/env python3
"""Execute the real channel/width helper against integer and decimal iw maps."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
RELATIVE = 'target/linux/airoha/an7581/base-files/usr/libexec/w1700k-wireless-regulatory'
HELPER = ROOT / '.build/openwrt' / RELATIVE
OUT = ROOT / 'research/checkpoints/2026-09-06-wifi-config/regulatory-tests.json'
OLD_SHA = '27075d0fe688df9e3405d03069fe48eb41389969409c008b5e2e8e1e7ff75708'
OLD_PATTERN = '$2 ~ /^[0-9]+$/'
NEW_PATTERN = '$2 ~ /^[0-9]+([.][0-9]+)?$/'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def phy_map(decimals, blocked_band=None, blocked_6g_channel=None):
    rows = ['Wiphy synthetic-fixture']
    for band, channels in (
        ('2g', range(1, 15)),
        ('5g', [*range(36, 65, 4), *range(100, 145, 4), *range(149, 178, 4)]),
        ('6g', [2, *range(1, 234, 4)]),
    ):
        rows += ['\tFrequencies:']
        for channel in channels:
            if band == '2g':
                mhz = 2484 if channel == 14 else 2407 + 5 * channel
            elif band == '5g':
                mhz = 5000 + 5 * channel
            else:
                mhz = 5935 if channel == 2 else 5950 + 5 * channel
            flags = '(20.0 dBm)'
            if (band == blocked_band or band == '2g' and channel == 14 or
                    band == '5g' and channel >= 149 or
                    band == '6g' and channel == blocked_6g_channel):
                flags = '(disabled)'
            elif band == '5g' and channel == 52:
                flags = '(20.0 dBm) (no IR)'
            elif band == '5g' and channel == 56:
                flags = '(20.0 dBm) (radar detection)'
            frequency = str(mhz) if decimals == 0 else f'{mhz:.{decimals}f}'
            rows.append(f'\t\t* {frequency} MHz [{channel}] {flags}')
    return '\n'.join(rows) + '\n'


def execute(helper, fixture, operation, arguments):
    env = dict(os.environ, LC_ALL='C', W1700K_IW_PHY_INFO_FILE=str(fixture))
    env.pop('W1700K_IW_PHY_INFO_LOADED', None)
    env.pop('W1700K_IW_PHY_INFO', None)
    result = subprocess.run(['sh', '-c', '. "$1"; shift; "$@"', 'regulatory-test',
                             str(helper), operation, *map(str, arguments)],
                            capture_output=True, text=True, env=env, timeout=15)
    assert result.returncode in (0, 1, 2), result.stderr
    assert not result.stdout and not result.stderr, (result.stdout, result.stderr)
    return result.returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    source = HELPER.read_text()
    lock = json.loads((ROOT / 'firmware/source-lock.json').read_text())
    expected = next(row['sha256'] for row in lock['openwrt']['changed_files'] if row['path'] == RELATIVE)
    assert digest(source.encode()) == expected, 'Prepared helper differs from source authority'
    assert source.count(NEW_PATTERN) == 2
    original = source.replace(NEW_PATTERN, OLD_PATTERN)
    assert digest(original.encode()) == OLD_SHA, 'Change exceeds the two frequency parsers'
    scratch = ROOT / '.local/wifi-config'
    scratch.mkdir(parents=True, exist_ok=True)
    cases, regressions, mutants = [], [], []
    with tempfile.TemporaryDirectory(prefix='regulatory-', dir=scratch) as directory:
        directory = Path(directory)
        old = directory / 'before.sh'
        old.write_text(original)
        for decimals in (0, 1, 3):
            name = f'decimal-{decimals}'
            fixture = directory / f'{name}.txt'
            fixture.write_text(phy_map(decimals))
            checks = [
                ('channel_valid', ('2g', 6, 'SA'), 0),
                ('channel_valid', ('2g', 14, 'JP'), 1),
                ('channel_valid', ('5g', 36, 'SA'), 0),
                ('channel_valid', ('5g', 52, 'SA'), 1),
                ('channel_valid', ('5g', 56, 'SA'), 0),
                ('channel_valid', ('5g', 161, 'SA'), 1),
                ('channel_valid', ('5g', 35, 'SA'), 1),
                ('channel_valid', ('6g', 33, 'SA'), 0),
                ('channel_valid', ('6g', 161, 'SA'), 0),
                ('channel_valid', ('6g', 2, 'SA'), 0),
                ('channel_valid', ('5g', 'auto', 'SA'), 0),
                ('channel_valid', ('6g', 'auto', 'SA'), 0),
                ('htmode_valid', ('2g', 'EHT20', 6, 'SA'), 0),
                ('htmode_valid', ('2g', 'EHT40', 6, 'SA'), 0),
                ('htmode_valid', ('5g', 'EHT80', 36, 'SA'), 0),
                ('htmode_valid', ('5g', 'EHT160', 36, 'SA'), 1),
                ('htmode_valid', ('5g', 'EHT80', 149, 'SA'), 1),
                ('htmode_valid', ('6g', 'EHT320', 33, 'SA'), 0),
                ('htmode_valid', ('6g', 'EHT320', 225, 'SA'), 1),
                ('htmode_valid', ('6g', 'EHT80', 'auto', 'SA'), 0),
                ('htmode_valid', ('6g', 'EHT320', 'auto', 'SA'), 1),
            ]
            for operation, arguments, wanted in checks:
                actual = execute(HELPER, fixture, operation, arguments)
                before = execute(old, fixture, operation, arguments)
                row = dict(fixture=name, operation=operation, arguments=arguments,
                           expected=wanted, actual=actual, before=before)
                assert actual == wanted, row
                cases.append(row)
                if before != wanted:
                    assert decimals != 0, row
                    regressions.append(row)
            for blocked_band in ('2g', '5g', '6g'):
                fixture.write_text(phy_map(decimals, blocked_band=blocked_band))
                operation, arguments = 'channel_valid', (blocked_band, 'auto', 'SA')
                actual = execute(HELPER, fixture, operation, arguments)
                before = execute(old, fixture, operation, arguments)
                row = dict(fixture=f'{name}-blocked-{blocked_band}', operation=operation,
                           arguments=arguments, expected=1, actual=actual, before=before)
                assert actual == 1, row
                cases.append(row)
                if before != 1:
                    assert decimals != 0
                    regressions.append(row)
            fixture.write_text(phy_map(decimals, blocked_6g_channel=45))
            operation, arguments = 'htmode_valid', ('6g', 'EHT320', 33, 'SA')
            actual = execute(HELPER, fixture, operation, arguments)
            before = execute(old, fixture, operation, arguments)
            row = dict(fixture=f'{name}-partial-320', operation=operation, arguments=arguments,
                       expected=1, actual=actual, before=before)
            assert actual == 1, row
            cases.append(row)
            if before != 1:
                assert decimals != 0
                regressions.append(row)
        fixture.write_text('')
        for operation, arguments, wanted in (
            ('channel_valid', ('2g', 6, 'SA'), 0),
            ('channel_valid', ('5g', 161, 'SA'), 0),
            ('channel_valid', ('6g', 33, 'SA'), 0),
            ('htmode_valid', ('5g', 'EHT80', 36, 'SA'), 0),
            ('htmode_valid', ('6g', 'EHT320', 225, 'SA'), 1),
        ):
            actual = execute(HELPER, fixture, operation, arguments)
            before = execute(old, fixture, operation, arguments)
            assert actual == before == wanted
            cases.append(dict(fixture='empty-map-fallback-unchanged', operation=operation,
                              arguments=arguments, expected=wanted, actual=actual, before=before))
        assert regressions
        fixture.write_text(phy_map(1, blocked_band='5g'))
        for index, arguments in ((0, ('5g', 161, 'SA')), (1, ('5g', 'auto', 'SA'))):
            parts = source.split(NEW_PATTERN)
            mutant_source = parts[0] + (OLD_PATTERN if index == 0 else NEW_PATTERN) + parts[1]
            mutant_source += (OLD_PATTERN if index == 1 else NEW_PATTERN) + parts[2]
            mutant = directory / f'mutant-{index}.sh'
            mutant.write_text(mutant_source)
            assert execute(mutant, fixture, 'channel_valid', arguments) != 1
            mutants.append(dict(reverted_parser=index, killed=True))
    result = dict(schema=1, passed=True, source_path=RELATIVE, source_sha256=expected,
                  original_sha256=OLD_SHA, test_sha256=digest(Path(__file__).read_bytes()),
                  counts=dict(cases=len(cases), reproduced_old_failures=len(regressions),
                              mutants_killed=len(mutants)), cases=cases, mutants=mutants,
                  scope='Actual POSIX helper on synthetic iw maps; no router or RF activity',
                  limits=['Static no-driver fallback policy is unchanged.',
                          'Channel admission is not beacon, association, traffic or regulatory certification.'])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, counts=result['counts'], output=str(args.out))))


if __name__ == '__main__':
    main()
