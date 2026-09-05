#!/usr/bin/env bash
set -euo pipefail

source_root=/home/captain/w1700k-openwrt-build/v687-corrective-source-20260901
upper_root=/home/captain/w1700k-openwrt-build/v686-release-73a8983-20260901/build-a-upper
merged_root=/home/captain/w1700k-openwrt-build/v686-release-73a8983-20260901/build-a-source
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
mode="${1:---sync}"

case "$mode" in
	--sync)
		mountpoint -q "$merged_root" && {
			echo "refusing to modify OverlayFS upper while $merged_root is mounted" >&2
			exit 2
		}
		;;
	--verify)
		mountpoint -q "$merged_root" || {
			echo "merged source is not mounted: $merged_root" >&2
			exit 3
		}
		;;
	*)
		echo "usage: $0 [--sync|--verify]" >&2
		exit 4
		;;
esac

cd "$source_root"
for file in "${files[@]}"; do
	if [ "$mode" = "--sync" ]; then
		cp --parents --preserve=mode,timestamps "$file" "$upper_root"
	fi
	cmp -s "$file" "$upper_root/$file"
	if [ "$mode" = "--verify" ]; then
		cmp -s "$file" "$merged_root/$file"
		sha256sum "$merged_root/$file"
	fi
done

echo "SYNC_V687_BUILD_OVERLAY_${mode#--}_PASS"
