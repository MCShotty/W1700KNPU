#!/usr/bin/env bash
set -euo pipefail

base=/home/captain/w1700k-openwrt-build/v686-corrective-source-20260901
candidate=/home/captain/w1700k-openwrt-build/v687-corrective-source-20260901
output=/mnt/c/Users/captain/Documents/Codex/2026-06-12/i-need-help-wiping-the-nand/work/patches/v687-corrective-source.patch
files=(
	feeds/luci/modules/luci-mod-network/htdocs/luci-static/resources/view/network/wireless.js
	feeds/luci/modules/luci-mod-network/tests/w1700k-wireless-transitions.test.js
	package/network/config/wifi-scripts/files-ucode/usr/share/ucode/wifi/hostapd.uc
	target/linux/airoha/an7581/base-files/usr/sbin/w1700k-radio-sanity
	target/linux/airoha/an7581/base-files/usr/sbin/w1700k-wireless-validate
	target/linux/airoha/an7581/tests/fixtures/w1700k-backend-sanity-functions.sh
	target/linux/airoha/an7581/tests/fixtures/w1700k-backend-validator-functions.sh
	target/linux/airoha/an7581/tests/w1700k-wireless-backend-adversarial.sh
)

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT HUP INT TERM

for file in "${files[@]}"; do
	git diff --no-index --src-prefix=a/ --dst-prefix=b/ -- \
		"$base/$file" "$candidate/$file" >>"$tmp" || [ "$?" -eq 1 ]
done

sed \
	-e "s#a$base/#a/#g" \
	-e "s#b$candidate/#b/#g" \
	"$tmp" >"$output"

git -C "$base" apply --check "$output"
sha256sum "$output"
