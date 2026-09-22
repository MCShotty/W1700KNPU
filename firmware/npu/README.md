# Generation Barrier Candidate

This code is **unpromoted**. It is not in the OpenWrt source lock, the packaged
NPU blob, or a router image. Do not infer safe NPU recovery from these tests.

`barrier.c` implements the common protocol for eight harts, including the
coordinator and tunnel hart. Generation-tagged worker and domain slots prevent
old completions from authorizing reclamation. A stopped but never-started hart
must participate; absence is not an acknowledgement. Generation exhaustion
fails closed and requires independently contained cold initialization.

## Caller Contract

- Control operations and domain completions run through one serialized
  coordinator. Each hart alone writes its worker slots. Do not reenter a hart's
  poll/refresh path from an interrupt. State must be aligned shared coherent
  memory. Hardware validation of that placement remains required.
- Close external producers. Each worker gates datapath interrupts and calls
  `npu_barrier_poll()` only at a reviewed ownership boundary. PARK/FAULT permits
  no further descriptor, allocator or DMA work. REFRESH permits only reloading
  new cached state, then `npu_barrier_refreshed()` with the returned epoch.
- Only after all harts park, collect generation-matched platform drain witnesses
  for ingress, copy engines, PPE/tunnel, Wi-Fi DMA, and interrupt publication.
  This list is a required minimum pending the full ownership inventory, not a
  proved exhaustive set. `npu_barrier_record_drain()` records a witness; it does
  not perform or prove the drain. A fence, IRQ mask, timeout or old DONE is not
  a witness. Keep the control mailbox functional without admitting other writes.
- `npu_barrier_reclaimable()` is the sole protocol authorization to reclaim old
  storage. After preparing replacement resources, call `prepare()` and then
  `release()`. Release immediately revokes reclamation, even if restart fails.
- Wait for every hart's new-generation refresh and successful platform restart,
  then call `arm()`. Only after arm succeeds may ingress reopen. A partial
  restart requires another complete stop before reclaiming anything.
- Timeouts retain resources and the stop generation. Repeated stop is idempotent
  while parked. Do not cold-initialize this state to escape a timeout.

## Current Evidence

- Same C compiles as native and RV32IMAC code: 9,351 differential call pairs,
  100 stop/resume cycles, each missing worker/domain/refresh, stale completions,
  partial restart, bad arguments and generation exhaustion. Three check-removal
  mutation controls fail as expected.
- Four test-only core-5 detours execute against original firmware instructions
  in Unicorn. Startup, outer poll and both empty-ring paths park; an in-flight
  helper delays ACK; replacement ring/index refresh and register/MIE preservation
  pass. The helper's return, other harts and drain witnesses are modeled.
- Native UART and PPE interrupt counterexamples remain after vendor STOP/GET0.
  Their real integration cannot be replaced by a worker-only patch.
- The combined emulator ELF now adds 16 adapters for the other six workers:
  20 detours total, with five refill pointer caches and both fast-RX indices
  refreshed. Fast startup also needs index refresh. New tests pass 16 stop/
  resume, 96 differential register/MSTATUS, 17 missing-startup, six in-flight
  and six interrupted-refresh cases, three shared-SRAM seven-worker cycles,
  and 19 negative controls. Scheduling is serialized; coordinator 0, helper
  returns and physical drains are modeled. See the `2026-09-05-npu-workers`
  checkpoint for exact scope and remaining reachability boundaries.
- Coordinator admission now has two native detours and a strict mailbox-table
  adapter. Eight saved contexts supply actual-code ACKs while control remains
  available. Deferred IRQs, active-handler retention and fault propagation pass
  1,667 native/RV32 pairs plus native-handler tests. Physical reclaim/restart
  capabilities remain clear. See `ADMISSION_ABI.md`; no production integration
  or automatic upgrade of legacy STOP/GET3 is claimed.

The test linker addresses and state at `0x3e906000` are emulation fixtures, not
validated production reservations. Do not append code at the original blob end:
the next region contains hart stacks. No patched firmware binary is emitted.

`startup.c/.h` adds a cold-loader header and coordinator initialization gate.
Two native reset adapters reject stale entries before coordinator BSS clear and
hold workers until candidate state initialization completes. The loader must
independently contain prior users and upload the fresh template coherently.
READY is not full bootstrap, all-hart acknowledgement or physical containment.
Fault/publication races use one authoritative atomic phase; an already-passed
gate is not instantaneously revoked. See the `2026-09-06-npu-startup` checkpoint.

`bootstrap.c/.h` adds a separate MT7996-only, six-command reserved-memory gate
and early version query. The test binding installs its mailbox handler through
native IRQ registration before source 8 is enabled, uses a private validated
payload and retains active/resource state after failure. Late cold workers no
longer misread the coordinator's normal marker update as warm entry. General
mt76 setup remains closed; this is not complete native boot or a physical
ownership witness. See `BOOTSTRAP_CONTRACT.md` and the `2026-09-06-npu-bootstrap`
checkpoint for the limited footprint checks and exact execution boundary.

The separate `tests/npu/bridge-startup-emulation.S` sidecar adds two hart7
failure guards without changing the original candidate ELF. Native bridge
startup no longer continues after a null allocation or failed channel bit in
the post-gate analysis fixture. Fifty-two native cases, seven mutants, four
missing models and18 late-ready holds pass; all28 detours with the initial gate
retained still park all eight harts without bridge access. The88-byte sidecar
is unpromoted. Allocator ownership, buffer extent, timer semantics, cold-init
permission and physical containment remain open. See the
`2026-09-09-npu-bridge-startup` checkpoint; this is not full boot or recovery.

`allocator.c/.h` adds a checked cold dynamic allocator with immutable definition
tables, explicit lock callbacks, under-lock metadata validation and full-extent/
cache-capacity checks. Failed calls preserve metadata and never release denied
ownership. Cached lookup remains valid when heap/cache capacity is exhausted.
The diagnostic attempt counter is not a reset generation. All metadata users
must honor the same lock; physical grant/release/cache semantics remain caller
contracts. Fixed-L2 getter paths are not replaced.

`tests/npu/allocator-bridge-emulation.c` binds only hart7's bridge allocation
call to this core. It uses native lock routines, validates the lock ID and
holds before base publication on failure. An allocation committed before a
concurrent barrier fault is retained, not rolled back. This standalone binding
leaves core0 and other callers unchanged; the newer startup binding below adds
reviewed core0 integration. All 29 detours
with the first gate retained keep every hart parked; no cold-init permission is
invented. Verification passes 1,367 same-C native/RV32 pairs, eight mutants,
32,000 pthread calls, 48 original comparisons, four counterexamples and eight
bridge cases.
The declared heap cannot fit type-2 after the core0/bridge allocation sequence;
checked rejection is not complete boot support. Memory budgeting, bridge
extent, global ownership, hardware lock/cache and production placement remain
open. See `2026-09-09-npu-allocator/REPORT.md` for exact evidence and replay.

`tests/npu/allocator-reset-emulation.S` corrects a separate lifetime defect:
native cold reset published a four-byte type-0x89 control allocation, then
cleared count/cursor and allowed the ID pool to reuse it. Two detours and a
20-byte adapter now initialize metadata before that allocation and preserve
its record. The native control writer no longer changes pool entries. A reset
must not discard records for published allocations; valid metadata alone
cannot detect live pointers retained elsewhere.

Five native primitive cases, four mutants, full core0 initialization, four
checked bridge cases and a later control-word write pass whole-memory checks.
All 31 detours with the first gate retained keep every hart parked. The word
costs 32 aligned bytes, leaving 2,305 bytes after bridge setup; the type-2
capacity deficit remains unresolved. This is an unpromoted, independently
contained cold-reset model, not safe active reset or hardware containment.
See `2026-09-09-npu-allocator-reset/REPORT.md` for replay and remaining contracts.

`tests/npu/allocator-startup-emulation.c/.S` selects seven reviewed core0 return
sites and the hart7 bridge caller at the getter entry. Other calls replay the
native first instruction and continue unmodified. The selected callers validate
type/role/cold state, then use the checked core and original lock routines.
Core0 failure enters the existing faulted idle only with an installed/enabled
strict control IRQ, saved interrupts enabled and no active callback. Otherwise
it holds with interrupts disabled and retained ownership; no service or callback
unwind is claimed. Hart7 publishes only the barrier fault and holds.

All seven core0 startup allocations are verified after IRQ8 installation, so
no new mailbox transport is needed. Eighteen failure/context cases, 52 control
replies, thirteen rejected legacy-version requests, five hart7 cases, eight
mutants, 36 preserved lookups and all 31 retained-gate detours pass. No failed
initializer resumes, and a post-commit fault retains its allocation. Whole
SRAM/heap/L2 checks and byte-identical replay apply. The startup getter hook
replaces the older hart7-only allocation detour, not both at once. Other
allocation callers, active-callback/IRQ-repair policy, memory budgeting and
physical delivery/containment/recovery remain open. See
`2026-09-09-npu-cold-allocator/REPORT.md` for exact scope and reproduction.

`tests/npu/txdone-init-emulation.c/.S` adds six selected cold API1/selector10
detours. Request/count and selected metadata checks, a private payload,
bufid/SKB ownership checks and a pre-load temporary bound preserve normal
TXDONE output while rejecting local failures. Partial descriptors/IDs and
active ownership are retained; failed helpers cannot silently clear the index
or publish legacy ready. Other callback consumers remain native and strict
API1 admission remains closed. This is not a production bootstrap route.

Sixty-two native cases, eight mutation tests, four integration controls and
four missing-model controls pass whole-memory/exact-write/lock checks. All
37 detours installed before reset retain every first startup gate. Replay is
byte-identical. Native RX0/2 fallback is equal before/after; corrected success
reads2,048 temporary
halfwords instead of8,192 across the4KiB allocation. The1,738-byte sidecar is
test-only and emits no patched firmware image. Actual host backing remains
unvalidated: the short-ring control stops at an access caught only by the
emulator. Full pointer/allocation provenance, asynchronous publication,
physical containment/lock/cache/drains and remaining boot/recovery paths stay
open. See `2026-09-09-npu-txdone-init/REPORT.md` for boundaries and replay.

## Host TXFREE Boundary

The unpromoted `005-mt7996-npu-txfree-preflight.patch` checks selected host
queue ownership, pointers, 512-entry metadata and DMA address before
attachment helpers. Normal allocation already requests 8 KiB. 152 host-C
cases, nine mutants, 34 unchanged controls, ten AArch64 objects and strict
checkpatch pass. The patch stays outside the firmware overlay/source lock.

Twenty-two native bridge cases feed recorded allocation-derived SET22/DESC10/
SET0 messages into the MT7996 fixture without preinitializing the descriptor
pointer. Full successful memory, exact writes/locks and strict API1 rejection
verify; receipts replay identically. MT7992 host rows test shared message
shape, not MT7992 firmware compatibility. Forged count still reaches a backing
failure caught only by the emulator, and three timeout-delivery alternatives
reach native ready despite host failure. Published ownership remains retained.
Earlier queue MMIO publication, actual DMA backing/cache, immutable ownership,
concurrent publication and full attachment/recovery/parity remain open. See
`2026-09-09-npu-txfree-host/REPORT.md` for boundaries and reproduction.

## Bridge Allocation Extents

Native bridge/header teardown now reproduces the 58,879-byte allocation
mismatch: the header getter adds 65,536. Four stores in a bridge-first
component order overwrite a following descriptor allocation; after actual
core0 startup the first store is 4,352 bytes beyond the heap. Eight primitives
and two startup cases pass exact memory/write checks and identical replay.

A 68 KiB ROM-table sizing hypothesis contains the selected header operations
in isolation but exceeds the startup budget by 8,448 bytes. The checked
allocator holds before publication, so this is not a fitting implementation.
The SKB initializer's hard-coded 28,672 entries also rule out shrinking its
allocation table alone. Full capacity/initialization/host-count contracts,
consumer bounds and placement remain open. No memory layout is promoted.
See `2026-09-09-npu-memory-budget/REPORT.md`.

## Command Ring Placement

The allocator layout now accepts optional immutable typed placements outside
the heap. Definition extents, alignment, wrapping, overlap and cached addresses
are checked; fixed records preserve native metadata but consume no heap cursor.
Backing, initialization and a non-aliasing address namespace remain caller
contracts. The metadata/result ABI is unchanged; the RV32 layout is 32 bytes.

An alternate test-only startup binding reserves all 32,784 command-ring bytes
in a PROGBITS section at 0x84060000. Native core0 initialization and the 68 KiB
bridge fit with 24,352 heap bytes left, without reducing descriptor/SKB/ring
capacity. Four selected header stores, eight native cached lookups and later
compiled type 2/9/10 allocations verify. The bridge size is changed in emulator
memory, not packaged in the ELF or a raw firmware image.

2,362 allocator differential cases, 64,000 threaded calls, 8,194 native queue
pairs and 28 mutation controls pass, alongside startup failure/control checks.
All 37 retained detours still park all harts; three receipts replay identically.
The queue probes enter explicit instruction slices and do not execute their
downstream helpers. Native consumers have no publication fences. Physical
cache/PMA/alias and ordering, complete loader backing, full allocation/consumer
closure and boot/recovery remain open. This profile stays unpromoted. See
`2026-09-09-npu-command-ring/REPORT.md`.

## Native Queue Ordering

`tests/npu/command-ring-order-emulation.S` adds four IORW fences through three
native detours. Its 44-byte test-only sidecar replays original operations at
producer publication, consumer acquisition and slot return without changing
queue capacity. It does not add cache maintenance or authorize reclamation.

96 pinned herd/RVWMO cases cover selected stale-payload/reuse outcomes and
successful handoffs. Producer acquire alone is redundant in this particular
coherent-memory projection; the four-boundary implementation is retained.
384 register/CSR comparisons and 8,194 native queue pairs pass. All 40 detours
installed before reset retain the initial gates. The unfenced baseline and
both exact receipt replays pass. Native slices and formal projections have
different scopes; neither proves physical cache/PMA, initialization visibility,
full alias/consumer/lifecycle closure, performance or NPU recovery. The candidate
remains unpromoted. See `2026-09-09-npu-ring-order/REPORT.md`.

## Host Generation-Control Client

`control-client.c/.h` adds an unpromoted host byte codec and serialized
DISCOVER/BIND/STOP/STATUS client. It checks reply identity, exact stop epochs,
snapshot consistency and one outstanding local completion ticket. Failure or
abort is terminal; late completions cannot advance the client. No resource
allocation/free, Linux provider binding, reclamation or restart API is provided.

6,443 x86/AArch64 comparisons, eleven round trips with eight saved RV32 contexts,
twelve firmware scenarios, ten mutants and ASan/UBSan pass. A complete parked
mask is only a software observation. Explicit controls retain V1's same-epoch
wire-replay and replacement-provider ambiguity; transport ownership must close
both. See `CONTROL_CLIENT_CONTRACT.md` and the `2026-09-14-npu-control-client`
checkpoint. This does not make existing L1 or full-reset cleanup safe.

## V2 Control Identity And Transport

`control-v2.c/.h` and `control-v2-client.c` add an unpromoted 80-byte protocol
with a wire sequence, loader-supplied boot identity and checked STATUS binding.
It reuses the existing admission/barrier and host epoch/mask checks without
changing the V1 source or silently downgrading the wire protocol. Failed BIND
requests consume their sequence so duplicate replay cannot activate them later.

830 x86/AArch64 host and 254 x86/RV32 server comparisons, 21 scenarios, 51
malformed/boundary cases, six mutants and eight saved contexts pass. Original
firmware and V1 endpoints reject the new probe; the V1 regression receipt is
unchanged. A deliberately reused boot identity plus replayed old BIND remains
accepted, preserving the real loader uniqueness obligation.

Candidate provider patch 928 carries the complete request/reply through the
existing coherent bounce buffer; legacy GET drops the request body and remains
unchanged. 290 sanitizer assertions, six AArch64 kernel objects and strict
checkpatch pass, with unchanged public layout. It is not applied to packaged
sources. The real loader, 80-byte bootstrap gate, mt76 binding, provider lifetime
and physical drains remain open. See `CONTROL_V2_CONTRACT.md` and
`research/checkpoints/2026-09-14-npu-control-v2/REPORT.md`.

## V2 Cold-Bootstrap Admission

`bootstrap-v2.c/.h` and the staged dispatch-gate patch join V2 control with the
existing cold-start/IRQ and six-command bootstrap binding. Requests stay at the
exact pinned buffer and are either 12 or 80 bytes. Binding too early would
invalidate the original bootstrap freshness predicate; the new gate consumes
and rejects that BIND without setting the admission nonce. Setup can continue,
but duplicate replay cannot bind later. Missing/stale identity fails cold startup.

Native reset/early version/original callback tests reach the existing core0
boundary at 0x8400e330, including the 56 KiB TX-check clear. Three valid profiles,
six early-BIND cases, six cold failures, six callback failures, 28 transport
rejections, 786 policy cases, eight mutants and 453 sanitizer assertions pass.
Standalone V2 regressions retain their prior behavior. The original V1/V2
sources remain unchanged; the test builder applies the guard patch in isolation.

That first checkpoint did not cover all-hart/postgate or later-detour
composition, a real loader-identity generator or physical containment/drain
proof. No cleanup/restart capability is added. See `BOOTSTRAP_V2_CONTRACT.md`
and `research/checkpoints/2026-09-16-npu-bootstrap-control/REPORT.md`.

## V2 All-Hart Cold-Start Composition

The separate composition runner now installs all 50 retained detours before
native reset and relinks dependent components against the V2 base. Four
banked-PLIC profiles reach all eight initial parking gates with exact V2 masks;
six cold rejections, three allocator failures, seven missing-hook controls and
one stale-link control pass. 209 x86/AArch64 host and 96 x86/RV32 control
comparisons pass. The full ring and checked allocator/reset placement remain
selected, and no postgate packet sidecar executes.

A flat-PLIC limit control loses mailbox enable despite successful direct
handler calls. Initial parking composition is now covered; physical delivery,
loader identity/coherency/placement, postgate boot, provider/mt76 integration
and real drains/recovery remain open. No existing firmware C or packaged source
is changed. See `research/checkpoints/2026-09-16-npu-bootstrap-composition/REPORT.md`.

## Host Callback And Reference Lifetime

Two further unpromoted patches cover selected Linux CPU lifetime boundaries.
Provider 929 initializes managed watchdog work before IRQ registration and
cancels it after devres releases the IRQ producers, including probe failure.
mt76 007 unpublishes both providers, waits for RCU readers, and retains references
through the detach function's queue cleanup. They compose with the existing
control-provider and earlier host candidates without changing public layout.

193 corrected provider cases, 24 corrected reader schedules, baseline controls,
four mutants and 12 AArch64 kernel objects pass. Actual driver/helper C executes
against explicit framework models under ASan/UBSan. This is not a loaded-kernel
or hardware test. Earlier token/ring cleanup, complete consumer IRQ/NAPI and
device lifetime, V2 integration, physical drains and safe recovery remain open.
See `research/checkpoints/2026-09-16-npu-host-lifetime/REPORT.md`.

## Replay

From the repository in WSL, with clang 21, lld 21, Unicorn 2.1.4 and pyelftools:

```sh
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_barrier_protocol.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_barrier_core5.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_firmware_stop_irqs.py
python3 tests/npu/verify_barrier_evidence.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_barrier_workers.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/verify_worker_evidence.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_firmware_mailbox_dispatch.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_admission_protocol.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_admission_native.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/verify_admission_evidence.py
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_control_client.py
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_control_v2.py
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/build_control_v2_provider.py
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_bootstrap_control_v2.py
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_bootstrap_v2_composition.py
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_npu_host_lifetime.py
```

The runner accepts system `ld.lld`, otherwise the locally unpacked
`.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld`. Proprietary inputs remain in
the existing ignored `.local/npu-quiescence/firmware/` directory with SHA guards.

Next: complete boot/helper/IRQ path closure; physical copy/PPE/tunnel/DMA drains;
production host integration; validated SRAM/code placement and cache
validation; then common Linux L1/full-reset/probe-unwind/removal retention and
late-completion generation checks. Full host-adapter parity and client Wi-Fi
acceptance remain separate open requirements.
