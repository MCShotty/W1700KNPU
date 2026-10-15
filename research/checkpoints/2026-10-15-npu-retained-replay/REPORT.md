# Retained Raw Regression Migration

## Latest Terminal Status

This producing cohort is finished. Actual allocator/caller retained-replay-q3
passed its nominal DESC10/RX PCIe prefix with full_setup=false and prior negative
suites explicitly skipped. Seven full-size retained fault cases passed, but
before-ready-plan failed:25606 original stores executed instead of25604, publishing
the final counter/ready effects before the outer callback rejected the changed
packet plan. That is a real native guard gap; this matrix remains failed.

The cached-summary repair now passes all103 focused units; its initial five red
tests below are historical, not an unresolved cache failure. Before the native
guard changed,526 files/36963130 bytes and311 declared replay inputs were copied
and hash-checked. Preservation receipt SHA256:
e99bd58f1adcd16db8003a18747c12d21bcd229a9bb99c633f4838b36990d25b.
This is not a complete executable environment or a relabeling of old failures.

The native guard fix and changed-pair qualification continue in
../2026-10-15-npu-desc10-plan/REPORT.md. Its fresh desc10-plan-q1 caller and late
faults are distinct from this completed cohort. The in-progress notes below
retain earlier observations; do not restart the old jobs from them. Full NPU
and hardware/stock parity remain incomplete.

## Original Scope

The broader raw regression is being migrated from its rejected manually seeded
TXDONE lease to the actual provider allocator/host caller and its captured
pre-DESC10 state. All eight old fault classes retain a 512-descriptor request;
the nominal operation retains all 25606 original stores. The previous failed
broader raw receipt remains failed. This checkpoint is not yet a passing broader
raw regression or complete native setup.

No firmware C/assembly, native admission guard, raw pair, provider binary or
image changed. No device, flash, radio, reset, retirement or subagent action.
The full NPU reverse-engineering and implementation goal remains active.

## Changes And Verified Evidence

- Removed the two observer-source hash exceptions from DESC10 restoration.
  Restoration rejects any captured input drift and unknown observer fields;
  unknown fields are checked before captured memory/context restoration.
- Captures now fingerprint imported project Python replay modules as well as
  explicit dependencies. Recorded hashes are checked, never rebased. The actual
  allocator driver supplies its provider/header and generated C/include/shared
  library inputs before native execution.
- Added an independent pre-state-derived ordered-effect/partial-memory oracle,
  plus read-only original-store/lock tracing in the actual caller. Twenty copied
  store instructions occupy nineteen original hook sites: b4bc shares the six-byte
  b4ba detour. Recording a trace alone is not a passing verdict.
- Focused tests currently pass 97 cases. These include strict restoration,
  capture closure, synthetic whole/partial oracles, dropped idempotent stores,
  wrong PCs/values/locks, eight fault contracts, independent sender-binary drift
  rejection and the migrated CLI entry point.
  The synthetic tests do not execute or admit the actual native constructor.
- Current-symbol metadata checks find the exact retained owner definitions and
  eight-byte packet plan. These are ELF/memory-layout checks, not native proof.
- Refreshed host provider609/nine compiled mutants and cold wire1436/45 compiled
  mutants pass with current test sources and address/undefined/leak sanitizers.
  Neither invocation runs a native peer or upgrades physical acceptance.
- Earlier current raw guard denials pass six explicitly synthetic forbidden
  contexts; they do not replace full-size success or the eight retained faults.
- The new oracle matches the hash-preserved historical native poststate across
  all 856064 original protected bytes and 2076 private PKT bytes. This is an
  artifact cross-check, not fresh current-source execution. Exact packet magic
  is 0x314b5043; the preserved native state caught and corrected an initially
  wrong oracle/fixture magic assumption.

Preserved latest qualification cohort: 300 files / 156171056 bytes under
.local/npu-raw-retained-20261015/producing-inputs-q1. Receipt SHA256:
9e0514711592c970ae1bdf3a0f3e84d4c49122e149025049b8eb7e727f16943f.
Historical artifact cross-check SHA256:
84380a1306ea1efc509668ed45b9b9b4785e5076fc8205d56e87560b3d3ad405.
Neither preservation receipt is a complete executable environment.

## Compiled Guard Inspection And Semantic Scope

REA rejected this RV32 ELF with unsupported ELF architecture. Direct headless
Ghidra12.1.2 with explicit RISCV:LE:32:AndeStar_v5:gcc exported all seven requested
functions, zero failed decompilations, from exact native-txdone.elf SHA256
902917c48c8af0a54f6e54fb89124f0fa802e8b8b219d36189f2cea1e330e799.
The compiled claim publisher retains committed IDs/counts before later status/
liveness failure. The ready guard checks0x6404 published/committed effects,
512 claims and SKB ownership before the final two original stores. Callback
assembly masks/restores MSTATUS and does not accept a completed counter alone.
DWARF expression, overlapping-global, type-propagation and calling-convention
warnings remain. This is compiled static evidence, not observed bus behavior.
Export SHA2568d8bcb13bfb71efe7964022dd544a833eb19c81b47e5d322ac24d3bbf432e3ba;
full export/logs remain local under .local/npu-raw-retained-20261015.

Actual Jev1.13.0 scope review selects reject-source-drift and bind-consumer-before-
execution at1.0/confidence1.0. Private-vs-published claim distinction0.90 and
eight fault-contract coverage0.88 are semantic judgments, not native proof.
Six-denials-satisfy-full-regression0.03, current-native-already-passed0.03 and
full-goal-complete0.02 preserve the current incomplete scope. Raw request/result
are local as jev-review-q1.json/jev-review-q1-result.json. Codex owns the code,
plans and exact checks; no Jev result is treated as execution or authorization.

## Historical In-Progress Notes

Actual allocator/caller retained-replay-q3 is running in
.local/npu-host-tx-lifetime-20261011/retained-replay-q3. Its inputs are frozen.
The supported 60-second host wall profile, unchanged 3M per-entry instruction
bound and finite cold checkpoint limits remain. It explicitly uses nominal-only
mode; skipped prior negative suites are not coverage.

Q1 was deliberately interrupted to close the missing Python producer-input
fingerprints. Q2 was deliberately interrupted to finish/test the raw CLI's stale
summary variables. Both are terminal non-passes, not native failure verdicts.
Do not restart or relabel those runs. Q3 has no final verdict yet.

Q3 has now passed all six API21 phases/53260 effects and API22. Its271-input
pre-DESC10 capture is available; full constructor/RX PCIe are still running.
Five retained fault cases pass: denied packet lock, partial pool after17
descriptors, claim fault, changed native head and release fault. Exact856064
protected/2076 PKT bytes, retained prior owners, original store/lock prefixes,
register/frame and code checks pass. The initial denied-probe-q1 failed on one
missing expected retained ADM+4 lease byte; denied-probe-q2 and all five current
cases pass after explicitly modeling that authenticated failure coeffect. Native
guards were not changed. The three full-prefix SKB/readiness cases remain live.

The existing31 early/operand/first-two-store native controls also pass with the
same strict current prefix and no observer-source hash exceptions. Fresh offline
image reinspection retained-replay-image-q2 passes the unchanged FIT/board/218
packages/78 module ABIs/22 exact archive objects.

Six new synthetic cache-audit tests expose five rejection gaps in the new
aggregate's saved-summary reuse branch: dropped rows, missing individual receipt,
short request, changed counters and a mismatched summary row are not rechecked.
The live batch is generating individual receipts, not using that cache branch.
Keep its inputs frozen until terminal, then repair cached-case validation and
rerun all103 units before final aggregate acceptance/publication. These new
tests are currently red;97 earlier focused tests pass. No all-green claim.

The sender shared-object hash is present in the independently produced host
compiler receipt, not duplicated in prefix.inputs. The migrated aggregate now
verifies that receipt, source hashes, exact shared binary and sanitized matrix
binary; it reports this separate provenance instead of rewriting the capture.

The retained fault consumer checks the exact original site/effect/lock prefix,
five original protected images, full private PKT state, unchanged prior owners,
packet-plan mutation, retained activity/inflight/fault state and callee-saved
register/frame/code integrity. It performs explicit late fixture mutations;
restoring this state is diagnostic, not fresh initialization. Its native eight
case results remain pending.

## Original Next Gates

1. Obtain Q3's terminal verdict, exact original-store trace and input closure.
2. Run all eight fault classes against its strictly current captured prefix;
   preserve full-size requests, partial claims and native guards.
3. Run the migrated raw CLI with the fresh caller receipt and six raw boot
   controls, then seal current evidence and publish the canonical work.
4. Continue real PCIe0/2/15 and INODE2/7 bindings/authenticated ordering, checked
   final IRQ/hot re-enable, full worker/hot packet ownership, physical backing/
   cache/exclusion/drains, reset/removal/rearm/recovery and exact-image/client
   acceptance. A passing regression will not close these requirements.

Unchanged unflashed FIT SHA256:
1aa174996f9d036d360f027234743a5cd5fd182fd21c820f01a9372a057bb714.
Offline reinspection raw-retained-image-q1 passes the same 218 packages,
78 module ABIs and 22 exact normal archive objects. It is not a hardware result.
