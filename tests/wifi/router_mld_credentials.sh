#!/bin/sh
set -eu
umask 077
tag=${1:-cred01}
expect=${2:-observe}
case "$tag" in *[!a-zA-Z0-9_-]*|'') exit 79 ;; esac
case "$expect" in observe|reject) ;; *) exit 79 ;; esac
run=/tmp/w1700k-wifi-credentials-20260907-$tag
replay=/var/run/hostapd/w1700k-credentials-$tag
baseline=a87e59eb9c6314be153d8af85f88ebbe0438a1cfb6e0e0ee92ee1b5f200c416d
cli=/tmp/w1700k-hostapd-cli
file_hash() { sha256sum "$1" | cut -d ' ' -f1; }
pending_hash() { uci changes wireless | sha256sum | cut -d ' ' -f1; }
[ "$(cat /tmp/sysinfo/board_name)" = gemtek,w1700k-ubi ] || exit 80
[ "$(uname -r)" = 6.18.44 ] || exit 81
[ "$(file_hash /etc/config/wireless)" = "$baseline" ] || exit 82
[ -z "$(uci changes wireless)" ] || exit 83
[ "$(file_hash /usr/share/hostap/hostapd.uc)" = e9bdbed02f2072121083130d1de0dc91996c95217550fd5604fcc641d96e6338 ] || exit 84
[ "$(file_hash /usr/share/ucode/wifi/hostapd.uc)" = 79004ebbb01a637a824806c7254170d55ba7a418bb137f370a305b9b4c2a4a86 ] || exit 84
[ "$(file_hash /usr/share/ucode/wifi/iface.uc)" = ef91cb5cb1e1c6c99d07c67d9dccdc4d846ed05a2c1f36afde9f49b2e9a79deb ] || exit 84
[ "$(file_hash /usr/share/ucode/wifi/mld-config.uc)" = 16db8c275cd64607845ae9b7a6093d05e260dcad5266e3cd8b61d8918d1df1f2 ] || exit 84
[ "$(file_hash /usr/lib/ucode/nl80211.so)" = 6c2af55f71276895be7e906f67479339984affe10bf893b05ae3e74cb2cff92d ] || exit 85
[ "$(file_hash /usr/libexec/w1700k-wireless-regulatory)" = 04497f40bb5c774d985784ee920b682da16d6e8ae71d55778400477a7111b7d5 ] || exit 86
[ "$(/usr/sbin/w1700k-wlan-npu-mode json | jsonfilter -e '@.npu.runtime_state')" = compiled-out ] || exit 87
[ "$(file_hash "$cli")" = 8777f2d924c39009e9eb40218cad4d1c5568de36c49b792f98f157cc4ec7dc22 ] || exit 88
[ ! -e "$run" ] && [ ! -e "$replay" ] || exit 89
mkdir -m700 "$run" "$replay"
chown network:network "$replay"
ubus call hostapd status >"$run/before.private.json"
[ "$(jsonfilter -i "$run/before.private.json" -e '@.interfaces.*.wiphy' | wc -l)" = 0 ] || exit 89
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
for key_id in a b; do hexdump -vn24 -e '/1 "%02x"' /dev/urandom >"$run/$key_id.key"; done
! cmp -s "$run/a.key" "$run/b.key" || exit 93

settle() {
    for poll in $(seq 1 35); do
        sleep 2
        ubus call hostapd status >"$run/$stage.status.private.json"
        ubus call network.wireless status >"$run/$stage.wireless.private.json"
        global=$(jsonfilter -i "$run/$stage.status.private.json" -e '@.interfaces.*.wiphy' | wc -l)
        links=$(jsonfilter -i "$run/$stage.status.private.json" -e '@.interfaces.*.links.*.running' | grep -c '^true$') || :
        busy=$(jsonfilter -i "$run/$stage.status.private.json" -e '@.interfaces.*.pending' -e '@.interfaces.*.links.*.pending' | grep -c '^true$') || :
        netbusy=$(jsonfilter -i "$run/$stage.wireless.private.json" -e '@.*.pending' | grep -c '^true$') || :
        up=$(jsonfilter -i "$run/$stage.wireless.private.json" -e '@.*.up' | grep -c '^true$') || :
        if [ "$global:$links:$busy:$netbusy:$up" = 1:3:0:0:3 ]; then
            printf 'STAGE=%s READY=1 MLO_LINKS=3 NETIFD_PENDING=0\n' "$stage"
            return 0
        fi
    done
    return 97
}
submit() {
    for radio in 0 1 2; do
        request=$(printf '{"phy":"phy0","radio":%s,"config":"%s/%s-phy0.%s.private.conf"}' "$radio" "$replay" "$1" "$radio")
        ubus call hostapd config_set "$request" >"$run/$stage.submit-$radio.private.json"
    done
}
marker_count() {
    count=0
    for link in 0 1 2; do
        "$cli" -p /var/run/hostapd -i ap-mld0 -l "$link" get_config >"$run/$stage.ctrl-$link.private.txt" 2>&1 || return 98
        grep -qx "config_id=$1" "$run/$stage.ctrl-$link.private.txt" && count=$((count + 1))
    done
    printf '%s' "$count"
}
for stage in a b; do
    [ "$(file_hash /etc/config/wireless)" = "$expected_config" ] && [ "$(pending_hash)" = "$pending" ] || exit 94
    key=$(cat "$run/$stage.key")
    [ "${#key}" = 48 ] || exit 93
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
set wireless.codex_credential_mld=wifi-iface
set wireless.codex_credential_mld.device='radio1 radio2 radio0'
set wireless.codex_credential_mld.mode='ap'
set wireless.codex_credential_mld.network='lan'
set wireless.codex_credential_mld.ssid='W1700K-Credential-MLD'
set wireless.codex_credential_mld.encryption='sae'
set wireless.codex_credential_mld.key='$key'
set wireless.codex_credential_mld.ieee80211w='2'
set wireless.codex_credential_mld.sae_pwe='2'
set wireless.codex_credential_mld.rnr='1'
set wireless.codex_credential_mld.isolate='1'
set wireless.codex_credential_mld.mlo='1'
EOF
    rc=$?
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
    for radio in 0 1 2; do
        source=/var/run/hostapd-phy0.$radio.conf
        target=$replay/$stage-phy0.$radio.private.conf
        # Verify the private source key and attach an observable native-C marker.
        grep -qx "wpa_passphrase=$key" "$source" || exit 99
        [ "$(grep -c '^interface=' "$source")" = 1 ] || exit 99
        [ "$(grep -c '^bss=' "$source")" = 0 ] || exit 99
        cp "$source" "$target"
        printf '\nconfig_id=credential-%s\n' "$stage" >>"$target"
        chown network:network "$target"
        chmod 600 "$target"
    done
    submit "$stage"
    settle
    count=$(marker_count credential-$stage)
    printf 'STAGE=%s CURRENT_KEY_FILE_VERIFIED=3 NATIVE_CURRENT_MARKERS=%s\n' "$stage" "$count"
    [ "$count" = 3 ] || exit 100
done
stage=replay-a
ubus call hostapd status >"$run/pre-replay.status.private.json"
iw dev >"$run/pre-replay.iw.private.txt"
submit a
settle
old=$(marker_count credential-a)
new=$(marker_count credential-b)
printf 'STAGE=%s UCI_KEY_B=1 REPLAY_KEY_A_FILE_VERIFIED=3 NATIVE_OLD_MARKERS=%s NATIVE_CURRENT_MARKERS=%s\n' "$stage" "$old" "$new"
if [ "$expect" = reject ]; then
    [ "$old:$new" = 0:3 ] || exit 101
    for radio in 0 1 2; do
        target=$replay/noid-phy0.$radio.private.conf
        sed '/^#mld_config_id=/d;s/^config_id=credential-b$/config_id=credential-noid/' "$replay/b-phy0.$radio.private.conf" >"$target"
        chown network:network "$target"
        chmod 600 "$target"
    done
    stage=replay-noid
    submit noid
    settle
    [ "$(marker_count credential-noid)" = 0 ] && [ "$(marker_count credential-b)" = 3 ] || exit 102
    for observation in 1 2 3; do
        sleep 2
        ubus call hostapd status >"$run/post-replay.status.private.json"
        iw dev >"$run/post-replay.iw.private.txt"
        cmp -s "$run/pre-replay.status.private.json" "$run/post-replay.status.private.json" || exit 103
        cmp -s "$run/pre-replay.iw.private.txt" "$run/post-replay.iw.private.txt" || exit 103
    done
    printf 'MISSING_MARKERS_REJECTED=3 NATIVE_CURRENT_MARKERS=3 HOSTAPD_AND_IW_UNCHANGED=1 STABLE_OBSERVATIONS=3\n'
fi
exit 0
