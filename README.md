# W1700K NPU and OpenWrt Workbench

Canonical private workspace for W1700K firmware development, WiFi/MLO fixes,
and stock host-adapter/NPU reverse engineering.

## Current State

The last router-tested image is **Daybreak21 WLAN-DMA R1 (2026-09-05)**,
Linux 6.18.44, SHA256
`0788f405337ceb030d873463bbf278497dcd9b86e8f75a1a3f57fd318eda195f`.
It deliberately compiles out WLAN NPU support; Ethernet offload is separate.
Stock NPU parity is **not complete**. Synthetic radio/MLO and LuCI save checks
passed; actual-client association and throughput acceptance remain open.

Start with [current reference](docs/W1700K_STOCK_PORT_CURRENT_REFERENCE.md),
[ledger](docs/W1700K_STOCK_PORT_LEDGER.md), and
[logging session](docs/W1700K_STOCK_PORT_LOGGING_SESSION_20260625.md).

## Layout

- `firmware/`: pinned public source revisions, full cumulative OpenWrt/LuCI
  patches, untracked local overlays, and the current build configuration.
- `tools/`: reproducible workspace preparation and migration verification.
- `research/`: preserved historical patches, tests, Ghidra exports, audit
  reports, and manifests. Archived experiments are not active build inputs.
- `releases/`: selected current/rollback release material and provenance.
- `docs/migration/`: migration, privacy screening, cleanup and path records.
- `.build/`, `.local/`, `.migration/`: ignored builds, protected local data and
  temporary staging. Never commit private keys or device-specific backups.

## Build Preparation

Use WSL native ext4. The canonical local checkout is `/home/captain/W1700KNPU`.

```sh
python3 tools/prepare_build.py
cd .build/openwrt
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin make -j4
```

The preparer refuses an existing destination and verifies every migrated
changed source file. It does not flash a router. Image signing keys are not
uploaded; fresh build keys must be generated or supplied locally.
An existing imported build may instead be reused as recorded in migration docs.

Do not force old `ubi2` recipes onto current images: the latest board is
`gemtek,w1700k-ubi`, with the OpenWrt U-Boot layout and compatibility metadata.
Validate the actual device and the exact FIT/DTB/sysupgrade metadata before use.

## Preservation Rules

Private router backups, factory/calibration, bootloader dumps, signing keys and
the recovery VHD stay local. Original historical files with suspected credentials
are quarantined locally rather than uploaded. Historical paths and test outcomes
are retained as evidence, not silently rewritten into claims of current support.
Upstream source licensing applies to source/diffs; stock vendor materials are
analysis inputs, not a blanket redistribution license or approved module port.
