# Native Cold Observer And Profile2 Prefix Progress

Scope: host-only observer implementation and actual raw RV32 diagnostic progress,
not complete NPU replay, target-driver lifetime or physical W1700K acceptance.
Continued without subagents from `6e9a0c1`; the full NPU goal remains active.

## Implemented

The explicit cold-observer profile uses the same loaded Unicorn C API and
source-bound build receipt. It replaces the reviewed ordinary-PC Python hook
chain at its original registration position, not guest instructions. Every
observed PC count and tick remains. MSTATUS/MIE/MTVEC and applicable instruction
words are freshly read; CSR record order and the existing MHARTID substitution
remain. Stop/skip-once, dynamic allocation returns, interesting PCs, active
tracking/RPC modes and changed metadata use the original callback chain.

The block adapter handles only eligible cached RPC blocks. It increments every
block and cached-site counter, fetches the current per-RPC Counter, and reads
fresh SP on every hit. Cache misses delegate the original byte/range/forbidden-
PC/capacity checks. Static field-name keys are interned; guest CSR, SP and
instruction values are not cached. Existing reference block-cache semantics
are retained, not replaced with a coarser observer.

The emulation bridge calls the same native entry while holding the caller GIL,
for a qualified single-emulator-thread profile. It forwards exact valid unsigned
arguments, clears stale callback exceptions, preserves backend-error priority
and callback exception identity. Count/native-timeout tests execute; this does
not establish general multi-threaded Unicorn compatibility. The read API stays
version2; the opt-in observer profile is version3.

The replay CLI adds `--native-cold-receipt` and `--output-root`. The default
remains the reference backend. Explicit output roots must already exist under
project `.local`, be writable/unaliased, and use native Linux storage. The Pair
class and boot/compare/effect/reply bodies remain byte-for-byte unchanged as
Python AST source segments. No frozen pair/oracle input assertion was waived.

## Executed Evidence

- `cold-observer-build-q23`: plain and UBSan each pass32 existing read/CSR and24
  observer tests, no failures/errors/skips. Repeated variants are56 unique test
  methods, not112. New tests execute RV32 fixtures and dynamic host injection.
- `cold-observer-controls-q28`: seven separately compiled UBSan adapters each
  fail exactly one intended assertion, with no errors/skips: coarsened PC count,
  omitted fresh CSR, discarded timeout, omitted dynamic return, omitted block
  count, stale SP and bypassed block-cache miss checks. Canonical source stays.
- `cold-observer-finite-q25`: actual raw reset prefixes compare19517 instructions,
  all40 mapped regions, compared registers, CSR/MMIO/events, counts and relevant
  state. Both transcript hashes are
  `8add6704554cdb085bd6dd4bb31a559abe4de0e29625ed266402b7da5ceb80a8`.
  Dispatch is19108 fast/409 reference. This is finite reset-state equivalence,
  not a full boot state comparison or throughput qualification.
- `cold-observer-probe-q24`: the complete actual profile2 raw prefix finishes
  with1136899 observed instructions,1131289 fast/5610 reference dispatches.
  Plan/discovery/status/server/cold-enrollment fields match the retained profile2
  evidence. The first138 positive RPC transcripts plus two cold-gate records
  match exactly after removing only wall-clock measurements.
- Fresh broad observer/tooling/lifetime-checker suite:167, zero skips. Previous
  selected kernel/module producers are revalidated, not rerun by these tests.

## Still Failed

The next, first PUBLISH still hits the original100M-instruction/60M-us RPC bound:
terminal PC `0x841049ee`,5892245 blocks,603896 metadata writes,259 payload reads,
one mailbox veneer/binding, one table write/read,24576 extent writes and14889
of24576 extent readbacks. The previous observer attempt q17 reached11440
readbacks, and original native q3 reached5422. Do not combine separate attempts
into a complete publication, infer an infinite loop, or relabel this as a pass.

Every raw-boot call retains3M instructions/10M-us. The unanswered longer-boot
proposal was unused. RPC bounds remain100M/60M-us. Neither original replay job
was restarted; absent service handles are not successes. No fresh full three-
profile19261-positive-RPC native verdict exists at this checkpoint.

Retain q12 raw-boot failure and q17/q24 publication failures, intermediate builds
and sources. Build-q6 failed a reference fixture setup: adding a hook after an
already-translated unhooked loop did not invoke it. The six-case diagnostic q8
reproduced identical behavior for both bridges; explicit cache invalidation
after hook installation corrected the fixture. Fresh builds q10/q16/q23 pass
the same callback-exception requirement. No failed receipt is promoted.

## Preservation And Boundaries

New400MiB/no-swap phases retain the existing C scratch lock, fresh Windows/WSL
RAM checks, old compact1GiB future allowance and dual2GiB storage margins.
Original stock source and four complete prior/current build-cache inventories
remain unchanged. The inherited57027 project flat bindings, two external inputs,
48 selected runtime external bindings, source versions, aliases and five complete
directory inventories remain separately bound rather than flattened/deduplicated.

The firmware source lock remains
`88502ab3798b2ccdf01e6fd3c8779bcd2ad0f24a970c080f97ac9992b97f740a`;
the mt76 patch remains
`bb4579282feedf23edbe09007eb7b1566ffc96dceb39e49984ddc7a1cbaa2e71`.
The retained four-module producer remains
`a840d3cccb1d0bd8cc60a856d1a1bb9723dfc05af73484d955a33978a458d22f`.
No production firmware/module change, current router image, module load, router
contact, calibration/recovery write or flash occurred.

Jev supplied nine pre-profile and eight narrow post-change semantic judgments.
The latter retained error-order0.66, per-RPC-counter0.68 and registration-order
0.74 uncertainty; source inspection and executed differential/error/replacement
tests, not a confidence threshold, resolve those obligations. Judgments are
supplemental evidence, never tests or execution authority. Existing cached
Ghidra text informs source-bound PC selection; no new Ghidra analysis is claimed.

Next: faithfully reduce remaining RPC observer cost and complete the native
recipe, then finish complete target/physical cold MCU-exit failure and queue/
page-pool retention/drain, firmware BA reuse, hot admission/retirement/rearm,
current image, router/actual-client, performance and stability qualification.
Synthetic coherent mappings, PLIC/IRQ delivery and MCU-result boundaries remain
models. CPU joins and observed RV32 instructions do not authorize physical DMA
retirement. Full project completion remains false.
