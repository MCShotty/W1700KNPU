#!/usr/bin/env python3
"""Check sanitized recorded startup evidence, not a fresh router/client test."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'research/checkpoints/2026-09-06-wifi-config'
EXPECTED = {
    'ap2g': (1, 0), 'ap5g': (1, 0), 'ap6g': (1, 0),
    'ap25': (2, 0), 'ap26': (2, 0), 'ap56': (2, 0), 'ap256': (3, 0),
    'mlo25': (1, 2), 'mlo26': (1, 2), 'mlo56': (1, 2), 'mlo256': (1, 3),
    'ap256dual': (6, 0), 'mlo56ap2': (2, 2), 'mlo256-reload': (1, 3),
    **{name: (1, 0) for name in [
        'ap2g-legacy-wpa2', 'ap2g-ht20-wpa2', 'ap2g-he20-mixed', 'ap2g-eht40',
        'ap5g-vht20-wpa2', 'ap5g-vht40-wpa2', 'ap5g-vht80-wpa2',
        'ap5g-he80-mixed', 'ap5g-eht160', 'ap6g-he20', 'ap6g-he40',
        'ap6g-he80', 'ap6g-he160', 'ap6g-eht320', 'ap6g-auto-eht80']},
}


def main():
    raw = (EVIDENCE / 'live-matrix.json').read_text(encoding='utf-8-sig')
    evidence = json.loads(raw)
    assert not re.search(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', raw)
    assert not re.search(r'"(?:ssid|key|password|macaddr)"\s*:', raw)
    rows = {row['profile']: row for row in evidence['cases']}
    assert len(rows) == len(evidence['cases']) == 29
    assert rows.keys() == EXPECTED.keys()
    for name, (interfaces, links) in EXPECTED.items():
        row = rows[name]
        assert row['global_interfaces'] == len(row['interfaces']) == interfaces, name
        assert row['mlo_links'] == links, name
        assert row['unique_global_addresses'] == interfaces, name
        assert row['after_cleanup_global_interfaces'] == 0, name
        counted_links = 0
        operating_channels = 0
        for iface in row['interfaces']:
            if iface['links']:
                for link in iface['links']:
                    assert link['running'] and not link['pending'], name
                    counted_links += 1
                    operating_channels += 1
            else:
                assert iface['running'] and not iface['pending'], name
                operating_channels += 1
        assert counted_links == links
        assert sum(line.startswith('channel ') for line in row['channel_lines']) == operating_channels
    assert any('width: 320 MHz' in line for line in rows['ap6g-eht320']['channel_lines'])
    assert any('width: 320 MHz' in line for line in rows['mlo256-reload']['channel_lines'])
    assert any('width: 160 MHz' in line for line in rows['ap5g-eht160']['channel_lines'])
    assert rows['ap2g-eht40']['channel_lines'][-1].startswith('channel 6 (2437 MHz), width: 20 MHz')
    post = json.loads((EVIDENCE / 'post-decoder-matrix.json').read_text(encoding='utf-8-sig'))
    assert len(post['cases']) == 7
    assert {row['profile'] for row in post['cases']} == {
        'post-ap256', 'post-mlo25', 'post-mlo26', 'post-mlo56', 'post-mlo256',
        'post-ap256dual', 'post-mlo56ap2'}
    for row in post['cases']:
        interfaces, links = EXPECTED[row['profile'].removeprefix('post-')]
        assert row['global_interfaces'] == row['unique_global_addresses'] == interfaces
        assert row['mlo_links'] == links and row['after_cleanup_global_interfaces'] == 0
        for iface in row['interfaces']:
            for status in iface['links'] or [iface]:
                assert status['running'] and not status['pending']
    final = json.loads((EVIDENCE / 'final-router-state.json').read_text(encoding='utf-8-sig'))
    assert final['router']['wireless_config_restored']
    assert not final['router']['pending_uci_changes']
    assert final['router']['hostapd_interfaces'] == 0
    assert final['router']['wlan_npu'] == 'compiled-out'
    assert final['router']['nl80211_hotfix_hash_verified']
    assert final['router']['hostapd_current_nl80211_inode_mapped']
    assert final['served_luci_status'] == 200
    package = json.loads((EVIDENCE / 'luci-package.json').read_text())
    assert final['served_luci_sha256'] == package['payload_sha256']
    print(json.dumps({'recorded_cases_verified': 29, 'post_decoder_cases_verified': 7,
                      'cleanup_and_served_payload_verified': True,
                      'fresh_router_or_client_test': False}))


if __name__ == '__main__':
    main()
