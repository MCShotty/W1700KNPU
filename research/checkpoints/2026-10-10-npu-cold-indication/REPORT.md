# Retained Cold Indication And ACK Metadata

Date: 2026-10-10. Canonical WSL workspace, mainline experimental source. This
checkpoint advances the full NPU reverse-engineering/implementation objective;
it does not complete that objective or establish stock parity. No router
contact, physical reset, hardware write or flash occurred.

## Implementation

The new `cold-indication.c/.h` owner is the14th portable archive object. Its
32-byte state retains a one-shot1536-record/12288-byte reservation, committed
and published prefixes, epoch and fault. It requires fresh zero records, reserves
each original8-byte record before read/store, checks the pending status value and
readback, then validates the entire `[0,0xe0000000]` array before success. The core
never performs the record stores. Faults never clear claims, retire the span,
recycle records or enable reinitialization.

The native adapter acquires original allocator lock18 before selecting the
unique type1 WLAN-arena reservation. It checks the original type6 subregion
offset0x1f020 and arena definition303168, snapshots count/used, reservation
identity and existing session/sequence, then calls the original selector8 body.
Hooks at0x8400bb10 and0x8400bb1a precede original record reads/stores. Every guarded
access rechecks the held bootstrap/parked/ready/drain/deferred state, allocator
snapshot, immutable plan and SRAM ring pointer. Denied acquisition never unlocks;
owned failure releases the software mutex but retains claims and the outer
active/inflight lease. Neither the modeled grant nor its release is DMA authority.

Cold private history grows64 to104 bytes by retaining all five RX/page counts
and completion snapshots. Indication address requires the full1536/1024/256/
512/1024 profile; DESC8 requires exactly1536. Ordered new commands are BAR0+
0xa040 indication address, indication DESC, then BAR0+0xa050 ACK metadata. The
80-byte NCS2/NCR2 envelope, existing provider boot/nonce and V2 sequence are
unchanged. No new session, reset owner or physical permission is created.

The checked provider routes DESC/address selector8 and API19 selector3. Original
selector3 only stores the ACK address at0x3e904610. Selectors0/2 also call the
TX initializer, which resets native indices and writes DMA base registers. They
remain unsupported on the strict path. Raw legacy functions and early probe
version dispatch are unchanged; unmarked profiles keep their earlier behavior.

The raw pair has63 hooks and twelve linked components. NOBITS sizes are104 for
the cold history,4 for allocator bridge state,1172 for page/indication state and
2120 for packet state. The portable archive remains a component library, not a
standalone bootable firmware image.

## Verification

- The exact world-built indication object passes12,322 host/RV32 calls,3,095
  controls and seven rejected mutants. Host address/undefined/leak sanitizers
  cover freshness, pending claims, readback, partial finish and fault retention.
- Actual provider C545/nine initial-session mutants and six BAR mutants pass.
  Cold server/codec/client C425/thirteen mutants include112 geometry,72 order,
  19 late-state,38 held-state,128 bad-length,20 request/reply,8 transport and
  five partial-profile controls. Three actual mt76 publication cases pass.
- Actual current txrx sender C invokes actual provider/client C into the checked
  raw RV32 pair using actual-C-published CODE/DATA. Nominal retains2,560 PKT/
  1,792 BA claims and all1536 indication records, with exact full array/status,
  unchanged packet/BA state, fifteen firmware-derived lease pairs and ACK SRAM
  readback. No synthetic active grant or direct owner initializer is supplied.
  Next TX0/API19 is denied with no native callback and completed-prefix16383.
- Five end-to-end cases pass: nominal, wrong boot identity before setup, first
  packet-claim fault, first BA-claim fault and first original indication-store
  fault. The last retains one committed/zero published record,2,560 PKT/1,792 BA
  claims, completed-prefix4095, sticky faults and active/inflight1. No rollback,
  resource release, new transport after close or new session is allowed.
- Thirty-four native controls pass from the actual-C pre-DESC8 snapshot:19
  reservation/lock/freshness controls and15 late metadata/identity/history/
  plan/worker/drain/deferred controls. Failed acquisition never releases lock18;
  acquired controls release it exactly once. All deny record stores, and late
  cases retain one unpublished claim. Snapshot restores are test-only and cover
  private CODE history, not a production reset or ownership-reinitialization API.
- Separate full raw replay passes3,072 PKT/1,792 BA claims, six boot and eight
  TXDONE controls. Its later direct lease/publication remain explicitly modeled.
- Parser60/eight, boot248/ten, lease13/four, probe269/three, request310/nine,
  memory273/159 with three original controls/nine mutants, retry6,174 and V2
  44 cases pass. Thirteen builder, four export and four module-ownership unit
  tests pass. Sixteen assembly groups pass without skips; independent and world
  raw builds have matching source-input maps and identical CODE/DATA.
- Full world exits0. Sixty-six top-level source files reconstruct, twelve nested
  kernel/mt76 files and thirteen provider components match compiled source.
  Actual W1700K FIT model/compatible/layout,218 packages and78 module ABI checks
  pass. Ghidra exports all54 exact packaged-provider functions, zero failed
  decompilations and no timeout. Strict driver-delta checkpatch has zero errors,
  warnings or checks; the previous three alignment checks are cleared.

The first native indication run exhausted the unchanged emulator wall budget;
the corrected observer yields at each existing guarded read rather than relaxing
the budget. One locked-pair compile attempt caught a mistyped domain macro, fixed
before qualification. The first new negative replay omitted the CODE-resident
cold history from its snapshot and correctly received a replay denial before
reaching the adapter. Its corrected full suite is the sealed receipt. None of
these failed attempts is counted as successful verification.

World still has upstream/package warnings and the previously seen ignored U-Boot
install error. This is not a warning-free build; complete FIT/package/module
verification is separately recorded.

## Semantic Review

Actual Jev1.13.0 design classifies indication records and failure retention with
confidence1.0; count-only ownership and physical-authority Nouls are0.07/0.05.
TX-register side effects are selected with probability0.65/confidence0.48, then
inspected against the original Ghidra body.

The eight-claim broad review returns six supported, one contradicted and one
not-established label. Before-access, full-profile and ACK claims are uncertain:
support0.44, contradiction0.45 and not-established0.44, respectively. Three
smaller source batches return read/store support1.0/0.76, full-profile/DESC support
0.94/1.0 and original ACK support0.79. The checked-routing claim still returns
contradicted0.56 with confidence0.34. Raw distributions, prompts, latency and
usage are preserved; these results are not unanimous approval or proof.

Codex checked the material uncertainties against exact source and tests. The
read hook branches to original failure on zero reserve; the store hook requires
pending ownership and publication success before original-loop continuation.
`begin` compares all five counts to limits before ADDR8; subsequent history and
DESC8 checks enforce the exact profile. The actual enum/sender produces API19,
whose checked wrapper routes only index3 to the cold envelope; other indices
fall through the unchanged raw sender. Native strict dispatch denies the next
TX0 request without invoking its callback. Original selector3 only stores ACK
SRAM, while0/2 call the register-writing initializer. C/native controls and exact
compiled artifacts, not semantic labels, support these model-scoped claims.

## Artifacts

- FIT26,960,714 bytes:
  `8dd1f2f4d62fbc9f8cf8061ead435527e01d85bcf90d0b05f3f6e4da0b1f16d9`.
- Packaged provider:
  `e409ad88ff976af54fad70d209ee70a14252502aec80fb34aad6bbe1254fbbb9`.
- CODE529528 bytes:
  `2fc23c7e095240ee39755944979290e439de603a698f30d4b0634ac689d96355`.
- DATA25728 bytes:
  `3e8d62db557ce5183cce23a173601e610b38bcbba7980481a49bc61fc9b21b2e`.
- Fourteen-object archive:
  `ee86953a56f524a98353748045b0df0e8e5bcce2253aabb3b9cb45bc7f467ecb`.
- Source lock:
  `319c4c22fbd6fc11ad6304f032ddba26bf279630b049b0fa0fb227a951685d4e`.

The previous complete FIT `5c94b20d...` and seven companion files are preserved
and hash-verified in ignored `.local/npu-cold-indication-20261010/pre-world-image/`.
Earlier/R1 images, calibration/bootloader/private backups remain protected.
No image is flashed.

## Remaining Scope

Next implement the strict TX0/TX2 register contract and remaining TX-token,
RX-address, INODE, TXDONE and final register/IRQ setup. Existing later/full raw
TXDONE regression uses an explicitly modeled direct lease; it is not the missing
full strict host setup lane.

Backing, mailbox delivery, host pointer publication, queue state, IRQ grants and
worker scheduling in native replay remain modeled. Independently establish actual
prior-user exclusion, exclusive backing/cache/DMA coherency and engine coverage.
Complete other owners/workers/hot/postgate, physical drains/retirement/teardown/
rearm/recovery, exact-image boot and actual clients. A software lease, BAR bound,
parked snapshot or retained claim never authorizes physical resource release.

## Reproduction

Use fresh names in ignored storage and immutable source/header copies while
world replaces its prepared trees. From canonical WSL:

```sh
export PYTHONPATH=.local/npu-reset/python-lib:tests/npu
provider=.local/merge-nonoc-20260923/kernel-merged/drivers/net/ethernet/airoha/airoha_npu.c
header=.local/merge-nonoc-20260923/kernel-merged/include/linux/soc/airoha/airoha_offload.h
make -C firmware/npu OUT=/home/captain/W1700KNPU/.build/merged-openwrt/bin/npu
python3 tests/npu/test_cold_indication.py --core-object .build/merged-openwrt/bin/npu/cold-indication.o --name fresh-indication-core
python3 tests/npu/test_cold_host_prefix.py --mt76 .local/merge-nonoc-20260923/mt76-merged --name fresh-indication-host
python3 tests/npu/test_cold_wire.py --source "$provider" --name fresh-indication-wire
python3 tools/build_npu_pair.py --output .local/npu-fresh-indication-pair --firmware-directory .build/merged-openwrt/build_dir/target-aarch64_cortex-a53_musl/linux-firmware-20260910/airoha
python3 tests/npu/test_checked_loader.py --source "$provider" --pair .local/npu-fresh-indication-pair --name fresh-indication-publish
python3 tests/npu/test_provider_session.py --source "$provider" --header "$header" --pair .local/npu-fresh-indication-pair --publication .local/npu-loader-publish-20261010/fresh-indication-publish/nominal --host-sender-receipt .local/npu-cold-pages-wire-20261010/fresh-indication-host/result.json --cold-commands --name fresh-indication-native
python3 tools/build_firmware.py --name fresh-indication-world --jobs 8
python3 tools/verify_merged_image.py --name fresh-indication-offline
```
