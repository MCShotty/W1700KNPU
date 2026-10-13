# Retained RX Enrollment And API22

Status: the selected actual-C/original-RV32 scope passes. Full NPU implementation
is not complete; physical backing and runtime acceptance remain unproved.

## Implemented Scope

Actual provider allocation enrolls eight retained mailbox handles plus the
actual512x16 RX-event ring before queue outputs. Later TX allocation appends
six retained handles. Lost replies preserve both native and host prefixes and
never expose outputs or authorize retirement. Selector0/API22 checks the exact
retained handle and completed14-record/eight-GET/six-API21 history.

The152-byte one-shot owner pins a120-byte RX/prior plan, reserves the exact
metadata preimage and retains a possible effect before the original4-byte store
at8400b5ec into3e903964. Neighbor/readback and full previous owner/effect checks
gate success. The original helper's s1/s0/ra frame is restored on rejection;
the outer original wrapper's unconditional1 cannot override sticky failure.
Original lock18 and masked IRQs protect the software callback. No reset,
rollback, drain permission or resource-retirement API is added.

## Completed Checks

- Exact compiled RX owner:487 host/RV32 calls,211 controls,12 success paths,
  seven mutants and address/undefined/leak sanitizer smoke.
- Actual allocation/queue C:166 cases/seven mutants; eleven delivery positions
  and early/late record/identity/plan/cache changes retain backing and outputs.
- Wire/server/client:1320 cases/34 mutants, including70 RX-specific cases.
- Seven regressions and21 nonzero unit tests pass. Source export verifies69 files.
- Raw16 components/126 hooks/archive18/private388 build normally. Independent
  raw builds are identical; all16 assembly groups pass. CODEc6548555/DATAe0495a5f.
- Full raw compatibility regression passes3072 PKT/1792 BA/six boot/eight TXDONE
  controls. Its later TXDONE lease/ring metadata are expressly modeled; an
  unowned direct API22 call now rejects before metadata changes.
- World and board/FIT/218-package/78-module checks pass. Ghidra decompiles61
  functions, covering all43 named executable ELF functions, with zero failures.
  REA independently inspects the372-byte message-routing body, untruncated.
- Eleven completed receipts/290 current input hashes verify without exceptions.
  Checkpatch:zero errors,three line-length warnings; not a strict-style pass.

## Native Test Scope

Session47388/PID673535 is terminal0. The actual provider allocator/client,
mt7996 caller and original raw RV32 peer pass15 mailbox/RX/TX enrollment records,
all six API21 phases/53260 effects/76 controls and API22 metadata/30 native
controls. Nominal execution changes only the exact metadata word within full
SRAM/heap/L2 comparisons, preserving earlier owners and neighboring bytes.
After-store held/readback/neighbor/TX-effect failures retain1/0 committed/published;
after-publication readback/nonce failures retain1/1. All deny outer success.
No tested rejection reaches an unowned address. Earlier q1/q2
runs were intentionally stopped for harness corrections, not observation
timeouts or API22 failures. Local interruption notes preserve that distinction.
The actual sender's next DESC10 rejection is an explicit -95 test stub, not an
executed authenticated initializer or production-readiness proof. The final
stdout summary retains a legacy14-record label; JSON/early trace correctly say15.
Three source line wraps and that diagnostic label remain cleanup for the next
proof cycle. No zero-warning style pass is claimed.

Jev's broad software-qualification check was moderately confident(.56), so the
exact executed assertions and reply were inspected. A focused scoped test claim
then scored supported(.94 confidence). Raw probabilities are retained; neither
judgment supplies physical authority or substitutes for the tests.

## Artifact Identity

- Unflashed FIT:82b1563a809b7c5a2b7872fde908e2d16b261e1f40306090f73a93ae498d19f7,26985290 bytes.
- Packaged provider:f163e26ed76787f8479243f4f93db84e9f44e4a73517c227b372d884983aba9c.
- Raw CODE:c6548555ef62323ea0bea98c19557fc960f814a7ae89e8939287cdb35aa3610e,854172 bytes.
- Raw DATA:e0495a5fe08275645f7aa6594560c9f959a0cc2b59727a4657eaae83bdfbd516,25728 bytes.
- Source lock:97374b47bd02b752b474cc32bd8ac8681175930eae056573fb94788609145853.
- Previous f185a731 image and seven companions are checksum-protected in
  `.local/npu-rx-event-bind-20261013/pre-api22-image/`.

No hardware, RF, flashing, reset, private-backup or subagent action occurred.
These are software/model/static/build checks, not physical DMA/exclusion/
coherency/drain/recovery or actual-client evidence. Finish native API22, then
authenticated DESC10/shared PKT/TXDONE/SKB, exact PCIe/INODE/final IRQ and all
remaining ownership/lifecycle/hot/physical/recovery/boot/client gates. The full
goal remains active. Scoped receipts are sealed with their hashes; local builds,
raw modules/images and private protected material are not uploaded.
