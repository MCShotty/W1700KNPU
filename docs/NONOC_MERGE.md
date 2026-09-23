# Unified Experimental Non-OC Merge

Status: source merge, complete image build and offline image verification pass.
No image has been flashed or hardware-tested in this merge.

The user's 2026-09-23 instruction makes the current implemented changes one
experimental source/build target. Earlier checkpoint labels such as
"unpromoted" describe historical state, not a separate current source track.
Missing implementation and missing hardware proof remain missing; integration
does not turn either into a completed feature.

## Pinned Base

- Non-OC release: [`ubi2_2026.09.23_r36536-288d79449f`](https://github.com/w1700k/builds/releases/tag/ubi2_2026.09.23_r36536-288d79449f).
- OpenW1700k: `288d79449f622a37c727cb12e81e85dba822aecb`.
- Kernel: 6.18.52, replacing 6.18.44.
- mt76 fork: `01367e60db433534ad0aa3d3b6c886de8cb7d44c`.
- LuCI: `d24568155976063c56ad001a0bd5d10ab4880f3e`.
- Other feed pins, source hashes and component mappings: `firmware/source-lock.json`.
- Build tree: `.build/merged-openwrt`. The old `.build/openwrt` remains intact.
- Unified image revision: `r36536-merged-288d79449f` in both the root filesystem
  and upgrade metadata. The standard OpenWrt `version` file prevents shallow
  Git history from reporting `r0`; the final hash suffix also satisfies APK.
- The newer mt76 archive is checksum-pinned rather than using upstream's `skip`.

## Combined Changes

- Their newer kernel, Wi-Fi firmware, PHY/platform/CPU-frequency fixes,
  standalone offload, monitoring and extra applications form the new base.
- Our Wi-Fi/MLO/userspace fixes and SQM/CAKE, adblock, SoftEther, HTTPS and
  custom status packages are retained. Full OpenSSL wpad/apk/HTTPS variants
  resolve mutually exclusive package choices. Only the W1700K image's selected
  modules are built; their all-kmods repository-build setting is not required
  for the combined installed feature set.
- Our mt76 changes 001-009 are reconciled into
  `900-w1700k-integrated-npu.patch`, preserving their debugfs/token views too.
  The Linux control client is compiled into mt76 through shared canonical
  `firmware/npu` sources, not maintained as an independently drifting copy.
- Provider mailbox ownership, memory preflight, V2 transport, IRQ/work lifetime
  and reset-controller corrections are in `999-w1700k-integrated-npu.patch`.
  The new 500ms poll remains. Setup retries are limited to allocation failure;
  ambiguous timeouts and remote/I/O errors are not blindly replayed. Every
  reserved region is validated and captured before the first setup command.
- Our older GRO-advertisement patch is superseded by equivalent behavior plus
  broader GRO synchronization already in their base.
- The bootstrap BIND gate is now part of `firmware/npu/control-v2.c`. It is
  byte-identical to the previously validated staged gate. The ten RV32 core
  units build together with `firmware/npu/Makefile`.
- Their channel-analysis and upgrade UI changes are included. The download
  helper now requires the appropriate LuCI session permission, POST for staging,
  the correct board/non-OC asset, actual SHA256 verification and compatibility
  validation before replacing the staging file. It performs no flashing.
  The UI explicitly warns that public upstream upgrades replace these custom
  kernel/NPU changes, even when settings are kept.

## Verification

- Source merge retains the newer mt76 pin and resolves the actual overlaps.
- 109 actual-C memory/load preflight cases pass against the merged provider.
- 6,174 allocation-retry cases and three broken-implementation controls pass.
- 44 Linux executor cases pass with the merged provider/client: 367 executor
  and 606 provider-model assertions. OF/regmap/storage/delivery/mutexes are modeled.
- Twenty actual prepared kernel/mt76 files match the merged/tested sources
  byte-for-byte; the final focused tests execute those prepared driver sources.
- Ten RV32 core objects and their deterministic static archive compile.
- The integrated bootstrap suite passes three valid profiles, six early-BIND
  cases, six cold failures, 28 transport rejections, 786 policy cases and eight
  mutants. All-hart cold-start composition passes with 50 retained detours,
  209 host and 96 server comparisons, failure and missing-hook controls.
- 18 synthetic updater cases pass without network access or flashing;
  authentication, wrong-board/tag, digest, compatibility and concurrency failures
  preserve the existing staged image. ShellCheck passes.
- Fresh host tools, cross-toolchain and complete `make world` pass. Final FIT
  component hashes, kernel payload, model/layout/compatibility, 218 installed
  packages, 78 module ABIs and selected driver/provider symbols verify.
- The actual DTB has the corrected 56 KiB TX buffer-check reservation and
  non-overlapping BA region. Non-OC OPPs cover 500-1200 MHz; this is configuration,
  not a measured CPU frequency. All packaged MT7996 firmware files match the
  pinned newer source. Ten RV32 objects verify as 32-bit RISC-V.
- A final clean-checkout replay reproduces all 60 locked changed source files.
  Source whitespace, Python syntax, ShellCheck and both LuCI JS syntax checks pass.
- Every upstream explicitly selected package is retained. Compared with our
  185 prior selections, only five TLS/certificate variants and the generic NPU
  firmware selection are replaced; their OpenSSL and board-specific MT7996
  replacements are verified inside the image. See `package-selection.json`.
- Independent Windows SHA256 readback verifies 151 source, receipt and image files.

Compact receipts are retained in
`research/checkpoints/2026-09-23-nonoc-merge/`; working inputs and complete build
logs remain under `.local/merge-nonoc-20260923/`. Authoritative source is exported
into `firmware/`. `validation.json` binds final sources to the receipts, including
the host-only metadata updates made after native tests; executable inputs match.

An initial bootstrap run stopped short of its expected endpoint under build
load. Its identical ELF passed isolated replay, and the complete rerun passed
with a recorded 60-second wall budget while retaining the 3-million instruction
bound and state assertions. A canceled run is not counted. Intermediate revision
metadata and APK-version failures were corrected and the final image rechecked.
Jev claim checks support the source/build scope and reject inferring physical
recovery or preservation of custom code by the public updater; they are not
substitutes for the deterministic checks above.

## Built Artifact

Local image:
`.build/merged-openwrt/bin/targets/airoha/an7581/openwrt-airoha-an7581-gemtek_w1700k-ubi-squashfs-sysupgrade.itb`

- Size: 26,932,042 bytes.
- SHA256: `132a35c746e008345032d1c862ea1ace1ef7a27d87a3fd363b8225045554e670`.
- Board: `gemtek,w1700k-ubi`; compatibility: `2.0`.
- Source lock SHA256: `1411822d0022b531f690eb8c28c1ca48e3d23985e1a9d8835bab7c6d6254176a`.

This is a locally built experimental image, not a flashed or router-accepted
release. No commit or push was performed in this merge session.

For a fresh build destination, run `tools/prepare_build.py`, then
`tools/build_firmware.py --name new-build --jobs 4`. Existing destinations and
receipt names are deliberately not overwritten. Offline verification is
`PYTHONPATH=.local/npu-reset/python-lib python3 tools/verify_merged_image.py --name new-image-check`.

## Still Incomplete

The Linux V2 client is part of the driver build, but automatic cold-session
initialization/caller wiring is not yet implemented. The RV32 core compiles,
but the real loader and postgate/native-hook integration are not yet complete;
the supplied MT7996 NPU firmware is not silently replaced with an emulator image.
Physical ownership/drains, complete reset/removal/rearm and stock parity remain
unverified. These are implementation gaps inside this unified experimental
project, not changes withheld on the grounds that they are experimental.

The last router-tested packaged baseline is still Daybreak21 R1 with WLAN NPU
disabled. Existing protected recovery, calibration, credentials and rollback
images are untouched. There has been no restricted INODE/DESC execution,
subagent delegation, router contact or flashing.
