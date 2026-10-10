# Retained Cold TX0/TX2 And Token Programming

## Scope

This checkpoint advances the full NPU reverse-engineering/implementation goal;
it does not complete it. Implemented source is integrated on the experimental
mainline. No router contact, reset, flash or physical write occurred.

`cold-tx.c/.h` is the15th portable archive object. A fresh80-byte owner pins a
44-byte plan, captures native register/token preimages and reserves11 ordered
writes before original stores. TX0 completes five writes, TX2 five more, then
the original32-bit token-limit store at0x3e900bc0 completes write11. Faults retain
committed/published progress, reserved claims and the outer active/inflight
lease. There is no rollback, reset, retirement or reclamation API.

Original allocator lock18 pins the unique existing type1 WLAN-arena entry,
allocator count/used,303168-byte extent, subregion table, bound BAR window,
boot/nonce/sequence, full RX/page counts and indication1536 state. Every guarded
access checks the held/parked/ready/drain/deferred context. A failed acquisition
never releases an unowned lock. Completion rechecks readback and pinned state
after releasing the acquired lock; ambiguous changes still deny outer success.

The separate13th raw native component has164 bytes of private BSS and adds11
operand-preserving hooks to the
previous63, for74 total. The actual checked provider routes API19 selectors0/2
and API33 selector0 through the existing authenticated80-byte cold envelope.
Private cold history stays104 bytes; there is no new session/nonce or wire ABI.
TX0 host metadata is BAR0+0xd4420; TX2 is +0xd4450 or HIF2 +0xd8450, with its
complete12-byte register span inside the bound window. Token limit is8192.
Native base registers preserve the original arena/+0x22020/+0x4a040 arithmetic
masked by0x1fffffff. The last value is one-past the reserved arena extent, as in
the original body; this is not proof of physical engine coverage or dereference.

## Qualification

- Exact world-built TX object:525 host/RV32 calls,205 controls,six rejected
  mutants; AddressSanitizer, UndefinedBehaviorSanitizer and leak checks pass.
- Cold wire/codec/executor:459 cases,16 mutants, including16 TX/HIF2 window
  cases. Wrong offsets, insufficient HIF2 span and relaxed token limit deny.
- Actual provider C:545 cases,nine mutants. Actual mt76 pointer-publication
  order passes three cases; actual mt7996 offload C completes16 commands through
  token publication. A later RXDESC-base GET is still denied without callback.
- The nominal actual-C/Linux/native replay passes34 indication and27 TX negative
  controls:15 preconditions and12 changes immediately before the first TX CSR
  store. The latter retain three committed/published writes and perform no native
  CSR store. Negative memory/register snapshot restores are test-only isolation,
  not a production reset, new session or active-grant API.
- All seven native cases pass: nominal, wrong boot identity and PKT/BA/
  indication/TX-register/token faults. The register fault retains4 committed/
  3 published writes with cold prefix16383; token retains11/10 with prefix65535.
  Both retain2,560 PKT/1,792 BA claims and active/inflight1. HIF2 actual-C/native
  replay also passes the shifted TX2 address and all27 TX controls.
- Full raw-only regression passes3,072 PKT/1,792 BA claims, six boot and eight
  TXDONE controls. Initial18 cold commands use actual cold-client C, with no
  test-written active lease or direct owner initializer. Only later TXDONE
  lease/ring metadata remain directly modeled. There is no post-load ELF
  injection; raw CODE/DATA copies and installed hooks are checked.
- Parser60/eight, boot248/ten, lifetime13/four, probe269/three, request310/nine,
  memory273/159 with three original controls/nine mutants, retry6174 and V2
  executor44 cases pass. Fresh world,66-file source reconstruction,12 nested
  compiled-source comparisons,13 canonical Linux component mappings,16 assembly
  groups without skips, FIT/218-package/78-module checks and54-function packaged
  provider Ghidra export pass. Driver delta has zero strict-checkpatch findings.
- The unchanged indication core is freshly replayed against its exact world
  object:12,322 host/RV32 calls,3,095 controls and seven mutants pass.

The15 archive objects,13 raw native components and13 canonical Linux provider
component mappings are different sets. The archive is not a standalone bootable
firmware image. Independent same-input raw builds have identical CODE/DATA;
their manifest hashes differ because output paths are recorded. The world pair
has the same raw bytes. Full world retains upstream/package warnings and an
ignored U-Boot install error; offline image verification is separate evidence,
not a warning-free-build claim.

## Semantic Review

Actual `jev-1.13.0` design and source-review requests/results are preserved.
Design classified TX as metadata plus native programming, token as publication,
subregion getter as not exclusive ownership, and partial failure as retain/deny.
The six-question source review selected retention and captured register
preimages at probability/confidence1.0. Readback-before-publication was0.88;
reserve-before-store was uncertain at0.67. Reset/retirement API and physical
proof claims were0.08/0.07. These judgments are not proof or unanimous approval.
The assembly calls the native reserve function and branches on its zero failure
return before the original field store; the C adapter returns1 only after the
core's zero-success status and pinned checks. Exact code and fault tests establish
that covered ordering, not a converted model-confidence threshold.

## Artifacts

- FIT26968906 bytes:
  `4da01cfe0136b72014b71f3220323a38ee9e5b3987396b69f55fba6cf8afae84`.
- Packaged `airoha_npu.ko`:
  `047984bf06c269b8a951f5bc4316346221dd72ac492010ea05f02bc92551fee2`.
- CODE547864 bytes:
  `3c6df8f00b727dcc313cc15ef83dfd3b070d4478686b77d5ab9590ad595bc5b8`.
- DATA25728 bytes:
  `006006f911158da30fddbe6dcc8ecaf63b57749f05a51c57a19a911be5885a1b`.
- Fifteen-object archive:
  `413cdd509fac32b91087896dde38acc384848614b4d6849ff4d587be6995db1e`.
- Source lock:
  `c62e208dc1a688afb8fa90b6e43898618c14a1c7447c7ed556b74e98e9cd3d00`.

Kernel6.18.52, mt76`01367e60`, OpenWrt`288d79449f`, revisionr36536-merged remain
the unified non-OC baseline. Previous FIT `8dd1f2f4...` and seven companions were
preserved and hash-verified in ignored
`.local/npu-cold-tx-20261010/pre-world-image/`. Older/R1 images, calibration,
bootloader, recovery and private device backups remain protected.

Early diagnostic harness failures are preserved in ignored fresh-name work:
alias/overlap request addresses, missing post-parking STATUS, a mutant compilation
warning, and a source-extractor typedef mismatch were corrected. The first full
raw qualification hit its emulator wall budget during the concurrent world
build. Final full replay uses the existing60000000us observer budget with its
instruction/state checks unchanged. No failed attempt is counted as a pass.

## Remaining Work

Complete checked RXDESC-base getters/host descriptor publication, TX buffer and
PCIe-address/INODE/TXDONE/final IRQ setup. The nominal next command is
GET-selector0/API4, not another TX0 operation. Complete all remaining owners,
workers/hot/postgate and independently establish prior-user exclusion,
exclusive backing/cache/DMA visibility and engine coverage. Physical
drains/retirement/teardown/rearm/recovery, exact-image boot and actual clients
remain required. Successful modeled register readback, parking, BAR bounds or
retained claims never authorize physical resource release or a new boot.
See `NEXT_SETUP_TRACE.md` for selector-specific original GET effects, the0x457
fallback and the host managed-TX-buffer exposure/lifetime requirement.

## Reproduction

Use fresh names in ignored canonical WSL storage; freeze consumed source/header/
test files during runs. Provider/header copies below are immutable during world
preparation. Do not run these commands against a router.

```sh
export PYTHONPATH=.local/npu-reset/python-lib:tests/npu
export NPU_EMULATION_TIMEOUT_US=60000000
provider=.local/merge-nonoc-20260923/kernel-merged/drivers/net/ethernet/airoha/airoha_npu.c
header=.local/merge-nonoc-20260923/kernel-merged/include/linux/soc/airoha/airoha_offload.h
python3 tests/npu/test_cold_tx.py --core-object .build/merged-openwrt/bin/npu/cold-tx.o --name fresh-tx-core
python3 tests/npu/test_cold_host_prefix.py --mt76 .local/merge-nonoc-20260923/mt76-merged --name fresh-tx-host
python3 tests/npu/test_cold_wire.py --source "$provider" --name fresh-tx-wire
python3 tools/build_npu_pair.py --output .local/npu-fresh-tx-pair --firmware-directory .build/merged-openwrt/build_dir/target-aarch64_cortex-a53_musl/linux-firmware-20260910/airoha
python3 tests/npu/test_checked_loader.py --source "$provider" --pair .local/npu-fresh-tx-pair --name fresh-tx-publish
python3 tests/npu/test_provider_session.py --source "$provider" --header "$header" --pair .local/npu-fresh-tx-pair --publication .local/npu-loader-publish-20261010/fresh-tx-publish/nominal --host-sender-receipt .local/npu-cold-pages-wire-20261010/fresh-tx-host/result.json --cold-commands --name fresh-tx-native
python3 tests/npu/test_npu_raw_pair.py --pair .local/npu-fresh-tx-pair --name fresh-tx-raw
python3 tools/build_firmware.py --name fresh-tx-world --jobs 8
python3 tools/verify_merged_image.py --name fresh-tx-offline
```
