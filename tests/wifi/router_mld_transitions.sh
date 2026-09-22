#!/bin/sh
set -eu
umask 077
tag=${1:-run01}
mode=${2:-rapid}
replay=${3:-none}
case "$mode" in rapid|settled) ;; *) exit 79 ;; esac
case "$replay" in none|stale) ;; *) exit 79 ;; esac
case "$tag" in *[!a-zA-Z0-9_-]*|'') exit 79 ;; esac
run=/tmp/w1700k-wifi-transitions-20260907-$tag
baseline=a87e59eb9c6314be153d8af85f88ebbe0438a1cfb6e0e0ee92ee1b5f200c416d
file_hash() { sha256sum "$1" | cut -d ' ' -f1; }
pending_hash() { uci changes wireless | sha256sum | cut -d ' ' -f1; }
[ "$(cat /tmp/sysinfo/board_name)" = gemtek,w1700k-ubi ] || exit 80
[ "$(uname -r)" = 6.18.44 ] || exit 81
[ "$(file_hash /etc/config/wireless)" = "$baseline" ] || exit 82
[ -z "$(uci changes wireless)" ] || exit 83
[ "$(file_hash /usr/libexec/w1700k-wireless-regulatory)" = 04497f40bb5c774d985784ee920b682da16d6e8ae71d55778400477a7111b7d5 ] || exit 84
[ "$(file_hash /usr/share/hostap/hostapd.uc)" = e9bdbed02f2072121083130d1de0dc91996c95217550fd5604fcc641d96e6338 ] || exit 85
[ "$(file_hash /usr/share/ucode/wifi/hostapd.uc)" = 79004ebbb01a637a824806c7254170d55ba7a418bb137f370a305b9b4c2a4a86 ] || exit 85
[ "$(file_hash /usr/share/ucode/wifi/iface.uc)" = ef91cb5cb1e1c6c99d07c67d9dccdc4d846ed05a2c1f36afde9f49b2e9a79deb ] || exit 85
[ "$(file_hash /usr/share/ucode/wifi/mld-config.uc)" = 16db8c275cd64607845ae9b7a6093d05e260dcad5266e3cd8b61d8918d1df1f2 ] || exit 85
[ "$(file_hash /usr/lib/ucode/nl80211.so)" = 6c2af55f71276895be7e906f67479339984affe10bf893b05ae3e74cb2cff92d ] || exit 86
[ "$(/usr/sbin/w1700k-wlan-npu-mode json | jsonfilter -e '@.npu.runtime_state')" = compiled-out ] || exit 87
[ ! -e "$run" ] || exit 88
[ -f /tmp/w1700k-transition-channel-check.uc ] || exit 88
[ "$(file_hash /tmp/w1700k-transition-channel-check.uc)" = e8383f5d0b8e335b08db42e345623a47411400bd91cbcf6f3f063348ec4fc939 ] || exit 88
mkdir -m700 "$run"
if [ "$replay" = stale ]; then
    replay_dir=/var/run/hostapd/w1700k-replay-$tag
    [ ! -e "$replay_dir" ] || exit 88
    mkdir -m700 "$replay_dir"
    chown network:network "$replay_dir"
fi
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
    if [ "$changed_runtime" = 1 ]; then
        wifi down >"$run/cleanup-down.private.log" 2>&1
    fi
    uci revert wireless
    cp -p "$run/wireless.before" /etc/config/wireless
    if [ "$changed_runtime" = 1 ]; then
        wifi up >"$run/cleanup-up.private.log" 2>&1
    fi
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
hexdump -vn24 -e '/1 "%02x"' /dev/urandom >"$run/lab.key"
key=$(cat "$run/lab.key")
[ "${#key}" = 48 ] || exit 93
previous_mld_hash=
previous_anchor=
previous_has_mld=0

configure() {
    config_rc=0
    uci batch <<EOF
set wireless.radio0.disabled='1'
set wireless.radio1.disabled='1'
set wireless.radio2.disabled='1'
set wireless.radio0.channel='$c0'
set wireless.radio1.channel='$c1'
set wireless.radio2.channel='$c2'
set wireless.radio0.htmode='$w0'
set wireless.radio1.htmode='$w1'
set wireless.radio2.htmode='$w2'
EOF
    rc=$?; [ "$rc" = 0 ] || config_rc=$rc
    for radio in $active; do
        uci set wireless.$radio.disabled=0 || config_rc=$?
    done
    for index in 0 1 2; do
        case " $ordinary " in
            *" radio$index "*)
                uci batch <<EOF
set wireless.codex_transition_ap$index=wifi-iface
set wireless.codex_transition_ap$index.device='radio$index'
set wireless.codex_transition_ap$index.mode='ap'
set wireless.codex_transition_ap$index.network='lan'
set wireless.codex_transition_ap$index.ssid='W1700K-Transition-$index'
set wireless.codex_transition_ap$index.encryption='sae'
set wireless.codex_transition_ap$index.key='$key'
set wireless.codex_transition_ap$index.ieee80211w='2'
set wireless.codex_transition_ap$index.sae_pwe='2'
set wireless.codex_transition_ap$index.rnr='1'
set wireless.codex_transition_ap$index.isolate='1'
EOF
                rc=$?; [ "$rc" = 0 ] || config_rc=$rc
                ;;
            *) uci -q delete wireless.codex_transition_ap$index ;;
        esac
    done
    if [ -n "$mld" ]; then
        uci batch <<EOF
set wireless.codex_transition_mld=wifi-iface
set wireless.codex_transition_mld.device='$mld'
set wireless.codex_transition_mld.mode='ap'
set wireless.codex_transition_mld.network='lan'
set wireless.codex_transition_mld.ssid='$mld_ssid'
set wireless.codex_transition_mld.encryption='sae'
set wireless.codex_transition_mld.key='$key'
set wireless.codex_transition_mld.ieee80211w='2'
set wireless.codex_transition_mld.sae_pwe='2'
set wireless.codex_transition_mld.rnr='1'
set wireless.codex_transition_mld.isolate='1'
set wireless.codex_transition_mld.mlo='1'
EOF
        rc=$?; [ "$rc" = 0 ] || config_rc=$rc
    else
        uci -q delete wireless.codex_transition_mld
    fi
    return "$config_rc"
}

for stage in 01-mlo25 02-add6g 03-channels 04-widths 05-drop2g 06-anchor6g 07-anchor5g 08-independent 09-mixed56 10-mixed26 11-triband320 12-ssid-change 13-ssid-return; do
    [ "$(file_hash /etc/config/wireless)" = "$expected_config" ] || exit 94
    [ "$(pending_hash)" = "$pending" ] || exit 94
    c0=6; c1=36; c2=37; w0=EHT20; w1=EHT80; w2=EHT80
    mld='radio1 radio2 radio0'; ordinary=; active=$mld
    mld_ssid=W1700K-Transition-MLD
    case "$stage" in
        01-mlo25|07-anchor5g) mld='radio1 radio0'; active=$mld ;;
        03-channels) c0=1; c1=44; c2=53 ;;
        04-widths) c0=1; c1=44; c2=53; w1=EHT40; w2=EHT160 ;;
        05-drop2g) mld='radio1 radio2'; active=$mld; c1=44; c2=53; w1=EHT40; w2=EHT160 ;;
        06-anchor6g) mld='radio2 radio0'; active=$mld; c0=1; c2=53; w2=EHT160 ;;
        08-independent) mld=; ordinary='radio0 radio1 radio2'; active=$ordinary ;;
        09-mixed56) mld='radio1 radio2'; ordinary=radio0 ;;
        10-mixed26) mld='radio2 radio0'; ordinary=radio1 ;;
        11-triband320|13-ssid-return) w2=EHT320 ;;
        12-ssid-change) w2=EHT320; mld_ssid=W1700K-Transition-Renamed ;;
    esac
    mlo_links=0; normal_count=0; link_radios=; normal_radios=; anchor=
    : >"$run/$stage.expected-ssids.private.txt"
    for radio in $mld; do
        [ -n "$anchor" ] || anchor=$radio
        mlo_links=$((mlo_links + 1))
        link_radios="$link_radios${radio#radio}\n"
    done
    if [ "$mlo_links" -gt 0 ]; then printf '%s\n' "$mld_ssid" >>"$run/$stage.expected-ssids.private.txt"; fi
    for radio in $ordinary; do
        normal_count=$((normal_count + 1))
        normal_radios="$normal_radios${radio#radio}\n"
        printf 'W1700K-Transition-%s\n' "${radio#radio}" >>"$run/$stage.expected-ssids.private.txt"
    done
    expected_global=$normal_count
    active_count=0
    for radio in $active; do active_count=$((active_count + 1)); done
    [ "$mlo_links" = 0 ] || expected_global=$((expected_global + 1))
    expected_link_radios=$(printf '%b' "$link_radios" | sort -n | tr '\n' ' ')
    expected_normal_radios=$(printf '%b' "$normal_radios" | sort -n | tr '\n' ' ')
    : >"$run/$stage.expected-channels.txt"
    for radio in $active; do
        case "$radio" in
            radio0) printf '%s %s %s %s\n' "$c0" "$((2407 + c0 * 5))" "${w0#EHT}" "$((2407 + c0 * 5))" ;;
            radio1)
                case "$c1:$w1" in
                    36:EHT80|44:EHT80) center=5210 ;;
                    44:EHT40) center=5230 ;;
                    *) exit 99 ;;
                esac
                printf '%s %s %s %s\n' "$c1" "$((5000 + c1 * 5))" "${w1#EHT}" "$center"
                ;;
            radio2)
                case "$c2:$w2" in
                    37:EHT80) center=6145 ;;
                    53:EHT80) center=6225 ;;
                    53:EHT160) center=6185 ;;
                    37:EHT320) center=6105 ;;
                    *) exit 99 ;;
                esac
                printf '%s %s %s %s\n' "$c2" "$((5950 + c2 * 5))" "${w2#EHT}" "$center"
                ;;
        esac
    done | sort >"$run/$stage.expected-channels.txt"
    sort "$run/$stage.expected-ssids.private.txt" >"$run/$stage.expected-ssids-sorted.private.txt"
    set +e
    configure >"$run/$stage.uci.private.log" 2>&1
    config_rc=$?
    pending=$(pending_hash)
    set -e
    [ "$config_rc" = 0 ] || exit 95
    /usr/sbin/w1700k-wireless-validate >"$run/$stage.validation.private.log" 2>&1 || exit 96
    uci commit wireless
    expected_config=$(file_hash /etc/config/wireless)
    pending=$(pending_hash)
    changed_runtime=1
    logger -t w1700k-test "W1700K-TRANSITION $run $stage BEGIN"
    wifi reload >"$run/$stage.reload.private.log" 2>&1
    ready=0
    poll=0
    while [ "$poll" -lt 35 ]; do
        sleep 2
        ubus call hostapd status >"$run/$stage.hostapd.private.json"
        global_count=$(jsonfilter -i "$run/$stage.hostapd.private.json" -e '@.interfaces.*.wiphy' | wc -l)
        global_running=$(jsonfilter -i "$run/$stage.hostapd.private.json" -e '@.interfaces.*.running' | grep -c '^true$') || :
        links_running=$(jsonfilter -i "$run/$stage.hostapd.private.json" -e '@.interfaces.*.links.*.running' | grep -c '^true$') || :
        pending_count=$(jsonfilter -i "$run/$stage.hostapd.private.json" -e '@.interfaces.*.pending' -e '@.interfaces.*.links.*.pending' | grep -c '^true$') || :
        actual_link_radios=$(jsonfilter -i "$run/$stage.hostapd.private.json" -e '@.interfaces.*.links.*.radio' | sort -n | tr '\n' ' ')
        actual_normal_radios=$(jsonfilter -i "$run/$stage.hostapd.private.json" -e '@.interfaces.*.radio' | sort -n | tr '\n' ' ')
        ubus call network.wireless status >"$run/$stage.wireless.private.json"
        wireless_pending=$(jsonfilter -i "$run/$stage.wireless.private.json" -e '@.*.pending' | grep -c '^true$') || :
        wireless_up=$(jsonfilter -i "$run/$stage.wireless.private.json" -e '@.*.up' | grep -c '^true$') || :
        settled=0
        if [ "$mode" = rapid ] || { [ "$wireless_pending" = 0 ] && [ "$wireless_up" = "$active_count" ]; }; then settled=1; fi
        iw dev >"$run/$stage.iw.private.txt"
        awk '$1 == "channel" && $5 == "width:" {gsub(/[()]/, "", $3); print $2, $3, $6, $9}' "$run/$stage.iw.private.txt" | sort >"$run/$stage.actual-channels.txt"
        logread >"$run/$stage.current.system.private.log"
        channel_match=0
        ucode /tmp/w1700k-transition-channel-check.uc "$run" "$stage" >"$run/$stage.channel-check.json" 2>"$run/$stage.channel-check.private.log" && channel_match=1
        awk '$1 == "ssid" {sub(/^[ \t]*ssid /, ""); print}' "$run/$stage.iw.private.txt" | sort >"$run/$stage.actual-ssids.private.txt"
        if [ "$global_count" = "$expected_global" ] && [ "$global_running" = "$normal_count" ] && [ "$links_running" = "$mlo_links" ] && [ "$pending_count" = 0 ] && [ "$actual_link_radios" = "$expected_link_radios" ] && [ "$actual_normal_radios" = "$expected_normal_radios" ] && [ "$channel_match" = 1 ] && [ "$settled" = 1 ] && cmp -s "$run/$stage.expected-ssids-sorted.private.txt" "$run/$stage.actual-ssids.private.txt"; then
            ready=1
            break
        fi
        poll=$((poll + 1))
    done
    ubus call network.wireless status >"$run/$stage.wireless.private.json"
    logread >"$run/$stage.system.private.log"
    printf 'STAGE=%s READY=%s GLOBAL=%s NORMAL_RUNNING=%s MLO_RUNNING=%s PENDING=%s POLLS=%s\n' "$stage" "$ready" "$global_count" "$global_running" "$links_running" "$pending_count" "$poll"
    printf 'STAGE=%s MODE=%s NETIFD_PENDING=%s NETIFD_UP=%s\n' "$stage" "$mode" "$wireless_pending" "$wireless_up"
    [ "$ready" = 1 ] || exit 97
    cat "$run/$stage.channel-check.json"
    if [ "$mlo_links" -gt 0 ]; then
        mld_addr=$(jsonfilter -i "$run/$stage.hostapd.private.json" -e '@.interfaces["ap-mld0"].macaddr')
        [ "${#mld_addr}" = 17 ] || exit 98
        mld_hash=$(printf '%s\n' "$mld_addr" | sha256sum | cut -d ' ' -f1)
        stable=not_required
        if [ "$previous_has_mld" = 1 ] && [ "$anchor" = "$previous_anchor" ]; then
            [ "$mld_hash" = "$previous_mld_hash" ] || exit 98
            stable=1
        fi
        previous_mld_hash=$mld_hash
        previous_anchor=$anchor
        previous_has_mld=1
        printf 'STAGE=%s SAME_ANCHOR_MLD_ADDRESS_STABLE=%s\n' "$stage" "$stable"
    else
        previous_has_mld=0
    fi
    if [ "$replay" = stale ]; then
        case "$stage" in
            12-ssid-change|13-ssid-return)
                ubus call hostapd status >"$run/$stage.pre-replay.hostapd.private.json"
                iw dev >"$run/$stage.pre-replay.iw.private.txt"
                logger -t w1700k-test "W1700K-STALE-REPLAY $tag $stage BEGIN"
                for radio in 0 1 2; do
                    request=$(printf '{"phy":"phy0","radio":%s,"config":"%s/%s-phy0.%s.private.conf"}' "$radio" "$replay_dir" "$saved_stage" "$radio")
                    ubus call hostapd config_set "$request" >"$run/$stage.replay-$radio.private.json"
                done
                logread | sed -n "/W1700K-STALE-REPLAY $tag $stage BEGIN/,$ p" >"$run/$stage.replay.system.private.log"
                [ "$(grep -c 'Reject stale MLD interface config on phy' "$run/$stage.replay.system.private.log")" = 3 ] || exit 100
                for radio in 0 1 2; do
                    request=$(printf '{"phy":"phy0","radio":%s,"config":"%s/absent-phy0.%s.conf"}' "$radio" "$replay_dir" "$radio")
                    if ubus call hostapd config_set "$request" >"$run/$stage.missing-$radio.private.json" 2>"$run/$stage.missing-$radio.private.log"; then
                        exit 103
                    fi
                    grep -q 'Invalid argument' "$run/$stage.missing-$radio.private.log" || exit 104
                done
                for attempt in 1 2 3; do
                    sleep 2
                    ubus call hostapd status >"$run/$stage.post-replay.hostapd.private.json"
                    iw dev >"$run/$stage.post-replay.iw.private.txt"
                    cmp -s "$run/$stage.pre-replay.hostapd.private.json" "$run/$stage.post-replay.hostapd.private.json" || exit 101
                    cmp -s "$run/$stage.pre-replay.iw.private.txt" "$run/$stage.post-replay.iw.private.txt" || exit 102
                done
                printf 'STAGE=%s STALE_RADIO_REPLAYS_REJECTED=3 MISSING_CONFIGS_REJECTED=3 HOSTAPD_AND_IW_UNCHANGED=1 STABLE_OBSERVATIONS=3\n' "$stage"
                ;;
        esac
        case "$stage" in
            11-triband320|12-ssid-change)
                for radio in 0 1 2; do
                    cp "/var/run/hostapd-phy0.$radio.conf" "$run/$stage-phy0.$radio.private.conf"
                    cp "$run/$stage-phy0.$radio.private.conf" "$replay_dir/$stage-phy0.$radio.private.conf"
                    chown network:network "$replay_dir/$stage-phy0.$radio.private.conf"
                    chmod 600 "$replay_dir/$stage-phy0.$radio.private.conf"
                done
                saved_stage=$stage
                ;;
        esac
    fi
done
echo 'TRANSITION_SEQUENCE_PASS=13'
exit 0
