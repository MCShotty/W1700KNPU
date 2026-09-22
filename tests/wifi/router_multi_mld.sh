#!/bin/sh
set -eu
umask 077
tag=${1:-multi01}
expect=${2:-blocked}
case "$tag" in *[!a-zA-Z0-9_-]*|'') exit 79 ;; esac
case "$expect" in blocked|run) ;; *) exit 79 ;; esac
run=/tmp/w1700k-wifi-multi-20260907-$tag
baseline=a87e59eb9c6314be153d8af85f88ebbe0438a1cfb6e0e0ee92ee1b5f200c416d
file_hash() { sha256sum "$1" | cut -d ' ' -f1; }
pending_hash() { uci changes wireless | sha256sum | cut -d ' ' -f1; }
[ "$(cat /tmp/sysinfo/board_name)" = gemtek,w1700k-ubi ] || exit 80
[ "$(uname -r)" = 6.18.44 ] || exit 81
[ "$(file_hash /etc/config/wireless)" = "$baseline" ] || exit 82
[ -z "$(uci changes wireless)" ] || exit 83
[ "$(file_hash /usr/libexec/w1700k-wireless-regulatory)" = 04497f40bb5c774d985784ee920b682da16d6e8ae71d55778400477a7111b7d5 ] || exit 84
[ "$(file_hash /usr/share/hostap/hostapd.uc)" = e9bdbed02f2072121083130d1de0dc91996c95217550fd5604fcc641d96e6338 ] || exit 85
[ "$(file_hash /usr/lib/ucode/nl80211.so)" = 6c2af55f71276895be7e906f67479339984affe10bf893b05ae3e74cb2cff92d ] || exit 86
[ "$(/usr/sbin/w1700k-wlan-npu-mode json | jsonfilter -e '@.npu.runtime_state')" = compiled-out ] || exit 87
[ ! -e "$run" ] || exit 88
mkdir -m700 "$run"
ubus call hostapd status >"$run/before-hostapd.private.json"
[ "$(jsonfilter -i "$run/before-hostapd.private.json" -e '@.interfaces.*.wiphy' | wc -l)" = 0 ] || exit 89
cp -p /etc/config/wireless "$run/wireless.before"
expected_config=$baseline
pending=$(pending_hash)
changed_runtime=0
stage=before
cleanup() {
    result=$?
    trap - EXIT HUP INT TERM
    set +e
    if [ "$(file_hash /etc/config/wireless)" != "$expected_config" ] || [ "$(pending_hash)" != "$pending" ]; then
        echo 'CLEANUP_REFUSED_CONCURRENT_CONFIG_CHANGE' >&2
        exit 90
    fi
    if [ "$changed_runtime" = 1 ]; then wifi down >"$run/cleanup-down.private.log" 2>&1; fi
    uci revert wireless
    cp -p "$run/wireless.before" /etc/config/wireless
    if [ "$changed_runtime" = 1 ]; then wifi up >"$run/cleanup-up.private.log" 2>&1; fi
    stable=0
    for attempt in 1 2 3 4 5 6; do
        sleep 2
        ubus call hostapd status >"$run/after-hostapd.private.json" || break
        count=$(jsonfilter -i "$run/after-hostapd.private.json" -e '@.interfaces.*.wiphy' | wc -l)
        iw dev >"$run/after-iw.private.txt"
        wdevs=$(awk '$1 == "Interface" { n++ } END { print n+0 }' "$run/after-iw.private.txt")
        if [ "$count" = 0 ] && [ "$wdevs" = 0 ]; then stable=$((stable + 1)); else stable=0; fi
        [ "$stable" -ge 3 ] && break
    done
    if [ "$(file_hash /etc/config/wireless)" != "$baseline" ] || [ -n "$(uci changes wireless)" ] || [ "$stable" -lt 3 ]; then
        echo 'CLEANUP_FAILED' >&2
        exit 91
    fi
    printf 'CLEANUP_OK LAST_STAGE=%s CONFIG_SHA256=%s HOSTAPD_INTERFACES=0 KERNEL_INTERFACES=0 RESULT_CODE=%s\n' "$stage" "$baseline" "$result"
    exit "$result"
}
trap cleanup EXIT
trap 'exit 92' HUP INT TERM
for index in a1 a2 b1 b2; do
    hexdump -vn24 -e '/1 "%02x"' /dev/urandom >"$run/key-$index.private"
    [ "$(wc -c <"$run/key-$index.private")" = 48 ] || exit 93
done
previous_a_anchor=; previous_b_anchor=; previous_a_mac=; previous_b_mac=
configure() {
    uci batch <<EOF
set wireless.radio0.disabled='0'
set wireless.radio1.disabled='0'
set wireless.radio2.disabled='0'
set wireless.radio0.channel='6'
set wireless.radio1.channel='36'
set wireless.radio2.channel='37'
set wireless.radio0.htmode='EHT20'
set wireless.radio1.htmode='EHT80'
set wireless.radio2.htmode='EHT80'
EOF
    for label in a b; do
        if [ "$label" = a ]; then radios=$radios_a; ssid=$ssid_a; key=$key_a; else radios=$radios_b; ssid=$ssid_b; key=$key_b; fi
        uci batch <<EOF
set wireless.codex_multi_$label=wifi-iface
set wireless.codex_multi_$label.device='$radios'
set wireless.codex_multi_$label.mlo='1'
set wireless.codex_multi_$label.mode='ap'
set wireless.codex_multi_$label.network='lan'
set wireless.codex_multi_$label.ssid='$ssid'
set wireless.codex_multi_$label.encryption='sae'
set wireless.codex_multi_$label.key='$key'
set wireless.codex_multi_$label.ieee80211w='2'
set wireless.codex_multi_$label.sae_pwe='2'
set wireless.codex_multi_$label.rnr='1'
set wireless.codex_multi_$label.isolate='1'
EOF
    done
}

for stage in 01-cold 02-rename-b 03-rename-a-rekey-b 04-return-both 05-rekey-a-drop-b5g 06-return-bands 07-both-renamed 08-original; do
    [ "$(file_hash /etc/config/wireless)" = "$expected_config" ] || exit 94
    [ "$(pending_hash)" = "$pending" ] || exit 94
    radios_a='radio1 radio2 radio0'; radios_b=$radios_a
    ssid_a=W1700K-Multi-A; ssid_b=W1700K-Multi-B
    key_a=$(cat "$run/key-a1.private"); key_b=$(cat "$run/key-b1.private")
    case "$stage" in
        02-rename-b) ssid_b=W1700K-Multi-B-Renamed ;;
        03-rename-a-rekey-b) ssid_a=W1700K-Multi-A-Renamed; ssid_b=W1700K-Multi-B-Renamed; key_b=$(cat "$run/key-b2.private") ;;
        05-rekey-a-drop-b5g) key_a=$(cat "$run/key-a2.private"); radios_b='radio2 radio0' ;;
        07-both-renamed) ssid_a=W1700K-Multi-A-Renamed; ssid_b=W1700K-Multi-B-Renamed ;;
    esac
    printf '%s\n%s\n' "$ssid_a" "$ssid_b" | sort >"$run/$stage.expected-ssids.private.txt"
    for radio in $radios_a $radios_b; do
        case "$radio" in
            radio0) echo '6 2437 20 2437' ;;
            radio1) echo '36 5180 80 5210' ;;
            radio2) echo '37 6135 80 6145' ;;
        esac
    done | sort >"$run/$stage.expected-channels.txt"
    configure >"$run/$stage.uci.private.log" 2>&1
    pending=$(pending_hash)
    if ! /usr/sbin/w1700k-wireless-validate >"$run/$stage.validation.private.log" 2>&1; then
        if [ "$expect" = blocked ] && [ "$stage" = 01-cold ] && grep -q 'already owned by MLO interface' "$run/$stage.validation.private.log"; then
            echo 'MULTI_MLD_OVERLAP_REJECTED=1 CONFIG_COMMIT=0 RADIO_RELOAD=0'
            exit 0
        fi
        exit 95
    fi
    [ "$expect" = run ] || exit 99
    uci commit wireless
    expected_config=$(file_hash /etc/config/wireless)
    pending=$(pending_hash)
    changed_runtime=1
    logger -t w1700k-test "W1700K-MULTI $run $stage BEGIN"
    reload_rc=0
    wifi reload >"$run/$stage.reload.private.log" 2>&1 || reload_rc=$?
    ready=0
    poll=0
    while [ "$poll" -lt 25 ]; do
        sleep 2
        ubus call hostapd status >"$run/$stage.hostapd.private.json"
        ubus call network.wireless status >"$run/$stage.wireless.private.json"
        iw dev >"$run/$stage.iw.private.txt"
        logread >"$run/$stage.system.private.log"
        global_count=$(jsonfilter -i "$run/$stage.hostapd.private.json" -e '@.interfaces.*.wiphy' | wc -l)
        wireless_pending=$(jsonfilter -i "$run/$stage.wireless.private.json" -e '@.*.pending' | grep -c '^true$') || :
        wireless_up=$(jsonfilter -i "$run/$stage.wireless.private.json" -e '@.*.up' | grep -c '^true$') || :
        awk '$1 == "channel" && $5 == "width:" {gsub(/[()]/, "", $3); print $2, $3, $6, $9}' "$run/$stage.iw.private.txt" | sort >"$run/$stage.actual-channels.txt"
        awk '$1 == "ssid" {sub(/^[ \t]*ssid /, ""); print}' "$run/$stage.iw.private.txt" | sort >"$run/$stage.actual-ssids.private.txt"
        groups_ready=1
        for label in a b; do
            if [ "$label" = a ]; then radios=$radios_a; ssid=$ssid_a; else radios=$radios_b; ssid=$ssid_b; fi
            ifname=$(awk -v target="$ssid" '$1 == "Interface" {iface=$2} $1 == "ssid" && $2 == target {print iface}' "$run/$stage.iw.private.txt")
            case "$ifname" in *[!a-zA-Z0-9_.-]*|'') groups_ready=0; continue ;; esac
            wanted=$(for radio in $radios; do echo "${radio#radio}"; done | sort -n | tr '\n' ' ')
            actual=$(jsonfilter -i "$run/$stage.hostapd.private.json" -e "@.interfaces[\"$ifname\"].links.*.radio" | sort -n | tr '\n' ' ')
            running=$(jsonfilter -i "$run/$stage.hostapd.private.json" -e "@.interfaces[\"$ifname\"].links.*.running" | grep -c '^true$') || :
            count=0; for radio in $radios; do count=$((count + 1)); done
            link_pending=$(jsonfilter -i "$run/$stage.hostapd.private.json" -e "@.interfaces[\"$ifname\"].links.*.pending" | grep -c '^true$') || :
            [ "$actual" = "$wanted" ] && [ "$running" = "$count" ] && [ "$link_pending" = 0 ] || groups_ready=0
        done
        if [ "$global_count" = 2 ] && [ "$wireless_pending" = 0 ] && [ "$wireless_up" = 3 ] && [ "$groups_ready" = 1 ] && cmp -s "$run/$stage.expected-channels.txt" "$run/$stage.actual-channels.txt" && cmp -s "$run/$stage.expected-ssids.private.txt" "$run/$stage.actual-ssids.private.txt"; then
            ready=1
            break
        fi
        poll=$((poll + 1))
    done
    printf 'STAGE=%s READY=%s MLD_GROUPS=%s NETIFD_PENDING=%s NETIFD_UP=%s POLLS=%s RELOAD_RC=%s\n' "$stage" "$ready" "$global_count" "$wireless_pending" "$wireless_up" "$poll" "$reload_rc"
    [ "$ready" = 1 ] && [ "$reload_rc" = 0 ] || exit 96
    for label in a b; do
        if [ "$label" = a ]; then radios=$radios_a; ssid=$ssid_a; previous_anchor=$previous_a_anchor; previous_mac=$previous_a_mac; else radios=$radios_b; ssid=$ssid_b; previous_anchor=$previous_b_anchor; previous_mac=$previous_b_mac; fi
        ifname=$(awk -v target="$ssid" '$1 == "Interface" {iface=$2} $1 == "ssid" && $2 == target {print iface}' "$run/$stage.iw.private.txt")
        address=$(jsonfilter -i "$run/$stage.hostapd.private.json" -e "@.interfaces[\"$ifname\"].macaddr")
        [ "${#address}" = 17 ] || exit 97
        anchor=${radios%% *}
        stable=not_required
        if [ "$anchor" = "$previous_anchor" ]; then [ "$address" = "$previous_mac" ] || exit 97; stable=1; fi
        printf 'STAGE=%s GROUP=%s SAME_ANCHOR_ADDRESS_STABLE=%s\n' "$stage" "$label" "$stable"
        if [ "$label" = a ]; then previous_a_anchor=$anchor; previous_a_mac=$address; else previous_b_anchor=$anchor; previous_b_mac=$address; fi
    done
    [ "$previous_a_mac" != "$previous_b_mac" ] || exit 98
done
echo 'MULTI_MLD_SEQUENCE_PASS=8'
exit 0
