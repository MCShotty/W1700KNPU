#!/bin/sh

set -u

hostapd_target=/usr/share/ucode/wifi/hostapd.uc
hostapd_patch=/tmp/w1700k-v687-hostapd.uc
validator_target=/usr/sbin/w1700k-wireless-validate
validator_patch=/tmp/w1700k-v687-wireless-validate
runner=/tmp/w1700k-v687-synthetic-test.sh
expected_hostapd_patch_sha="${1:?usage: $0 HOSTAPD_PATCH_SHA HOSTAPD_ORIGINAL_SHA VALIDATOR_PATCH_SHA VALIDATOR_ORIGINAL_SHA}"
expected_hostapd_original_sha="${2:?usage: $0 HOSTAPD_PATCH_SHA HOSTAPD_ORIGINAL_SHA VALIDATOR_PATCH_SHA VALIDATOR_ORIGINAL_SHA}"
expected_validator_patch_sha="${3:?usage: $0 HOSTAPD_PATCH_SHA HOSTAPD_ORIGINAL_SHA VALIDATOR_PATCH_SHA VALIDATOR_ORIGINAL_SHA}"
expected_validator_original_sha="${4:?usage: $0 HOSTAPD_PATCH_SHA HOSTAPD_ORIGINAL_SHA VALIDATOR_PATCH_SHA VALIDATOR_ORIGINAL_SHA}"
hostapd_mounted=0
validator_mounted=0

cleanup() {
	if [ "$validator_mounted" -eq 1 ]; then
		umount "$validator_target" || {
			echo "FAIL: could not unmount temporary wireless validator overlay" >&2
			return 1
		}
		validator_mounted=0
	fi
	if [ "$hostapd_mounted" -eq 1 ]; then
		umount "$hostapd_target" || {
			echo "FAIL: could not unmount temporary hostapd.uc overlay" >&2
			return 1
		}
		hostapd_mounted=0
	fi
}

trap 'cleanup' EXIT HUP INT TERM

[ "$(cat /tmp/sysinfo/board_name 2>/dev/null)" = 'gemtek,w1700k-ubi' ] || {
	echo 'FAIL: refusing live hotfix test on a different board' >&2
	exit 64
}
[ "$(sha256sum "$hostapd_target" | awk '{ print $1 }')" = "$expected_hostapd_original_sha" ] || {
	echo 'FAIL: installed hostapd.uc does not match the expected V6.86 baseline' >&2
	exit 65
}
[ "$(sha256sum "$hostapd_patch" | awk '{ print $1 }')" = "$expected_hostapd_patch_sha" ] || {
	echo 'FAIL: uploaded hostapd.uc hash mismatch' >&2
	exit 66
}
[ "$(sha256sum "$validator_target" | awk '{ print $1 }')" = "$expected_validator_original_sha" ] || {
	echo 'FAIL: installed wireless validator does not match the expected V6.86 baseline' >&2
	exit 67
}
[ "$(sha256sum "$validator_patch" | awk '{ print $1 }')" = "$expected_validator_patch_sha" ] || {
	echo 'FAIL: uploaded wireless validator hash mismatch' >&2
	exit 68
}
chmod 0755 "$validator_patch" || exit 69
[ -x "$validator_patch" ] || exit 69
sh -n "$runner" || exit 67
sh -n "$validator_patch" || exit 69

mount -o bind "$hostapd_patch" "$hostapd_target" || exit 70
hostapd_mounted=1
mount -o bind "$validator_patch" "$validator_target" || exit 71
validator_mounted=1
[ "$(sha256sum "$hostapd_target" | awk '{ print $1 }')" = "$expected_hostapd_patch_sha" ] || exit 72
[ "$(sha256sum "$validator_target" | awk '{ print $1 }')" = "$expected_validator_patch_sha" ] || exit 73

EXPECTED_NPU_MODE=0 sh "$runner"
test_rc=$?

cleanup || exit 74
trap - EXIT HUP INT TERM
[ "$(sha256sum "$hostapd_target" | awk '{ print $1 }')" = "$expected_hostapd_original_sha" ] || {
	echo 'FAIL: hostapd.uc baseline did not reappear after unmount' >&2
	exit 75
}
[ "$(sha256sum "$validator_target" | awk '{ print $1 }')" = "$expected_validator_original_sha" ] || {
	echo 'FAIL: wireless validator baseline did not reappear after unmount' >&2
	exit 76
}

echo "LIVE_HOTFIX_TEST_RC=$test_rc"
exit "$test_rc"
