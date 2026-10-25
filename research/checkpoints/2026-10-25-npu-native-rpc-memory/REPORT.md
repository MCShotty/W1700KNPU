# Native Metadata Observer And First Publication

Continued solo from `addd5de`. Scope is host callback qualification and actual
RV32 first-publication progress, not complete native replay or W1700K hardware.
The full NPU reverse-engineering/implementation goal remains active.

## Implemented

Host observer profile4 adds a source-bound metadata memory callback to the
existing read API2 extension. It is installed at the original registration
positions. During RPCs, ordinary CODE/SRAM reads return exactly as the reference
does. Payload and DMA/table exclusions take precedence. Unmatched/protected
accesses and inactive callbacks retain the original parent chain.

Eligible metadata writes use the current `rpc_writable` tuple and Counter,
freshly read SP before counting, preserve min-SP and increment on every callback.
I/O remains delegated to the original Pair methods, retaining scoped extent,
IRQ/active-owner, digest and fault-injection checks. No guest data value is
cached; no firmware instruction or ownership check is removed. The previous
instruction/block observers and their count/CSR/SP obligations remain.

The profile remains explicit, source-bound, Linux x86_64/CPython3.14/Unicorn2.1.4,
single-engine/thread, GIL-attached emulation. The default CLI backend is still
reference. Production firmware, mt76 patch, source lock and modules do not change.

## Executed

- `rpc-memory-build-q16`: plain and UBSan each pass32 read/CSR and37 observer
  units, zero failures/errors/skips. These are69 unique methods repeated across
  variants, not138 unique tests. Thirteen metadata cases extend the prior24
  observer methods, including actual RV32 memory/hook transcripts with fresh
  host injection and direct callback IRQ/owner/refusal/injection/range behavior.
- `rpc-memory-controls-q21`: eleven independently compiled broken adapters each
  fail exactly their intended assertion, with no errors/skips. Four new controls
  bypass memory exclusions, reuse stale metadata SP, coarsen write counts, or
  count before SP failure. Seven prior instruction/block/API controls repeat.
- `rpc-memory-finite-q17`: both actual raw reset traces execute19517 instructions
  and match40 mapped regions, compared registers, CSR/MMIO/events and counters.
  Transcript SHA256 is
  `8add6704554cdb085bd6dd4bb31a559abe4de0e29625ed266402b7da5ceb80a8`.
  A separate deterministic check proves the reduced owner is exactly Pair,
  has no effect override, and `h.effect.__func__ is Pair.effect`; three direct
  refusal/injection/boundary tests repeat. These add no unique test methods
  and are host callback tests, not physical or additional guest executions.
- Fresh broader tooling/checker suite passes167 with zero skips. Prior selected
  kernel/module producers are revalidated, not rerun as part of this work.

## First Publication Now Passes

Fresh `rpc-memory-probe-q9` and `probe-q18` each complete the actual profile2
raw prefix with1136899 observed instructions,1131289 fast/5610 reference code
dispatches. Retained plan/discovery/status/server/cold enrollment and the first
138 RPCs plus two cold-gate records match after removing only timing.

Both then complete the first PUBLISH, giving139 positive RPC/oracle journal
comparisons. Each observes7438798 blocks,760661 metadata writes,515 payload
reads, one mailbox veneer/binding, one table write, two table reads and exactly
24576 extent writes AND24576 readbacks. Complete broker journal, all DMA/SRAM
and code comparisons pass. Completed transcripts agree across both probes.
Publication walls are53252729911ns and54105626699ns, within the unchanged60M-us
deadline. This is not general performance/stability acceptance.

The publication write digest is
`7e2dc8facc3964f3e5ea108336975b68255d216be9790c96a755419e64aeb23e`;
rolling transcript digest is
`1a54c8045ff71e4d388ba6e87e3714d3190bd690da7c74f11356afe6df1158b4`.
All raw-boot calls retain3M instructions/10M-us and RPCs retain100M/60M-us.
The unanswered longer-boot proposal was not used. Earlier failed native q3 and
supplemental q12/q17/q24 remain failed and preserved, not relabelled.

## Retained Failures And Semantic Checks

Build-q3 failed two reference fixture cases because the reduced Pair lacked
its constructor's retained list. Exact constructor state was added; no refusal
was weakened. Controls-q20 caught ten mutants but its final generator also
inserted a count into the read branch, so Werror rejected uninitialized use.
The corrected q21 targets only metadata writes and freshly completes all11;
compiler flags and failed evidence remain unchanged.

Jev supplied nine source-obligation and nine implementation judgments. Its
I/O-delegation answer0.17 prompted direct actual-effect tests and deterministic
function-identity verification. Four focused follow-ups give delegation0.91,
actual-effect-test0.53, refusal-assertion0.86 and physical sufficiency0.08.
Keep that uncertainty and the earlier disagreement. Source inspection, exact
identity, executed positive/negative cases and compiled controls establish the
host behavior; model confidence is neither a test nor execution authority.

## Full Replay And Remaining Goal

The next phase is a fresh complete three-profile19261-RPC recipe,387 publications
and6150 reset/MCU pairs, including its existing transport/identity/fault controls.
The prepared full-q31 wrapper requires the published clean checkpoint and qualified
receipt, preserves all native budgets, directs output to C scratch, and checks
the complete driver result. The background dispatcher changes only waiting and
acknowledgement around the existing resource guard: same400MiB/no-swap, C lock,
fresh dual backing/RAM margins, old compact1GiB future allowance and bounded
output. Exact live guard/child argv and cgroup caps are verified. Missing/timed-
out observations are not terminal results or authority to restart the job.

This checkpoint proves first publication, not the complete recipe. Inspect
`w1700k-npu-rpc-memory-full-q31.service`, its actual processes and final receipt
before any complete native claim. Neither old original replay was restarted.
Keep the source-bound inputs frozen while the full replay is live.

Five complete protected source/cache inventories, inherited57349 project flat
bindings, three external inputs,48 selected runtime external bindings, consumed
source/doc versions and aliases remain separately bound. Firmware source lock
`88502ab3798b2ccdf01e6fd3c8779bcd2ad0f24a970c080f97ac9992b97f740a`,
mt76 patch `bb4579282feedf23edbe09007eb7b1566ffc96dceb39e49984ddc7a1cbaa2e71`
and four-module producer
`a840d3cccb1d0bd8cc60a856d1a1bb9723dfc05af73484d955a33978a458d22f` stay.
No router image, module load, router contact, calibration/recovery write or flash.

Full target/physical cold MCU-exit failure and queue/page-pool retention/drain,
current-firmware BA reuse, hot admission/retirement/rearm, current image/router,
actual clients, performance and stability remain. Coherent mappings, PLIC/IRQ
delivery and MCU replies are models. CPU joins or raw RV32 execution do not
prove physical DMA retirement. Full project completion remains unproven.
