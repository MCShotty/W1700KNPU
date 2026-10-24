# RRO Profile2 Attribution And Host Register Reads

Date: 2026-10-24. Goal-turn classification: progress. Full NPU goal remains active.
No subagents, firmware change, current image, module load or hardware action.

## Retained Failure

The frozen full RRO native-q3 result remains a terminal failure. Profiles0/1 each
completed6421 positive RPCs and2050 reset transactions; profile2 completed OPEN
and137 ENROLL operations, then its first PUBLISH hit the unchanged100M-instruction/
60M-us RPC bound. All24576 extent writes completed;5422 of24576 required extent
readbacks were observed. There is no complete native verdict.

Exact GNU symbols/disassembly/addr2line on the retained rro-wire ELF6a1319f1
place PC0x84104c72 in active_owner, at a worker-readiness load followed by an
acquire fence and conditional rejection branch. Its loaded value/return was not
captured. This identifies the instruction, not a rejected owner, infinite loop,
physical ordering fault or router-performance result. CODEe6bc914c/DATAad905cb0
remain byte-identical. The original job was not restarted.

## Fresh Diagnostics

The supplemental probe retains the exact original observer, pair, oracle and
full raw reset/coordinator/seven-worker/V2/cold-enrollment prefix. Its intended
OPEN/all137 ENROLL/first PUBLISH recipe compares complete journals, all12MiB DMA,
native SRAM/code and retained TX/RX backing, and checks the whole prepublication
transcript against the retained run. It is not a replacement for all three full
profiles, resets, control cases or hardware acceptance.

None of the new probes reaches that RRO request. Under the existing10-second
boot wall bound, scalar and existing CSR batching stop in the clear loop near
0x840103c4; the native-read variant stops at0x84004ef6. The3M boot instruction and
100M/60M-us RPC bounds remain unchanged. A separately labelled60-second diagnostic
boot-budget question is pending at this checkpoint, not approved or exercised.

The cProfile run deliberately adds observer overhead. It attributes repeated
register/C API and layered-hook costs but cannot establish unprofiled runtime or
physical performance. Its terminal PC/registers and complete statistics remain.

## Implemented Tooling

Added `tests/npu/native-read-api.c`, `native_read_api.py`, actual API tests and
`tools/build_npu_read_api.py`. The explicitly loaded adapter calls the same loaded
Unicorn uc_reg_read/uc_reg_read_batch functions without caching architectural
values. It checks thread and live engine-handle identity on every call, retains
the engine owner, propagates UcError, preserves non-fast-path call behavior and
supports cycle collection. The helper pins the reviewed Linux x86_64,
GIL-enabled CPython3.14/Unicorn2.1.4 binding and exact extension identity.

This is opt-in host analysis tooling. The canonical Pair observer still uses its
original default; no guest instruction or hook was removed, and no NPU module,
raw firmware, source lock or image changed. The build CLI is a compiler primitive;
run it only through a fresh resource-qualified phase while protected jobs are live.
Its build.json supplies the NPU_READ_API_BUILD_RECEIPT used by the actual API tests.

## Verification

- Plain14cd2aab and UBSanbfcddcce builds each pass26 API/CSR tests, zero skips.
  These include every GPR plus PC/selected CSRs, fresh writes/context restore,
  unchanged memory/registers, backend failures, handle/thread misuse, fallback
  calls, GC and actual guest instruction-hook transcripts with dynamic injection.
- Corrected-budget read-only requalification repeats both26-test suites. The
  public build CLI independently reproduces both exact binary hashes, then repeats
  both suites again under the corrected budget. Final public-builder peak65.3MiB
  is within128MiB/no swap. This is not whole-driver Linux/physical qualification.
- One100000-SP-read sample: Python457041097ns, native133675524ns elapsed, about
  3.4x. Reads occur without guest execution. This is not whole-replay throughput
  or router-speed evidence; no universal performance threshold is asserted.
- Refreshed observer/tooling/inventory/phase checks plus five build-CLI refusal
  cases pass147 tests, zero skips. The latter check unsupported host/GIL, invalid
  output, existing output and help without launching a compiler. Peak70.9MiB stays
  within128MiB/no swap. This suite does not execute native NPU firmware.

## Resource Audit

Initial auxiliary controllers omitted the protected compact replay's1GiB future
output allowance from their estimates. Their evidence is kept and is not silently
relabelled as resource-qualified. Initial host observations each show3366989824
free bytes. No original job/lock was changed and no actual cap breach is observed.

Corrected current/public phases explicitly budget1GiB compact future output plus
64MiB auxiliary output plus the unchanged2GiB storage margin on both the guest and
actual Windows backing volume. A0.25-second watcher stops the auxiliary process
group on an observed60MiB cohort breach; it is not a filesystem quota. The reserve
leaves4MiB for journal/metadata overhead. All full live RAM caps plus2GiB guest
margin and2GiB+128MiB Windows headroom are checked. Corrected phases run at128MiB,
no swap; producer/test results are positive. This does not retroactively repair
the earlier estimates. No swap, VM, global policy or native-limit change occurred.

The first static dispatch lacked the fresh Windows storage sidecar and stopped
before decoding. A later diagnostic refused an existing CSR-result path before
boot. Those refused attempts and all failed native prefixes remain unchanged.

## HIF2 Next

The current lookup returns a devm hif object after taking only a device reference;
remove also deletes its list node without the lookup spinlock. A binding-aware
replacement must retain a device across lookup, serialize list removal and qualify
the expected supplier driver and fresh drvdata before use.

Managed device links provide driver-presence/unbind ordering; stateless links do
not. [Kernel device-link documentation](https://docs.kernel.org/driver-api/device_link.html).
Local Linux6.18.52 core.c additionally initializes an already-unbinding supplier's
link to SUPPLIER_UNBIND, so a non-null link alone is insufficient. Qualify
CONSUMER_PROBE before supplier resources are used. No HIF2 patch or real unbind
qualification is claimed here.

## Remaining

Resolve the fresh raw-boot deadline, then complete the full native RRO recipe.
Full cold work/MCU unwind, HIF2 binding, firmware BA late/reuse ordering, hot
admission, production retirement/rearm, independent physical drains and current
image/boot/client/performance/stability acceptance remain. Firmware/source-lock
1177bd53/current module producer8582153e are unchanged.

Jev performed narrow causality/source/scope checks only. The owner-rejection0.45,
probe-limit0.62 and API-test-native-completion0.32 judgments remain uncertain;
actual source, compiled tests and failed terminal PCs govern these claims.
Exact scoped/transitive bindings and limitations are recorded in EVIDENCE.json.
