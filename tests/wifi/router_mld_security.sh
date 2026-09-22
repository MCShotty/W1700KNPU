#!/bin/sh
set -eu
umask 077
tag=${1:-security01}
phase=${2:-after}
case "$tag" in *[!a-zA-Z0-9_-]*|'') exit 79 ;; esac
case "$phase" in
    before) receiver=deab7d45c2866548b2c6dda99168d4e78c2d927e08a657faef6e2f4644729bae
            generator=e0bbdf764f06f775912831794ba81ea64bf47dc25a3b29731fc1db4945ffaa41
            iface=4fb0e2f44df2eaa52f7c11cb92075965552ce53086c647df6e9f2a39fb5e61a1 ;;
    after) receiver=e9bdbed02f2072121083130d1de0dc91996c95217550fd5604fcc641d96e6338
           generator=79004ebbb01a637a824806c7254170d55ba7a418bb137f370a305b9b4c2a4a86
           iface=ef91cb5cb1e1c6c99d07c67d9dccdc4d846ed05a2c1f36afde9f49b2e9a79deb ;;
    *) exit 79 ;;
esac
run=/tmp/w1700k-wifi-security-20260909-$tag
baseline=a87e59eb9c6314be153d8af85f88ebbe0438a1cfb6e0e0ee92ee1b5f200c416d
cli=/tmp/w1700k-hostapd-cli
file_hash() { sha256sum "$1" | cut -d ' ' -f1; }
pending_hash() { uci changes wireless | sha256sum | cut -d ' ' -f1; }
[ "$(cat /tmp/sysinfo/board_name)" = gemtek,w1700k-ubi ] || exit 80
[ "$(uname -r)" = 6.18.44 ] || exit 81
[ "$(file_hash /etc/config/wireless)" = "$baseline" ] || exit 82
[ -z "$(uci changes wireless)" ] || exit 83
[ "$(file_hash /usr/share/hostap/hostapd.uc)" = "$receiver" ] || exit 84
[ "$(file_hash /usr/share/ucode/wifi/hostapd.uc)" = "$generator" ] || exit 84
[ "$(file_hash /usr/share/ucode/wifi/iface.uc)" = "$iface" ] || exit 84
[ "$(file_hash /usr/share/ucode/wifi/mld-config.uc)" = 16db8c275cd64607845ae9b7a6093d05e260dcad5266e3cd8b61d8918d1df1f2 ] || exit 84
[ "$(file_hash /usr/lib/ucode/nl80211.so)" = 6c2af55f71276895be7e906f67479339984affe10bf893b05ae3e74cb2cff92d ] || exit 85
[ "$(file_hash /usr/libexec/w1700k-wireless-regulatory)" = 04497f40bb5c774d985784ee920b682da16d6e8ae71d55778400477a7111b7d5 ] || exit 86
[ "$(/usr/sbin/w1700k-wlan-npu-mode json | jsonfilter -e '@.npu.runtime_state')" = compiled-out ] || exit 87
[ "$(file_hash "$cli")" = 8777f2d924c39009e9eb40218cad4d1c5568de36c49b792f98f157cc4ec7dc22 ] || exit 88
[ ! -e "$run" ] || exit 89
mkdir -m700 "$run"
ubus call hostapd status >"$run/before.private.json"
[ "$(jsonfilter -i "$run/before.private.json" -e '@.interfaces.*.wiphy' | wc -l)" = 0 ] || exit 89
ucode - >"$run/cipher-capability.json" <<'UCODE'
import { wiphy_info } from 'wifi.common';
let phy = wiphy_info('phy0');
let supported = 0x000fac09 in (phy.cipher_suites ?? []);
printf('%J\n', { gcmp256: supported });
exit(supported ? 0 : 89);
UCODE
cp -p /etc/config/wireless "$run/wireless.before"
expected_config=$baseline
pending=$(pending_hash)
changed=0
stage=before
cleanup() {
    result=$?
    trap - EXIT HUP INT TERM
    set +e
    if [ "$(file_hash /etc/config/wireless)" != "$expected_config" ] || [ "$(pending_hash)" != "$pending" ]; then
        echo CLEANUP_REFUSED_CONCURRENT_CONFIG_CHANGE >&2
        exit 90
    fi
    [ "$changed" = 0 ] || wifi down >"$run/cleanup-down.private.log" 2>&1
    uci revert wireless
    cp -p "$run/wireless.before" /etc/config/wireless
    [ "$changed" = 0 ] || wifi up >"$run/cleanup-up.private.log" 2>&1
    stable=0
    for attempt in 1 2 3 4 5 6; do
        sleep 2
        ubus call hostapd status >"$run/after.private.json" || break
        iw dev >"$run/after-iw.private.txt"
        count=$(jsonfilter -i "$run/after.private.json" -e '@.interfaces.*.wiphy' | wc -l)
        wdevs=$(awk '$1 == "Interface" { n++ } END { print n+0 }' "$run/after-iw.private.txt")
        if [ "$count" = 0 ] && [ "$wdevs" = 0 ]; then stable=$((stable + 1)); else stable=0; fi
        [ "$stable" -lt 3 ] || break
    done
    [ "$(file_hash /etc/config/wireless)" = "$baseline" ] && [ -z "$(uci changes wireless)" ] && [ "$stable" -ge 3 ] || exit 91
    printf 'CLEANUP_OK LAST_STAGE=%s CONFIG_SHA256=%s HOSTAPD_INTERFACES=0 KERNEL_INTERFACES=0 RESULT_CODE=%s\n' "$stage" "$baseline" "$result"
    exit "$result"
}
trap cleanup EXIT
trap 'exit 92' HUP INT TERM
hexdump -vn24 -e '/1 "%02x"' /dev/urandom >"$run/test.key"
key=$(cat "$run/test.key")
[ "${#key}" = 48 ] || exit 93

settle() {
    stable=0
    for poll in $(seq 1 35); do
        sleep 2
        ubus call hostapd status >"$run/$stage.status.private.json"
        ubus call network.wireless status >"$run/$stage.wireless.private.json"
        global=$(jsonfilter -i "$run/$stage.status.private.json" -e '@.interfaces.*.wiphy' | wc -l)
        links=$(jsonfilter -i "$run/$stage.status.private.json" -e '@.interfaces.*.links.*.running' | grep -c '^true$') || :
        busy=$(jsonfilter -i "$run/$stage.status.private.json" -e '@.interfaces.*.pending' -e '@.interfaces.*.links.*.pending' | grep -c '^true$') || :
        netbusy=$(jsonfilter -i "$run/$stage.wireless.private.json" -e '@.*.pending' | grep -c '^true$') || :
        up=$(jsonfilter -i "$run/$stage.wireless.private.json" -e '@.*.up' | grep -c '^true$') || :
        if [ "$global:$links:$busy:$netbusy:$up" = 1:3:0:0:3 ]; then stable=$((stable + 1)); else stable=0; fi
        [ "$stable" -lt 3 ] || return 0
    done
    return 97
}

for stage in default explicit-off explicit-on default-restored ft; do
    [ "$(file_hash /etc/config/wireless)" = "$expected_config" ] && [ "$(pending_hash)" = "$pending" ] || exit 94
    expected=3
    [ "$phase" != before ] || expected=0
    ft=0
    case "$stage" in
        explicit-off) flags=0; expected=0 ;;
        explicit-on) flags=1; expected=3 ;;
        ft) flags=1; ft=1; expected=3 ;;
        *) flags=unset ;;
    esac
    set +e
    uci batch >"$run/$stage.uci.private.log" 2>&1 <<EOF
set wireless.radio0.disabled='0'
set wireless.radio1.disabled='0'
set wireless.radio2.disabled='0'
set wireless.radio0.channel='6'
set wireless.radio1.channel='36'
set wireless.radio2.channel='37'
set wireless.radio0.htmode='EHT20'
set wireless.radio1.htmode='EHT80'
set wireless.radio2.htmode='EHT80'
set wireless.codex_security_mld=wifi-iface
set wireless.codex_security_mld.device='radio1 radio2 radio0'
set wireless.codex_security_mld.mode='ap'
set wireless.codex_security_mld.network='lan'
set wireless.codex_security_mld.ssid='W1700K-Security-MLD'
set wireless.codex_security_mld.encryption='sae'
set wireless.codex_security_mld.key='$key'
set wireless.codex_security_mld.ieee80211w='2'
set wireless.codex_security_mld.sae_pwe='2'
set wireless.codex_security_mld.rnr='1'
set wireless.codex_security_mld.isolate='1'
set wireless.codex_security_mld.mlo='1'
set wireless.codex_security_mld.ieee80211r='$ft'
EOF
    rc=$?
    if [ "$flags" = unset ]; then
        uci -q delete wireless.codex_security_mld.gcmp256 || :
        uci -q delete wireless.codex_security_mld.sae_ext_key || :
    else
        uci set wireless.codex_security_mld.gcmp256="$flags" || rc=$?
        uci set wireless.codex_security_mld.sae_ext_key="$flags" || rc=$?
    fi
    pending=$(pending_hash)
    set -e
    [ "$rc" = 0 ] || exit 95
    /usr/sbin/w1700k-wireless-validate >"$run/$stage.validation.private.log" 2>&1 || exit 96
    uci commit wireless
    expected_config=$(file_hash /etc/config/wireless)
    pending=$(pending_hash)
    changed=1
    wifi reload >"$run/$stage.reload.private.log" 2>&1
    settle
    generated_akm=0
    generated_cipher=0
    native_akm=0
    native_cipher=0
    for radio in 0 1 2; do
        source=/var/run/hostapd-phy0.$radio.conf
        grep -qx "wpa_passphrase=$key" "$source" || exit 98
        grep -qx 'ieee80211w=2' "$source" || exit 98
        if grep -q '^wpa_key_mgmt=.*SAE-EXT-KEY' "$source"; then generated_akm=$((generated_akm + 1)); fi
        if grep -q '^wpa_pairwise=.*GCMP-256' "$source"; then generated_cipher=$((generated_cipher + 1)); fi
        ctrl="$run/$stage.ctrl-$radio.private.txt"
        "$cli" -p /var/run/hostapd -i ap-mld0 -l "$radio" get_config >"$ctrl" 2>&1 || exit 99
        grep -qx 'wpa=2' "$ctrl" && grep -q '^key_mgmt=.*SAE' "$ctrl" && grep -q '^rsn_pairwise_cipher=.*CCMP' "$ctrl" || exit 99
        if grep -q '^key_mgmt=.*SAE-EXT-KEY' "$ctrl"; then native_akm=$((native_akm + 1)); fi
        if grep -q '^rsn_pairwise_cipher=.*GCMP-256' "$ctrl"; then native_cipher=$((native_cipher + 1)); fi
        if [ "$ft" = 1 ]; then grep -q '^key_mgmt=.*FT-SAE-EXT-KEY' "$ctrl" || exit 100; fi
    done
    printf 'PHASE=%s STAGE=%s LINKS_ENABLED=3 GENERATED_EXT=%s GENERATED_GCMP=%s NATIVE_EXT=%s NATIVE_GCMP=%s EXPECTED=%s FT=%s\n' "$phase" "$stage" "$generated_akm" "$generated_cipher" "$native_akm" "$native_cipher" "$expected" "$ft"
    [ "$generated_akm:$generated_cipher:$native_akm:$native_cipher" = "$expected:$expected:$expected:$expected" ] || exit 101
done

if [ "$phase" = after ]; then
    stage=reject-owe-transition
    ubus call hostapd status >"$run/reject-before.private.json"
    iw dev >"$run/reject-before-iw.private.txt"
    set +e
    uci batch >"$run/reject.uci.private.log" 2>&1 <<EOF
set wireless.codex_security_mld.encryption='owe'
set wireless.codex_security_mld.owe_transition='1'
EOF
    rc=$?
    pending=$(pending_hash)
    set -e
    [ "$rc" = 0 ] || exit 102
    if /usr/sbin/w1700k-wireless-validate >"$run/reject.validation.private.log" 2>&1; then exit 103; fi
    grep -q 'OWE transition' "$run/reject.validation.private.log" || exit 103
    [ "$(file_hash /etc/config/wireless)" = "$expected_config" ] && [ "$(pending_hash)" = "$pending" ] || exit 104
    uci revert wireless
    pending=$(pending_hash)
    ubus call hostapd status >"$run/reject-after.private.json"
    iw dev >"$run/reject-after-iw.private.txt"
    cmp -s "$run/reject-before.private.json" "$run/reject-after.private.json" || exit 105
    cmp -s "$run/reject-before-iw.private.txt" "$run/reject-after-iw.private.txt" || exit 105
    printf 'OWE_TRANSITION_REJECTED=1 CONFIG_COMMIT=0 RADIO_RELOAD=0 HOSTAPD_AND_IW_UNCHANGED=1\n'
fi
exit 0
