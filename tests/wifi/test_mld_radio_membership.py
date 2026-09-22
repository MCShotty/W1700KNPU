#!/usr/bin/env python3
"""Execute MLD radio admission and reload selection with modeled framework state."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
RELATIVE = 'package/network/services/hostapd/files/hostapd.uc'
SOURCE = ROOT / '.build/openwrt' / RELATIVE
UCODE = ROOT / '.build/openwrt/staging_dir/hostpkg/bin/ucode'
OUT = ROOT / 'research/checkpoints/2026-09-07-wifi-transitions/membership-tests.json'
NAMES = ['mld_radio_matches', 'mld_ssid_matches', 'mld_config_matches', 'bss_check_mld', 'mld_update_iface_refs',
         'iface_check_mld', 'mld_config_uses', 'mld_collect_reload']


def function(source, name):
    match = re.search(r'^function ' + name + r'\([^\n]*\)\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    return match[0]


def program(source):
    body = '\n'.join(function(source, name) for name in NAMES
                     if f'function {name}(' in source)
    return '''
let hostapd = { data: { mld: {}, config: {} }, bss: {}, printf: function() {} };
let operations = [];
function access() { return true; }
function phy_open(phy) { return { phy, name: phy }; }
function phy_wdev_add(phy, name, config) { push(operations, 'create'); return 0; }
function wdev_set_up() { push(operations, 'up'); return true; }
function wdev_remove() { push(operations, 'remove'); }
''' + body + '''
function reset(mask, existing) {
  operations = [];
  hostapd.data.mld = { mld0: { config: { phy: 'phy0' }, radio_mask: mask,
    ifname: 'mld0', macaddr: '02:00:00:00:00:10', anchor_radio: 1,
    has_wdev: existing, iface: { 'phy0.0': true } } };
  hostapd.data.config = {};
  hostapd.bss = {};
}
let cases = [];
function admission(name, mask, radio, phy, existing, wanted) {
  reset(mask, existing);
  let bss = { ifname: 'mld0', mld_ap: true };
  let accepted = !!bss_check_mld({ name: phy }, phy + '.' + radio, bss, radio);
  push(cases, { name, pass: accepted == wanted &&
    (wanted || (!length(operations) && bss.mld_bssid == null)), accepted, operations });
}
for (let mask in [3, 5, 6, 7])
  for (let radio in [0, 1, 2])
    admission('mask-' + mask + '-radio-' + radio, mask, radio, 'phy0', true, !!(mask & (1 << radio)));
admission('wrong-phy-existing', 3, 1, 'phy9', true, false);
admission('wrong-phy-create', 3, 1, 'phy9', false, false);
admission('wrong-radio-create', 3, 2, 'phy0', false, false);
admission('right-radio-create', 3, 1, 'phy0', false, true);
admission('legacy-default-radio-zero', 1, null, 'phy0', true, true);
admission('negative-radio', 3, -1, 'phy0', true, false);
admission('fractional-radio', 3, 1.5, 'phy0', true, false);
admission('out-of-range-radio', 1 << 32, 32, 'phy0', true, false);

reset(3, true);
let config = { phy: 'phy0', radio_idx: 2, bss: [
  { ifname: 'mld0', mld_ap: true }, { ifname: 'ordinary', mld_ap: false }
] };
let valid = iface_check_mld({ phy: 'phy0' }, 'phy0.2', config);
push(cases, { name: 'reject-outside-mask-without-dropping-ordinary-bss',
  pass: !valid && length(config.bss) == 1 && config.bss[0].ifname == 'ordinary' &&
    !length(operations) && hostapd.data.mld.mld0.iface['phy0.2'] == null });

function config_for(phy, radio) {
  return { phy, radio_idx: radio, bss: [], orig_bss: [{ ifname: 'mld0', mld_ap: true }] };
}
function reload_case(name, mask, include_config, wanted) {
  reset(mask, true);
  let data = hostapd.data.mld.mld0;
  data.iface = { 'phy0.2': true, missing: true };
  hostapd.bss = { 'phy0.0': { mld0: true }, 'phy0.1': { mld0: true },
    'phy9.1': { mld0: true } };
  hostapd.data.config = { 'phy0.0': config_for('phy0', 0),
    'phy0.1': config_for('phy0', 1), 'phy0.2': config_for('phy0', 2),
    'phy0.3': config_for('phy0', 3), 'phy9.1': config_for('phy9', 1) };
  let reload = { previous_other_mld: true };
  mld_collect_reload(reload, 'mld0', data, include_config);
  let actual = sort(keys(reload));
  push(cases, { name, pass: sprintf('%J', actual) == sprintf('%J', sort(wanted)), actual });
}
reload_case('activation-filters-all-candidate-sources', 3, true,
  ['previous_other_mld', 'phy0.0', 'phy0.1']);
reload_case('activation-new-anchor-and-mask', 5, true,
  ['previous_other_mld', 'phy0.0', 'phy0.2']);
reload_case('detach-preserves-all-old-references', 3, false,
  ['previous_other_mld', 'phy0.0', 'phy0.1', 'phy0.2', 'phy9.1', 'missing']);
printf('%J\\n', cases);
'''


def execute(source):
    with tempfile.TemporaryDirectory(dir=ROOT / '.local/wifi-transitions') as temp:
        script = Path(temp) / 'test.uc'
        script.write_text(program(source))
        run = subprocess.run([str(UCODE), str(script)], capture_output=True, text=True, timeout=20)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    source = SOURCE.read_text()
    lock = json.loads((ROOT / 'firmware/source-lock.json').read_text())
    sha = lambda value: hashlib.sha256(value).hexdigest()
    assert sha(source.encode()) == next(row['sha256'] for row in lock['openwrt']['changed_files']
                                        if row['path'] == RELATIVE)
    old = (ROOT / 'tests/wifi/fixtures/hostapd_mld_radio_membership_before.uc').read_text()
    assert sha(old.encode()) == 'd89d217e0a8655ec9f877aeb0968843b6d838510504083e51347d9979849492b'
    rows = execute(source)
    assert all(row['pass'] for row in rows), rows
    baseline_failures = [row['name'] for row in execute(old) if not row['pass']]
    assert 'activation-filters-all-candidate-sources' in baseline_failures
    assert 'wrong-radio-create' in baseline_failures
    mutants = {
        'remove-admission-guard': source.replace(
            '\tif (!mld_radio_matches(mld_data, phydev.name, radio))\n\t\treturn;\n', ''),
        'remove-reload-filter': source.replace(
            'if (!include_config || (config &&\n\t\t    mld_radio_matches(data, config.phy, config.radio_idx) &&\n\t\t    mld_config_uses(config, name, data)))',
            'if (true)'),
        'remove-phy-identity': source.replace('data && data.config.phy == phy &&', 'data &&'),
    }
    killed = {}
    for name, mutant in mutants.items():
        assert mutant != source
        killed[name] = [row['name'] for row in execute(mutant) if not row['pass']]
        assert killed[name], name
    report = dict(scope='Actual ucode admission/reload-selection functions; modeled framework only',
                  source_sha256=sha(source.encode()), harness_sha256=sha(Path(__file__).read_bytes()),
                  passed=len(rows), cases=rows, baseline_failures=baseline_failures, killed_mutants=killed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': len(rows), 'old_failures': len(baseline_failures), 'mutants_killed': len(killed)}))


if __name__ == '__main__':
    main()
