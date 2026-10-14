# Portable INODE Owner

## Canonical Promotion - 2026-10-15

Source is now firmware/npu/cold-inode.c/.h; canonical tests and all eleven store
trampolines are in tests/npu. Exact normal22-object build qualification passes
382 host/2312 RV32 calls,142 controls, eight compiled host mutants/sanitizers,
120 original-store ABI cases with explicit guard stubs and4/1036 original
prefix cases. Real native guard/authenticated admission remains open.
See ../2026-10-15-npu-owner-promotion/REPORT.md for the current producing cohort.
Staged paths and current-input hashes below describe the preserved historical
cohort; they are not source-drift exceptions or post-promotion receipts.

## Scope

The staged188-byte plan/4372-byte owner implements original selector2's1030
effects (three flags,1026 four-byte ICV clears, final flag), then selector7's
six effects. It requires the finished PCIe0/2/15 owner and earlier TX/RX/DESC10
ownership, exact paired-CODE type109/base and metadata3e902ac0, and full4104-byte
ICV geometry. Prior validity is rechecked after reader callbacks. Possible
effects and captured preimages survive failure; no reset/retirement API exists.

Source was initially staged in .local/npu-inode-next-20261014 and is now in the
normal unified build without a separate experimental mode. It is not instantiated or bound to original
stores/authenticated caller. No final IRQ, worker release, physical readiness,
cache/DMA/drain/reset/removal/rearm/recovery/boot/client acceptance is established.

## Current Evidence

| Receipt | Result | Scope |
| --- | --- | --- |
| host-q5/result.json |382 calls/142 controls, both HIF profiles | Compiled portable C; whole logical window/flags/prior state and original-derived event oracle. |
| mutants-q3/result.json | Eight compile and fail behavioral assertions; sanitizers pass | Host fault sensitivity, ASan/UBSan/leak. |
| original-prefixes-q1.json | Four nominal/1036 interrupted prefixes | Original lookup/INODE instructions in synthetic RAM; pre-store cuts, not real bus/concurrent faults. |
| single-rv32-q1.json |2312 compared calls/142 controls, both profiles; terminal0 | Full exact normal-Os comparison, one real effect per finite-budget call. |

Three completed receipt input maps verify56 current files. Host receipt SHA256:
7340dd76aa1e86eccbfeb1f4029c07e04a7df6d963e0791f58338201f7767d71.
Mutant receipt SHA256:
74911710bca16faa57435d3c3850dde71b57975a44543755ba87c8bd0ffcccfe.

Final .local/npu-inode-next-20261014/checkpoint-q1.json verifies all five receipt
hashes and71 current inputs, actual binaries/mutants/generated IRQ source and
sanitizer logs. SHA256:
e9376b5f965747e35bd8eb838a90a5287777a2108a85c035fa0ce674f8f54b47.
The compiled-RV32 full sequence/control set is now passed, not pending. The
larger call count comes from single-effect invocations with unchanged500M/
30-second entry limits; no effects/controls were dropped or guards bypassed.

Controls cover exact fixed109/base/pointer, plan/owner dirtiness, wrong stage/
value/epoch, malformed address/width/value/preimage, partial ICV preimage reads,
possible effects without stores, wrong readback, replay, late-stage failures,
readonly live corruption and eight mutation types during begin/reserve/publish/
finish. Every logical/prior field is compared; only named injections, the
owner's fault bit and explicit read diagnostics may change in fault probes.

The eight compiled mutants remove top-prior reader equality, permit unfinished
PCIe, omit nested-prior post-read checks, ignore type109, repeat the first clear
instead of the last, accept wrong store addresses/readback, or forget possible
effects. Prototype terminations/compile issues are not counted as killed mutants.

## Original Store And Continuation ABI

Implemented native-inode-stores.S/.ld for all eleven original four-byte stores.
The120-case probe executes the actual callback/helper and exact original opcodes
with explicit ownership guard stubs and only printf skipped. It covers two
register seeds,12/24-byte frames, all store sites and first/middle/last ICV clear
failures before/after effects. Saved registers, original16-byte frames and whole
64KiB DATA/eightKiB ICV-neighbor memory match exact retained prefixes.

The final selector2 store occurs after original ra/s0 restoration; its unwind
does not reload them. Other selected stores still have both saved. The original
callback returns1 in every case, including inner failure; real outer completion
and live-context checks are mandatory before admission. This is not a real
ownership guard/caller or physical verdict. See NEXT_INODE.md.

ABI receipt SHA256483ddbe7387e63902c3db61545eae4eedf0e7006af72529821290b719c5eec27.
Incremental checkpoint-abi-q1.json checks78 current inputs/six scoped receipts;
SHA256d01fde288c46235410c353e19d86e28f59cbe1ef4f353e48c528e2f8a8e3cb04.

## Corrections And Limits

- The combined prerequisite fixture exceeded the existing500M instruction
  limit. It now invokes each actual prerequisite API separately. A later
  multi-effect batch also exceeded the entry limit. The current single-effect
  driver preserves500M instructions/30 seconds per invocation and exercises the
  full nominal sequence/control set; no checks/effects were dropped.
- UBSan caught intermediate out-of-bounds pointer arithmetic in the fixture.
  It is corrected to base+(address-base). Affected RV32-q2/session12075/
  PID2644558 was intentionally terminated (terminal1), not a native verdict.
- The first short-clear mutant had an invalid out-of-bounds recipe and
  terminated its prototype. The final in-bounds duplicate-clear mutant is the
  successful behavioral test; the prototype termination is not acceptance.
- A late nested-TX fault probe already failed closed, but only after owner
  initialization. Rechecking the complete prior after new reads now detects
  these faults before that advancement; eight nested/owner mutation controls
  exercise the stricter behavior. No unsafe success is claimed for that probe.
- Compiler stack usage reports4688 bytes for the largest individual frame.
  The full native caller/reader/interrupt chain and physical stack budget are
  not established. This measured frame is not a complete stack bound.
- Some selector7 flags already contain their requested values. Readback cannot
  distinguish a real idempotent write from no write; actual original native
  site execution and guard integration remain mandatory.

Actual Jev1.13.0 selects the host-portable/in-progress scope1.0/confidence1.0
and retains idempotent-site gap0.91/full-stack gap0.95/reclamation-authority0.05.
Its supplied state recorded the then-pending RV32/sanitizer/mutant verdicts;
later deterministic receipts establish the completed host checks, not that
semantic judgment. Raw request/results remain local.

The final fresh-state Jev batch selects portable compiled scope and modeled
IRQ error loss (each1.0/confidence1.0), with real native binding needed0.91 and
drain/reuse authority0.05. This does not change the deterministic proof scopes.

## Continuing Work

The final IRQ path is now traced separately: two host regmap writes, not extra
RV32 mailbox callbacks. Exact extracted provider/wrapper/initializer C passes21
sanitized fixture cases;12 modeled register-error cases still return0 because
the current ops/wrapper ABI is void. Seven earlier initializer errors correctly
propagate without final IRQ calls. No source or hardware was changed by this
test. Error propagation, partial ownership/readback and the hot poll re-enable
caller remain to implement; see NEXT_IRQ.md for the exact source/contract.

Older actual caller82479/PID3199667 now passes DESC10:25606 effects/512 new
claims/3072 total/RXsteps2/ready1/error0 and all856064 protected bytes. Independent
verification checks all actual/expected bytes,225 current source input hashes,
CPU context and30 saved regions/44 files; receipt SHA256
ca8a37dea83b44ff1dac0f31c1fb741cd4650866b269671d5f176635f0e6cbe4.
Its PCIe stage remains live, with no complete sender verdict. The new RV32 run is
terminal0; only that older full caller remains live. The earlier restored-prefix
native PCIe30-case/267-input matrix is terminal0; the redundant serial copy was
intentionally interrupted afterward, not passed. Preserve its live input set.

After their terminal verdicts, promote the qualified staged PCIe/INODE source,
fixtures and tests to normal Makefile/exports/source-lock paths. Bind actual
original stores, exact locks/IRQs/neighbor/readback/frame/held session and caller
ordering, including late faults and lost/mutated replies. Then full IRQ/worker/
hot packet/lifecycle/physical/drain/recovery/boot/actual clients remain required.

FIT69c88ce9 remains unchanged and unflashed. No new world image, commit/push,
router/flash/reset/Wi-Fi/power/private-backup changes or subagents occurred.
