#!/bin/sh
set -eu
[ "$(cat /tmp/sysinfo/board_name)" = gemtek,w1700k-ubi ] || exit 80
[ "$(uname -r)" = 6.18.44 ] || exit 88
[ -z "$(uci changes wireless)" ] || exit 81
[ "$(sha256sum /etc/config/wireless | cut -d ' ' -f1)" = a87e59eb9c6314be153d8af85f88ebbe0438a1cfb6e0e0ee92ee1b5f200c416d ] || exit 82
[ "$(sha256sum /usr/libexec/w1700k-wireless-regulatory | cut -d ' ' -f1)" = 04497f40bb5c774d985784ee920b682da16d6e8ae71d55778400477a7111b7d5 ] || exit 83
[ "$(sha256sum /usr/share/hostap/hostapd.uc | cut -d ' ' -f1)" = e9bdbed02f2072121083130d1de0dc91996c95217550fd5604fcc641d96e6338 ] || exit 84
[ "$(sha256sum /usr/share/ucode/wifi/hostapd.uc | cut -d ' ' -f1)" = 79004ebbb01a637a824806c7254170d55ba7a418bb137f370a305b9b4c2a4a86 ] || exit 84
[ "$(sha256sum /usr/share/ucode/wifi/iface.uc | cut -d ' ' -f1)" = ef91cb5cb1e1c6c99d07c67d9dccdc4d846ed05a2c1f36afde9f49b2e9a79deb ] || exit 84
[ "$(sha256sum /usr/sbin/w1700k-wireless-validate | cut -d ' ' -f1)" = 8ad893d582ad04e3b93923747cf7aa52cf9a8a14ea5d8dd0d479cf6452a73604 ] || exit 84
[ "$(sha256sum /www/luci-static/resources/view/network/wireless.js | cut -d ' ' -f1)" = 92897bf26ad78dd3833418552f288460730baede09cc9aff152b05ef933a8e43 ] || exit 84
[ "$(sha256sum /usr/share/ucode/wifi/mld-config.uc | cut -d ' ' -f1)" = 16db8c275cd64607845ae9b7a6093d05e260dcad5266e3cd8b61d8918d1df1f2 ] || exit 84
[ "$(sha256sum /usr/share/schema/wireless.wifi-iface.json | cut -d ' ' -f1)" = a3291ac102b0b97cee5e57f128fc2b9b34b428f052b52f16c849e310b79866d0 ] || exit 85
[ "$(sha256sum /usr/lib/ucode/nl80211.so | cut -d ' ' -f1)" = 6c2af55f71276895be7e906f67479339984affe10bf893b05ae3e74cb2cff92d ] || exit 89
status=$(ubus call hostapd status)
[ "$(printf '%s' "$status" | jsonfilter -e '@.interfaces.*.wiphy' | wc -l)" = 0 ] || exit 86
[ "$(iw dev | awk '$1 == "Interface" {n++} END {print n+0}')" = 0 ] || exit 93
wireless_status=$(ubus call network.wireless status)
pending=$(printf '%s' "$wireless_status" | jsonfilter -e '@.*.pending' | grep -c '^true$') || :
[ "$pending" = 0 ] || exit 94
[ "$(/usr/sbin/w1700k-wlan-npu-mode json | jsonfilter -e '@.npu.runtime_state')" = compiled-out ] || exit 87
inode=$(ls -i /usr/lib/ucode/nl80211.so | awk '{ print $1 }')
hostapd_pids=$(pidof hostapd)
[ -n "$hostapd_pids" ] || exit 90
mapped=0
for pid in $hostapd_pids; do
    grep -q '/usr/lib/ucode/nl80211.so' "/proc/$pid/maps" || continue
    awk -v inode="$inode" '$6 == "/usr/lib/ucode/nl80211.so" { found=1; if ("x" $5 != "x" inode || $7 == "(deleted)") bad=1 } END { exit (!found || bad) }' "/proc/$pid/maps" || exit 91
    mapped=$((mapped + 1))
done
[ "$mapped" -ge 1 ] || exit 92
printf '%s\n' '{"board":"gemtek,w1700k-ubi","kernel":"6.18.44","wireless_config_restored":true,"pending_uci_changes":false,"netifd_pending":0,"hostapd_interfaces":0,"kernel_interfaces":0,"wlan_npu":"compiled-out","hostapd_script_sha256":"e9bdbed02f2072121083130d1de0dc91996c95217550fd5604fcc641d96e6338","regulatory_hotfix_hash_verified":true,"hostapd_hotfix_hash_verified":true,"credential_generator_hash_verified":true,"credential_helper_hash_verified":true,"luci_hotfix_hash_verified":true,"nl80211_hotfix_hash_verified":true,"hostapd_current_nl80211_inode_mapped":true}'
exit 0
