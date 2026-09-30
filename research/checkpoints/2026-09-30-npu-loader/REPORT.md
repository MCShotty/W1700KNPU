# NPU Firmware Pair Preflight And Reset-Domain Review

Checked 2026-09-30. The source update is integrated into the unified kernel
patch and source lock. Actual loader C passes host fault tests and complete
Linux 6.18.52 provider object builds. The existing flashed image is unchanged;
this checkpoint does not establish a new hardware boot or physical drain.

## Loader Correction

The committed provider at `ec39858` copies the RV32 image before requesting
and validating its SRAM data image. A missing or oversized second image can
therefore return an error after code memory has already changed. Zero-length
images are also accepted by that implementation.

The updated loader obtains and validates both images before either copy.
Empty images return `-EINVAL`; oversized images return `-E2BIG`. Request errors
retain their status, with missing firmware translated to `-EPROBE_DEFER` as
before. Every acquired object is released once on the covered paths. Both DTS
names and standard SoC profiles use this same paired loader.

The integrated patch is `firmware/overlay/openwrt/target/linux/airoha/patches-6.18/999-w1700k-integrated-npu.patch`.
Its source-lock fingerprint is updated. Reapplying it to the retained pinned
upstream provider reproduces the tested source exactly, SHA256
`8dc8545d3b5ea776820f2d75ed0795fee0ca8f93a12bb9e0708169320425f052`.

## Verification

- 273 ASan/UBSan host cases execute the actual extracted loader C. They cover
  three profiles, DTS/default selection, request errors, empty/oversized images,
  boundary lengths, missing match data, mapping failure and invalid regions.
  Complete code/data destinations and guards remain unchanged on rejection.
  Successful cases verify both copies, their ordering and exact object release.
- Four original-source controls fail: missing data, oversized data, empty code
  and empty data. All pass after correction. Six compiled mutants are rejected:
  early code publication, empty acceptance, lost code/data release, incorrect
  data-image selection and hidden second-request errors.
- Complete before/after providers compile as two AArch64 objects for the actual
  prepared Linux 6.18.52 kernel, with no compiler diagnostics. Strict checkpatch
  reports zero errors, warnings and checks. Sources, configuration, generated
  kernel headers and Module.symvers remain unchanged during testing.
- Existing prepared-driver regressions pass 109 memory-preflight cases, 6,174
  allocation-retry cases and 44 Linux control-executor cases. The memory test's
  loader stub was adapted for the paired signature; it does not replace the new
  actual-request and whole-destination fault checks.
- All 60 locked OpenWrt/LuCI source files replay from their pinned bases.
  Receipts and input/artifact fingerprints are retained in this directory.
- Independent Windows readback verifies 174 referenced WSL files totaling
  26,119,092 bytes, with no SHA256 mismatch. The prior built image still matches
  its physical-boot checkpoint hash; the source update has not replaced it.

## Reset-Domain Evidence

A read-only Ghidra export from the previously analyzed stock kernel selects
40 functions and direct callers with zero failed decompilations. The input
SHA256 is `a51e6d0a6deee620a5f715c9469f193906cdf3fcea28b97ce01cf88383aa704e`.
The number selected is not a statement of complete ownership coverage.

The current reset map separates NPU logical ID 8 (offset 0x830, bit 9) from
GDMA logical ID 38 (offset 0x834, bit 14). Stock `ecnt_gdma_drv_probe` only maps
its device; `ecnt_gdma_drv_remove` returns zero without a drain operation.
`boot_npu_all_cores` publishes eight boot addresses, config and trigger, with
fixed delays. `host_set_npu_core_on_off` changes the core mask and trigger;
these operations do not demonstrate completion of independent bus work.
The current provider's watchdog captures a dump; it does not restart cores.

Jev checks are supplementary. The initial pair-preflight question was uncertain
(0.55), and the final release-path judgment favored support with probability
0.59. Actual path inspection, object-ownership assertions and mutation controls
supply the software evidence. The integration and physical-containment scope
judgments are retained with their full probabilities.

## Remaining Work And Replay

This fixes request/size preflight, not atomic live replacement or contained cold
reset. Hardware reset/engine coverage, loader identity and storage publication,
V2 setup/recovery callers, full postgate execution and physical drain/rearm
remain required for the full NPU implementation. No new image, module load,
router test or flash is claimed by this checkpoint.

```sh
python3 tests/npu/test_npu_firmware_loader.py --name replay --output-dir .local/npu-loader-20260930/replay-evidence
python3 tests/npu/test_nonoc_merge.py --prepared --name loader-replay
python3 tests/test_prepared_sources.py --name source-replay-loader-replay
```

Choose fresh result names. The successful canonical loader build is
`.local/npu-loader-20260930/verified-three/`; earlier scaffold/style failures
are not counted as passing evidence. Private input ELFs and generated binaries
stay in ignored storage. The full NPU goal remains unfinished.
