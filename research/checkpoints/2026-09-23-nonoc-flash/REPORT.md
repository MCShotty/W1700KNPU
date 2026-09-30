# Merged Image Physical Boot Check

Completed 2026-09-24 local time (UTC evidence captured 2026-09-23).
Result: **basic boot and wired management pass; Wi-Fi remains blocked by a
pre-existing retained configuration error.** This is not full NPU acceptance.

## Flashed Image

- Source commit: `18eae4c7269bc753d8dd5e7bc47078593edfc171`.
- Revision: `r36536-merged-288d79449f`; kernel: `6.18.52`.
- Actual board and serial boot model: Gemtek W1700K, `gemtek,w1700k-ubi`.
- Image: 26,932,042 bytes, SHA256
  `132a35c746e008345032d1c862ea1ace1ef7a27d87a3fd363b8225045554e670`.
- The first 26,932,042 bytes read back from the flashed `fit` volume match that
  SHA256 exactly. Four installed NPU/mt76 module hashes match the inspected image.

The user explicitly authorized this flash. Pinned SSH was bound to the wired
interface. COM3 at 115200 baud was matched to the same router using a console
marker, then captured the upgrade and boot. The exact image passed the router's
`sysupgrade -T` check. Normal settings-preserving sysupgrade ran without force.

## Preservation

The write scope was only `fit` and `rootfs_data` inside MTD `ubi`
(`0x00700000-0x1be00000`). Protected partition ranges were unchanged:

- `vendor`: `0x00000000-0x00600000`.
- `chainloader`: `0x00600000-0x00700000`.
- `reserved_bmt`: `0x1be00000-0x20000000`.

Before/after byte hashes match for those three partitions and the `ubootenv`,
`ubootenv2`, and `factory` UBI volumes. Network, wireless, DHCP and Dropbear
configuration hashes also match. Settings, full overlay, factory and environment
backups were copied off-device and verified before writing. The verified
Daybreak21 R1 rollback image was available locally and was not needed.

Private backups and raw serial/system logs remain in ignored
`.local/flash-20260923/`; they are not included in this checkpoint.

## Observed Behavior

- New kernel/revision reachable over pinned wired SSH after reboot.
- Five wired pings answered, with no loss.
- HTTPS LuCI serves its expected unauthenticated login form (HTTP 403), without
  a server error. No authenticated browser workflow was exercised.
- NPU and MT7996 firmware initialize. Actual debugfs reports compiled NPU
  support, NPU/PPE provider attachment, HWRRO mode 1 and RX token size 32768.
- Five monotonic uptime observations span 120.93 seconds; later readback at
  478.52 seconds confirms continued operation. No unexpected reboot, kernel
  panic, oops or call trace was observed in the captured interval.
- Core board/module/memory/provider health reads succeeded; the separate
  wireless validator fails as described below. The cpufreq driver exposes
  a 500-1200 MHz policy; this is not an independent physical clock measurement.

## Limitations And Findings

The wireless validator rejects `radio1` channel 161/EHT80 for its configured
SA regulatory domain. The exact same errors are present in the pre-flash logs,
and the configuration is byte-identical. Its global validation blocks all three
radio setup attempts; no Wi-Fi virtual interfaces are active. Nothing here
establishes client association, throughput or packet offload. No country,
channel, transmit-power, Wi-Fi-association or other radio setting was changed.
See `wireless-diagnostic.json`.

The status script still hard-codes old OpenWrt-base and mt76 source hashes.
Its runtime provider fields are useful, but those provenance labels are stale.
Installed module hashes independently verify the newer image; correcting the
source labels is a follow-up, not a claim that the old driver was running.

Bootloader environment CRC and early `fw_env.config`/NVMEM warnings were
captured. They did not prevent boot, and protected environment/factory bytes
remain unchanged. Retain these warnings for investigation, not as proof of
calibration or stock parity.

The supplied legacy NPU firmware remains in use. The compiled V2 Linux client
and RV32 core do not make missing loader/caller/postgate wiring complete.
Physical drains, reset/removal/rearm, client traffic and sustained-load recovery
remain unvalidated. No recovery stress, additional flash or rollback was run.

`summary.json` contains the sanitized deterministic results. The retained Jev
claim checks are supplementary semantic evidence, not hardware authorization or
a substitute for the actual boot, readback and management checks.
