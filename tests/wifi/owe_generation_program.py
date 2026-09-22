#!/usr/bin/env python3
"""Emit actual-source security generation/admission checks with in-memory I/O."""
import argparse
from pathlib import Path
import re

from test_mld_ssid import function

ROOT = Path(__file__).resolve().parents[2]
TREE = ROOT / '.build/openwrt'
WIFI = TREE / 'package/network/config/wifi-scripts/files-ucode/usr/share/ucode/wifi'
RECEIVER = TREE / 'package/network/services/hostapd/files/hostapd.uc'
HELPER = TREE / 'package/network/config/wifi-scripts/files/usr/share/ucode/wifi/mld-config.uc'


def functions(path, names=None):
    source = path.read_text().replace('export function', 'function')
    if names is None:
        names = re.findall(r'^function (\w+)\(', source, re.M)
    return '\n\n'.join(function(source, name) for name in names)


PRELUDE = r'''
import { md5, sha256 } from 'digest';
let files = {}, writes = [], results = [], cases = [], config_data = '', iface_idx = 0;
let phy_features = {}, status = {};
const mlo_link_local_fields = { macaddr: true };
let fs = {
  stat: path => exists(files, path),
  rename: (a, b) => { files[b] = files[a]; delete files[a]; push(writes, b); },
  readfile: path => files[path],
  writefile: (path, value) => { files[path] = value; push(writes, path); return length(value); },
  open: function(path, mode) {
    if (mode == 'w') { files[path] = ''; push(writes, path); }
    if (mode == 'a') files[path] ??= '';
    let offset = 0;
    return {
      write: value => { files[path] += value; return length(value); },
      close: () => true,
      read: function() {
        if (offset >= length(files[path])) return null;
        let end = index(substr(files[path], offset), '\n');
        end = end < 0 ? length(files[path]) - 1 : offset + end;
        let line = substr(files[path], offset, end + 1 - offset);
        offset = end + 1;
        return line;
      }
    };
  }
};
let open = fs.open, readfile = fs.readfile;
let netifd = { set_vlan: function() {}, add_process: function() {},
  setup_failed: function() {} };
global.ubus = { list: () => true, call: name => name == 'network.wireless' ? status : ({ pid: 1 }) };
let hostapd = { data: { file_fields: {} } };
let libuci = { cursor: () => ({ get: () => null }) };
function check(name, pass) { push(cases, { name, pass: !!pass }); }
function clone(value) { return json(sprintf('%J', value)); }
'''

CASES = r'''
let profiles = [
  { name: 'sae', encryption: 'sae', mlo: true, extended: true, gcmp: true },
  { name: 'sae-ft', encryption: 'sae', mlo: true, extended: true, ft: true, gcmp: true },
  { name: 'owe', encryption: 'owe', mlo: true, gcmp: true },
  { name: 'enterprise', encryption: 'wpa3', mlo: true, gcmp: true },
  { name: 'enterprise192', encryption: 'wpa3-192', mlo: true, gcmp: true },
  { name: 'sae-explicit-off', encryption: 'sae', mlo: true,
    overrides: { gcmp256: false, sae_ext_key: false } },
  { name: 'sae-forced-ccmp', encryption: 'sae+ccmp', mlo: true, extended: true },
  { name: 'sae-forced-gcmp256', encryption: 'sae+gcmp256', mlo: true, extended: true, gcmp: true },
  { name: 'sae-no-driver-gcmp', encryption: 'sae', mlo: true, extended: true, no_gcmp: true },
  { name: 'ordinary-sae', encryption: 'sae' },
  { name: 'ordinary-sae-mixed', encryption: 'sae-mixed', legacy: true },
  { name: 'ordinary-compat-eht', encryption: 'sae-compat', override_gcmp: true, legacy: true },
  { name: 'ordinary-compat-he', encryption: 'sae-compat', htmode: 'HE20', legacy: true },
  { name: 'ordinary-sae-explicit-on', encryption: 'sae', extended: true, gcmp: true,
    overrides: { gcmp256: true, sae_ext_key: true } },
  { name: 'owe-transition', encryption: 'owe', mlo: true, transition: 'auto' },
  { name: 'owe-manual-ifname', encryption: 'owe', mlo: true, transition: 'ifname' },
  { name: 'owe-manual-bssid', encryption: 'owe', mlo: true, transition: 'bssid' },
  { name: 'ordinary-owe-transition', encryption: 'owe', transition: 'auto' },
  { name: 'ordinary-owe-manual-ifname', encryption: 'owe', transition: 'ifname' },
  { name: 'ordinary-owe-manual-bssid', encryption: 'owe', transition: 'bssid' }
];
for (let band in ['2g', '5g', '6g']) {
  for (let profile in profiles) {
    if (band == '6g' && profile.legacy) continue;
    let path = '/var/run/hostapd-phy0.0.conf';
    files = { [path]: 'prior-config' }; writes = []; config_data = 'prior-buffer'; iface_idx = 0;
    phy_features = { cipher_gcmp256: !profile.no_gcmp };
    let mlo = !!profile.mlo;
    let transition = profile.transition;
    let name = mlo ? 'ap-mld0' : 'ordinary0';
    let config = { mode: 'ap', ifname: name, ssid: 'Synthetic',
      encryption: profile.encryption, key: 'synthetic-passphrase',
      ieee80211w: 2, sae_pwe: 2, rnr: true, mlo, radios: [1, 2, 0],
      macaddr: '02:00:00:00:00:01', ieee80211r: !!profile.ft,
      auth_server: '192.0.2.1', auth_secret: 'synthetic-radius-secret',
      ...(profile.overrides ?? {}) };
    if (transition == 'auto') config.owe_transition = true;
    if (transition == 'ifname') config.owe_transition_ifname = 'ordinary-open0';
    if (transition == 'bssid') {
      config.owe_transition_bssid = '02:00:00:00:00:03';
      config.owe_transition_ssid = 'Synthetic-open';
    }
    let descriptor = clone(config);
    let radio = index(['2g', '5g', '6g'], band);
    let radios = map(['2g', '5g', '6g'], (band, radio) => ({ band, radio,
      country: 'SA', channel: [6, 36, 37][radio], htmode: profile.htmode ?? 'EHT20' }));
    let data = { phy: 'phy0', phy_suffix: '.0', vif_phy_suffix: '.0',
      config: { ...radios[radio], num_global_macaddr: 1 },
      interfaces: { test: { name: 'test', config, vlans: [], stas: [] } } };
    status = {};
    for (let rc in radios)
      status['radio' + rc.radio] = { config: rc, interfaces: [{ section: 'test', config: clone(config) }] };
    let snapshot = clone(data);
    if (transition == 'auto') data.interfaces.test.config.owe_transition_ifname = 'ordinary-open0';
    let label = band + '-' + profile.name;
    let rejected;
    try { setup(data, snapshot); } catch (e) { rejected = '' + e; }
    let should_reject = transition && (mlo || band == '6g');
    check(label + '-admission', should_reject ? !!rejected && index(rejected, 'OWE transition') >= 0 : !rejected);
    if (should_reject) {
      check(label + '-no-file-mutation', !length(writes) && files[path] == 'prior-config' && config_data == 'prior-buffer');
      push(results, { profile: label, rejected: !!rejected, error: rejected, writes: length(writes) });
      continue;
    }
    if (rejected) { push(results, { profile: label, error: rejected }); continue; }
    let parsed = iface_load_config('phy0', radio, path);
    let id = mld_config_id(descriptor);
    let encrypted = parsed.bss[0];
    let rows = [];
    for (let bss in parsed.bss) {
      let props = {};
      for (let line in bss.data) {
        let pair = split(line, '=', 2);
        props[pair[0]] = pair[1];
      }
      push(rows, { ifname: bss.ifname, ssid: bss.ssid, mld: !!bss.mld_ap,
        fingerprint: bss.mld_config_id != null,
        wpa: props.wpa ?? '0', key_mgmt: props.wpa_key_mgmt,
        pairwise: props.wpa_pairwise ?? props.rsn_pairwise,
        override_pairwise: props.rsn_override_pairwise_2,
        transition_ifname: props.owe_transition_ifname });
    }
    push(results, { profile: label, bss: rows });
    if (mlo) {
      check(label + '-encrypted-mld', encrypted.mld_ap == 1);
      check(label + '-descriptor-admission', mld_config_matches({ config: descriptor, config_id: id }, encrypted));
      check(label + '-encrypted-fingerprint', encrypted.mld_config_id == id);
    }
    let want_open = transition == 'auto';
    check(label + '-bss-count', length(parsed.bss) == (want_open ? 2 : 1));
    if (want_open) {
      let bss = parsed.bss[1];
      check(label + '-open-not-mld', !bss.mld_ap);
      check(label + '-open-visible-ssid', bss.ssid == descriptor.ssid);
    }
    if (band == '6g')
      check(label + '-all-bss-rsn', !length(filter(rows, x => x.wpa != '2')));
    check(label + '-gcmp256', (index(rows[0].pairwise ?? '', 'GCMP-256') >= 0) == !!profile.gcmp);
    if (index(profile.encryption, 'sae') == 0 && !profile.legacy)
      check(label + '-sae-ext-key', (index(rows[0].key_mgmt ?? '', 'SAE-EXT-KEY') >= 0) == !!profile.extended);
    if (profile.ft)
      check(label + '-ft-sae-ext-key', index(rows[0].key_mgmt ?? '', 'FT-SAE-EXT-KEY') >= 0);
    if (profile.override_gcmp)
      check(label + '-override-gcmp256', rows[0].override_pairwise == 'GCMP-256');
  }
}
let failures = filter(cases, x => !x.pass);
print(sprintf('%J\n', { cases: length(cases), failures, results,
  scope: 'Actual AP/security generation, full setup validation, parser and admission; ubus inventory, radio capabilities, I/O, schema defaults and MAC allocation modeled',
  radio_or_config_changes: false }));
exit(length(failures) ? 1 : 0);
'''


def program():
    common = functions(WIFI / 'common.uc', [
        'append_raw', 'append', 'escape_string', 'append_string', 'append_vars',
        'append_list', 'append_string_vars', 'set_default', 'push_config',
        'touch_file', 'append_value', 'comment', 'dump_config', 'flush_config', 'log'])
    iface = functions(WIFI / 'iface.uc', ['parse_encryption', 'wpa_key_mgmt'])
    iface = ('let iface = (function() {\n' + iface + '\nreturn { parse_encryption, wpa_key_mgmt, '
             "prepare: config => { config.macaddr ??= '02:00:00:00:00:02'; } }; })();\n")
    ap = 'let ap = (function() {\n' + functions(WIFI / 'ap.uc') + '\nreturn { generate }; })();\n'
    source = (WIFI / 'hostapd.uc').read_text()
    names = re.findall(r'^(?:export )?function ((?:mlo_|validate_mlo|validate_owe)\w*)\(', source, re.M)
    generator = functions(WIFI / 'hostapd.uc', names + ['setup_interface', 'setup'])
    receiver = functions(RECEIVER, ['config_add_bss', 'iface_load_config',
                                    'mld_ssid_matches', 'mld_config_matches'])
    helper = functions(HELPER)
    radio = "\nfunction generate(config) { append('driver', 'nl80211'); append('channel', 6); }\n"
    return PRELUDE + common + radio + iface + ap + helper + '\n' + generator + '\n' + receiver + CASES


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--mutant', choices=['mlo-default-off', 'skip-owe-preflight', 'override-explicit'])
    args = parser.parse_args()
    source = program()
    replacements = {
        'mlo-default-off': [('let enhanced = mlo ||', 'let enhanced = false ||')],
        'skip-owe-preflight': [('\tvalidate_owe_transition(data);', '\t/* mutation: preflight omitted */')],
        'override-explicit': [('config.gcmp256 ??= enhanced;', 'config.gcmp256 = enhanced;'),
                              ('config.sae_ext_key ??= enhanced;', 'config.sae_ext_key = enhanced;')],
    }
    for old, new in replacements.get(args.mutant, []):
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    args.out.write_text(source)
    print(args.out)
