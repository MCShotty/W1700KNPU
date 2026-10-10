# W1700K NPU and OpenWrt Workbench

## 2026-10-10 - Provider-Owned Initial Session

The real reserved-memory callback now owns one checked V2 session in the NPU
provider, not per mt76 attachment. It verifies the loader's boot identity before
setup, sends the existing six-command prefix, binds and polls the held initial
epoch. Failure stays sticky; reattachment cannot create another nonce or replay
setup. Close joins this CPU path without releasing exposed DMA storage.

Actual C passes279 cases/nine mutants; the Linux client completes the prefix
against assembled RV32 firmware using C-published DATA, and a wrong identity
stops before setup. Packaged-module Ghidra, full raw ownership regression,
world/63-file replay and FIT/218-package/78-module checks pass. Latest FIT:
`6a7dc41e...`; previous `b0400eaa...` and R1 are preserved. No flash/contact.
Full strict RX/TXDONE setup, physical containment/retirement and clients remain
open. Evidence: `research/checkpoints/2026-10-10-npu-provider-session/REPORT.md`.

## 2026-10-10 - Checked Boot Launch

The actual provider now checks every existing boot-register write, stops on the
first error without retry/reclamation, and permits only one launch attempt.
Checked MT7996 pairs also require the expected version reply before provider
publication; legacy version reporting stays diagnostic. Actual-C 248 cases/ten
mutants and 265 probe cases/three mutants/one original-source control pass.
Native early version succeeds before DISCOVER, matching Linux probe order.

The current6.18.52 reset map now reconstructs exactly and passes147 IDs/23,088
host and5,007 AArch64 instruction cases. Its independent-engine coverage is
still not a physical containment certificate. Full world/source/image checks
pass; latest FIT `b0400eaa...`, previous `05ca2802...` preserved. No flash/contact.
Full strict setup, physical containment/retirement and clients remain open.
Evidence: `research/checkpoints/2026-10-10-npu-boot-launch/REPORT.md`.

## 2026-10-10 - Checked Loader And Mainline Pair Packaging

The normal experimental image now packages the checked MT7996 CODE/DATA pair.
The actual Linux loader checks its ABI/digests and zero session storage, obtains
a nonzero runtime random identity, publishes the real private memory/request
plan and identity, and checks SRAM readback. Exposed DMA mailboxes are retained;
same-instance reload and retained-device rebind are rejected. Retirement is not
implemented, so the module remains pinned after exposure.

Actual-C fault/mutant tests, all-hart native boot from C-published bytes, full raw
RX/TXDONE/BA replay, independent assembly, two package builds and incremental
manifest refresh pass. Latest offline-verified FIT: `05ca2802...`; previous images
are preserved. No flash or router contact. Physical cold containment, complete
strict setup, other owners/hot lifecycle, drains/recovery and clients remain open.
The newest entry defines current state; older dated entries retain their original
scope. Details: `research/checkpoints/2026-10-10-npu-loader-publish/REPORT.md`.

## 2026-10-10 - Provider Request Plan Bridge

The actual MT7996 provider now preflights its coherent mailbox before copying
firmware and prepares the native six-region private snapshot. Actual-C guards/
mutants and raw-native dynamic-address bootstrap pass. Full world/60-file replay/
offline image checks pass; the new FIT is `8efb19fb...`. The previous image is
preserved. This does not publish SRAM/identity, establish reset containment or
install the raw pair. Full strict setup, lifecycle and physical acceptance remain
open. Details: `research/checkpoints/2026-10-10-npu-provider-plan/REPORT.md`.

## 2026-10-10 - Paired Raw NPU Build

The checked native composition now builds a complete raw CODE/DATA pair through
the canonical `pair` target. Independent builds are byte-identical. Fifteen
assembly groups, full raw-only replay with3,072 packet/1,792 page claims and
failure controls, plus actual-provider-C exact-pair copy tests pass. No ELF bytes
are injected after raw loading. Eight build-runner/offline image checks pass.
This is an assembled artifact with modeled platform inputs, not a flashed or
physically accepted replacement. Real loader/storage/identity-plan publication,
strict setup and full lifecycle/physical gates remain. Reproduction and receipts:
`research/checkpoints/2026-10-10-npu-raw-pair/REPORT.md`.

## 2026-10-10 - Shared RX/TXDONE Packet Claims

TXDONE now uses the same retained packet state as RX0/RX2 in native instruction
composition. The full prefix/ring retains 3,072 claims; complete native RAM/SKB,
ordered locks, 25 controls and six mutants pass. Full RX/page regression and
unchanged-image checks also pass. Readiness now rejects late plan/history/bitmap
corruption without reclaiming resources. The real loader still installs the
vendor pair, not these linked hooks. Evidence and the exact installation gap:
`research/checkpoints/2026-10-10-npu-cold-txdone/REPORT.md` and `INSTALL_TRACE.md`
in that directory. Real loader/strict setup/hot lifecycle/physical gates remain.

## 2026-10-10 - Cold RX Packet Ownership

The normal RV32 archive now includes a distinct cold packet ownership profile.
Selected RX0/RX2 callers execute original lock/initializer instructions with
retained claims, immutable table identity and guarded release/readiness.
The 61-site composition passes 2,560 packet claims, 50 controls and six mutants;
1,792 separate BA-page claims leave packet state unchanged. Exact core/sanitizer,
page/statistics regression, full build/source and offline image checks pass.
This is native-emulated integration, not a replacement vendor blob or physical
acceptance. Full setup, other owners, hot lifecycle and hardware gates remain.
Evidence and remaining work: `research/checkpoints/2026-10-10-npu-cold-packet/REPORT.md`.

## 2026-10-10 - Checked RX Statistics Callers

Original RX0/RX2 statistics allocation now uses the checked active-callback
path in native instruction composition. Guards stop failed statistics clears,
RX initialization and readiness while retaining resources. Two nominal rings,
26 controls/six mutants and startup/page/postgate regressions pass. No vendor
blob, loader or physical acceptance is implied. Details and next gates:
`research/checkpoints/2026-10-10-npu-rx-stats/REPORT.md`.

## 2026-10-10 - Native Page Ownership Composition

The shared ownership core now publishes validated native queue heads. Checked
DESC5/6/7 caller composition runs original initializer instructions and prevents
false outer success/readiness after allocation or late-publication faults.
The 54-site replay passes 1,792 claims, 48 controls and six binding mutants;
exact archive replay, sanitizers, full build and offline image checks pass.
This is native-emulated caller integration, not a replacement vendor blob or
hardware acceptance. Remaining gates and receipts are in
`research/checkpoints/2026-10-10-npu-cold-page-native/REPORT.md`.

## 2026-10-01 - Mainline Follow-Up

The user authorized merging the cold-page work and final test-runner change
into `main`. The runner now accepts the exact compiled RV32 core object and
records its path/hash. Fresh source and archive-member replay each pass 5,702
calls, 294 controls and ten mutants with sanitizers; eight build-runner tests
and offline image verification also pass. See the final receipts in
`research/checkpoints/2026-10-01-npu-cold-page/REPORT.md`.
The core remains unwired to native callers; physical acceptance is still open.
No flash or hardware change accompanies this source integration.

## 2026-10-01 - Checked Cold Page Ownership Core

- Preserved pending work after remote-verified `eabfedb`; completed the shared
  cold-page ownership core and added cursor/claim-history consistency validation.
  Claims and late-fault committed resources remain retained; no recycle/reset
  reclamation is implemented. The core is compiled, not wired into native callers.
- 5,702 host/RV32 calls, 294 controls, ten mutants and address/undefined/leak
  sanitizers pass. Existing 273/165 loader-memory, nine mutants, 6,174 retry and
  44 V2 cases pass. Eleven RV32 components and offline image checks pass; unchanged
  FIT `230e03a7b87cb9e14e0464b53d324bb2c4eb650b3c9a64a63514b30dde4458fe`.
- Corrected native 50-hook caller replay shows direct RX0/RX2 statistics callers
  use original unchecked type-10/type-9 allocator fallback, adding two records.
  Strict setup remains denied; an earlier expected-hold assertion was incorrect.
- TypeSafe receipts retain the five initial semantic checks and three approved
  claim checks; exact models/probabilities are recorded in the report.
  Full native ownership/error/publication, strict callers, loader,
  physical drains/recovery and clients remain open. No flash or hardware changes.
  Evidence: `research/checkpoints/2026-10-01-npu-cold-page/REPORT.md`.


Canonical workspace for W1700K firmware development, WiFi/MLO fixes,
and stock host-adapter/NPU reverse engineering.

## Current State

Updated 2026-10-10. The objective is complete stock-NPU reverse engineering and
implementation, including host/firmware integration and hardware validation.

The active source is the **unified experimental non-OC merge**, pinned to
OpenW1700k `288d79449f`, Linux **6.18.52**, and mt76 `01367e60`.
Our provider/driver corrections and Linux control client are build inputs, with
WLAN NPU enabled. The RV32 core has a normal build target. There is no separate
release-ready versus experimental source track. Build and hardware verification
remain distinct. The complete image builds and passes offline FIT/board/package/
module checks as `r36536-merged-288d79449f`. The September 23 image passed a user-authorized flash, basic boot and wired
management checks, with unchanged protected storage. At that checkpoint, Wi-Fi
remained blocked by the retained channel-161/SA validation error seen before
flashing. Current hardware state must be rechecked; client traffic and complete
NPU recovery are not validated.
See the [physical boot report](research/checkpoints/2026-09-23-nonoc-flash/REPORT.md) and the
[merge report](docs/NONOC_MERGE.md) for the image path, SHA256 and test receipts.

The current source also validates and snapshots the MT7996 WLAN
memory plan before either firmware copy. Generic/PPE-only profiles retain their
optional WLAN behavior and caller-local setup plans. The new portable host-C
replay passes 273 loader cases, 165 additional load scenarios, three original
failure controls, nine rejected mutants, 6,174 retry cases and 44 V2 executor
cases. This change is integrated in the canonical patch/source lock and now has
a compiled/linked AArch64 provider module and ten RV32 objects;
its full image passes offline FIT/board/firmware/218-package/78-module checks.
The candidate has not been booted or flashed. See the
[cold-memory checkpoint](research/checkpoints/2026-09-30-npu-cold-memory/REPORT.md)
and [completed cloud validation](research/checkpoints/2026-09-30-npu-cloud-build/REPORT.md).

That source and its deferred history documents were synchronized back to
the local WSL checkout. The preceding full local build passed the same offline checks;
the packaged NPU provider matches the cloud module byte-for-byte. The local
FIT has its own SHA256:
`277abd0b754200a0b330a35d4c759f264f918ec182cddc6c650fb734f46b4e4b`.
The host suite also passes with LeakSanitizer enabled. See the
[WSL sync checkpoint](research/checkpoints/2026-10-01-wsl-sync/REPORT.md).

Native startup continuation fixes hart7's first-boot allocation phase mismatch
in the shared replay binding. With all 50 detours installed, hart7 now reaches
its outer loop under explicit host-publication and hardware models; other
workers still await later host setup. This is not a new packaged firmware or
physical boot claim. See the
[postgate checkpoint](research/checkpoints/2026-10-01-npu-postgate/REPORT.md).

The latest production correction covers the MT7996 INODE wrapper's 24-byte
read span with zero-extended short requests. Other valid profile/command frame
lengths and caller bytes are preserved; invalid lengths and NULL-positive-data
are rejected before allocation/copy. Actual provider C and the packaged
AArch64 sender each pass 1,056 frame cases and 30 controls. All 16 original
RV32 wrapper entries accept those emitted bytes within their declared extent;
five mutants are rejected. The full image and 60-file source replay pass.
Preceding local FIT SHA256:
`031f7bd2b28e0507ddfe810602a7edef71c63900244935e7d460ab58ab35a0cc`.
This image has not been flashed. Native selector readiness, physical delivery
and complete recovery remain open; padding is not a proved Wi-Fi root-cause
fix. See the [INODE framing checkpoint](research/checkpoints/2026-10-01-npu-inode-frame/REPORT.md).

The formerly entry-only DESC5/6/7/8 consumers now execute their complete native
helper paths after RX0/RX2 initialization. Four nominal cases, 48 controls and
five native mutants establish their descriptor/ID footprints and failure state.
A DESC6 count of 513 corrupts the arena pointer despite an outer success reply.
The production provider now bounds the selected MT7996 page/indication requests
before transport; actual C and packaged AArch64 instructions/table each pass
12,096 cases and 384 rejections, with six provider mutants rejected. The full
build, image/source checks and INODE/memory regressions pass. Latest FIT SHA256:
`230e03a7b87cb9e14e0464b53d324bb2c4eb650b3c9a64a63514b30dde4458fe`.
This is not a native allocation-failure, full attachment or physical acceptance
fix. See the [page-ring checkpoint](research/checkpoints/2026-10-01-npu-page-rings/REPORT.md).

The preceding paired-loader source checkpoint is [`ac4c639`](https://github.com/MCShotty/W1700KNPU/commit/ac4c6390f070d5f5e0e4e7365e96cbaa89c99d89).
It preflights both NPU firmware images before either copy, rejects empty images
and releases acquired firmware on error. The correction is included in the
unified kernel patch and source lock. The earlier flashed image predates it.

The following target-object/source-tree evidence applies to that preceding
paired-loader checkpoint, not the newer memory-plan change:

| Verification | Paired-Loader Evidence |
| --- | --- |
| Firmware pair loader | 273 actual-C host cases, four original failure controls and six rejected mutants |
| Provider build | Complete before/after AArch64 objects on Linux 6.18.52; strict checkpatch passes |
| Existing regressions | 109 memory, 6,174 retry and 44 Linux V2 control cases |
| Source reconstruction | All 60 locked OpenWrt/LuCI files replay; kernel patch reproduces the tested provider |
| Independent readback | 174 referenced files match their SHA256 fingerprints |

The [loader checkpoint](research/checkpoints/2026-09-30-npu-loader/REPORT.md)
records the software tests and reset-domain review. The paired-loader change is also included in the September 30 cold-memory
candidate, which now passes full offline image verification. That candidate
has not been booted or flashed.

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

Use a native Linux filesystem, including WSL ext4 or the authorized cloud
checkout. The current local checkout is `/home/captain/W1700KNPU`,
accessible in Explorer at `\\wsl.localhost\Ubuntu\home\captain\W1700KNPU`.
The registered Ubuntu backing disk is under `D:\WSL\Ubuntu`.
The earlier `D:\W1700K-Recovery` snapshot location was absent in the
2026-09-30 directory check. Verify current recovery material before using
historical backup paths.

For a fresh destination:

```sh
python3 tools/prepare_build.py --destination .build/local-openwrt
python3 tools/build_firmware.py --destination .build/local-openwrt --target tools/install --name local-tools
make -C .build/local-openwrt package/firmware/linux-firmware/prepare V=s
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tools/build_firmware.py --destination .build/local-openwrt --name local-build
```

On this WSL executor, the working build is `.build/merged-openwrt`; the earlier
`.build/openwrt` is retained as a rollback/evidence reference. Use fresh
destination and log names; the preparer refuses an existing destination and
verifies every locked changed source file. It does not flash a router. Image
signing keys are not uploaded; fresh build keys must be generated or supplied locally.
An existing imported build may instead be reused as recorded in migration docs.
The cloud transfer contains source/evidence. This computer's existing WSL build
was refreshed and rebuilt after synchronization; other executors must prepare
their own build trees and local credentials.
The combined builder compiles the RV32 archive and checked raw pair using host
Clang/LLD with RISC-V support and `ar`. Python needs Unicorn, Capstone and
pyelftools; the local dependency directory above supplies the existing tested
versions. The hash-pinned original pair comes from prepared linux-firmware, or
an explicit workspace `--npu-firmware-directory`. Pair staging is validated
before package installation, and all three staged files are package dependencies.
The archive itself is not raw CODE. Runtime loader publication is implemented;
physical cold containment/retirement, complete strict setup and postgate remain
unfinished. The builder and verifier never contact a router.

For the portable current provider/loader/retry/V2 host checks (GCC and Git):

```sh
python3 tests/npu/test_cold_memory_plan.py --name readme-cold-replay
```

Address, undefined-behavior and leak checks are enabled by default. Hosts that
cannot run LeakSanitizer can explicitly use `--disable-leak-check`; the receipt
records the reduced coverage.

With the pinned build and Python ELF tooling available, verify current source
replay and the built image using fresh result names:

```sh
python3 tests/test_prepared_sources.py --name source-readme-replay
PYTHONPATH=.local/npu-reset/python-lib python3 tools/verify_merged_image.py --name readme-image-check
```

Older paired-loader/prepared-driver runners use checkpoint-specific `.local/`
snapshots. Their reports identify the source context needed to replay them;
the portable memory-plan suite above covers the current provider.

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
