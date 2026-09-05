#!/usr/bin/env bash
set -euo pipefail

LOWER='/home/captain/w1700k-openwrt-build/v685-release-73a8983-20260901/build-a-source'
UPPER='/home/captain/w1700k-openwrt-build/v686-release-73a8983-20260901/build-a-upper'
WORK='/home/captain/w1700k-openwrt-build/v686-release-73a8983-20260901/build-a-work'
SOURCE='/home/captain/w1700k-openwrt-build/v686-release-73a8983-20260901/build-a-source'
EVIDENCE='/home/captain/w1700k-openwrt-build/v687-release-73a8983-20260901/build-a-evidence'
EXPECTED_HEAD='73a8983e15f78c9d3f4102da074d8d484603a4d0'
EXPECTED_LUCI_HEAD='32ff41fc22271205fa245bcc6b2992603a91d675'
MODE="${1:---status}"

case "$MODE" in
	--status|--build|--clean-build|--resume-build) ;;
	*) echo "usage: $0 [--status|--build|--clean-build|--resume-build]" >&2; exit 2 ;;
esac

[ "$(id -u)" -eq 0 ] || { echo 'must run as root' >&2; exit 3; }
for path in "$LOWER" "$UPPER" "$WORK" "$SOURCE" "$EVIDENCE"; do
	[ -d "$path" ] || { echo "missing build path: $path" >&2; exit 4; }
done
[ ! -L "$SOURCE" ] || { echo 'merged source path is a symlink' >&2; exit 5; }

if ! mountpoint -q "$SOURCE"; then
	mount -t overlay overlay \
		-o "lowerdir=$LOWER,upperdir=$UPPER,workdir=$WORK" \
		"$SOURCE"
fi

mount_source="$(findmnt -rn -o SOURCE -T "$SOURCE")"
mount_type="$(findmnt -rn -o FSTYPE -T "$SOURCE")"
[ "$mount_source" = 'overlay' ] || { echo "unexpected mount source: $mount_source" >&2; exit 6; }
[ "$mount_type" = 'overlay' ] || { echo "unexpected mount type: $mount_type" >&2; exit 7; }

BUILD_ENV=(
	HOME=/home/captain
	USER=captain
	LOGNAME=captain
	SHELL=/bin/bash
	PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
	LANG=C
	LC_ALL=C
	TZ=UTC
	TMPDIR=/tmp
)

run_as_builder() {
	runuser -u captain -- env -i "${BUILD_ENV[@]}" "$@"
}

root_head="$(run_as_builder git -C "$SOURCE" rev-parse HEAD)"
luci_head="$(run_as_builder git -C "$SOURCE/feeds/luci" rev-parse HEAD)"
[ "$root_head" = "$EXPECTED_HEAD" ] || { echo "unexpected root HEAD: $root_head" >&2; exit 8; }
[ "$luci_head" = "$EXPECTED_LUCI_HEAD" ] || { echo "unexpected LuCI HEAD: $luci_head" >&2; exit 9; }
[ -f "$SOURCE/.config" ] || { echo 'missing .config' >&2; exit 10; }

run_as_builder git -C "$SOURCE" diff --check
run_as_builder git -C "$SOURCE/feeds/luci" diff --check

echo "mode=$MODE"
echo "source=$SOURCE"
echo "mount_source=$mount_source"
echo "mount_type=$mount_type"
echo "root_head=$root_head"
echo "luci_head=$luci_head"
echo "config_sha256=$(sha256sum "$SOURCE/.config" | awk '{print $1}')"
echo 'root_status_begin'
run_as_builder git -C "$SOURCE" status --short
echo 'root_status_end'
echo 'luci_status_begin'
run_as_builder git -C "$SOURCE/feeds/luci" status --short
echo 'luci_status_end'

[ "$MODE" != '--status' ] || { echo 'result=STATUS_PASS'; exit 0; }

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
log_prefix="$EVIDENCE/$timestamp"
result_file="$log_prefix-result.txt"
result_written=0
build_pid=''

write_failure_result() {
	status="$?"
	trap - EXIT HUP INT TERM
	if [ -n "$build_pid" ] && kill -0 "$build_pid" 2>/dev/null; then
		kill -TERM -- "-$build_pid" 2>/dev/null || true
		wait "$build_pid" 2>/dev/null || true
	fi
	if [ "$result_written" -eq 0 ]; then
		{
			echo "timestamp_utc=$timestamp"
			echo "mode=$MODE"
			echo "exit_status=$status"
			echo 'result=BUILD_FAIL'
		} >"$result_file"
	fi
	exit "$status"
}
trap write_failure_result EXIT HUP INT TERM

jobs="${W1700K_BUILD_JOBS:-$(nproc)}"
if [ "$jobs" -gt 16 ]; then
	jobs=16
fi

{
	echo "timestamp_utc=$timestamp"
	echo "source=$SOURCE"
	echo "root_head=$root_head"
	echo "luci_head=$luci_head"
	echo "jobs=$jobs"
	echo "uname=$(uname -a)"
	echo "wsl_release=$(cat /proc/sys/kernel/osrelease)"
	echo "config_sha256_before=$(sha256sum "$SOURCE/.config" | awk '{print $1}')"
	df -B1 "$SOURCE"
} >"$log_prefix-environment.txt"

run_as_builder git -C "$SOURCE" status --short >"$log_prefix-root-status-before.txt"
run_as_builder git -C "$SOURCE/feeds/luci" status --short >"$log_prefix-luci-status-before.txt"
run_as_builder git -C "$SOURCE" diff --binary >"$log_prefix-root.patch"
run_as_builder git -C "$SOURCE/feeds/luci" diff --binary >"$log_prefix-luci.patch"

echo "BUILD_TIMESTAMP=$timestamp"
echo "BUILD_JOBS=$jobs"

if [ "$MODE" = '--clean-build' ]; then
	echo 'Removing inherited generated build state...'
	for generated in build_dir staging_dir tmp logs bin; do
		generated_path="$SOURCE/$generated"
		[ ! -L "$generated_path" ] || {
			echo "generated path is a symlink: $generated_path" >&2
			exit 12
		}
		if [ -e "$generated_path" ]; then
			[ "$(realpath -m -- "$generated_path")" = "$generated_path" ] || {
				echo "generated path mismatch: $generated_path" >&2
				exit 13
			}
			if findmnt -rn -M "$generated_path" >/dev/null 2>&1; then
				echo "generated path is a mount point: $generated_path" >&2
				exit 14
			fi
			echo "PURGE_GENERATED=$generated_path" | tee -a "$log_prefix-dirclean.log"
			rm -rf --one-file-system -- "$generated_path"
		fi
		[ ! -e "$generated_path" ] || {
			echo "generated path remains: $generated_path" >&2
			exit 15
		}
	done
fi

echo 'Running make defconfig...'
run_as_builder make -C "$SOURCE" defconfig 2>&1 | tee "$log_prefix-defconfig.log"

if [ "$MODE" = '--build' ]; then
	clean_targets=(
		'package/kernel/mt76/clean'
		'package/kernel/mac80211/clean'
		'package/network/utils/iwinfo/clean'
		'package/network/config/wifi-scripts/clean'
		'package/network/services/hostapd/clean'
		'package/base-files/clean'
		'package/feeds/luci/luci-base/clean'
		'package/feeds/luci/luci-mod-network/clean'
		'package/feeds/luci/luci-app-w1700k-npu/clean'
	)

	echo 'Invalidating touched package outputs...'
	for target in "${clean_targets[@]}"; do
		echo "CLEAN_TARGET=$target"
		run_as_builder make -C "$SOURCE" -j1 "$target" V=s 2>&1 | tee -a "$log_prefix-clean.log"
	done
fi

echo 'Starting full V6.87 corrective engineering/provenance build...'
setsid runuser -u captain -- env -i "${BUILD_ENV[@]}" \
	make -C "$SOURCE" -j"$jobs" V=s \
	>"$log_prefix-build.log" 2>&1 &
build_pid="$!"
while kill -0 "$build_pid" 2>/dev/null; do
	sleep 30
	if kill -0 "$build_pid" 2>/dev/null; then
		echo "BUILD_HEARTBEAT=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
		tail -n 1 "$log_prefix-build.log" | cut -c1-240
	fi
done
set +e
wait "$build_pid"
build_status="$?"
set -e
build_pid=''
if [ "$build_status" -ne 0 ]; then
	echo "full build failed with status $build_status" >&2
	tail -n 80 "$log_prefix-build.log" >&2
	exit "$build_status"
fi

run_as_builder git -C "$SOURCE" status --short >"$log_prefix-root-status-after.txt"
run_as_builder git -C "$SOURCE/feeds/luci" status --short >"$log_prefix-luci-status-after.txt"
sha256sum "$SOURCE/.config" >"$log_prefix-config.sha256"
find "$SOURCE/bin/targets/airoha/an7581" -maxdepth 1 -type f -printf '%f\n' | sort >"$log_prefix-target-files.txt"
find "$SOURCE/bin/targets/airoha/an7581" -maxdepth 1 -type f -print0 | sort -z | xargs -0 -r sha256sum >"$log_prefix-target-sha256.txt"

artifact="$SOURCE/bin/targets/airoha/an7581/openwrt-airoha-an7581-gemtek_w1700k-ubi-squashfs-sysupgrade.itb"
[ -f "$artifact" ] || { echo "missing exact W1700K UBI sysupgrade ITB: $artifact" >&2; exit 11; }
artifact_count=1

dumpimage="$SOURCE/staging_dir/host/bin/dumpimage"
if [ -x "$dumpimage" ]; then
	"$dumpimage" -l "$artifact" >"$log_prefix-dumpimage.txt" 2>&1
fi

{
	echo "timestamp_utc=$timestamp"
	echo "artifact_count=$artifact_count"
	echo "config_sha256_after=$(sha256sum "$SOURCE/.config" | awk '{print $1}')"
	df -B1 "$SOURCE"
	echo 'result=BUILD_PASS'
} >"$result_file"
result_written=1
trap - EXIT HUP INT TERM

echo "EVIDENCE_PREFIX=$log_prefix"
echo "ARTIFACT_COUNT=$artifact_count"
echo 'result=BUILD_PASS'
