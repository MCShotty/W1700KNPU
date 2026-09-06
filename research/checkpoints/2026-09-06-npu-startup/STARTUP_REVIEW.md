# Startup Independent Review

2026-09-06. Bounded static review of the requested startup sources, adapter,
linker script, `build_platform`, two new tests and their recorded JSON results.
No source edits, test/build reruns, generated-output changes or hardware actions.

## Finding: P2 - READY Can Publish After The Fault Latch

Evidence: `firmware/npu/startup.c:23-27,34-39,71-87`;
`tests/npu/startup-platform-emulation.c:28-41`.
`fail()` stores `fault = 1` before storing `phase = FAILED`. Publication checks
the fault only before its separate phase CAS. A waiting poll also checks the
fault before acquiring the phase. Thus the CAS does not arbitrate against the
first, already-latched half of failure.

Concrete source-level interleaving, valid even with sequentially consistent
memory; no cache, physical containment or weak-ordering assumption is needed:

1. Start with a valid header, phase INITIALIZING, fault zero, clean initialized
   barrier/admission/masks and arrivals 0, 1 and 2 already registered.
2. Hart 0 passes every `npu_startup_publish()` check and pauses before line 85.
   Hart 2 passes `npu_startup_poll()`'s fault/arrival checks and pauses before
   its phase load at line 37.
3. Hart 1 re-enters with its arrival already set. Its arrival CAS fails and
   `fail()` stores fault one at line 25; pause it before line 26.
4. Hart 0 successfully changes INITIALIZING to READY and returns success,
   although the startup fault is already one.
5. Hart 2 reads that READY and returns CONTINUE. Its adapter can return to the
   native reset continuation without another fault check. Hart 1 subsequently
   finishes publishing FAILED and the adapter's barrier fault.

This is a concrete split-state gate race, not an executed hardware failure or
proof of subsequent native memory accesses. Hart 0's adapter polls again after
publication and would notice the fault; that does not protect hart 2's already
in-progress poll. Merely retaining the fault bit or the existing phase CAS does
not prevent this schedule.

Correction direction: give failure/publication one authoritative atomic phase
transition and an explicit linearization rule; do not publish the failure latch
before the state that prevents READY. Revalidate the fault after acquiring READY
before permitting continuation. Keep the assembly fault path consistent:
`tests/npu/startup-emulation.S:39-48` has the same fault-then-phase split.
Add an instruction-paused three-hart test at the stores/CAS/load above. The
desired contract must not imply instantaneous containment of a hart that had
already passed the gate before failure.

## Tests And Limits

- The existing interrupted-initialization case pauses before `npu_barrier_init`,
  executes the other hart's complete failure, then resumes hart 0
  (`test_startup_native.py:238-249`). It does not cover the interleaving above.
  Protocol schedules execute whole calls serially (`test_startup_protocol.py:60-79,96-114`).
- Before-BSS rejection is demonstrated for conditions installed before entry
  (`test_startup_native.py:190-234,252-261`). The precheck is a sequence of reads,
  not an arrival claim (`startup-emulation.S:9-38`); interruption after its
  fault read or before hart 0's later arrival claim is untested. Treat a broader
  no-BSS-writes-after-concurrent-fault claim as a test/contract gap, not as a
  second independently established bug in this review.
- Cold-loader honesty is explicit in `startup.h:25-26` and the adapter's first
  comment. A valid fresh-looking header is not a prior-user containment witness.
  The test-only 25,024-byte template preserves the 3,084-byte native prefix,
  zeros the extension and places the 64-byte header at `0x3e906180`
  (`test_startup_native.py:34-41`). It is not a deployable blob or host loader.
- Hart-owned arrival CASes are separate from coordinator barrier/admission init.
  The coordinator does not clear worker arrival slots; late first arrivals after
  READY are intentional. READY initializes the closed candidate state, not an
  all-eight-hart quiescence receipt. No additional arrival-ownership bug found.
- No concrete ABI/overlap bug found at the specified layout: startup is
  `[0x3e906180,0x3e9061c0)`, below the conservative `0x3e908000` limit and after
  the mask slot ending at `0x3e906158`. Size/offset assertions cover the raw
  assembly fields; the reset gate restores the displaced AUIPC result explicitly.
  Recorded register comparisons cover 32 cases. These checks do not prove real
  SRAM reservation, stack/cache behavior or subsequent native bootstrap/IRQs.

## Evidence Binding

Current `startup.c` SHA256:
`9580a0d0bcc6ae1d00e0792228aeabe092ac26c968ff2e78d85b9e22fc48f914`.
It matches the recorded protocol result's source hash. That result reports
173 cases, 2,126 C/RV32 differential calls and six killed mutants; the native
result reports 32 reset orders and 32 register cases. These are existing results,
not reviewer reruns, and do not include the new counterexample schedule.

Captured result SHA256 values:
- `startup-protocol-tests.json`: `925d005bd8334b7f8c9896d86d8010dce2a92d6bfbbd1d0c099d0bcc3820db43`.
- `startup-native-tests.json`: `c20eaad7fa7eb73b1cd9a3be6239d645e11090fa7445d19a4ce55596caa1677b`.

Only tracked write: this review. No scratch files, staging, commits, subagents,
router actions or parent implementation changes. No stock-parity claim.

## Addendum - Phase-First Correction Re-Review

2026-09-06. Reviewed only updated `firmware/npu/startup.c` and
`tests/npu/startup-emulation.S`. **Original P2 addressed at source level;
no additional actionable bug found in this correction.** Original finding,
counterexample and old result bindings above are preserved. New regressions
were not read, awaited or rerun; their outcome is not certified here.

- `startup.c:23-28,89-94`: the release store of FAILED now precedes the fault
  latch. FAILED's store and the publisher's CAS arbitrate on the same atomic
  phase. If FAILED precedes the CAS in that word's modification order, the
  INITIALIZING-to-READY CAS cannot succeed. No reviewed path resurrects FAILED
  absent the explicitly external fresh-loader reset.
- `startup.c:38-42`: after acquiring READY, the poll rechecks the fault and
  rejects an observed latch. In the original three-hart schedule, pausing the
  failure after its fault store now necessarily leaves phase FAILED already
  published: the waiting publisher fails its CAS and cannot supply a new READY
  to the waiting poller. A poll paused after a previously valid READY load,
  but before its second fault load, also rejects when that load observes one.
- `startup-emulation.S:39-51`: phase at offset 12 is stored first, startup
  fault at 16 second, barrier fault third. Each store has its own preceding
  `fence rw, w`; in particular the fences at lines 45 and 49 order the earlier
  stores before the later stores. This matches the C phase-first release
  ordering for the candidate's ordinary shared-memory contract. It is not
  evidence that physical SRAM/cache/containment requirements are satisfied.

Linearization limit: successful publication linearizes at its CAS; failure at
the authoritative FAILED store. A successful poll can be placed at its READY
acquire, with the later fault check acting as a veto. If the CAS wins first,
publication may return success even after a subsequent failure. Likewise a
poll that already read READY can still continue if its final fault read is
zero, including a failure paused between the new phase and latch stores, or
a failure occurring after that final read. These are overlapping/in-flight
operations, not READY resurrection. Do not require a test paused after the
final fault read to retroactively fail or infer instantaneous hart containment.

Reviewed SHA256 values:
- `startup.c`: `3871ecd96e5978bca57c6e8692c809a71ca083465894c0ae5b5bb4aeb8459fe6`.
- `startup-emulation.S`: `b29c875d0ed3e1b55f33879002b6e62bee79369b2fd58498c504fcc0ea6d0c46`.

This addendum changes only the review. Earlier loader, before-BSS interleaving
and hardware-proof limits remain open; no parent sources or shared outputs changed.
