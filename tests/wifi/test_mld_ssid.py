#!/usr/bin/env python3
"""Run original ucode parser, admission and cache selection against SSID races."""
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
GENERATOR = ROOT / '.build/openwrt/package/network/config/wifi-scripts/files-ucode/usr/share/ucode/wifi/common.uc'
UCODE = ROOT / '.build/openwrt/staging_dir/hostpkg/bin/ucode'
OUT = ROOT / 'research/checkpoints/2026-09-07-wifi-transitions/ssid-tests.json'
FIXTURE = ROOT / 'tests/wifi/fixtures/hostapd_mld_ssid_before.uc'
NAMES = ['mld_radio_matches', 'mld_ssid_matches', 'mld_config_matches', 'bss_check_mld',
         'iface_set_config', 'config_add_bss', 'iface_load_config',
         'mld_config_uses', 'mld_collect_reload', 'phy_name']


def function(source, name):
    match = re.search(r'^function ' + name + r'\([^\n]*\)\s*\{.*?^\}', source, re.M | re.S)
    assert match, name
    return match[0]


def program(source):
    body = '\n'.join(function(source, name) for name in NAMES
                     if f'function {name}(' in source)
    body += '\n' + function(GENERATOR.read_text(), 'escape_string')
    handler = re.search(r'\tconfig_set: \{\n.*?\t\tcall: function\(req\) \{(.*?)^\t\t\}\n\t\},', source, re.M | re.S)
    assert handler or '\tconfig_set: {' not in source
    if handler:
        body += '\nfunction config_set_request(req) {' + handler[1] + '\n}\n'
    return r'''
import { open, writefile } from 'fs';
let operations = [];
let completions = [];
let cases = [];
let hostapd = { data: { mld: {}, config: {}, file_fields: {} }, bss: {}, printf: function() {}, getpid: () => 42 };
let libubus = { STATUS_INVALID_ARGUMENT: 2 };
function mld_reject_concurrent_mutation() { return false; }
function access() { return true; }
function phy_open(phy) { push(operations, 'phy-open'); return { phy, name: phy }; }
function phy_wdev_add() { push(operations, 'create'); return 0; }
function wdev_set_up() { push(operations, 'up'); return true; }
function wdev_remove() { push(operations, 'remove'); }
function iface_check_mld() { push(operations, 'check'); return true; }
function iface_config_remove() { push(operations, 'remove-config'); return 0; }
function iface_reload_config() { push(operations, 'reload'); return true; }
function iface_update_supplicant_macaddr() {}
function iface_restart() { die('Unexpected restart'); }
function log_exception() { die('Unexpected exception'); }
''' + body + r'''
function check(name, pass) { push(cases, { name, pass: !!pass }); }
function make_bss(ssid, mld) { return { ifname: 'mld0', mld_ap: mld ?? true, ssid }; }
function config_for(ssid, radio) {
  return { phy: 'phy0', radio_idx: radio ?? 0, bss: [make_bss(ssid)] };
}
function reset(expected) {
  operations = []; completions = [];
  hostapd.data.mld = { mld0: { config: { phy: 'phy0', ssid: expected }, radio_mask: 7,
    ifname: 'mld0', macaddr: '02:00:00:00:00:10', anchor_radio: 1, has_wdev: true, iface: {} } };
  hostapd.data.config = { 'phy0.0': config_for(expected) };
  hostapd.bss = {};
}
let parser_cases = [
  ['hex-ascii', 'ssid2=4e6577', 'New'],
  ['raw-ascii', 'ssid=New', 'New'],
  ['raw-equals', 'ssid=a=b', 'a=b'],
  ['raw-space', 'ssid= a ', ' a '],
  ['hex-upper', 'ssid2=4E6577', 'New'],
  ['quoted-ascii', 'ssid2="New"', 'New'],
  ['quoted-inner-quotes', 'ssid2="a"b"', 'a"b'],
  ['quoted-literal-slash', 'ssid2="a\\nb"', 'a\\nb'],
  ['quoted-equals-space', 'ssid2=" a=b "', ' a=b '],
  ['quoted-no-closing-quote', 'ssid2="New', null],
  ['quoted-trailing-data', 'ssid2="New"bad', null],
  ['hex-binary', 'ssid2=610062ff', hexdec('610062ff')],
  ['hex-utf8', 'ssid2=d8b4d8a8d983d8a9', hexdec('d8b4d8a8d983d8a9')],
  ['hex-max-length', 'ssid2=' + hexenc('abcdefghijklmnopqrstuvwxyz123456'), 'abcdefghijklmnopqrstuvwxyz123456'],
  ['last-definition-wins', 'ssid=Old\nssid2=4e6577', 'New'],
  ['last-raw-wins', 'ssid2=4f6c64\nssid=New', 'New'],
  ['odd-hex', 'ssid2=abc', null],
  ['non-hex', 'ssid2=zz', null],
  ['hex-space-not-accepted-by-C', 'ssid2=4e 6577', null],
  ['missing-ssid', 'mld_ap=1', null],
];
for (let value in ['New', ' a=b ', 'a"b', 'a\\b', hexdec('d8b4d8a8d983d8a9'), hexdec('610062ff')])
  push(parser_cases, ['actual-generator-' + hexenc(value), 'ssid2=' + escape_string(value), value]);
for (let row in parser_cases) {
  let text = 'driver=nl80211\ninterface=mld0\nmld_ap=1\n' + row[1] + '\n';
  writefile(ARGV[0], text);
  let config = iface_load_config('phy0', 0, ARGV[0]);
  check('parser-' + row[0], config.bss[0].ssid == row[2]);
  check('parser-retains-data-' + row[0], join('\n', config.bss[0].data) == 'mld_ap=1\n' + row[1]);
}
writefile(ARGV[0], 'interface=mld0\nssid2=4e6577\nbss=ordinary\nssid=Other\n');
let parsed = iface_load_config('phy0', 0, ARGV[0]);
check('parser-bss-boundaries', parsed.bss[0].ssid == 'New' && parsed.bss[1].ssid == 'Other');
reset('New');
let failed_load = iface_load_config('phy0', 0, ARGV[0] + '.absent');
check('nonempty-missing-path-reports-load-error', failed_load.load_error);
let preserved = hostapd.data.config['phy0.0'];
let failed_result = iface_set_config('phy0.0', failed_load, (valid) => push(completions, valid));
check('failed-load-preserves-config-and-calls-failure', failed_result === false &&
  !length(operations) && hostapd.data.config['phy0.0'] == preserved &&
  length(completions) == 1 && completions[0] === false);
let explicit_remove = iface_load_config('phy0', 0, '');
check('empty-path-removal-contract-preserved', !explicit_remove.load_error && !length(explicit_remove.bss));

for (let row in [ ['same', 'New', 'New', true], ['stale', 'New', 'Old', false],
    ['missing', 'New', null, false], ['untyped', 'New', 123, false],
    ['legacy-descriptor', null, 'Old', true], ['legacy-missing', null, null, true],
    ['binary-exact', hexdec('610062'), hexdec('610062'), true],
    ['binary-nul-is-not-terminator', hexdec('610062'), 'a', false],
    ['case-sensitive', 'New', 'new', false] ]) {
  reset(row[1]);
  let bss = make_bss(row[2]);
  let result = !!bss_check_mld({ name: 'phy0' }, 'phy0.0', bss, 0);
  check('admit-' + row[0], result == row[3] && (row[3] ||
    (!length(operations) && bss.mld_bssid == null)));

  reset(row[1]);
  let old = hostapd.data.config['phy0.0'];
  let before = sprintf('%J', old);
  let config = config_for(row[2]);
  let incoming = sprintf('%J', config);
  result = iface_set_config('phy0.0', config, (valid) => push(completions, valid));
  check('set-result-' + row[0], (result !== false) == row[3] &&
    length(completions) == 1 && completions[0] == row[3]);
  if (!row[3])
    check('set-preserves-state-' + row[0], !length(operations) &&
      hostapd.data.config['phy0.0'] == old && sprintf('%J', old) == before &&
      sprintf('%J', config) == incoming);
}
reset('New');
let ordinary = config_for('Old'); ordinary.bss[0].mld_ap = false;
check('ordinary-bss-unaffected', iface_set_config('phy0.0', ordinary) !== false);
reset('New');
hostapd.data.mld = {};
check('detach-with-absent-owner', iface_set_config('phy0.0', config_for('Old'), null, true) !== false);
reset('New');
check('filter-mode-cannot-admit-stale-present-owner', iface_set_config('phy0.0', config_for('Old'), null, true) === false && !length(operations));
reset('New');
check('remove-unaffected', iface_set_config('phy0.0', null, (valid) => push(completions, valid)) !== false && completions[0]);

for (let expected in ['New', 'Old']) {
  reset(expected);
  let data = hostapd.data.mld.mld0;
  data.iface = { 'phy0.0': true };
  hostapd.bss = { 'phy0.1': { mld0: true } };
  hostapd.data.config = { 'phy0.0': config_for('New', 0),
    'phy0.1': config_for('New', 1), 'phy0.2': config_for('Old', 2) };
  for (let name, config in hostapd.data.config) {
    config.orig_bss = config.bss; config.bss = [];
  }
  let selected = { other_owner: true };
  mld_collect_reload(selected, 'mld0', data, true);
  let wanted = expected == 'New' ? ['other_owner', 'phy0.0', 'phy0.1'] : ['other_owner', 'phy0.2'];
  check('cache-all-sources-' + expected, sprintf('%J', sort(keys(selected))) == sprintf('%J', sort(wanted)));
  selected = {};
  mld_collect_reload(selected, 'mld0', data, false);
  check('detach-keeps-old-refs-' + expected, sprintf('%J', sort(keys(selected))) == sprintf('%J', ['phy0.0', 'phy0.1']));
}
printf('%J\n', cases);
'''.replace("printf('%J\\n', cases);", (r'''
reset('New');
let previous_config = hostapd.data.config['phy0.0'];
let reply = config_set_request({ args: { phy: 'phy0', radio: 0, config: ARGV[0] + '.absent' } });
check('request-file-open-failure-reports-invalid-argument', reply === 2 && !length(operations) &&
  hostapd.data.config['phy0.0'] == previous_config);
reset('New');
writefile(ARGV[0], 'interface=mld0\nmld_ap=1\nssid2="Old"\n');
previous_config = hostapd.data.config['phy0.0'];
reply = config_set_request({ args: { phy: 'phy0', radio: 0, config: ARGV[0] } });
check('stale-request-preserves-active-state-with-existing-pid-reply-contract', reply.pid === 42 &&
  !length(operations) && hostapd.data.config['phy0.0'] == previous_config);
reset('New');
reply = config_set_request({ args: { phy: 'phy0', radio: 0, config: '' } });
check('explicit-empty-path-request-removal-still-works', reply.pid === 42 && index(operations, 'remove-config') >= 0);
''' if handler else '') + "printf('%J\\n', cases);")


def execute(source):
    with tempfile.TemporaryDirectory() as temp:
        script = Path(temp) / 'test.uc'
        script.write_text(program(source))
        run = subprocess.run([str(UCODE), str(script), str(Path(temp) / 'hostapd.conf')],
                             capture_output=True, text=True, timeout=20)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    sha = lambda value: hashlib.sha256(value).hexdigest()
    source = SOURCE.read_text()
    lock = json.loads((ROOT / 'firmware/source-lock.json').read_text())
    assert sha(source.encode()) == next(row['sha256'] for row in lock['openwrt']['changed_files']
                                        if row['path'] == RELATIVE)
    generator_relative = GENERATOR.relative_to(ROOT / '.build/openwrt').as_posix()
    entry = next((row for row in lock['openwrt']['changed_files'] if row['path'] == generator_relative), None)
    generator_hash = entry['sha256'] if entry else sha(subprocess.check_output(
        ['git', 'show', lock['openwrt']['base'] + ':' + generator_relative], cwd=ROOT / '.build/openwrt'))
    assert sha(GENERATOR.read_bytes()) == generator_hash
    rows = execute(source)
    assert all(row['pass'] for row in rows), [row for row in rows if not row['pass']]
    old = FIXTURE.read_text()
    assert sha(old.encode()) == '017d7f9dd03f8fd24249ee6aa75eaa80b8a9b1fdd277311f5f3b3d2b46d87d2c'
    baseline = [row['name'] for row in execute(old) if not row['pass']]
    assert 'cache-all-sources-New' in baseline and 'set-preserves-state-stale' in baseline
    guard = re.search(r'\t// A late radio worker.*?\n\tlet phy = config.phy;', source, re.S)[0]
    mutants = {
        'remove-pre-mutation-guard': source.replace(guard, '\tlet phy = config.phy;'),
        'remove-bss-guard': source.replace('\tif (!mld_config_matches(mld_data, bss))\n\t\treturn;\n', ''),
        'remove-cache-ssid-filter': source.replace('mld_config_uses(config, name, data)))', 'mld_config_uses(config, name)))'),
        'ignore-missing-ssid': source.replace("type(bss.ssid) == 'string' && bss.ssid == data.config.ssid", "bss.ssid == null || bss.ssid == data.config.ssid"),
        'decode-hex-as-raw': source.replace("hexdec(value, '')", 'value'),
        'ignore-quoted-encoding': re.sub(r'bss.ssid = length\(value\).*?hexdec\(value, \'\'\);', "bss.ssid = hexdec(value, '');", source, flags=re.S),
        'ignore-file-load-error': source.replace('if (config?.load_error)', 'if (false)'),
        'ignore-request-file-load-error': source.replace('if (config.load_error)\n\t\t\t\treturn libubus.STATUS_INVALID_ARGUMENT;', 'if (false)\n\t\t\t\treturn libubus.STATUS_INVALID_ARGUMENT;'),
    }
    killed = {}
    for name, mutant in mutants.items():
        assert mutant != source, name
        killed[name] = [row['name'] for row in execute(mutant) if not row['pass']]
        assert killed[name], name
    report = dict(scope='Actual ucode parser/admission/cache, config_set dispatcher and wifi-scripts string encoder; framework I/O callbacks modeled; quoted/hex ssid2 and raw ssid syntax',
                  source_sha256=sha(source.encode()), harness_sha256=sha(Path(__file__).read_bytes()),
                  generator_sha256=sha(GENERATOR.read_bytes()),
                  runner_sha256=sha(program(source).encode()), ucode_sha256=sha(UCODE.read_bytes()),
                  baseline_sha256=sha(old.encode()), passed=len(rows), cases=rows,
                  baseline_failures=baseline, killed_mutants=killed)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=len(rows), old_failures=len(baseline), mutants_killed=len(killed))))


if __name__ == '__main__':
    main()
