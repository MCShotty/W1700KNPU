# Portable DESC10 Owner

Status: the selected portable compiled-C/RV32 scope passes. Full NPU
implementation and acceptance remain incomplete. Work began on October 13;
this checkpoint is recorded on October 14 in the user's Asia/Riyadh timezone.

## Changes

`firmware/npu/cold-txdone.c/.h` adds a136-byte plan and13512-byte one-shot owner
to the normal portable Makefile, now19 objects. Begin requires the finished
RX-event owner with matching plan/readback and an intact2560-claim PKT prefix.
It retains that bitmap and independently budgets512 further claims, including
committed claims whose native queue-head publication did not complete.

The ordered recipe owns25606 possible stores: count and typed ID-pool pointer,
six stores per descriptor/ID, temporary sentinels/occupied IDs, SKB state clear/
mark/ordered queue, head/tail, counter and ready byte. Reservations retain a
possible effect before writing. Address, width, value and readback gate
publication. Failed prefixes are never reset, rearmed or retired.

The original constructor sites were checked against the pinned CODE bytes with
Capstone. This is static evidence of the selected stores, not dynamic execution,
new native hooks or hardware behavior. Native caller contracts still include
original locks, exact typed allocations, immutable TX descriptor inputs, prior
owner liveness, appropriate mapped backing and coherent readback.

The earlier three provider line-length warnings and hard-coded native stdout
record count are corrected. Reversing the three formatting edits exactly
reproduces sealed source SHA256
`5f8b768b9ad1a9f1d3bbd71c0597c983131a71756f321a8b524d04485d268ff3`.
Strict checkpatch with `--no-tree --strict --no-signoff` reports zero errors,
warnings and checks. The stdout expression is checked for14 and15 records;
the complete old allocator/caller replay was not rerun for this diagnostic edit.

## Verification

- Exact `-Os` object from the normal Makefile:3656 compared host-C/RV32 entry
  calls,3541 controls, eight killed mutants and ASan/UBSan/leak checks pass.
  Three DMA aliases, all3378 owner words for dirty reinitialization, full
  logical memory and all ordered address/width/value events are covered.
  Batches compare full state at15 phase checkpoints; the fixture checks each
  portable API return during each batch. Entry-call counts are not a count of
  every nested portable API invocation.
- Finished RX owner regression:487 compared calls,211 controls, twelve success
  paths, seven mutants and sanitizers pass using its normal compiled object.
- Independent current-input raw builds are identical. All16 image test groups
  including repeat-build, exact hooks, linked symbols, preimages, sections and
  byte readback pass. The new portable owner is not in the raw dispatcher.
- Source export verifies64 OpenWrt plus five LuCI files. The final source-lock
  SHA256 is `512dd84da3f4630c3e5ec2d359726dbdbdaf3dedc5ccf2f69e4c15c4760ac2bc`.
- Five completed receipts and210 distinct current input hashes verify without
  exceptions. The verifier also checks exact archive membership/object bytes,
  test binaries, mutant binaries, unchanged image and diagnostic expression.
- Jev performed bounded claim checks. Its broad source-only review was
  uncertain/conflicting on some invariants; focused actual compiled cases
  establish the tested active-RX, ready-only and retained-failure behavior.
  Focused semantic review preserves uncertainty and rejects physical-runtime
  claims. Jev results are not treated as proof or action authority.

Early q1/q2/q3/q5 runs ended with explicit failures, not timeouts: fixture
constant materialization emitted an unresolved memcpy; fixture PKT/TXPKT
geometry was mixed up; a reinitialization test assumed the wrong rejection
code; and an invalid-address control accidentally reused its valid own base.
These were corrected before q6. q4 passed an earlier diagnostic test version;
only current q6 and the named current regressions are used here.

## Unchanged Image

No new world image, AArch64 provider/Ghidra run, full original allocator/caller
or original native DESC10 replay is claimed. CODE/DATA remain:

- CODE `c6548555ef62323ea0bea98c19557fc960f814a7ae89e8939287cdb35aa3610e`,854172 bytes.
- DATA `e0495a5fe08275645f7aa6594560c9f959a0cc2b59727a4657eaae83bdfbd516`,25728 bytes.
- Raw16 components/126 hooks and private cold state388 bytes remain unchanged.
- Existing unflashed FIT
  `82b1563a809b7c5a2b7872fde908e2d16b261e1f40306090f73a93ae498d19f7`
  is hash-checked unchanged. Current source is ahead of that image.

## Remaining Work

The new owner has no native instance or callback binding. Authenticated DESC10
still denies. `NEXT_DESC10.md` records the original store sites and concrete
integration work. Do not weaken the existing2560-claim prior-owner check into
trusting an arbitrary current PKT count, or reuse a test-written callback lease
as evidence of actual cold setup.

PCIe/INODE/final IRQ, remaining owners/workers/hot paths, physical backing/
exclusion/coherency/drains/retirement/removal/rearm/recovery, exact-image boot
and actual-client acceptance remain part of the original full objective.
No router contact, flash/reset, Wi-Fi/power change, private-backup change or
subagent occurred. The goal stays active.
