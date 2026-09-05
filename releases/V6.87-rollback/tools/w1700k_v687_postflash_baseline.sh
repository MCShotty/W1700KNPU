#!/bin/sh

set -u

expected_board=gemtek,w1700k-ubi
expected_image_size=20415292
board="$(cat /tmp/sysinfo/board_name 2>/dev/null)"

[ "$board" = "$expected_board" ] || {
	echo "refusing post-flash probe on board: ${board:-unknown}" >&2
	exit 64
}

echo '===== identity ====='
ubus call system board
printf 'boot_id='
cat /proc/sys/kernel/random/boot_id
dmesg | grep -F 'Machine model:' | tail -n 1

echo
echo '===== installed hashes ====='
sha256sum \
	/usr/share/ucode/wifi/hostapd.uc \
	/usr/sbin/w1700k-wireless-validate \
	/usr/sbin/w1700k-radio-sanity \
	/etc/config/wireless

echo
echo '===== V6.87 markers ====='
grep -F 'country_code ?? config.country' /usr/share/ucode/wifi/hostapd.uc
grep -F 'must use EHT20 for a reliable 2.4GHz MLO link' \
	/usr/share/ucode/wifi/hostapd.uc \
	/usr/sbin/w1700k-wireless-validate
grep -F 'mandatory 20/40 coexistence fallback cannot update this MLD safely' \
	/usr/sbin/w1700k-radio-sanity

echo
echo '===== live FIT prefix ====='
head -c "$expected_image_size" /dev/ubi0_3 | sha256sum

echo
echo '===== UBI ====='
ubinfo -a

echo
echo '===== services ====='
for service in uhttpd dnsmasq softethervpnserver adblock; do
	if /etc/init.d/"$service" status >/dev/null 2>&1; then
		echo "$service=running"
	else
		echo "$service=not-running"
	fi
done

echo
echo '===== NPU mode ====='
if [ -x /usr/sbin/w1700k-wlan-npu-mode ]; then
	/usr/sbin/w1700k-wlan-npu-mode status
else
	echo 'w1700k-wlan-npu-mode helper unavailable'
fi

echo
echo '===== memory ====='
free

echo
echo '===== wireless ====='
iw dev
ubus call network.wireless status

echo
echo '===== temporary state ====='
mount | grep -E 'hostapd\.uc|w1700k-wireless-validate' || true
ps w | grep -E '[w]1700k|[r]estore-watchdog' || true

echo
echo '===== fatal kernel diagnostics ====='
fatal_pattern='WARNING: CPU|BUG:|Oops:|Unable to handle kernel|Call trace:|kernel panic|Fatal exception|KASAN:|UBSAN:|DMA-API:|Out of memory|oom-killer|watchdog.*(expired|timeout|lockup)|firmware crash|MCU.*(timeout|failed)|reset failed|I/O error|UBI error|quarantin'
if dmesg | grep -Ei "$fatal_pattern"; then
	echo 'fatal_diagnostics=present'
	exit 1
fi
echo 'fatal_diagnostics=none'
