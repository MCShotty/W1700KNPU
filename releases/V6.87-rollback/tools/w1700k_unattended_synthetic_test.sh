#!/bin/sh
# shellcheck disable=SC3043 # BusyBox ash supports local variables.

set -u

expected_board=gemtek,w1700k-ubi
expected_npu_mode="${EXPECTED_NPU_MODE:-0}"
board="$(cat /tmp/sysinfo/board_name 2>/dev/null)"
[ "$board" = "$expected_board" ] || {
	echo "refusing synthetic tests on board: ${board:-unknown}" >&2
	exit 64
}

work=/tmp/w1700k-synthetic-test
wireless_config="${W1700K_WIRELESS_CONFIG:-/etc/config/wireless}"
backup="$work/wireless.original"
original_ifnames="$work/wireless-ifnames.original"
current_ifnames="$work/wireless-ifnames.current"
restore_log="$work/wireless-restore.log"
watchdog_log="$work/restore-watchdog.log"
failures=0
tests=0
restored=0
restore_ok=1
original_enabled_ifaces=0
test_key="$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24)"

mkdir -p "$work"
cp "$wireless_config" "$backup" || exit 1
for section in $(uci -q show wireless | sed -n 's/^wireless\.\([^=]*\)=wifi-iface$/\1/p'); do
	[ "$(uci -q get wireless."$section".disabled)" = 1 ] ||
		original_enabled_ifaces=$((original_enabled_ifaces + 1))
done
iw dev 2>/dev/null | awk '$1 == "Interface" { print $2 }' | sort -u >"$original_ifnames"
if [ "$original_enabled_ifaces" -gt 0 ] && [ ! -s "$original_ifnames" ]; then
	echo "refusing synthetic tests: enabled wireless config has no runtime interfaces" >&2
	exit 1
fi

restore_wireless() {
	[ "$restored" -eq 0 ] || return 0
	restored=1
	trap - EXIT HUP INT TERM
	wifi down >"$restore_log" 2>&1 || true
	remove_unexpected_runtime_ifaces >>"$restore_log" 2>&1
	if cp "$backup" "$wireless_config" && uci -q revert wireless &&
	   wifi up >>"$restore_log" 2>&1; then
		if [ -n "${watchdog_pid:-}" ]; then
			kill -TERM "-$watchdog_pid" 2>/dev/null || true
			sleep 1
			[ -d "/proc/$watchdog_pid" ] && kill_process_tree "$watchdog_pid"
		fi
		echo "restored original wireless config"
	else
		restore_ok=0
		echo "wireless restore failed; leaving independent watchdog armed" >&2
		cat "$restore_log" >&2 2>/dev/null || true
	fi
}

remove_unexpected_runtime_ifaces() {
	local ifname

	for ifname in $(iw dev 2>/dev/null | awk '$1 == "Interface" { print $2 }'); do
		grep -Fqx "$ifname" "$original_ifnames" || iw dev "$ifname" del || true
	done
}

kill_process_tree() {
	local pid="$1" child

	[ -d "/proc/$pid" ] || return 0
	for child in $(cat "/proc/$pid/task/$pid/children" 2>/dev/null); do
		kill_process_tree "$child"
	done
	kill "$pid" 2>/dev/null || true
}

wait_for_restored_runtime() {
	local elapsed=0

	while [ "$elapsed" -lt 45 ]; do
		if iw dev 2>/dev/null | grep -q 'W1700K-.*-Synthetic'; then
			sleep 1
			elapsed=$((elapsed + 1))
			continue
		fi

		iw dev 2>/dev/null | awk '$1 == "Interface" { print $2 }' |
			sort -u >"$current_ifnames"
		if ubus call network.wireless status 2>/dev/null |
			grep -Eq '"pending":[[:space:]]*true|"retry_setup_failed":[[:space:]]*true'; then
			sleep 1
			elapsed=$((elapsed + 1))
			continue
		fi

		if cmp -s "$original_ifnames" "$current_ifnames"; then
			return 0
		fi

		sleep 1
		elapsed=$((elapsed + 1))
	done

	return 1
}

trap restore_wireless EXIT HUP INT TERM

setsid sh -c "sleep 900; wifi down; for i in \$(iw dev 2>/dev/null | awk '\$1 == \"Interface\" { print \$2 }'); do iw dev \"\$i\" del || true; done; cp '$backup' '$wireless_config'; wifi up" \
	</dev/null >"$watchdog_log" 2>&1 &
watchdog_pid=$!

record_pass() {
	tests=$((tests + 1))
	echo "PASS: $1"
}

record_fail() {
	tests=$((tests + 1))
	failures=$((failures + 1))
	echo "FAIL: $1" >&2
}

disable_all_ifaces() {
	local section

	for section in $(uci -q show wireless | sed -n 's/^wireless\.\([^=]*\)=wifi-iface$/\1/p'); do
		uci set wireless."$section".disabled=1
	done
	uci -q delete wireless.codex_synth
}

configure_radio() {
	local radio="$1" band="$2" channel="$3" htmode="$4" enabled="$5"

	uci set wireless."$radio".country=US
	uci set wireless."$radio".band="$band"
	uci set wireless."$radio".channel="$channel"
	uci set wireless."$radio".htmode="$htmode"
	uci -q delete wireless."$radio".txpower
	uci set wireless."$radio".disabled="$enabled"
}

create_test_ap() {
	local ssid="$1"
	shift

	uci set wireless.codex_synth=wifi-iface
	uci set wireless.codex_synth.mode=ap
	uci set wireless.codex_synth.network=lan
	uci set wireless.codex_synth.ssid="$ssid"
	uci set wireless.codex_synth.encryption=sae
	uci set wireless.codex_synth.key="$test_key"
	uci set wireless.codex_synth.ieee80211w=2
	uci set wireless.codex_synth.sae_pwe=2
	uci set wireless.codex_synth.rnr=1
	uci set wireless.codex_synth.hidden=1
	uci set wireless.codex_synth.disabled=0
	uci -q delete wireless.codex_synth.device
	for radio in "$@"; do
		uci add_list wireless.codex_synth.device="$radio"
	done
	if [ "$#" -gt 1 ]; then
		uci set wireless.codex_synth.mlo=1
	else
		uci -q delete wireless.codex_synth.mlo
	fi
	uci commit wireless
}

current_ap_state() {
	local wanted_ssid="$1"

	# Bind observations to the current test SSID so asynchronous teardown of a
	# previous AP cannot satisfy the next case. This handles both ordinary APs
	# and the linked channel lines emitted for an MLD interface.
	iw dev 2>/dev/null | awk -v wanted="$wanted_ssid" '
		/^[[:space:]]*Interface / { matched = 0; link_ids = "" }
		/^[[:space:]]*ssid / {
			name = $0
			sub(/^[[:space:]]*ssid /, "", name)
			matched = (name == wanted)
		}
		matched && /channel [0-9]+ \([0-9]+ MHz\), width: [0-9]+ MHz/ {
			freq = $0
			sub(/^.*\(/, "", freq)
			sub(/ MHz\).*$/, "", freq)
			width = $0
			sub(/^.*width: /, "", width)
			sub(/ MHz.*$/, "", width)
			print "channel=" freq ":" width
		}
		matched && /- link ID[[:space:]]+[0-9]+/ {
			id = $0
			sub(/^.*- link ID[[:space:]]+/, "", id)
			sub(/[[:space:]].*$/, "", id)
			link_ids = link_ids (link_ids == "" ? "" : " ") id
		}
		matched && /Radios:/ {
			radios = $0
			sub(/^.*Radios:[[:space:]]*/, "", radios)
			gsub(/[[:space:]]+/, " ", radios)
			print "radios=" radios
			if (link_ids != "")
				print "link_ids=" link_ids
		}
	'
}

width_is_allowed() {
	local actual="$1" allowed="$2" width
	local old_ifs="$IFS"

	IFS=,
	for width in $allowed; do
		[ "$actual" = "$width" ] && {
			IFS="$old_ifs"
			return 0
		}
	done
	IFS="$old_ifs"
	return 1
}

channel_contract_matches() {
	local state_file="$1" frequencies="$2" allowed_widths="$3"
	local frequency actual old_ifs="$IFS"

	case "$frequencies" in
		5g160-us)
			# A 160 MHz AP necessarily spans DFS spectrum in the US. Hostapd may
			# move to any primary in either complete block after a radar event.
			frequencies='5180,5200,5220,5240,5260,5280,5300,5320,5500,5520,5540,5560,5580,5600,5620,5640'
			;;
	esac

	IFS=,
	for frequency in $frequencies; do
		actual="$(sed -n "s/^channel=$frequency://p" "$state_file" | head -n 1)"
		if [ -n "$actual" ] && width_is_allowed "$actual" "$allowed_widths"; then
			IFS="$old_ifs"
			return 0
		fi
	done
	IFS="$old_ifs"
	return 1
}

wait_for_ap_state() {
	local ssid="$1" expected_radios="$2" timeout="$3" contracts="$4"
	local elapsed=0 contract frequencies allowed ready expected_link_ids

	case "$expected_radios" in
		*" "*) expected_link_ids="$expected_radios" ;;
		*) expected_link_ids= ;;
	esac

	while [ "$elapsed" -lt "$timeout" ]; do
		current_ap_state "$ssid" > "$work/current-ap-state"
		ready=1
		grep -qx "radios=$expected_radios" "$work/current-ap-state" || ready=0
		[ -z "$expected_link_ids" ] ||
			grep -qx "link_ids=$expected_link_ids" "$work/current-ap-state" || ready=0
		for contract in $contracts; do
			frequencies="${contract%%:*}"
			allowed="${contract#*:}"
			channel_contract_matches "$work/current-ap-state" "$frequencies" "$allowed" || ready=0
		done
		[ "$ready" -eq 1 ] && return 0
		sleep 2
		elapsed=$((elapsed + 2))
	done
	return 1
}

capture_case_state() {
	local label="$1"

	echo "--- $label: iw dev ---"
	iw dev 2>/dev/null || true
	echo "--- $label: hostapd states ---"
	for object in $(ubus list 'hostapd.*' 2>/dev/null); do
		echo "[$object]"
		ubus call "$object" get_status 2>/dev/null || true
	done
	echo "--- $label: recent log ---"
	logread 2>/dev/null | grep -Ei 'mt76|mt7996|hostapd|mlo|eht|dfs|radar|failed|error' | tail -100 || true
}

run_luci_scan_case() {
	local label="$1" radio="$2" ssid="$3" expected_radios="$4" contracts="$5"
	local marker="w1700k-luci-scan-${label}-$$" scan_pid watchdog_pid rc
	local out="$work/luci-scan-${label}.json" err="$work/luci-scan-${label}.err"
	local dmesg_out="$work/luci-scan-${label}.dmesg"

	printf '%s\n' "$marker" >/dev/kmsg
	ubus call iwinfo scan "{\"device\":\"$radio\"}" >"$out" 2>"$err" &
	scan_pid=$!
	(
		sleep 60
		kill -TERM "$scan_pid" >/dev/null 2>&1 || true
	) &
	watchdog_pid=$!
	if wait "$scan_pid"; then
		rc=0
	else
		rc=$?
	fi
	kill "$watchdog_pid" >/dev/null 2>&1 || true
	wait "$watchdog_pid" >/dev/null 2>&1 || true

	dmesg | sed -n "/$marker/,$ p" >"$dmesg_out"
	if [ "$rc" -eq 0 ] &&
		jsonfilter -i "$out" -e '@.results' >/dev/null 2>&1 &&
		wait_for_ap_state "$ssid" "$expected_radios" 45 "$contracts" &&
		! grep -Ei 'BUG:|Oops:|Unable to handle kernel|Call trace:|Kernel panic|Fatal exception|firmware crash|reset failed|channel switch.*timed out|scan.*timed out' "$dmesg_out" >/dev/null; then
		record_pass "$label LuCI radio scan completed and AP state recovered"
	else
		record_fail "$label LuCI radio scan completed and AP state recovered"
		echo "scan_rc=$rc radio=$radio" >&2
		cat "$err" >&2
		cat "$out" >&2
		cat "$dmesg_out" >&2
		capture_case_state "$label-luci-scan"
	fi
}

run_ap_case() {
	local label="$1" expected_radios="$2" timeout="$3" contracts ssid radio
	shift 3

	echo
	echo "===== $label ====="
	disable_all_ifaces
	configure_radio radio0 2g 6 EHT40 1
	configure_radio radio1 5g 36 EHT80 1
	configure_radio radio2 6g 37 EHT320 1

	case "$label" in
		2g-eht40)
			configure_radio radio0 2g 6 EHT40 0
			# 20/40 coexistence may require a standards-compliant fallback to 20 MHz.
			contracts='2437:20,40'
			;;
		5g-eht80)
			configure_radio radio1 5g 36 EHT80 0
			contracts='5180:80'
			;;
		5g-eht160)
			configure_radio radio1 5g 36 EHT160 0
			contracts='5g160-us:160'
			;;
		6g-eht320)
			configure_radio radio2 6g 37 EHT320 0
			contracts='6135:320'
			;;
		mlo-5g-6g)
			configure_radio radio1 5g 36 EHT80 0
			configure_radio radio2 6g 37 EHT320 0
			contracts='5180:80 6135:320'
			;;
		mlo-tri-band)
			configure_radio radio0 2g 6 EHT20 0
			configure_radio radio1 5g 36 EHT80 0
			configure_radio radio2 6g 37 EHT320 0
			contracts='2437:20 5180:80 6135:320'
			;;
		*) record_fail "$label has no synthetic frequency contract"; return ;;
	esac

	ssid="W1700K-$label-Synthetic"
	create_test_ap "$ssid" "$@"
	if ! /usr/sbin/w1700k-wireless-validate; then
		record_fail "$label backend validation"
		capture_case_state "$label"
		return
	fi

	wifi reload >/dev/null 2>&1 || true
	if wait_for_ap_state "$ssid" "$expected_radios" "$timeout" "$contracts"; then
		record_pass "$label AP bring-up with radios $expected_radios and $contracts"
		for radio in "$@"; do
			run_luci_scan_case "$label-$radio" "$radio" "$ssid" "$expected_radios" "$contracts"
		done
	else
		record_fail "$label AP bring-up with radios $expected_radios and $contracts"
		cat "$work/current-ap-state" 2>/dev/null || true
	fi
	capture_case_state "$label"
}

expect_validation_failure() {
	local label="$1"

	if /usr/sbin/w1700k-wireless-validate >/tmp/w1700k-validator-negative.log 2>&1; then
		record_fail "$label was accepted"
	else
		record_pass "$label was rejected"
		cat /tmp/w1700k-validator-negative.log
	fi
	uci revert wireless
}

echo "board: $board"
echo "kernel: $(uname -r)"
echo "release: $(. /etc/openwrt_release; echo "$DISTRIB_DESCRIPTION")"
echo "watchdog_pid: $watchdog_pid"

mld_log_marker="w1700k-synthetic-mld-start-$$"
logger -t w1700k-synthetic "$mld_log_marker"

status_file="$work/npu-mode-status"
/usr/sbin/w1700k-wlan-npu-mode status > "$status_file" 2>&1 || true
if [ "$expected_npu_mode" = 0 ] &&
	grep -Eq '^configured: mt7996e([[:space:]]|$)' "$status_file" &&
	grep -qx 'loaded: wlan_npu_mode=0' "$status_file"; then
	record_pass "production NPU mode is 0"
elif [ "$expected_npu_mode" = 3 ] &&
	grep -q '^configured: mt7996e wlan_npu_mode=3\([[:space:]]\|$\)' "$status_file" &&
	grep -qx 'loaded: wlan_npu_mode=3' "$status_file"; then
	record_pass "experimental NPU mode 3 is configured and loaded"
elif case "$expected_npu_mode" in 1|2|4) true ;; *) false ;; esac &&
	grep -q "^mt7996e wlan_npu_mode=$expected_npu_mode\([[:space:]]\|$\)" /etc/modules.d/mt7996e &&
	[ "$(cat /sys/module/mt7996e/parameters/wlan_npu_mode 2>/dev/null)" = "$expected_npu_mode" ]; then
	record_pass "unsupported NPU mode $expected_npu_mode is loaded for fail-closed validation"
else
	record_fail "expected NPU mode $expected_npu_mode is configured and loaded"
fi

trans_file="$(find /sys/kernel/debug/ieee80211 -maxdepth 3 -type f \
	-name npu-trans-lifecycle 2>/dev/null | head -n 1)"
parity_file="$(find /sys/kernel/debug/ieee80211 -maxdepth 3 -type f \
	-name w1700k-stock-npu-parity-map 2>/dev/null | head -n 1)"
trans_json="$work/npu-trans-lifecycle.json"
if /usr/sbin/w1700k-wlan-npu-mode trans-lifecycle > "$trans_json" 2>&1; then
	if [ "$expected_npu_mode" = 0 ] &&
		grep -q '"status":"inactive-clean"' "$trans_json"; then
		record_pass "mode 0 transport lifecycle is inactive and clean"
	elif case "$expected_npu_mode" in 1|2|4) true ;; *) false ;; esac &&
		grep -q '"status":"inactive-clean"' "$trans_json"; then
		record_pass "unsupported mode $expected_npu_mode transport failed closed and stayed clean"
	elif [ "$expected_npu_mode" = 3 ] &&
		grep -q '"status":"ready"' "$trans_json" &&
		grep -q '"assigned_slots":2' "$trans_json" &&
		grep -q '"trans1_hook_registered":1' "$trans_json" &&
		grep -q '"trans2_hook_registered":1' "$trans_json"; then
		record_pass "mode 3 transport lifecycle has two committed hooks"
	else
		record_fail "mode $expected_npu_mode transport lifecycle state"
		cat "$trans_json"
	fi
else
	record_fail "mode $expected_npu_mode transport lifecycle verifier"
	cat "$trans_json"
fi

if [ "$expected_npu_mode" = 0 ]; then
	ppe_failures=0
	for key in \
		stock_wlan_force_ring \
		stock_wlan_force_qos \
		stock_wlan_port_ag_3f \
		stock_force_cpu_ring_commit \
		stock_wlan_actdp \
		stock_udp_bypass_ring \
		stock_multicast_ratelimit_ring7 \
		stock_multicast_ratelimit_commit; do
		grep -q "^$key: configured=0 " "$status_file" || ppe_failures=$((ppe_failures + 1))
	done
	if [ "$ppe_failures" -eq 0 ]; then
		record_pass "production NPU mode has baseline PPE policy"
	else
		record_fail "production NPU mode has baseline PPE policy ($ppe_failures mismatches)"
	fi
fi

run_ap_case 2g-eht40 0 30 radio0
run_ap_case 5g-eht80 1 40 radio1
run_ap_case 5g-eht160 1 100 radio1
run_ap_case 6g-eht320 2 40 radio2
run_ap_case mlo-5g-6g '1 2' 70 radio1 radio2
run_ap_case mlo-tri-band '0 1 2' 70 radio1 radio2 radio0

if logread 2>/dev/null | sed -n "/$mld_log_marker/,$ p" |
	grep -Eq 'Failed to create interface .*: -23|Failed to create MLD .*: -23'; then
	record_fail 'MLO reconfiguration avoided duplicate-interface ENFILE'
else
	record_pass 'MLO reconfiguration avoided duplicate-interface ENFILE'
fi

if logread 2>/dev/null | sed -n "/$mld_log_marker/,$ p" |
	grep -Eq 'netifd: radio[0-2].*command failed: Not supported \(-95\)'; then
	record_fail 'multi-radio setup avoided repeated unsupported antenna writes'
else
	record_pass 'multi-radio setup avoided repeated unsupported antenna writes'
fi

echo
echo '===== backend rejection tests ====='
uci set wireless.radio0.htmode=EHT40
expect_validation_failure '2.4GHz MLO using coexistence-unsafe EHT40'

uci set wireless.radio0.band=5g
expect_validation_failure 'radio0 configured as 5GHz'

uci set wireless.radio1.htmode=EHT320
expect_validation_failure 'radio1 configured for EHT320'

uci set wireless.radio0.radio=99
expect_validation_failure 'unsupported physical radio index'

uci set wireless.codex_alias=wifi-device
uci set wireless.codex_alias.radio=1
uci set wireless.codex_alias.band=5g
uci set wireless.codex_alias.channel=36
uci set wireless.codex_alias.htmode=EHT80
uci set wireless.codex_alias.country=US
expect_validation_failure 'duplicate physical radio index'

uci set wireless.codex_synth.mlo=1
uci -q delete wireless.codex_synth.device
uci add_list wireless.codex_synth.device=radio1
expect_validation_failure 'single-link MLO'

uci set wireless.codex_overlap=wifi-iface
uci set wireless.codex_overlap.mode=ap
uci set wireless.codex_overlap.network=lan
uci set wireless.codex_overlap.ssid=W1700K-Overlapping-MLO
uci set wireless.codex_overlap.encryption=sae
uci set wireless.codex_overlap.key="$test_key"
uci set wireless.codex_overlap.ieee80211w=2
uci set wireless.codex_overlap.sae_pwe=2
uci set wireless.codex_overlap.rnr=1
uci set wireless.codex_overlap.mlo=1
uci add_list wireless.codex_overlap.device=radio1
uci add_list wireless.codex_overlap.device=radio2
expect_validation_failure 'overlapping MLO radio ownership'

uci set wireless.codex_synth.mlo=banana
expect_validation_failure 'malformed MLO flag'

uci set wireless.codex_synth.encryption=psk2
uci set wireless.codex_synth.ieee80211w=1
expect_validation_failure '6GHz MLO with WPA2 and optional PMF'

uci set wireless.radio1.channel=auto
expect_validation_failure 'MLO member using automatic channel selection'

uci set wireless.radio1.punct_bitmap=99999999999999999999
expect_validation_failure 'oversized EHT puncturing bitmap'

echo
echo '===== service and kernel health ====='
for service in uhttpd dnsmasq softethervpnserver; do
	if /etc/init.d/"$service" status >/dev/null 2>&1; then
		record_pass "$service service running"
	else
		record_fail "$service service running"
	fi
done

if [ -x /etc/init.d/adblock ] && /etc/init.d/adblock enabled && \
	grep -q '/etc/init.d/adblock reload.*dnsmasq restart' /etc/crontabs/root 2>/dev/null; then
	record_pass "adblock installed, enabled, and scheduled"
else
	record_fail "adblock installed, enabled, and scheduled"
fi

if dmesg | grep -Ei 'WARNING: CPU|BUG:|Oops:|Unable to handle kernel|Call trace:|kernel panic|Fatal exception|KASAN:|UBSAN:|DMA-API:|Out of memory|oom-killer|watchdog.*(expired|timeout|lockup)|firmware crash|MCU.*(timeout|failed)|reset failed|I/O error|UBI error|quarantin'; then
	record_fail 'kernel log has no fatal diagnostics'
else
	record_pass 'kernel log has no fatal diagnostics'
fi

if [ "$expected_npu_mode" = 3 ]; then
	hostadpt=/sys/kernel/debug/airoha-npu/stock_hostadpt_irq_index
	if [ -r "$hostadpt" ]; then
		cp "$hostadpt" "$work/stock-hostadpt-after"
		if [ "$(grep -c '^tx_count_match=1$' "$work/stock-hostadpt-after")" -eq 2 ] &&
			[ "$(grep -c '^rx_count_match=1$' "$work/stock-hostadpt-after")" -eq 2 ] &&
			[ "$(grep -c '^tx_base_reg=.* desc=1024$' "$work/stock-hostadpt-after")" -eq 2 ] &&
			[ "$(grep -c '^rx_base_reg=.* desc=512$' "$work/stock-hostadpt-after")" -eq 2 ]; then
			record_pass "mode 3 programmed stock-compatible hostadpt rings"
		else
			record_fail "mode 3 programmed stock-compatible hostadpt rings"
			cat "$work/stock-hostadpt-after"
		fi
	else
		record_fail "mode 3 hostadpt ring monitor is available"
	fi

	if [ -r "$parity_file" ]; then
		cp "$parity_file" "$work/stock-npu-parity-after"
		if [ "$(grep -c 'wfdma_expected:512 wfdma_live:512 wfdma_valid:1 wfdma_match:1$' "$work/stock-npu-parity-after")" -eq 2 ] &&
			[ "$(grep -c 'wfdma_expected:1024 wfdma_live:1024 wfdma_valid:1 wfdma_match:1$' "$work/stock-npu-parity-after")" -eq 1 ] &&
			grep -qx 'stock_downstream_wfdma_ring_match=1' "$work/stock-npu-parity-after" &&
			grep -qx 'stock_tx_topology_match=1' "$work/stock-npu-parity-after"; then
			record_pass "mode 3 live downstream WFDMA rings are 512/1024"
		else
			record_fail "mode 3 live downstream WFDMA rings are 512/1024"
			cat "$work/stock-npu-parity-after"
		fi

		if grep -qx 'tx_token_balance_matches_current_scope=legacy-observed-window-vs-global-idr' "$work/stock-npu-parity-after" &&
			grep -Eq '^tx_token_observed_window_net=-?[0-9]+$' "$work/stock-npu-parity-after" &&
			grep -Eq '^tx_token_unobserved_net_current=-?[0-9]+$' "$work/stock-npu-parity-after" &&
			grep -qx 'tx_token_scoped_accounting_identity=1' "$work/stock-npu-parity-after"; then
			record_pass "mode 3 token telemetry reports explicit counter scope"
		else
			record_fail "mode 3 token telemetry reports explicit counter scope"
			cat "$work/stock-npu-parity-after"
		fi
	else
		record_fail "mode 3 stock NPU parity monitor is available"
	fi

	if dmesg | grep -q 'NPU version:'; then
		record_pass "mode 3 completed NPU firmware handshake"
	else
		record_fail "mode 3 completed NPU firmware handshake"
	fi

	if [ -r "$trans_file" ] &&
		grep -qx 'status=ready' "$trans_file" &&
		grep -qx 'assignment_balance_ok=1' "$trans_file" &&
		grep -qx 'assign_overflow=0' "$trans_file" &&
		grep -qx 'hook_register_mismatch=0' "$trans_file" &&
		grep -qx 'irq_blocked=0' "$trans_file" &&
		grep -qx 'trans1_irq_missing=0' "$trans_file" &&
		grep -qx 'trans1_irq_mismatch=0' "$trans_file" &&
		grep -qx 'trans2_irq_missing=0' "$trans_file" &&
		grep -qx 'trans2_irq_mismatch=0' "$trans_file" &&
		grep -qx 'txfree_bad_version=0' "$trans_file"; then
		record_pass "mode 3 transport scheduler stayed fail-closed and clean"
	else
		record_fail "mode 3 transport scheduler stayed fail-closed and clean"
		cat "$trans_file" 2>/dev/null || true
	fi

	txfree_truncated="$(sed -n 's/^txfree_truncated=//p' "$trans_file")"
	txfree_mismatch="$(sed -n 's/^txfree_count_mismatch=//p' "$trans_file")"
	if [ -n "$txfree_truncated" ] && [ "$txfree_truncated" -le 8 ] &&
		[ "$txfree_truncated" -eq "$txfree_mismatch" ]; then
		record_pass "mode 3 TXFREE short notifications stayed bounded and accounted"
	else
		record_fail "mode 3 TXFREE short notifications stayed bounded and accounted"
		cat "$trans_file" 2>/dev/null || true
	fi

	echo
	echo "===== mode 3 transport lifecycle snapshot ====="
	cat "$trans_file" 2>/dev/null || true
fi

echo
echo '===== wireless restoration ====='
restore_wireless
if [ "$restore_ok" -eq 1 ] && cmp -s "$backup" "$wireless_config"; then
	record_pass 'original wireless configuration restored byte-for-byte'
else
	record_fail 'original wireless configuration restored byte-for-byte'
fi

if wait_for_restored_runtime; then
	record_pass 'restored runtime matches original wireless interface set'
else
	record_fail 'restored runtime matches original wireless interface set'
	capture_case_state restored-runtime
fi

echo
echo "tests: $tests"
echo "failures: $failures"
exit "$failures"
