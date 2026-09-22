#!/usr/bin/env python3
"""Exercise actual file parsing and BSS reload selection with modeled driver I/O."""
import argparse
from pathlib import Path
import re

from test_mld_ssid import function

ROOT = Path(__file__).resolve().parents[2]
TREE = ROOT / '.build/openwrt'
SOURCE = TREE / 'package/network/services/hostapd/files/hostapd.uc'
COMMON = TREE / 'package/network/config/wifi-scripts/files/usr/share/hostap/common.uc'
NAMES = [
    'config_add_bss', 'iface_load_config', 'remove_file_fields', 'bss_remove_file_fields',
    'bss_ifindex_list', 'bss_config_hash', 'bss_find_existing', 'get_config_bss',
    'radio_line_is_chan', 'radio_base', 'radio_reload_class', 'iface_gen_config',
    'bss_reload_psk', 'normalize_rxkhs', 'bss_reload_rxkhs', 'iface_reload_config',
]

PRELUDE = r'''
import { sha1 } from 'digest';
let files = {}, calls = [], logs = [], active = null;
function clone(value) { return json(sprintf('%J', value)); }
function readfile(path) { return files[path]; }
function open(path) {
  if (!exists(files, path)) return null;
  let lines = split(files[path], '\n'), offset = 0;
  return { read: () => offset < length(lines) ? lines[offset++] + '\n' : null, close: () => true };
}
let hostapd = { data: { pending_config: {} }, bss: {}, interfaces: {},
  sha1: value => value == null ? null : sha1(value),
  rkh_derive_key: value => value,
  printf: value => push(logs, value) };
function phy_is_fullmac() { return false; }
function iface_config_macaddr_list(config) { return { [config.bss[0].bssid]: 0 }; }
function iface_macaddr_init(phydev, config, addresses) { return addresses; }
function iface_channel_switch() { die('Unexpected channel change'); }
function wdev_remove() { die('Unexpected interface removal'); }
function bss_macaddr_next() { die('Unexpected MAC allocation'); }
'''

CASES = r'''
function config_text(mlo, extra) {
  return 'driver=nl80211\nchannel=6\ninterface=synthetic0\n' +
    'bssid=02:00:00:00:00:01\nssid=Synthetic\nwpa=2\nwpa_key_mgmt=SAE\n' +
    'sae_password_file=/sae\nwpa_psk_file=/psk\nvlan_file=/vlan\n' +
    'accept_mac_file=/accept\n' + (mlo ? 'mld_ap=1\nmld_link_id=0\n' : '') + (extra ?? '');
}
let profiles = [
  { name: 'unchanged', want: 'none' },
  { name: 'sae-rekey', file: '/sae', content: 'new-synthetic-passphrase|mac=02:00:00:00:00:02\n', want: 'full' },
  { name: 'sae-remove-all', file: '/sae', content: '', want: 'full' },
  { name: 'sae-add-peer', file: '/sae', content: 'old-synthetic-passphrase|mac=02:00:00:00:00:02\nsecond-passphrase|mac=02:00:00:00:00:03\n', want: 'full' },
  { name: 'sae-change-vlan', file: '/sae', content: 'old-synthetic-passphrase|mac=02:00:00:00:00:02|vlanid=17\n', want: 'full' },
  { name: 'sae-change-identifier', file: '/sae', content: 'old-synthetic-passphrase|mac=02:00:00:00:00:02|id=changed\n', want: 'full' },
  { name: 'sae-and-psk', file: '/sae', content: 'new-synthetic-passphrase\n', psk: true, want: 'full' },
  { name: 'psk-only', file: '/psk', content: '00:00:00:00:00:00 new-synthetic-passphrase\n', want: 'files' },
  { name: 'vlan-only', file: '/vlan', content: '17 synthetic-vlan17\n', want: 'files' },
  { name: 'acl-only', file: '/accept', content: '02:00:00:00:00:03\n', want: 'full' },
  { name: 'nonfile-setting', extra: 'wpa_group_rekey=700\n', want: 'full' },
  { name: 'sae-new-path-same-content', new_path: true, want: 'files' },
  { name: 'sae-new-path-new-content', new_path: true, content: 'new-synthetic-passphrase\n', want: 'full' },
];
let rows = [];
for (let mlo in [false, true]) {
  for (let profile in profiles) {
    files = { '/sae': 'old-synthetic-passphrase|mac=02:00:00:00:00:02\n',
      '/psk': '00:00:00:00:00:00 old-synthetic-passphrase\n', '/vlan': '', '/accept': '' };
    files['/config'] = config_text(mlo);
    let old = iface_load_config('phy0', 0, '/config');
    if (profile.file) files[profile.file] = profile.content;
    if (profile.psk) files['/psk'] = '00:00:00:00:00:00 second-synthetic-passphrase\n';
    files['/config'] = config_text(mlo, profile.extra);
    if (profile.new_path) {
      files['/sae-new'] = profile.content ?? files['/sae'];
      files['/config'] = replace(files['/config'], 'sae_password_file=/sae\n', 'sae_password_file=/sae-new\n');
    }
    let next = iface_load_config('phy0', 0, '/config');
    for (let config in [old, next])
      if (mlo) config.bss[0].mld_bssid = '02:00:00:00:00:01';
    calls = []; logs = [];
    active = { set_config: (text, index, files_only) => {
        push(calls, { operation: 'set_config', files_only: !!files_only }); return 0;
      }, ctrl: command => { push(calls, { operation: command }); return command == 'GET_RXKHS' ? '' : 'OK'; },
      rename: () => die('Unexpected rename'), delete: () => die('Unexpected BSS deletion') };
    hostapd.bss = { 'phy0.0': { synthetic0: active } };
    hostapd.interfaces = { 'phy0.0': { state: () => 'ENABLED', set_bss_order: () => true,
      add_bss: () => die('Unexpected new BSS') } };
    let changed_hash = old.bss[0].hash.sae_password_file != next.bss[0].hash.sae_password_file;
    let ok = iface_reload_config('phy0.0', { name: 'phy0' }, next, old);
    let selected = filter(calls, call => call.operation == 'set_config');
    let route = !length(selected) ? 'none' : selected[0].files_only ? 'files' : 'full';
    push(rows, { name: (mlo ? 'mlo-' : 'ordinary-') + profile.name,
      mlo, changed_sae_hash: changed_hash, route, expected: profile.want,
      passed: ok && route == profile.want && length(selected) <= 1, calls });
  }
}
let failures = filter(rows, row => !row.passed);
printf('%J\n', { cases: length(rows), failures, rows,
  scope: 'Actual parser/file hashes, equality, existing-BSS matching and full reload selector. Filesystem and native driver/resource callbacks modeled.' });
exit(length(failures) ? 1 : 0);
'''


def program(source):
    constants = []
    for pattern in [r'hostapd.data.file_fields = \{.*?\n\};',
                    r'hostapd.data.iface_fields = \{.*?\n\};',
                    r'const radio_chan_fields = \[.*?\n\];']:
        match = re.search(pattern, source, re.S)
        assert match, pattern
        constants.append(match[0])
    return (PRELUDE + '\n'.join(constants) + '\n' + function(COMMON.read_text(), 'is_equal') + '\n' +
            '\n\n'.join(function(source, name) for name in NAMES) + CASES)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--ignore-sae-hash', action='store_true')
    args = parser.parse_args()
    source = args.source.read_text()
    if args.ignore_sae_hash:
        assert 'delete new_cfg.hash.sae_password_file;' not in source
        anchor = '\tdelete new_cfg.hash.wpa_psk_file;'
        assert source.count(anchor) == 1
        source = source.replace(anchor, anchor + '\n\tdelete new_cfg.hash.sae_password_file;')
    args.out.write_text(program(source))
    print(args.out)
