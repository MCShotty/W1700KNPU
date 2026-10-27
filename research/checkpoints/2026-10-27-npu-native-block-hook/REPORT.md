# Native Block Hook And Ten-Publication Qualification

Base `f63ed536e552d975c630fe7a49c77e870dd7d04f`; continued without subagents.
This implements a host observer entry, not a target firmware or hardware fix.
Read API2 remains; observer profile6 requires a fresh explicit source-bound
build receipt. The complete NPU objective is not achieved by this checkpoint.

## Entry And Ownership

The raw Pair's single block registration stays at its original configure point.
A default method performs the exact old `hook_add`; only the opt-in subclass
installs a C function pointer. The Python binding source is now pinned in both
the build input set and runtime receipt check. Native API signatures, registry,
engine and thread are checked. The cold/block/memory/emulate inner bodies remain
byte-identical; the gateway supplies the original CPU/PC/size/None values.
Every block/site count, fresh SP and original cache-miss/effect check remains.

The pointer holder strongly owns its observer. A temporary registry guard
precedes native registration; failed Python publication rolls back the real
native hook. If rollback fails, the guard retains userdata until engine cleanup.
The C entry acquires the GIL and an in-flight observer reference, including
self-unhook. Real execution, callback order, Counter replacement, fresh SP,
GC, registration/unhook and rollback failures are exercised.

The first hook exception remains authoritative; emulator backend precedence
stays unchanged. Initial build-q3 passed its88 existing methods but did not
preserve the caught exception during stopping. New context-q4 reproduces one
assertion failure, zero errors/skips, on that retained binary. Corrected q5
saves/restores handled exception state, including outer context and secondary
stop errors. See the [CPython exception-state APIs](https://docs.python.org/3.14/c-api/exceptions.html#c.PyErr_GetHandledException).
This checks exception identity/context, not byte-identical Python traceback
frames or diagnostic function names after replacing the trampoline.

## Executed Checks

Plain and UBSan q5 each pass32 read/CSR plus57 observer methods:89 unique
methods repeated across variants, not178 unique tests. Sixteen observer methods
were added. No failures/errors/skips occur in those passing suites. Keep q3's
producing sources and q4's expected failing regression; q3 is not the final
qualified adapter. A preparation refusal for a dynamic-BASE template is also
retained; its fresh correction changes no runtime or test assertion.

Controls-q6 compiles18 independent mutants with the same flags. Every mutant
fails exactly one intended assertion, zero errors/skips. New controls swap
native arguments, omit balanced in-flight retention or omit handled context.
The existing counter/CSR/timeout/miss/memory/argument controls remain.

Finite-q7 matches19517 actual raw instructions, all40 memory regions, registers,
CSRs, events and MMIO. Both transcript hashes remain
`8add6704554cdb085bd6dd4bb31a559abe4de0e29625ed266402b7da5ceb80a8`.
Actual Pair.effect identity and three repeated direct effect tests also pass;
these repetitions add no unique unit methods or physical I/O acceptance.

The fixed actual RV32 loop executes400000 block callbacks with real Pair.block,
the old vectorcall adapter and the new direct entry. Guest counts, final state
and cache keys match. Old/new UBSan medians are1072086212/530710539ns, a2.0201
baseline/candidate wall ratio. This is a host microbenchmark, not NPU/router
throughput or complete-recipe performance acceptance.

Fresh tooling/checker167 passes with zero skips. All five complete protected
source/cache inventories match. Prior kernel/module producers are revalidated,
not rerun; no new target-kernel or physical-device result is claimed.

## Fresh Native Probes

All boot calls retain3M instructions/10s; RPCs retain100M/60s. Same400MiB/no swap,
C storage lock and dual backing/RAM reserves remain. Each probe starts from raw
initial state. No old interrupted or failed replay is resumed or restarted.

Profile0 probe-ten-q10 completes150 checked RPCs and publications0-9. Every
publication completes24576 extent writes AND24576 readbacks, table1-write/
2-read, broker comparison and full DMA/SRAM/code checks. Times range40.84-45.37s.
Ordinal9, which failed in old full-q25, completes in43592216169ns. All177 old
JSONL records/149 positives match except wall_ns; the additional publication
crosses that observed frontier, not the entire native matrix.

Fresh profile2 q14 completes139 RPCs and first publication41235315129ns, with
the same full I/O/memory requirements. All141 canonical rows match except
timing. Neither probe is a complete profile or a complete three-profile verdict.

## Physical Cleanup Lead

This is source-only. Three current MCU/shared/caller source files match inputs
of the retained four-module producer a840d3cc. The present selected-C test stub
is recorded separately, not presented as a new hardware or binary analysis.

POWER_OFF uses `wait_resp=false`; shared send passes NULL wait_seq and returns
after enqueue success. The shown UNI descriptor requests ACK only for non-NULL
wait_seq. MCU exit ignores the send status, logs firmware-state poll failure,
and returns void; the cleanup caller continues. Its test stubs return restart
success and a false firmware-state result, so they do not exercise actual
transport or a failing poll. This does not establish physical drain failure,
but it shows why propagating enqueue status alone would not prove retirement.
Physical MCU/queue/page-pool retention and a real drain witness remain open.

Jev's focused implementation judgments retain material uncertainty, including
arguments0.67, retention0.75 and first-error0.65. Executed fixtures, mutants and
direct code inspection establish their covered software scope, not probabilities.
The physical status question is uncertain0.53; the void signature and standalone
caller were inspected directly. Raw requests/results remain private evidence.

## Next Complete Recipe

The prepared full-q21 runner retains the entire three-profile19261-positive-RPC,
387-publication and6150-each RESET/MCU_BEGIN/MCU_COMPLETE recipe. No profile2 gate,
limit or memory/I/O assertion is removed. Publish the clean source and evidence
closure first; verify actual guard/wrapper/driver argv, cgroup and CPU progress,
then inspect final driver/wrapper verdicts. Freeze bound sources while live.
An observation timeout never authorizes a restart.

Source lock88502ab3, mt76 patchbb457928 and four-module producera840d3cc remain
unchanged. No new router image, module load, router contact or flash occurred.
Full native, physical retirement, firmware BA reuse, hot admission/retirement/
rearm, current image/router/actual-client/performance/stability remain. All
consumed versions, failures, aliases and inherited evidence are retained in
the ignored cohort/native C scratch and bound by EVIDENCE.json.
