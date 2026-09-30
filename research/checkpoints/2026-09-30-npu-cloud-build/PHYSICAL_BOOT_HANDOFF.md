# W1700K physical boot handoff

30 September 2026

The exact cloud-built candidate passes offline validation. No new hardware test has run. Confirm the current device and recovery setup before agreeing one bounded initial boot check. This checklist does not authorize booting or flashing.

## Candidate and rollback

Delivered candidate filename follows. Verify its full SHA256; the original OpenWrt basename is retained in the repository evidence.

`W1700K-NPU-candidate-20260930-sysupgrade.itb`

Candidate: 26,932,042 bytes; gemtek,w1700k-ubi; image compatibility 2.0. It reuses kernel 6.18.52 and revision r36536-merged-288d79449f from the prior image. Those labels cannot identify this update; require FIT/hash and installed provider-module readback.

`SHA256 6abd366c08b5ad1609c4333cb2c1a9a52a212522a9be0951f71d137f82615c0d`

Packaged airoha_npu.ko SHA256 follows. The other three mt76 modules intentionally match the previous unchanged source.

`29a25d03b19e8927a230d5f82369325d26af064dd73b066761a9c35b52e6eed9`

Daybreak21 R1 rollback: 20,439,877 bytes. This historical baseline has WLAN NPU compiled out. The protected cloud copy in releases/Daybreak21-R1 was rehashed successfully. Current user-side availability and a usable restore path remain unverified.

`SHA256 0788f405337ceb030d873463bbf278497dcd9b86e8f75a1a3f57fd318eda195f`

## What passed and what remains open

- The full OpenWrt world build, FIT integrity, board metadata, configured NPU memory reservations, packaged firmware, 218 packages and all 78 module ABI checks pass.

- The actual target provider module builds; six selected Ghidra decompilations pass. All 17 retained allocated file-backed provider sections match the compiled module to the exact image. Only expected .note.gnu.build-id metadata is removed.

- All 1,951 numeric rootfs ownership entries are 0/0. Ten RV32 objects compile; they are not a bootable replacement. The image still uses the inspected legacy NPU firmware.

- Final host replay passes 273 loader cases, 165 added load cases, 3 controls, 9 mutants, 6,174 retry cases and 44 V2 cases; eight builder tests also pass.

Full NPU parity remains incomplete. Physical engine ownership, containment, drain, teardown and rearm are unproven; native loader, production caller and postgate integration remain unfinished. Provider attachment and memory geometry do not establish those properties.

## Confirm these details first

- [ ] Which physical W1700K is the target, and what are its current board identifier, compatibility version and MTD/UBI layout? Bind its wired management identity to its serial console; do not reuse a historical IP address or COM port.

- [ ] Can you access its serial console and bootloader now, and restore a locally available, hash-verified R1 image? Confirm current private settings, overlay, factory/calibration and environment backups are off-device and readable. Keep backups local and private.

- [ ] Once those checks pass, approve or decline the exact device, image hash and proposed method, including write scope, settings preservation, outage and recovery plan. Readiness alone is not boot or flash authorization.

## Before any physical action

- [ ] Independently compare the current board and partition/UBI layout with the image. Recheck the copied candidate hash, and require the actual router to accept sysupgrade -T without force. Passing that test alone does not prove the layout or recovery path is safe.

- [ ] Prefer a documented, applicable nonpersistent staged boot if a suitable artifact exists. This build has CONFIG_TARGET_ROOTFS_INITRAMFS unset and no initramfs artifact. The supplied candidate is a sysupgrade .itb; do not treat it as RAM-boot input or use the sibling chainload-uboot artifact.

- [ ] A previous image used normal settings-preserving sysupgrade without force after board binding, serial capture and sysupgrade -T. That is historical evidence only. If flash is proposed now, obtain explicit bounded authorization for this exact image and current device before writing.

- [ ] Record current protected-partition and environment/factory-volume hashes, selected configuration hashes, installed module hashes and baseline logs. Verify backups and rollback first; preserve bootloader, chainloader, calibration and private data. Start continuous serial capture before any authorized boot or flash.

## Stop conditions

- STOP for any board, layout, hash or compatibility mismatch, a failed sysupgrade -T, or unavailable serial/bootloader access, private backups or usable rollback.

- Image metadata includes a standard device 1.0 versus image 2.0 mismatch message about partition/BMT and chainloader changes. It is not permission to force, wipe, repartition or replace a chainloader. Any mismatch needs separate recovery and layout planning.

- STOP for an unexpected write target, changed settings policy, new warning requiring a destructive workaround, panic/oops, reboot loop or lost management. Preserve logs and use only the separately agreed recovery plan; do not improvise reset, erase or recovery stress.

## Initial evidence after an authorized boot

- Capture complete serial boot and timestamped kernel/system logs, board/layout, kernel identity and monotonic uptime. Check wired management only on the verified connection. Observe at least two minutes of idle operation and retain warnings.

- If flashed, hash exactly the candidate-length FIT readback and compare installed NPU/mt76 modules with the image. Compare protected bytes and selected settings with the preflight record. Record provider attachment, NPU reservations and available read-only status.

- Recheck the historical radio1 channel 161/EHT80 rejection under country SA without assuming it persists. Record current validation and interfaces; do not change radio power, regulatory/channel settings or the computer's Wi-Fi association. Do not run reset, drain, teardown, rearm or traffic stress.

Conclude only whether this initial boot and wired management check passed. Keep Wi-Fi/client traffic, physical recovery and full NPU acceptance open until separately implemented, authorized and tested.

## Evidence sources

- `research/checkpoints/2026-09-30-npu-cloud-build/REPORT.md`

- `.local/merge-nonoc-20260923/cloud-image-verified/result.json`

- `.local/merge-nonoc-20260923/cloud-image-verified/code-and-ownership.json`

- `research/checkpoints/2026-09-23-nonoc-flash/REPORT.md` and `summary.json`

- `releases/Daybreak21-R1/REPORT.md`

- Delivered candidate filename: `W1700K-NPU-candidate-20260930-sysupgrade.itb`

- Original candidate file: `.build/merged-openwrt/bin/targets/airoha/an7581/openwrt-airoha-an7581-gemtek_w1700k-ubi-squashfs-sysupgrade.itb`

- Verified cloud rollback file: `releases/Daybreak21-R1/openwrt-airoha-an7581-gemtek_w1700k-ubi-squashfs-sysupgrade.itb`

- Build setting checked directly: `.build/merged-openwrt/.config`; no initramfs artifact in the target output directory.
