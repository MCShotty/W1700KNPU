# INODE Plan Snapshot Candidate

2026-10-20. Implemented in the main working source; qualification is in
progress. This is not yet a successful original cold constructor or a new
packaged image. The full NPU implementation objective remains open.

## Failure And Change

Both preceding frozen callers failed at INODE preimage 217/1030 before an
original INODE store. A strictly restored default probe reproduced the exact
stop. Both failure PCs are in the same DMA-plan validator. Pure-function
measurements with the failed run's exact plan count 5,293 instructions for a
full plan check and 5,321 for the public recipe lookup, in synthetic calling
contexts. These are not whole-constructor or physical timing bounds.

The core now retains full geometry/owner validation, snapshots the complete
188-byte plan, and requires byte equality before each metadata, published-prefix
and preimage reader and after each successful read. Only bounded internal loops use the
private validated recipe. The public recipe API still performs its complete
geometry check. Existing full transitive owner checks remain around the read
sequences, including the late tail recheck before final local-owner comparisons.

The native private reader now authorizes only the literal identity metadata,
fixed ICV span and existing fixed flag span. It retains its opaque, running,
MSTATUS, null-output, width, alignment and fixed ICV-layout checks. It never
derives the authorized I/O span from unchecked mutable plan fields. The core
establishes the full plan at the read boundaries; this narrow view alone does
not establish geometry or ownership. No native count/time limit or progress
checkpoint changes. Plan/owner sizes, selectors and all 1030+6 effects remain.

## Evidence So Far

- Exact snapshot predicate: 378 host/RV32 cases, including each of 188 bytes
  changed before and after a read. Independent before/after guard-removal
  mutants are caught in both builds. Plans here are synthetic byte patterns,
  not geometry-qualified cold owners. Repeated unit runs are not extra coverage.
- Actual compiled fixed reader: 1,101 RV32 cases, 1,076 allowed / 25 denied,
  with exact reads, ABI and protected-memory checks. Explicitly synthetic
  running/plan globals select the view; no owner or SETUP is provisioned and
  no original constructor executes. Receipt `f90058b7`.
- Existing host core: 592 calls / 326 controls pass, preserving both full
  1036-effect projections and all existing late-owner rejection cases.
  The normal-object RV32 regression remains running; do not claim its result.
- All ten host INODE mutants are rejected. The type-109 omission operator is
  adapted to the new checked-reader call name, not removed. The first default
  120-second sanitizer run times out; a separately named 600-second host-only
  address/undefined/leak run passes. Original default/native limits remain.
- 96 unique focused units pass with no skips, receipt `8112a2fe`. The earlier
  35-unit run and repeated predicate cases overlap and are not added together.
- All22 normal RV32 archive objects compile. Two raw builds are byte-identical:
  CODE `658c9c329b34945ba196f60bafc09a81ed6f5f15011d15f632d8594f3c632392`
  (998988 bytes), DATA `3d821c93e8d298d57dee941b3b05e748551b527c3beb6c70b28d15c748e329a4`
  (25728 bytes), 20 components / 168 hooks. All20 image groups pass with the
  repeat pair supplied. An earlier no-compare invocation skipped only that
  repeat test and is not the all20 verdict.
- Actual provider checked-pair loader: 60 cases / eight mutants pass for the
  new pair. All six negative raw-boot controls pass. Actual-C publication
  readback reaches the eight-hart parked startup state. Neither check
  establishes successful cold INODE or physical containment.

The443-path partial preflight audit hashes
`5653ecea7cb5210fe4b47d6e5f04e683431a2be436c2b05f56377a84bc7f153a`.
Metadata-only `PREFLIGHT.json` hashes
`3ae6cf28a3ef96e9392d1d4a2f093fb989d3c9f3c5a128990fa4a56a7114eb0c`.
Its producing Git state is explicitly dirty at a4bb94d, with exact source
hashes; it does not identify the uncommitted code as already present in that
commit. Normal-object RV32 and original cold acceptance remain pending.

The normal INODE stack object matches the normal object's allocated and
relocation sections. Its largest individual frame is now4704 bytes; begin240,
prior-live480 and read-plan32. This is not a whole-chain/IRQ/per-hart/physical
bound. The older partial graph remains older-CODE-bound and is not requalified.

The proposed predicate's Jev checks returned Noul0.94/0.83/0.90/0.97 for the
before/after/owner-order/fixed-view wording. Physical-exclusion/coherence was
explicitly contradicted at1.0. These are narrow proposal judgments, not code
approval; uncertainty is retained and the actual compiled controls supply the
covered predicate evidence.

Fresh source/scope checks on the implemented code return Noul0.96/0.94/0.94
for the byte guard, retained public validation and late-owner ordering.
Fresh original cold completion remains `not_established`0.87/confidence0.80;
synthetic view-scope wording is supported1.0. Result SHA256
`bf3b7c036c264c0c8c827b42a0209509747e53e06114895bcebb173e48fbd25b`.
This new state does not erase the earlier proposal uncertainty or substitute
for pending runtime qualification.

## Next Gates

Finish the normal-object RV32 regression and remaining build/startup checks,
audit their exact source/binary receipts, then run fresh corrected both-HIF
actual cold callers with unchanged full sizes and budgets. Do not transplant
new code into an old captured prefix and call it a fresh proof.

The four frozen eight-DESC10/all36-tail fault jobs remain on older raw858d1408
in reader-controls-v1. Their results can only qualify that producing cohort,
not this new pair. Both original v3 callers remain failed. Current INODE
stage1/all24 faults and broader full setup/hot/IRQ/RRO/lifecycle/DMA/cache/
drain/recovery/original/indirect/stack/physical/boot/client gates remain.

The built633b4d71 FIT predates this optimization and stays protected along
with978f9ddd/a22300ea. Linux source-lockd6b6e2da/22 exported sources are unchanged;
the native INODE implementation is not one of those Linux exports. A new
whole-image qualification is required after this candidate is validated.
No flash, module load, radio change, hardware contact or subagents.
