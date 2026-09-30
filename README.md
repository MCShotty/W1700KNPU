# W1700K NPU and OpenWrt Workbench

Canonical workspace for W1700K firmware development, WiFi/MLO fixes,
and stock host-adapter/NPU reverse engineering.

## Current State

Updated 2026-09-30. The objective is complete stock-NPU reverse engineering and
implementation, including host/firmware integration and hardware validation.

The active source is the **unified experimental non-OC merge**, pinned to
OpenW1700k `288d79449f`, Linux **6.18.52**, and mt76 `01367e60`.
Our provider/driver corrections and Linux control client are build inputs, with
WLAN NPU enabled. The RV32 core has a normal build target. There is no separate
release-ready versus experimental source track. Build and hardware verification
remain distinct. The complete image builds and passes offline FIT/board/package/
module checks as `r36536-merged-288d79449f`. A user-authorized flash now passes
basic boot and wired management checks, with unchanged protected storage.
Wi-Fi remains blocked by the same retained channel-161/SA validation error seen
before flashing; client traffic and complete NPU recovery are not validated.
See the [physical boot report](research/checkpoints/2026-09-23-nonoc-flash/REPORT.md) and the
[merge report](docs/NONOC_MERGE.md) for the image path, SHA256 and test receipts.

The latest source checkpoint is [`ac4c639`](https://github.com/MCShotty/W1700KNPU/commit/ac4c6390f070d5f5e0e4e7365e96cbaa89c99d89).
It preflights both NPU firmware images before either copy, rejects empty images
and releases acquired firmware on error. The correction is included in the
unified kernel patch and source lock. The earlier flashed image predates it.

| Verification | Latest Evidence |
| --- | --- |
| Firmware pair loader | 273 actual-C host cases, four original failure controls and six rejected mutants |
| Provider build | Complete before/after AArch64 objects on Linux 6.18.52; strict checkpatch passes |
| Existing regressions | 109 memory, 6,174 retry and 44 Linux V2 control cases |
| Source reconstruction | All 60 locked OpenWrt/LuCI files replay; kernel patch reproduces the tested provider |
| Independent readback | 174 referenced files match their SHA256 fingerprints |

The [loader checkpoint](research/checkpoints/2026-09-30-npu-loader/REPORT.md)
records the software tests and reset-domain review. The paired-loader change
has not yet been tested in a newly built or flashed firmware image.

The retained rollback baseline is **Daybreak21 WLAN-DMA R1 (2026-09-05)**,
Linux 6.18.44, SHA256
`0788f405337ceb030d873463bbf278497dcd9b86e8f75a1a3f57fd318eda195f`.
It deliberately compiles out WLAN NPU support; Ethernet offload is separate.
Stock NPU parity is **not complete**. Synthetic radio/MLO and LuCI save checks
passed; actual-client association and throughput acceptance remain open.

Start with [current reference](docs/W1700K_STOCK_PORT_CURRENT_REFERENCE.md),
[ledger](docs/W1700K_STOCK_PORT_LEDGER.md), and
[logging session](docs/W1700K_STOCK_PORT_LOGGING_SESSION_20260625.md).
The [remaining-work checklist](docs/REMAINING_WORK.md) is the resume plan.

## Remaining NPU Work

- Establish contained cold-provider reset and ownership of every affected engine.
- Supply fresh loader identity, reserved storage and coherent publication.
- Connect actual Linux/mt76 setup and recovery callers in DISCOVER/setup/BIND order.
- Complete native postgate execution, physical DMA drains, teardown and rearm.
- Validate sustained traffic, recovery and actual Wi-Fi/MLO clients on hardware.

The current Wi-Fi channel/regulatory configuration, stale status-script source
labels and boot-environment/NVMEM warnings also remain on the checklist.

## Layout

- `firmware/`: pinned public source revisions, full cumulative OpenWrt/LuCI
  patches, tracked overlays, RV32/host components and the build configuration.
- `tests/`: actual-source fault harnesses, emulation and source-replay checks.
- `tools/`: reproducible workspace preparation and migration verification.
- `research/`: preserved historical patches, tests, Ghidra exports, audit
  reports, and manifests. Archived experiments are not active build inputs.
- `releases/`: selected current/rollback release material and provenance.
- `docs/migration/`: migration, privacy screening, cleanup and path records.
- `.build/`, `.local/`, `.migration/`: ignored builds, protected local data and
  temporary staging. Never commit private keys or device-specific backups.

See [migration and cleanup report](docs/migration/REPORT.md) for exact retained
archives and retirement receipts. Historical source/research is provided as a
checksummed archive with 49,891 entries and a searchable JSON manifest. Large
binary inputs use `.parts.json` manifests; `tools/restore_artifact.py` restores
the original file with end-to-end SHA256 verification.

## Build Preparation

Use WSL native ext4. The canonical local checkout is `/home/captain/W1700KNPU`,
accessible in Explorer at `\\wsl.localhost\Ubuntu\home\captain\W1700KNPU`.
The registered Ubuntu backing disk is under `D:\WSL\Ubuntu`.
The earlier `D:\W1700K-Recovery` snapshot location was absent in the
2026-09-30 directory check. Verify current recovery material before using
historical backup paths.

For a fresh destination:

```sh
python3 tools/prepare_build.py --destination .build/local-openwrt
python3 tools/build_firmware.py --destination .build/local-openwrt --name local-build
```

The current working build is `.build/merged-openwrt`; the earlier
`.build/openwrt` is retained as a rollback/evidence reference. Use fresh
destination and log names; the preparer refuses an existing destination and
verifies every locked changed source file. It does not flash a router. Image
signing keys are not uploaded; fresh build keys must be generated or supplied locally.
An existing imported build may instead be reused as recorded in migration docs.
The combined builder also compiles the RV32 component library using a host
Clang with RISC-V support and `ar`. That library is not yet a replacement
bootable NPU image: production loader identity, placement and postgate wiring
remain unfinished implementation work.

To replay the latest software checks, choose fresh result names:

```sh
python3 tests/npu/test_npu_firmware_loader.py --name readme-replay --output-dir .local/npu-loader-20260930/readme-replay-evidence
python3 tests/npu/test_nonoc_merge.py --prepared --name readme-replay
python3 tests/test_prepared_sources.py --name source-readme-replay
```

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
