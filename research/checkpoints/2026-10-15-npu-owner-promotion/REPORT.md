# Canonical PCIe Tail And INODE Owners

## Scope

The qualified portable PCIe-tail and INODE implementations, fixtures and original
store ABI probes now belong to canonical source/tests and the normal22-object
RV32 archive. They are not temporary alternate implementations. Real native
owner/guard/authenticated-history bindings for PCIe0/2/15 and INODE2/7 remain
open; the raw pair remains18 components/147 hooks. No router, flash, radio,
reset, reclamation or physical acceptance action occurred. No subagents.
Qualification here means the explicitly listed test scopes, not general
correctness, complete native admission or an all-green project regression.

## Producing Cohort Preservation

Before canonical edits,530 successful producing input/output files (31185536
bytes) were copied and individually hash-verified under
.local/npu-pcie-bind-20261014/producing-inputs-q1. Receipt SHA256:
e3a17791214ba919984d4e6393686ce5863d53dd8ae1a7cc3addfe5aa6c94ad2.
This is a bounded historical cohort, not a full execution environment. Historical
receipts continue to describe those preserved bytes, not later current sources;
no source rewriting or input-drift waiver is used.

Fresh actual-C allocator/caller run82479 is terminal0 through six API21 phases/
53260 effects, API22, DESC10 and RX PCIe. Both final stage comparisons cover all
856064 protected bytes. It preserves full_setup=false/prior_controls_skipped=true.
Receipt SHA256:
e1804169dddf00595c0ac70ddf28034450b17b1d32db823b37c531a8e6662750.
This is a fresh native prefix, not complete initialization or passing skipped
negative suites. All older native jobs are terminal.

## Canonical Implementation

- firmware/npu/cold-pcie-tail.c/.h and cold-inode.c/.h are byte-identical to
  the qualified staged source/headers and are included in the normal Makefile.
- Canonical drivers take --core-directory and link those exact normal-Os
  objects, retaining copies and hashes rather than recompiling substitutes.
- INODE and PCIe-tail fixtures are independent translation units. A fixture-only
  context accessor preserves the actual portable prerequisite APIs.
- INODE native comparison runs one actual effect per call with unchanged500M
  instruction/30-second limits. All1036 effects and142 controls remain present.
- A separate compiler stack-usage probe matches normal object allocated and
  relocation sections. Largest individual frame4688 bytes is not a complete
  caller/interrupt-chain or physical stack bound.
- The tested read-only PCIe reader checkpoint now belongs to ColdProviderRequest.
  Native guards and finite instruction/checkpoint/state bounds are retained.
- Image verification now requires every archive member exactly once with bytes
  matching the verified normal objects. Harmless fresh/incremental member-order
  differences are not treated as object differences or reproducible archive hashes.

## Deterministic Qualification

| Scope | Result | Evidence directory |
| --- | --- | --- |
| PCIe-tail host/RV32 |446 calls/376 controls each, both profiles | .local/npu-pcie-tail-owner/canonical-{host,rv32}-q1 |
| PCIe-tail faults/sanitizers | Seven compiled mutants killed; ASan/UBSan/leak pass | .local/npu-pcie-tail-owner/canonical-mutants-q1 |
| INODE host/RV32 |382/2312 calls,142 controls each, both complete profiles | .local/npu-inode-owner/canonical-{host,rv32}-q1 |
| INODE faults/sanitizers | Eight compiled mutants killed; ASan/UBSan/leak pass | .local/npu-inode-owner/canonical-mutants-q1 |
| PCIe original stores/ABI |42 cases/nine sites, explicit guard stubs | .local/npu-pcie-tail-store-abi/canonical-q1 |
| INODE original stores/ABI |120 cases/eleven sites, explicit guard stubs | .local/npu-inode-store-abi/canonical-q1 |
| Original INODE lookup/prefixes | Four nominal/1036 synthetic pre-store cuts | .local/npu-owner-promotion-20261015/original-inode-prefixes-q1.json |
| Final host IRQ contract |21 actual-C modeled cases,12 write errors still lost | .local/npu-final-irq-contract/canonical-q1 |
| Focused observer/oracle/header/archive units |61 pass, including seven archive controls | tests/npu/test_npu_core_archive.py and related observer tests |
| Repeated raw pair/image groups | Two current-input builds/all18 groups pass | .local/npu-owner-promotion-20261015/pair-{q1,q2} and pair-verification-q2.json |
| Source reconstruction |70 OpenWrt/5 LuCI and header closure pass | .local/npu-owner-promotion-20261015/source-export-q2.json |
| Complete world | terminal0 | .local/merge-nonoc-20260923/build-owner-promotion-q1.json |
| FIT/board/packages/modules/core |218 packages/78 module ABIs/22 exact archive objects | .local/merge-nonoc-20260923/owner-promotion-image-q2/result.json |
| Current provider session |609 cases/nine compiled mutants/sanitizers pass | .local/npu-provider-session-20261010/owner-promotion-q2 |
| Current cold wire |1436 cases/45 compiled mutants/sanitizers pass | .local/npu-cold-wire-20261010/owner-promotion-q2 |

All jobs are terminal. Broader raw12172 is terminal1, not passed. Six boot controls,
2560 RX claims and1792 BA claims complete, then its later modeled TXDONE lease
is rejected before any descriptor stores or ready write. The fixture manually
sets ADM active and ring metadata, then directly calls8400fe34 without the current
authenticated RX/API22/DESC10 prerequisites. Exact first failed condition was
not captured, so this source-based explanation is not a captured guard-PC trace.
Final input closure and later controls were not reached. Do not weaken admission,
discard full512-store/fault coverage or relabel this as a passing full raw run.
Move that regression onto the actual retained caller history. Its terminal row
and limits are recorded in .local/npu-owner-promotion-20261015/raw-regression-failure-q1.json.

Current provider/wire q2 receipts were rerun after firmware README changes,
because their explicit input maps include that non-executable file. No such
source-drift exception was added. Qualification status rechecks299 current
inputs/14 passing scoped receipts, all owner/mutant/ABI/generated IRQ binaries,
22 exact normal/world/archive object bytes,530 historical files, eight protected
prior-image files and61 units. It deliberately has no ambiguous all-passed flag:
canonical_portable_build_image_checks_passed=true,
broader_raw_regression_passed=false and full_npu_goal_complete=false.
Artifact .local/npu-owner-promotion-20261015/qualification-q1.json SHA256:
c75a3f8cb55206156cdeb2a481502b6475dd6440b07abc249222c6a34c5b5ddc.

Actual Jev1.13.0 selects insufficient-legacy-fixture at1.0/confidence1.0 and
implementation-and-validation at1.0/confidence1.0; full-raw-pass0.02,
new-native-admission0.06 and observed-physical-IRQ-error0.03. The portable-scope
claim is less decisive (supported0.71/confidence0.56), so it remains explicitly
limited to the deterministic test rows above. These judgments are not proof,
execution traces or authority to change native admission. Raw request/result
remain local beside the status artifact.

PCIe canonical RV32 receipt SHA256:
5c2f0b707e74447290ee76be01185b6834e6474aa78d2a0909ff6a70a20bc322.
INODE canonical RV32 receipt SHA256:
cd04fb29f1645d5b60f18b3681eb06143369b8e42c8d16d670b56765ba6e06ba.
Original-store ABI receipt SHA256 values:
bcc30a486b60168bf8f6dc791ca1e4caf9bdcb033d6d4dc6dd134a5d18e11f75
and73210b2e4ae7863258b900372be398cd2dbfbd2178463df3207954398cd68414.

The initial repeat comparison against historical pair-q4 failed strict input
manifest equality, as new source/fixtures and a different original-pair path were
included. All shared input hashes and CODE/DATA bytes were unchanged. A second
independent build from the current inputs passes exact manifest and binary
comparison. The failed report remains local; no verifier was weakened.

## Unified Unflashed Image

FIT .build/merged-openwrt/bin/targets/airoha/an7581/
openwrt-airoha-an7581-gemtek_w1700k-ubi-squashfs-sysupgrade.itb is26997578 bytes.
SHA256:
1aa174996f9d036d360f027234743a5cd5fd182fd21c820f01a9372a057bb714.
Actual DTB model: Gemtek W1700K (OpenWrt U-Boot layout), Linux6.18.52.
Provider SHA256 remains:
1a001dc25cf6882716fa63b8490cc2440d2c028f0405a4254c13ac660663784f.
The prior69c88ce9 image and seven companions were copied and hash-verified under
.local/npu-owner-promotion-20261015/protected-fit69c88ce9 before world.

Raw CODE937828 bytes/SHA256:
eea4cfc6ed5032d1556894a666de9245ca484626c538e2b8d667e72895936aae.
Raw DATA25728 bytes/SHA256:
8fb7ca09bdf581035bc24f85965e43a046de3f333d20eedfd296f2cf4a0dea9d.
Source-lock SHA256:
5fdb8df36cbab92ba9e45155ccb2c03c0bf9afd1a295f22e14eac0a02ee22d7f.
The fresh and incremental archives have different member order, but all22
standalone/member object bytes match. This is offline/software evidence only.

## Next Full-Goal Work

1. Migrate the broader raw regression from its insufficient legacy lease to actual
   retained RX/API22/DESC10 caller history, preserving full512-store and negative
   coverage. The existing failed run remains failed; no guard bypass is permitted.
2. Bind the remaining nine PCIe stores to real retained owners, exact typed spans,
   session/BAR/nonce, original lock18, masked IRQs, neighbors, frame/readback and
   explicit authenticated successor history. Do not forge older SETUP state.
3. Bind all eleven INODE stores, exact fixed109 definition/full4104-byte backing
   and retained ICV/flag neighbors. Require actual site execution for idempotent
   stores; callback return1 or matching readback alone cannot prove execution.
4. Extend actual server/client/prepared-provider ordering and fresh full-caller
   success plus early/late failure, reply, HIF and native mutation coverage.
5. Implement the separately traced checked final host IRQ contract, including
   hot NAPI re-enable, lifetime/order, readback and retained ambiguous effects.
   Partial IRQ failure never authorizes resource release or physical drain claims.
6. Complete worker/hot TX/RX/packet/completion/refill/reorder ownership, physical
   backing/cache/exclusion and full DMA/worker drains, reset/removal/rearm/recovery.
7. Verify latest exact-image boot, actual clients/Wi-Fi/MLO, throughput and sustained
   memory/resource/fault recovery behavior. Full stock parity remains incomplete.

Exact native contracts: ../2026-10-14-npu-pcie-tail-owner/NEXT_NATIVE.md,
../2026-10-15-npu-inode-owner/NEXT_INODE.md and NEXT_IRQ.md. This checkpoint does
not narrow or complete the full NPU reverse-engineering and implementation goal.
