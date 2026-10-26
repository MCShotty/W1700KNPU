# Native Observer Vectorcall

This checkpoint continues from `b9a90dd`. It reduces host observation cost,
not guest checks or physical NPU lifetime requirements. Complete native replay
and full hardware/client acceptance remain unproven.

## Call Protocol

Observer profile5 uses the documented [CPython vectorcall protocol](https://docs.python.org/3.14/c-api/call.html)
for the same cold/block/memory callbacks. Pointers initialize during `__new__`,
before `__init__`; `tp_call` uses the tuple bridge. Reference calls retain the
complete positional count/offset, keyword names/values and original exceptions.
An explicit balanced recursion guard covers pure-C reference cycles.

All three inner bodies equal the exact argument-transport transform of their
preserved predecessors. Counter updates, fresh SP/CSR/instruction/data reads,
current owner Counter/ranges, engine/thread guards, excluded-effect delegation,
hook positions and fallback conditions remain. The Python registration
implementation is byte-identical after normalizing only the API number.
Read API2 and default reference replay stay; the candidate requires an explicit
source-bound build receipt. No guest-value cache or new firmware substitution.

## Qualification

Build-q4 passes32 read/CSR plus41 observer methods per plain/UBSan variant:
73 unique methods repeated, not146 unique cases. Four new methods exercise the
actual vectorcall pointer/pre-init state, unusual argument/keyword/tuple calls,
original error identity and recursive-reference refusal. Controls-q11 compiles
15 independent mutants, each producing exactly one designated assertion failure
with zero errors/skips. No compiler or sanitizer flag was relaxed.

Finite-q5 compares19517 actual raw instructions across40 mapped memory regions,
registers/CSRs/MMIO/PLIC/events/counters. Both transcripts have SHA256
`8add6704554cdb085bd6dd4bb31a559abe4de0e29625ed266402b7da5ceb80a8`.
Exact Pair.effect identity and three repeated direct refusal/injection/boundary
tests pass; repeats add no new unique methods or physical IRQ/DMA evidence.

Benchmark-q14 runs real Pair.block and old/new UBSan callbacks through a fixed
actual RV32 loop. All produce400000 block callbacks and identical final state,
code/cache and counters. Three old/new rounds alternate order. Median wall time
is1161237851ns candidate versus1297070377ns old, about10.5% less candidate time.
This is a host microbenchmark, not full native or router performance acceptance.

## Fresh Publication Evidence

Profile0 probe-q12 completes141 RPCs, with its retained140-RPC prefix matching
q31 and a complete first PUBLISH in56296801479ns. All24576 writes/readbacks,
one table write/two reads, complete broker journal and full DMA/SRAM/code checks
pass. Profile2 probe-p2-q17 completes139 RPCs, matching the retained138-RPC prefix,
with a first-publication wall time of54247317018ns and the same complete
I/O requirements. Complete matching transcripts exclude only wall time.

Original raw calls retain3M instructions/10M us and RPCs100M/60M us. The complete
recipe remains three profiles/19261 positive RPCs and journal comparisons,
387 publications,6150 each RESET/MCU_BEGIN/MCU_COMPLETE and the existing controls.
Full-q25 is prepared for a separately named fresh raw-state run, not a resumed
or spliced partial state. Its finite dispatcher verifies actual live guard/
child argv and cgroup caps. Inspect actual process state and final wrapper/
driver result; dispatch, logs and observation timeouts are not acceptance.
Freeze all bound firmware/adapter/harness inputs while that run is live.

## Retained Failures And Scope

Benchmark-q6/inspection-q8 retain an incorrect hand-derived TB-count failure.
Count-limited Unicorn splits the loop into two TB callbacks per iteration;
fresh actual reference/old/new executions establish the corrected contract.
Controller-q7 correctly refuses two keyword-mutant subtest assertions where
exactly one was required. Fresh q11 narrows mutants to one subcase without
changing the verifier or canonical tests. Preparer-q9 refuses an incorrect
phase-name occurrence count; fresh q13 verifies both sites. Nothing is relabelled.

Jev's broad initial questions retain uncertainty; focused eligible-branch count
is0.68 and registration0.75, while fresh-SP0.94/current-Counter0.89 are higher.
Raw probabilities and questions remain in evidence. Exact source transforms,
unchanged registration and executed tests/mutants establish the covered software
behavior, not model confidence. No new Ghidra analysis is claimed.

Fresh tooling/checker167/zero skips, five complete protected source/cache
inventories and the complete inherited evidence bindings are rechecked.
Retained ARM64/UML/module producers are revalidated, not reexecuted. Same400MiB/
no swap, C storage lock and dual backing/RAM margins stay. Original interrupted/
failed replay receipts remain unchanged; no old replay was restarted.

Production lock88502ab3/patchbb457928/four-module producera840d3cc stay. No new
router image, module load, router contact or flash. Complete native replay,
physical cold MCU-exit failure/queue/page-pool retention/drain, current-firmware
BA reuse, hot admission/retirement/rearm, current image/hardware/actual-client/
performance/stability acceptance remain unfinished.
