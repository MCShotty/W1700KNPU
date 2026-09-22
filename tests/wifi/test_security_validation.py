#!/usr/bin/env python3
"""Execute the complete shell validator with read-only synthetic UCI and iw data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

from test_regulatory_channels import phy_map

ROOT = Path(__file__).resolve().parents[2]
BASE = Path('target/linux/airoha/an7581/base-files')
SOURCE = ROOT / '.build/openwrt' / BASE / 'usr/sbin/w1700k-wireless-validate'
HELPER = ROOT / '.build/openwrt' / BASE / 'usr/libexec/w1700k-wireless-regulatory'


def config(devices, transition, *, disabled=False, encryption='owe'):
    values = {}
    for radio, band, channel in [(0, '2g', 6), (1, '5g', 36), (2, '6g', 37)]:
        name = f'wireless.radio{radio}'
        values[name] = 'wifi-device'
        for key, value in dict(type='mac80211', radio=radio, band=band,
                               country='SA', channel=channel, htmode='EHT20', disabled=0).items():
            values[f'{name}.{key}'] = str(value)
    values['wireless.test'] = 'wifi-iface'
    options = dict(mode='ap', device=' '.join(f'radio{i}' for i in devices),
                   mlo=int(len(devices) > 1), network='lan', encryption=encryption,
                   key='synthetic-passphrase', ieee80211w=2, rnr=1, sae_pwe=2,
                   disabled=int(disabled), ssid='Synthetic')
    if transition.startswith('auto-'):
        options['owe_transition'] = transition.removeprefix('auto-')
    elif transition == 'ifname':
        options['owe_transition_ifname'] = 'synthetic-open0'
    elif transition == 'bssid':
        options['owe_transition_bssid'] = '02:00:00:00:00:02'
        options['owe_transition_ssid'] = 'Synthetic-open'
    values.update({f'wireless.test.{k}': str(v) for k, v in options.items()})
    return values


def run(source, values, scratch):
    types = '\n'.join(f'{k}={v}' for k, v in values.items() if k.count('.') == 1)
    branches = '\n'.join(f'{shlex.quote(k)}) printf "%s\\n" {shlex.quote(v)} ;;'
                         for k, v in values.items())
    library = scratch / 'functions.sh'
    library.write_text('board_name() { echo gemtek,w1700k-ubi; }\n'
        'uci() {\n[ "$1" = -q ] && shift\n'
        f'if [ "$1 $2" = "show wireless" ]; then printf "%s\\n" {shlex.quote(types)}; return; fi\n'
        'if [ "$1" != get ]; then echo unexpected-uci-command >&2; return 99; fi\n'
        f'case "$2" in\n{branches}\n*) return 1 ;;\nesac\n}}\n')
    fixture = scratch / 'phy.txt'
    fixture.write_text(phy_map(1))
    env = dict(os.environ, W1700K_FUNCTIONS_LIB=str(library),
               W1700K_REG_HELPER=str(HELPER), W1700K_IW_PHY_INFO_FILE=str(fixture), LC_ALL='C')
    env.pop('W1700K_IW_PHY_INFO_LOADED', None)
    env.pop('W1700K_IW_PHY_INFO', None)
    return subprocess.run(['sh', str(source)], env=env, text=True,
                          capture_output=True, timeout=20)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    rows = []
    with tempfile.TemporaryDirectory(prefix='w1700k-security-') as name:
        scratch = Path(name)
        for devices in [[0], [1], [2], [1, 0], [1, 2, 0]]:
            for transition in ['none', 'auto-0', 'auto-1', 'auto-true', 'ifname', 'bssid']:
                reject = (len(devices) > 1 or 2 in devices) and transition not in ['none', 'auto-0']
                for disabled in [False, True]:
                    values = config(devices, transition, disabled=disabled)
                    expected = 1 if reject and not disabled else 0
                    current = run(SOURCE, values, scratch)
                    before = run(args.before, values, scratch)
                    assert not current.stdout and not before.stdout
                    assert 'unexpected-uci-command' not in current.stderr + before.stderr
                    assert current.returncode == expected, (devices, transition, disabled, current.stderr)
                    assert not expected or 'OWE transition' in current.stderr, current.stderr
                    assert before.returncode == 0, before.stderr
                    rows.append(dict(devices=devices, transition=transition, disabled=disabled,
                                     expected=expected, current=current.returncode, before=before.returncode))
        for devices in [[2], [1, 0], [1, 2, 0]]:
            result = run(SOURCE, config(devices, 'ifname', encryption='sae'), scratch)
            assert result.returncode == 0, result.stderr
            rows.append(dict(devices=devices, control='SAE ignores unused OWE fields', current=0))
    report = dict(cases=len(rows), failures=[], predecessor_failures=sum(r.get('expected', 0) for r in rows),
                  source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  predecessor_sha256=hashlib.sha256(args.before.read_bytes()).hexdigest(), results=rows,
                  scope='Complete shell validator and regulatory helper; synthetic read-only UCI/iw/board inputs')
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'results'}))


if __name__ == '__main__':
    main()
