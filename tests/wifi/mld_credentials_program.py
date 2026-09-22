#!/usr/bin/env python3
"""Emit an actual-source ucode test program for execution with target digest.so."""
import argparse
import hashlib
from pathlib import Path

from test_mld_ssid import function

ROOT = Path(__file__).resolve().parents[2]
TREE = ROOT / '.build/openwrt'
HOSTAPD = TREE / 'package/network/services/hostapd/files/hostapd.uc'
HELPER = TREE / 'package/network/config/wifi-scripts/files/usr/share/ucode/wifi/mld-config.uc'
NETIFD = TREE / 'package/network/config/wifi-scripts/files/lib/netifd/wireless.uc'
GENERATOR = TREE / 'package/network/config/wifi-scripts/files-ucode/usr/share/ucode/wifi/hostapd.uc'
NAMES = ['mld_radio_matches', 'mld_ssid_matches', 'mld_config_matches',
         'bss_check_mld', 'iface_set_config', 'config_add_bss',
         'iface_load_config', 'mld_config_uses', 'mld_collect_reload']

PRELUDE = r'''
import { open, writefile } from 'fs';
let cases = [], operations = [], completions = [];
let hostapd = { data: { mld: {}, config: {}, file_fields: {} }, bss: {}, printf: function() {} };
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
function check(name, pass) { push(cases, { name, pass: !!pass }); }
function clone(value) { return json(sprintf('%J', value)); }
'''

CASES = r'''
let raw = { mode: 'ap', mlo: true, ssid: 'Synthetic-MLD', key: 'synthetic-key-a',
  encryption: 'sae', ieee80211w: 2, sae_pwe: 2, radios: [1, 2, 0],
  network: ['lan'], isolate: true, rnr: true, wds: true,
  radio_macaddr: ['02:00:00:00:00:01', '02:00:00:00:00:02', '02:00:00:00:00:03'] };
let owners = {}, local = clone(raw);
let ifname = mlo_vif_create(local, [{ band: '5g' }], {}, owners);
owners[ifname].phy = 'phy0';
let id = mld_config_id(owners[ifname]);
check('sha256-real-module-known-vector', sha256('test') == '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08');
for (let i = 0; i < 3; i++) {
  let link = clone(raw);
  link.ifname = ifname;
  mlo_vif_macaddr(link, ['radio1', 'radio2', 'radio0'], ['radio1', 'radio2', 'radio0'][i], i);
  check('real-producer-link-' + i, mld_config_id(link) == id);
}
let reverse = {};
for (let key in sort(keys(raw), (a, b) => a < b ? 1 : -1)) reverse[key] = raw[key];
check('top-level-order-irrelevant', mld_config_id(reverse) == mld_config_id(raw));
check('nested-order-irrelevant', mld_config_id({ x: { a: 1, b: 2 } }) == mld_config_id({ x: { b: 2, a: 1 } }));
check('array-order-preserved', mld_config_id({ x: [1, 2] }) != mld_config_id({ x: [2, 1] }));
check('type-preserved', mld_config_id({ x: 1 }) != mld_config_id({ x: '1' }));
check('missing-not-null', mld_config_id({}) != mld_config_id({ x: null }));
for (let field, value in { key: 'synthetic-key-b', encryption: 'sae-mixed', ieee80211w: 1,
    sae_pwe: 1, ssid: 'Changed', network: ['guest'], isolate: false, rnr: false,
    radios: [2, 1, 0], wds: false, hostapd_options: ['sae_groups=19'],
    radio_macaddr: ['02:00:00:00:00:04'], auth_secret: 'synthetic-radius',
    key1: 'synthetic-wep', sae_password_file: '/tmp/synthetic-sae',
    eap_type: 'tls', auth_server: '192.0.2.1', wpa_psk_file: '/tmp/synthetic-psk' }) {
  let changed = clone(raw); changed[field] = value;
  check('shared-field-changes-identity-' + field, mld_config_id(changed) != mld_config_id(raw));
}
let snapshot_data = { config: {}, interfaces: { test: { config: clone(raw) } } };
let snapshot = mlo_setup_snapshot(snapshot_data);
snapshot_data.interfaces.test.config.key = 'mutated';
check('actual-snapshot-retains-key', snapshot.interfaces.test.config.key == raw.key);

function make_config(token) {
  return { phy: 'phy0', radio_idx: 0, bss: [{ ifname: 'mld0', mld_ap: true,
    ssid: raw.ssid, mld_config_id: token }] };
}
function reset() {
  operations = []; completions = [];
  hostapd.data.mld = { mld0: { config: { ...raw, phy: 'phy0' }, config_id: id,
    radio_mask: 7, ifname: 'mld0', macaddr: '02:00:00:00:00:10',
    anchor_radio: 1, has_wdev: true, iface: { 'phy0.0': true } } };
  hostapd.data.config = { 'phy0.0': make_config(id) };
  hostapd.bss = {};
}
let other = clone(raw); other.key = 'synthetic-key-b';
for (let row in [['current', id, true], ['old-key', mld_config_id(other), false],
    ['missing-marker', null, false], ['malformed-marker', 'invalid', false]]) {
  reset();
  let incoming = make_config(row[1]), old = hostapd.data.config['phy0.0'];
  let before = sprintf('%J', incoming);
  let result = iface_set_config('phy0.0', incoming, (ok) => push(completions, ok));
  check('request-result-' + row[0], (result !== false) == row[2] &&
    length(completions) == 1 && completions[0] == row[2]);
  if (!row[2]) check('reject-before-mutation-' + row[0], !length(operations) &&
    hostapd.data.config['phy0.0'] == old && sprintf('%J', incoming) == before);
  reset();
  let bss = make_config(row[1]).bss[0];
  result = !!bss_check_mld({ name: 'phy0' }, 'phy0.0', bss, 0);
  check('bss-admission-' + row[0], result == row[2] && (row[2] || !length(operations)));
  reset();
  hostapd.data.config['phy0.0'] = make_config(row[1]);
  let selected = {};
  mld_collect_reload(selected, 'mld0', hostapd.data.mld.mld0, true);
  check('cached-activation-' + row[0], !!selected['phy0.0'] == row[2]);
  selected = {};
  mld_collect_reload(selected, 'mld0', hostapd.data.mld.mld0, false);
  check('old-detach-retained-' + row[0], !!selected['phy0.0']);
}
let path = '/tmp/w1700k-credential-parser-synthetic.conf';
writefile(path, 'interface=mld0\nmld_ap=1\n#mld_config_id=' + id + '\nbss=ordinary\nssid=Ordinary\n');
let parsed = iface_load_config('phy0', 0, path);
check('marker-parser-keeps-bss-boundary', parsed.bss[0].mld_config_id == id && parsed.bss[1].mld_config_id == null);
check('marker-survives-inline-config', index(parsed.bss[0].data, '#mld_config_id=' + id) >= 0);
let failures = filter(cases, c => !c.pass);
print(sprintf('%J\n', { cases: length(cases), failures, crypto: 'target digest.sha256',
  source_functions: true, framework_io: 'modeled', client_authentication: false }));
exit(length(failures) ? 1 : 0);
'''


def program(source, mutant=None):
    body = '\n'.join(function(source, name) for name in NAMES
                     if f'function {name}(' in source)
    helper = HELPER.read_text().replace('export function', 'function')
    if mutant == 'remove-id-guard':
        old = '(!data?.config_id || bss.mld_config_id == data.config_id)'
        assert old in body
        body = body.replace(old, 'true')
    if mutant == 'omit-key':
        helper = helper.replace('let common = { ...config };',
                                'let common = { ...config }; delete common.key;')
    if mutant == 'ignore-marker':
        old = '\t\tif (val[0] == "#mld_config_id")\n\t\t\tbss.mld_config_id = val[1];'
        assert old in body
        body = body.replace(old, '')
    producer = '\n'.join(function(NETIFD.read_text(), name)
                         for name in ['mlo_vif_create', 'mlo_vif_macaddr'])
    generator = GENERATOR.read_text().replace('export function', 'function')
    # Only the hardware-free immutable snapshot path is needed here.
    snapshot = function(generator, 'mlo_setup_snapshot')
    return PRELUDE + helper + '\n' + producer + '\n' + body + '\n' + (
        "function mlo_local_links(data) { return [true]; }\n" + snapshot) + CASES


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=HOSTAPD)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--mutant', choices=['remove-id-guard', 'omit-key', 'ignore-marker'])
    parser.add_argument('--extract-baseline-fixture', action='store_true')
    args = parser.parse_args()
    source = args.source.read_text()
    if args.extract_baseline_fixture:
        assert hashlib.sha256(args.source.read_bytes()).hexdigest() == 'c5db50945a641ab94a31ff11de143fa28d187b046fd4adb7bdb15ea3c0086212'
        args.out.write_text('\n\n'.join(function(source, name) for name in NAMES
                           if f'function {name}(' in source) + '\n')
    else:
        args.out.write_text(program(source, args.mutant))
    print(args.out)
