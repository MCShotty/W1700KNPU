# Checked NPU Boot Launch And Current Reset Evidence

Date: 2026-10-10. Source baseline `5dbfae8d65e164281cf4d1e44fa439f47f505734`.
Canonical WSL workspace `/home/captain/W1700KNPU`, mainline experimental build.
This closes a real provider boot-error path and refreshes reset evidence.
The full NPU reverse-engineering/implementation goal remains incomplete.
No router, hardware MMIO, physical reset, module loading or flash occurred.

## Correction

The old probe copied/published firmware, ignored all existing boot-register
write statuses and published its provider regardless. A version-read failure
was also only diagnostic, even for the checked pair. The preceding retained
DMA lease made post-copy failures survivable without automatically reclaiming
possibly owned mailboxes, but did not propagate launch failures.

The canonical provider now uses `airoha_npu_start_firmware()`:

- Require copied firmware/exposed lease; checked pairs also require published
  native metadata/nonzero identity. Invalid state causes no boot-register I/O.
- Latch a launch attempt before the first write and reject every later attempt
  without changing state or issuing I/O. This is not a reset/rearm API.
- Check all14 existing writes: four backup/handshake words, eight core bases,
  configuration and trigger. Preserve nominal values/order/delays, return the
  first error, and perform no retry, rollback, reset or buffer release.
- For the checked MT7996 profile, require successful version transport and the
  expected native0x457 reply before `platform_set_drvdata`. Unmarked legacy
  version reporting remains optional; common write errors reject every profile.
- Retain exposed coherent buffers/device/module lifetime after any error,
  including modeled write failures after a side effect. Register success and
  a version reply are not whole-device readiness or physical containment.

The original-source full-probe control reproduces false provider publication
after an injected launch error. The corrected probe rejects it. The packaged
binary has the same guards in its inlined probe block, confirmed with Ghidra.

## Evidence

| Scope | Passing Result | Receipt |
| --- | --- | --- |
| Actual boot-sequence C | 248 cases,224 before/after-effect write faults,ten compiled mutants; ASan/UBSan/leak | `boot-launch.json` |
| Actual probe/IRQ/work/lease/helper C | 265 fault/delivery cases,three mutants and one original-source control | `probe-lifetime.json` |
| Actual loader/parser/RNG/publisher C | 60 cases/eight mutants; retained lease13/four | `checked-loader.json`, `dma-lifetime.json` |
| Current pre-copy request plan | 310 cases,476 pre-copy checks,nine mutants | `request-plan.json` |
| Canonical memory/retry/V2 | 273/159 cases,three prior controls,nine mutants,6,174 retry and44 V2 | `memory-retry-v2.json` |
| Actual current C plus exact packaged pair | 273 matrix/seven copy/publication/failure cases | `pair-loader.json` |
| C-published raw native bootstrap | Version before DISCOVER while nonce slots remain zero; later all eight harts park, strict full setup still denies | `native-published.json` |
| Full raw native RX/TXDONE/BA | 3,072 PKT/1,792 separate BA claims; six boot/eight TXDONE controls | `raw-native.json` |
| Independent assembly | Same CODE/DATA;16 groups,zero skips,61 hooks/12 components | `assembly.json` |
| Exact packaged provider Ghidra | Full auto-analysis;33 discovered executable functions,one selected probe export,zero decompile failures | `ghidra-provider.txt`, `ghidra.json` |
| Current reset source/target | Exact6.18.52 reconstruction;147 IDs/23,088 host/5,007 AArch64 cases,including3,087 native faults | `reset-map.json` |
| Source/build/image | 62 locked files; full world; FIT/DTB/hash/218 packages/78 module ABIs | `source-replay.json`, `build.json`, `image.json` |
| Source style | Strict current delta:0 errors/warnings/checks | `checkpatch.log` |

The source tests model regmap/timing/version, DMA/devres and CPU IRQ/work delivery.
The probe runner replaces firmware loading only at its caller boundary to inject
pre/post-exposure faults; parser/copy/publication are tested separately. Test
teardown retirement is not a driver reclaim operation. Native reset callbacks
execute target-compiled instructions with modeled regmap, not physical MMIO.
Native raw execution retains the held callback/backing/IRQ model; no post-load
ELF injection or synthetic plan/identity overwrite occurs in the C-publication
bootstrap. Full strict data setup remains denied. Counts are scoped evidence,
not a measure of total-goal completion.

## Exact Image

Linux6.18.52, mt76 `01367e60`, OpenW1700k `288d79449f`, board
`gemtek,w1700k-ubi`, compatibility2.0, revision `r36536-merged-288d79449f`.

- FIT,26,956,618 bytes:
  `b0400eaa873beeb309fc10e7376255f89cefb7c1f986096863916f5a4ee222b6`.
- Packaged provider:
  `64229ba1fc646463516ea411eb410466ecb495eceb9bb8aec10de3c1db19ad56`.
- CODE unchanged:
  `bc15190ead08ebb44a6feba439f39ae8e7bcbaf9e5ce5851a3e2146ebd1893a5`.
- DATA unchanged:
  `5311ef172aec19164723a273230d47fb147b7bee8e522f13a86580ce87c58d75`.
- Kernel patch:
  `3bfbe94be831a5a5b78b407b441321355be879f55ebc0dec3d27d0cdc3d936a9`.
- Source-lock:
  `af81c3c101b6f30cc227bc6be287df88148000c1cc85400df3206a7f4dd73fd8`.

The preceding verified05ca2802 FIT is preserved locally with hash readback.
R1, recovery/calibration, bootloader and keys are untouched. The complete world
retains upstream/package warnings and an ignored U-Boot install error; it is
not a warning-free build or a bootloader operation. Binaries, projects and
protected inputs stay local; this checkpoint publishes source/text receipts.

## Reset Boundary

The active reset driver is now reconstructed from the hash-pinned6.18.52 archive
and actual patch stack, rather than relying on the older6.18.44 inventory.
Full current driver and real-kernel layout objects compile; current callback
instructions preserve error, side-effect, polarity and translation behavior.
NPU logical8 maps0x830/bit9, while GDMA/WDMA/WOE/HSDMA/TDMA/FE-related entries
remain distinct. The compiled board NPU node still has no reset binding.

This verifies current source/translation, not reset-domain coverage, outstanding
bus-work disposition, SRAM accessibility while reset, independent-owner closure,
cache visibility or physical retirement. A named NPU line is not assumed to
contain the standalone copy engine, FE/PPE, tunnel or Wi-Fi endpoint masters.
The engine matrix records the refreshed scope without inventing a reset sequence.

## Remaining Work

1. Establish real prior-user cold exclusion, exact reservation/backing and cache/
   DMA visibility contracts, with independent physical witnesses and shared-owner
   coverage. No flag, version reply or software parking substitutes for them.
2. Wire real strict Linux DISCOVER/setup/BIND and its once-owned provider/session
   lifetime. The compiled Linux executor still has no real setup caller.
3. Complete other packet/page owners, workers/hot lifecycle and postgate paths.
4. Implement physical drains/retirement, teardown/rearm/recovery and resource/
   token reclamation. Current exposed mailbox retention/module pin is permanent.
5. Separately validate exact-image physical boot/recovery and real clients.
   Last physical evidence remains September23, not this new image.

## Replay

Run in the canonical workspace with current dependencies and fresh names:

```sh
export PYTHONPATH=.local/npu-reset/python-lib:tests/npu
python3 tests/npu/test_boot_launch.py --source .local/merge-nonoc-20260923/kernel-merged/drivers/net/ethernet/airoha/airoha_npu.c --name launch-fresh
python3 tests/npu/test_current_reset_map.py --name reset-fresh
python3 tests/npu/test_cold_memory_plan.py --name boot-fresh
python3 tools/build_firmware.py --target world --jobs 4 --name boot-fresh
python3 tools/verify_merged_image.py --name boot-fresh-offline
```

Do not run prepared-directory tests while world replaces that directory. The
Ghidra MCP inventory found no live instance; installed12.1.2 headless analysis
was used against the exact packaged ELF. The initial UNC helper/dot-directory
attempts never produced an accepted export. A hash-verified local helper mirror
and ignored non-dot scratch project completed analysis without changing the
Windows execution policy. Old failure outputs remain local, not passing proof.

## Semantic Checks

Actual TypeSafe `jev-1.13.0` follows the
[current official API](https://docs.typesafe.ai/api). Seven pre-change checks
classified ambiguous-failure retention and reset/version scope. Eight post-change
checks retained physical-reset/whole-goal Noul0.03/0.05, not completion claims.
The combined getter/publication Noul0.43 was explicitly uncertain. It was split
into checked-branch getter error, mismatch and caller-publication questions;
those return error/protocol-error(probability1.0/confidence1.0) and Noul0.96.
Actual C cases/mutants and the packaged Ghidra branches supply the verification,
not a model confidence threshold. Raw requests/probabilities are retained.

`verification.json` and `file-manifest.json` seal the scoped source/evidence.
The full user objective remains active; this is not final NPU acceptance.
