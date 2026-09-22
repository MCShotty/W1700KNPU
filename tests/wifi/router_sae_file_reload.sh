#!/bin/sh
set -eu
umask 077
tag=${1:-file01}
kind=${2:-ordinary}
phase=${3:-after}
case "$tag" in *[!a-zA-Z0-9_-]*|'') exit 79 ;; esac
case "$kind" in
    ordinary) devices=radio1; radios=1; ifname=file-ap0; mlo=0; normal_count=1; link_count=0 ;;
    mlo) devices='radio1 radio2 radio0'; radios='0 1 2'; ifname=file-mld0; mlo=1; normal_count=0; link_count=3 ;;
    *) exit 79 ;;
esac
case "$phase" in
    before) receiver=deab7d45c2866548b2c6dda99168d4e78c2d927e08a657faef6e2f4644729bae ;;
    after) receiver=e9bdbed02f2072121083130d1de0dc91996c95217550fd5604fcc641d96e6338 ;;
    *) exit 79 ;;
esac
run=/tmp/w1700k-sae-file-20260909-$tag
service=/var/run/hostapd/w1700k-sae-file-$tag
baseline=a87e59eb9c6314be153d8af85f88ebbe0438a1cfb6e0e0ee92ee1b5f200c416d
cli=/tmp/w1700k-hostapd-cli
hash() { sha256sum "$1" | cut -d ' ' -f1; }
pending_hash() { uci changes wireless | sha256sum | cut -d ' ' -f1; }
[ "$(cat /tmp/sysinfo/board_name)" = gemtek,w1700k-ubi ] || exit 80
[ "$(uname -r)" = 6.18.44 ] || exit 81
[ "$(hash /etc/config/wireless)" = "$baseline" ] || exit 82
[ -z "$(uci changes wireless)" ] || exit 83
[ "$(hash /usr/share/hostap/hostapd.uc)" = "$receiver" ] || exit 84
[ "$(hash /usr/sbin/wpad)" = fc9178f2f65c066d0fcca94c3a63359143ed3c08e3d6d67061b952b66adbdc39 ] || exit 84
[ "$(hash /usr/share/ucode/wifi/hostapd.uc)" = 79004ebbb01a637a824806c7254170d55ba7a418bb137f370a305b9b4c2a4a86 ] || exit 84
[ "$(hash /usr/share/ucode/wifi/iface.uc)" = ef91cb5cb1e1c6c99d07c67d9dccdc4d846ed05a2c1f36afde9f49b2e9a79deb ] || exit 84
[ "$(hash /usr/lib/ucode/nl80211.so)" = 6c2af55f71276895be7e906f67479339984affe10bf893b05ae3e74cb2cff92d ] || exit 85
[ "$(hash /usr/sbin/w1700k-wireless-validate)" = 8ad893d582ad04e3b93923747cf7aa52cf9a8a14ea5d8dd0d479cf6452a73604 ] || exit 86
[ "$(/usr/sbin/w1700k-wlan-npu-mode json | jsonfilter -e '@.npu.runtime_state')" = compiled-out ] || exit 87
[ "$(hash "$cli")" = 8777f2d924c39009e9eb40218cad4d1c5568de36c49b792f98f157cc4ec7dc22 ] || exit 88
[ ! -e "$run" ] && [ ! -e "$service" ] || exit 89
mkdir -m700 "$run" "$service"
chown network:network "$service"
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
    if [ "$(hash /etc/config/wireless)" != "$expected_config" ] || [ "$(pending_hash)" != "$pending" ]; then
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
    [ "$(hash /etc/config/wireless)" = "$baseline" ] && [ -z "$(uci changes wireless)" ] && [ "$stable" -ge 3 ] || exit 91
    printf 'CLEANUP_OK LAST_STAGE=%s CONFIG_SHA256=%s HOSTAPD_INTERFACES=0 KERNEL_INTERFACES=0 RESULT_CODE=%s\n' "$stage" "$baseline" "$result"
    exit "$result"
}
trap cleanup EXIT
trap 'exit 92' HUP INT TERM
for name in global a b; do hexdump -vn24 -e '/1 "%02x"' /dev/urandom >"$run/$name.key"; done
key=$(cat "$run/global.key")
key_a=$(cat "$run/a.key")
key_b=$(cat "$run/b.key")
[ "${#key}:${#key_a}:${#key_b}" = 48:48:48 ] || exit 93
[ "$key_a" != "$key_b" ] && [ "$key" != "$key_a" ] && [ "$key" != "$key_b" ] || exit 93

write_passwords() {
    case "$1" in
        initial|restore) printf '%s|mac=02:00:00:00:00:02\n' "$key_a" >"$service/passwords.next" ;;
        rekey) printf '%s|mac=02:00:00:00:00:02\n' "$key_b" >"$service/passwords.next" ;;
        empty) : >"$service/passwords.next" ;;
        *) exit 93 ;;
    esac
    chown network:network "$service/passwords.next"
    chmod 600 "$service/passwords.next"
    mv "$service/passwords.next" "$service/passwords.sae"
}
write_passwords initial
set +e
uci batch >"$run/configure.private.log" 2>&1 <<EOF
set wireless.radio0.disabled='1'
set wireless.radio1.disabled='0'
set wireless.radio2.disabled='1'
set wireless.radio0.channel='6'
set wireless.radio1.channel='36'
set wireless.radio2.channel='37'
set wireless.radio0.htmode='EHT20'
set wireless.radio1.htmode='EHT80'
set wireless.radio2.htmode='EHT80'
set wireless.codex_file_ap=wifi-iface
set wireless.codex_file_ap.device='$devices'
set wireless.codex_file_ap.ifname='$ifname'
set wireless.codex_file_ap.mode='ap'
set wireless.codex_file_ap.network='lan'
set wireless.codex_file_ap.ssid='W1700K-File-Reload'
set wireless.codex_file_ap.encryption='sae'
set wireless.codex_file_ap.key='$key'
set wireless.codex_file_ap.sae_password_file='$service/passwords.sae'
set wireless.codex_file_ap.ieee80211w='2'
set wireless.codex_file_ap.sae_pwe='2'
set wireless.codex_file_ap.rnr='1'
set wireless.codex_file_ap.isolate='1'
set wireless.codex_file_ap.mlo='$mlo'
EOF
rc=$?
for radio in $radios; do uci set wireless.radio$radio.disabled=0 || rc=$?; done
pending=$(pending_hash)
set -e
[ "$rc" = 0 ] || exit 94
/usr/sbin/w1700k-wireless-validate >"$run/validation.private.log" 2>&1 || exit 95
uci commit wireless
expected_config=$(hash /etc/config/wireless)
pending=$(pending_hash)
changed=1
wifi reload >"$run/start.private.log" 2>&1

settle() {
    stable=0
    for poll in $(seq 1 35); do
        sleep 2
        ubus call hostapd status >"$run/$stage.status.private.json"
        ubus call network.wireless status >"$run/$stage.wireless.private.json"
        global=$(jsonfilter -i "$run/$stage.status.private.json" -e '@.interfaces.*.wiphy' | wc -l)
        normal=$(jsonfilter -i "$run/$stage.status.private.json" -e '@.interfaces.*.running' | grep -c '^true$') || :
        links=$(jsonfilter -i "$run/$stage.status.private.json" -e '@.interfaces.*.links.*.running' | grep -c '^true$') || :
        busy=$(jsonfilter -i "$run/$stage.status.private.json" -e '@.interfaces.*.pending' -e '@.interfaces.*.links.*.pending' | grep -c '^true$') || :
        netbusy=$(jsonfilter -i "$run/$stage.wireless.private.json" -e '@.*.pending' | grep -c '^true$') || :
        if [ "$global:$normal:$links:$busy:$netbusy" = "1:$normal_count:$link_count:0:0" ]; then stable=$((stable + 1)); else stable=0; fi
        [ "$stable" -lt 3 ] || return 0
    done
    return 96
}
settle
count=0
for radio in $radios; do
    cfg=/var/run/hostapd-phy0.$radio.conf
    grep -qx "sae_password_file=$service/passwords.sae" "$cfg" || exit 97
    cp "$cfg" "$run/config-$radio.private.conf"
    count=$((count + 1))
done
for stage in initial rekey empty restore; do
    [ "$(hash /etc/config/wireless)" = "$expected_config" ] && [ "$(pending_hash)" = "$pending" ] || exit 98
    write_passwords "$stage"
    marker="w1700k-sae-file-$tag-$stage"
    logger -t w1700k-sae-file "$marker"
    for radio in $radios; do
        cfg=/var/run/hostapd-phy0.$radio.conf
        cmp -s "$cfg" "$run/config-$radio.private.conf" || exit 99
        request=$(printf '{"phy":"phy0","radio":%s,"config":"%s"}' "$radio" "$cfg")
        ubus call hostapd config_set "$request" >"$run/$stage-request-$radio.private.json"
    done
    settle
    logread >"$run/$stage-log.private.txt"
    awk -v marker="$marker" 'index($0, marker) { found=1; next } found { print } END { if (!found) exit 1 }' \
        "$run/$stage-log.private.txt" >"$run/$stage-delta.private.txt" || exit 100
    files=$(grep -c "Update config data files for bss $ifname" "$run/$stage-delta.private.txt") || :
    full=$(grep -c "Reload config for bss '$ifname'" "$run/$stage-delta.private.txt") || :
    restarts=$(grep -c 'Restart interface for phy' "$run/$stage-delta.private.txt") || :
    want_files=0
    want_full=0
    if [ "$stage" != initial ]; then
        if [ "$phase" = before ]; then want_files=$count; else want_full=$count; fi
    fi
    for radio in $radios; do
        ctrl="$run/$stage-ctrl-$radio.private.txt"
        if [ "$mlo" = 1 ]; then
            "$cli" -p /var/run/hostapd -i "$ifname" -l "$radio" get_config >"$ctrl" 2>&1
        else
            "$cli" -p /var/run/hostapd -i "$ifname" get_config >"$ctrl" 2>&1
        fi
        grep -qx 'wpa=2' "$ctrl" && grep -q '^key_mgmt=.*SAE' "$ctrl" || exit 101
    done
    printf 'PHASE=%s KIND=%s STAGE=%s AP_LINKS=%s FILES_ONLY=%s FULL_BSS=%s INTERFACE_RESTARTS=%s CONFIG_FILES_UNCHANGED=1 READY=1\n' \
        "$phase" "$kind" "$stage" "$count" "$files" "$full" "$restarts"
    [ "$files:$full:$restarts" = "$want_files:$want_full:0" ] || exit 102
done
exit 0
