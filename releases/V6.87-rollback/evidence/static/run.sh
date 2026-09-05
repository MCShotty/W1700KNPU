#!/usr/bin/env bash
set -euo pipefail

source_root="${1:?usage: $0 SOURCE_ROOT}"
workspace_root=/mnt/c/Users/captain/Documents/Codex/2026-06-12/i-need-help-wiping-the-nand

node "$workspace_root/work/tests/v687-hostapd-mlo-country-20260901/mlo-country-alias.test.js" \
	"$source_root"
bash "$workspace_root/work/tests/v686-build-a-focused-20260901/run.sh" \
	"$source_root"
sh "$source_root/target/linux/airoha/an7581/tests/w1700k-wireless-backend-adversarial.sh"
sh -n "$workspace_root/tools/w1700k_unattended_synthetic_test.sh"
shellcheck --severity=warning --shell=sh \
	"$workspace_root/tools/w1700k_unattended_synthetic_test.sh"
git -C "$source_root" diff --check

echo PASS_V687_HOSTAPD_MLO_COUNTRY_GATE
