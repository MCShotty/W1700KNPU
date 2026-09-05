#!/usr/bin/env bash
set -euo pipefail

SOURCE="${1:-/home/captain/w1700k-openwrt-build/v686-release-73a8983-20260901/build-a-source}"
OUT="${2:?usage: $0 SOURCE OUT [BUILD_LOG]}"
BUILD_LOG="${3:-}"
TARGET="$SOURCE/bin/targets/airoha/an7581"
IMAGE="$TARGET/openwrt-airoha-an7581-gemtek_w1700k-ubi-squashfs-sysupgrade.itb"
MANIFEST="$TARGET/openwrt-airoha-an7581-gemtek_w1700k-ubi.manifest"
TARGET_SUMS="$TARGET/sha256sums"
PROFILES="$TARGET/profiles.json"
EXPECTED_HEAD='73a8983e15f78c9d3f4102da074d8d484603a4d0'
EXPECTED_LUCI_HEAD='32ff41fc22271205fa245bcc6b2992603a91d675'
MAX_FIT_BYTES=20697088
MIN_HEADROOM=65536

fail() {
	echo "FAIL: $*" >&2
	exit 1
}

require_file() {
	[ -f "$ROOT/$1" ] || fail "rootfs is missing /$1"
}

require_text() {
	path="$1"
	text="$2"
	grep -Fq -- "$text" "$ROOT/$path" || fail "/$path is missing marker: $text"
}

require_pattern() {
	path="$1"
	pattern="$2"
	grep -Eq -- "$pattern" "$ROOT/$path" || fail "/$path is missing expected pattern: $pattern"
}

require_package() {
	grep -Eq "^$1[[:space:]]+-[[:space:]]+" "$MANIFEST" || fail "manifest is missing package $1"
}

[ -d "$SOURCE" ] || fail "source is missing: $SOURCE"
[ ! -e "$OUT" ] || fail "output already exists: $OUT"
[ -s "$IMAGE" ] || fail "sysupgrade image is missing: $IMAGE"
[ -s "$MANIFEST" ] || fail "package manifest is missing: $MANIFEST"
[ -s "$TARGET_SUMS" ] || fail "target sha256sums is missing: $TARGET_SUMS"
[ -s "$PROFILES" ] || fail "target profiles.json is missing: $PROFILES"
[ "$(git -C "$SOURCE" rev-parse HEAD)" = "$EXPECTED_HEAD" ] || fail 'unexpected source HEAD'
[ "$(git -C "$SOURCE/feeds/luci" rev-parse HEAD)" = "$EXPECTED_LUCI_HEAD" ] || fail 'unexpected LuCI HEAD'
git -C "$SOURCE" diff --check
git -C "$SOURCE/feeds/luci" diff --check

DUMPIMAGE="$SOURCE/staging_dir/host/bin/dumpimage"
UNSQUASHFS="$SOURCE/staging_dir/host/bin/unsquashfs"
DTC="$SOURCE/staging_dir/host/bin/dtc"
[ -x "$DUMPIMAGE" ] || DUMPIMAGE="$(command -v dumpimage)"
[ -x "$UNSQUASHFS" ] || UNSQUASHFS="$(command -v unsquashfs)"
[ -x "$DTC" ] || DTC="$(command -v dtc)"
[ -x "$DUMPIMAGE" ] || fail 'dumpimage is unavailable'
[ -x "$UNSQUASHFS" ] || fail 'unsquashfs is unavailable'
[ -x "$DTC" ] || fail 'dtc is unavailable'
command -v python3 >/dev/null || fail 'python3 is unavailable'

tmpdir="$(mktemp -d /tmp/w1700k-v687-verify.XXXXXX)"
trap 'rm -rf -- "$tmpdir"' EXIT HUP INT TERM
ROOT="$tmpdir/rootfs"
mkdir -p "$OUT"

image_bytes="$(stat -c %s "$IMAGE")"
[ "$image_bytes" -le "$MAX_FIT_BYTES" ] || fail "image exceeds fit volume: $image_bytes"
headroom=$((MAX_FIT_BYTES - image_bytes))
[ "$headroom" -ge "$MIN_HEADROOM" ] || fail "image leaves only $headroom bytes of fit headroom"
image_name="$(basename "$IMAGE")"
image_sha256="$(sha256sum "$IMAGE" | awk '{print $1}')"

(
	cd "$TARGET"
	sha256sum --check sha256sums
) >"$OUT/TARGET-SHA256-CHECK.txt"

python3 - "$PROFILES" "$image_name" "$image_sha256" "$image_bytes" \
	>"$OUT/PROFILE-CHECK.txt" <<'PY'
import json
import sys

path, image_name, expected_sha256, expected_size = sys.argv[1:]
expected_size = int(expected_size)

with open(path, "r", encoding="utf-8") as handle:
    data = json.load(handle)

profiles = data.get("profiles")
if not isinstance(profiles, dict) or set(profiles) != {"gemtek_w1700k-ubi"}:
    raise SystemExit("unexpected target profile set")

profile = profiles["gemtek_w1700k-ubi"]
if profile.get("supported_devices") != ["gemtek,w1700k-ubi"]:
    raise SystemExit("unexpected supported_devices")

images = [entry for entry in profile.get("images", [])
          if entry.get("name") == image_name]
if len(images) != 1:
    raise SystemExit("sysupgrade image is not uniquely represented in profiles.json")

image = images[0]
if image.get("filesystem") != "squashfs" or image.get("type") != "sysupgrade":
    raise SystemExit("unexpected image filesystem or type")
if image.get("sha256") != expected_sha256:
    raise SystemExit("profiles.json image hash mismatch")
if image.get("size") != expected_size:
    raise SystemExit("profiles.json image size mismatch")

print("profile=gemtek_w1700k-ubi")
print("supported_device=gemtek,w1700k-ubi")
print(f"image={image_name}")
print(f"sha256={expected_sha256}")
print(f"size={expected_size}")
print("result=PASS")
PY

"$DUMPIMAGE" -l "$IMAGE" >"$OUT/FIT-METADATA.txt"
grep -q 'Image 0 (kernel-1)' "$OUT/FIT-METADATA.txt" || fail 'FIT kernel node is missing'
grep -q 'Image 1 (fdt-1)' "$OUT/FIT-METADATA.txt" || fail 'FIT FDT node is missing'
grep -q 'Image 2 (rootfs-1)' "$OUT/FIT-METADATA.txt" || fail 'FIT rootfs node is missing'
grep -Eq 'w1700k-ubi.*device tree blob' "$OUT/FIT-METADATA.txt" || fail 'FIT has the wrong W1700K DTB'
grep -q "Default Configuration: 'config-1'" "$OUT/FIT-METADATA.txt" || fail 'FIT default configuration is wrong'

"$DUMPIMAGE" -T flat_dt -p 1 -o "$tmpdir/w1700k.dtb" "$IMAGE" >/dev/null
"$DUMPIMAGE" -T flat_dt -p 2 -o "$tmpdir/rootfs.squashfs" "$IMAGE" >/dev/null
"$DTC" -I dtb -O dts -o "$OUT/EMBEDDED-W1700K.dts" "$tmpdir/w1700k.dtb" 2>"$OUT/DTC-DIAGNOSTICS.txt"
grep -Eq 'model = ".*W1700K' "$OUT/EMBEDDED-W1700K.dts" || fail 'embedded DTB has the wrong model'
grep -q 'compatible = "gemtek,w1700k-ubi"' "$OUT/EMBEDDED-W1700K.dts" || fail 'embedded DTB has the wrong compatible'

"$UNSQUASHFS" -no-progress -no-exit-code -d "$ROOT" "$tmpdir/rootfs.squashfs" \
	>"$OUT/UNSQUASHFS.txt" 2>&1

for path in \
	lib/netifd/wireless.uc \
	lib/netifd/wireless/mac80211.sh \
	usr/share/hostap/hostapd.uc \
	usr/share/ucode/wifi/hostapd.uc \
	usr/sbin/w1700k-radio-sanity \
	usr/sbin/w1700k-wireless-validate \
	usr/sbin/w1700k-wlan-npu-mode \
	www/luci-static/resources/network.js \
	www/luci-static/resources/view/network/wireless.js \
	www/luci-static/resources/view/system/w1700k-npu.js \
	lib/firmware/airoha/en7581_MT7996_npu_data.bin \
	lib/firmware/airoha/en7581_MT7996_npu_rv32.bin; do
	require_file "$path"
done

for path in \
	lib/firmware/airoha/en7581_npu_data.bin \
	lib/firmware/airoha/en7581_npu_rv32.bin; do
	[ ! -e "$ROOT/$path" ] || fail "rootfs contains generic MT7992 firmware /$path"
done

require_text lib/netifd/wireless.uc 'return ubus.call({' 
require_text lib/netifd/wireless.uc 'Reject MLO interface'
require_text usr/share/hostap/hostapd.uc 'function format_exception(e)'
require_text usr/share/ucode/wifi/hostapd.uc 'country_code ?? config.country'
require_text usr/share/ucode/wifi/hostapd.uc 'must use EHT20 for a reliable 2.4GHz MLO link'
require_text lib/netifd/wireless/mac80211.sh 'if (!w1700kRadioMapActive) {'
require_text usr/sbin/w1700k-radio-sanity 'repair_sta_network()'
require_text usr/sbin/w1700k-radio-sanity 'mandatory 20/40 coexistence fallback cannot update this MLD safely'
require_text usr/sbin/w1700k-wireless-validate 'STA must bind to exactly one dedicated client network'
require_text usr/sbin/w1700k-wireless-validate 'MLO requires EHT20 on 2.4GHz radio'
require_text usr/sbin/w1700k-wlan-npu-mode 'w1700k_mlo_tx_policy) echo 0'
require_text www/luci-static/resources/view/network/wireless.js 'function w1700kMloSafeRadioState'
require_text www/luci-static/resources/view/network/wireless.js 'this.apChannelsByRadio'
require_text www/luci-static/resources/view/network/wireless.js 'must use EHT20 for reliable MLO operation'
require_pattern www/luci-static/resources/network.js "this\\.ubus\\('dev',[[:space:]]*'iwinfo',[[:space:]]*'frequency'\\)"
require_text www/luci-static/resources/view/system/w1700k-npu.js 'deprecated alias (uses upstream)'

for package in \
	airoha-en7581-mt7996-npu-firmware-w1700k \
	kmod-mt7996e \
	kmod-mt7996-firmware \
	wpad-mbedtls \
	luci-ssl \
	luci-app-sqm \
	sqm-scripts \
	adblock \
	luci-app-adblock \
	softethervpn5-server \
	luci-app-softether \
	luci-app-w1700k-npu; do
	require_package "$package"
done

if find "$ROOT" -type f \( \
	-name 'npu.ko' -o \
	-name 'hostadpt.ko' -o \
	-name 'mt7990*.ko' -o \
	-name 'mt_wifi*.ko' -o \
	-name 'mtk_hwifi.ko' -o \
	-name 'mtk_pci.ko' -o \
	-name 'npu_bridge_cmd' -o \
	-name 'wifimgr' \) -print -quit | grep -q .; then
	fail 'rootfs contains a forbidden stock WiFi/NPU binary'
fi

mt76_module="$(find "$ROOT/lib/modules" -type f -name mt76.ko -print -quit)"
mt7996_module="$(find "$ROOT/lib/modules" -type f -name mt7996e.ko -print -quit)"
[ -n "$mt76_module" ] || fail 'mt76.ko is missing'
[ -n "$mt7996_module" ] || fail 'mt7996e.ko is missing'
grep -aq 'w1700k_mlo_tx_policy' "$mt7996_module" || fail 'mt7996e lacks MLO policy parameter'

for patch in \
	package/kernel/mac80211/patches/subsys/999-wifi-mac80211-use-active-preferred-link-for-ancillary-mlo.patch \
	package/kernel/mt76/patches/9999zzzzzzzzzzzz51a-mt76-complete-npu-provider-fallback-abi.patch \
	package/kernel/mt76/patches/9999zzzzzzzzzzzz52-mt7996-default-upstream-mlo-tx-policy.patch \
	package/network/utils/iwinfo/patches/103-nl80211-bounded-temp-scan-lifecycle.patch; do
	[ -s "$SOURCE/$patch" ] || fail "source patch is missing: $patch"
done

if [ -n "$BUILD_LOG" ]; then
	[ -s "$BUILD_LOG" ] || fail "build log is missing: $BUILD_LOG"
	BUILD_RESULT="${BUILD_LOG%-build.log}-result.txt"
	[ "$BUILD_RESULT" != "$BUILD_LOG" ] || fail 'build log name does not end in -build.log'
	[ -s "$BUILD_RESULT" ] || fail "build result receipt is missing: $BUILD_RESULT"
	[ "$(grep -c '^result=BUILD_PASS$' "$BUILD_RESULT")" -eq 1 ] || \
		fail 'build result receipt does not record exactly one BUILD_PASS'
	if grep -Eq '^result=BUILD_FAIL$|^exit_status=[1-9][0-9]*$' "$BUILD_RESULT"; then
		fail 'build result receipt records a failed build'
	fi
	cp "$BUILD_RESULT" "$OUT/BUILD-RESULT.txt"
fi

old_source='/home/captain/w1700k-openwrt-build/v685-release-73a8983-20260901/build-a-source'
if rg -l --hidden --text --no-messages "$old_source" \
	"$SOURCE/build_dir" "$SOURCE/staging_dir" "$SOURCE/tmp" | head -n 1 | grep -q .; then
	fail 'generated build state still references the V6.85 source path'
fi

find "$ROOT" -type f -printf '/%P\n' | LC_ALL=C sort >"$OUT/ROOTFS-FILES.txt"
sha256sum \
	"$SOURCE/package/kernel/mac80211/patches/subsys/999-wifi-mac80211-use-active-preferred-link-for-ancillary-mlo.patch" \
	"$SOURCE/package/kernel/mt76/patches/9999zzzzzzzzzzzz51a-mt76-complete-npu-provider-fallback-abi.patch" \
	"$SOURCE/package/kernel/mt76/patches/9999zzzzzzzzzzzz52-mt7996-default-upstream-mlo-tx-policy.patch" \
	"$SOURCE/package/network/utils/iwinfo/patches/103-nl80211-bounded-temp-scan-lifecycle.patch" \
	>"$OUT/PATCH-SHA256.txt"

{
	echo '# W1700K V6.87 Corrective Engineering Verification'
	echo
	echo "- Result: PASS"
	echo "- Image: $IMAGE"
	echo "- Image SHA256: $image_sha256"
	echo "- Image bytes: $image_bytes"
	echo "- FIT volume headroom: $headroom"
	echo "- Source HEAD: $EXPECTED_HEAD"
	echo "- LuCI HEAD: $EXPECTED_LUCI_HEAD"
	echo "- Rootfs files: $(wc -l <"$OUT/ROOTFS-FILES.txt" | tr -d ' ')"
	echo "- Packages: $(wc -l <"$MANIFEST" | tr -d ' ')"
	echo '- Required WiFi, MLO, NPU, LuCI, SQM, adblock, and SoftEther assets: PASS'
	echo '- Target sha256sums and profiles.json binding: PASS'
	echo '- Forbidden stock WiFi/NPU binaries absent: PASS'
	echo '- Corrective source markers embedded in rootfs: PASS'
	echo '- Relocated V6.85 generated-path references absent: PASS'
	echo '- V6.87 country alias and 2.4GHz MLO coexistence safeguards embedded: PASS'
	echo '- Status: engineering verified; eligible for normal sysupgrade compatibility and live validation.'
} >"$OUT/REPORT.md"

(
	cd "$OUT"
	find . -maxdepth 1 -type f ! -name SHA256SUMS.txt -printf '%P\0' | sort -z | xargs -0 -r sha256sum
) >"$OUT/SHA256SUMS.txt"

echo "REPORT=$OUT/REPORT.md"
echo "IMAGE_SHA256=$image_sha256"
echo 'result=PASS'
