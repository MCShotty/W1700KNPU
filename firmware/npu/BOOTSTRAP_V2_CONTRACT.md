# V2 Cold-Bootstrap Adapter Candidate

This is an **unpromoted software candidate** for the selected MT7996 bootstrap
profile. It joins V2 control with the existing cold-start/IRQ registration and
six-command memory setup. It is not a production loader, complete all-hart boot,
physical quiescence certificate or safe L1/full-reset/removal implementation.

## Components

- `bootstrap-v2.c/.h` provide cold session initialization, the exact request
  transport gate, and bootstrap-specific BIND policy.
- `001-gate-v2-bind-for-bootstrap.patch` in the
  `2026-09-16-npu-bootstrap-control` checkpoint stages a gated V2 dispatch entry.
  It leaves standalone `npu_control_v2_dispatch()` behavior unchanged. The
  canonical V1/V2 sources are not patched in place; the test builder applies
  this candidate to an isolated copy. Linking the adapter requires this patch.
- `tests/npu/bootstrap-v2-platform-emulation.c` composes the new adapter with
  the existing reset, admission, strict-mailbox and native bootstrap callback
  bindings. Its addresses and loader bytes are test fixtures, not approved
  production reservations.

## Initialization

The session must be zero, the supplied 64-bit boot identity nonzero, and common
admission/barrier state structurally fresh. Initialization rejects an active
handler, session nonce, common fault, noninitial generation, release/prepare/
arm, old worker/drain slots or deferred IRQ state. Failure preserves the V2
session and faults common admission; it does not erase prior session history.

The native test path calls this initializer through the existing cold-start
gate. It does not externally initialize the session after boot. Missing identity
or stale session bytes prevent startup READY and source-8 installation. The
identity is copied once; subsequent changes to loader input do not change it.

These checks do not establish physical cold containment or uniqueness across
real boots. The loader must independently contain previous users, supply fresh
storage and a never-reused identity, publish it coherently, and only then release
harts. The V2 reused-identity/replayed-BIND limitation still applies.

## Transport

The V2 bootstrap profile accepts only synchronous mailbox function-0 flags
exactly equal to 1, at the exact pinned request-buffer base. The declared region
must be 256 bytes, word aligned, and wholly inside the existing 0x80000000 to
0xc0000000 aperture. Allowed request sizes are 12 for the original bootstrap
packet or 80 for V2 control. In particular, 64-byte V1 control is rejected by
this profile before payload access.

Failed native setup still leaves V2 diagnostic transport available at the same
retained buffer. A different address, alias, offset, size or flag does not gain
access because setup failed. Real backing, cache coherence, pending-transaction
ownership and provider/callback lifetime remain platform obligations.

The original V1 `npu_bootstrap_transport()` is unchanged. Selecting this V2
binding is explicit; adding a source file does not upgrade a packaged image.

## Binding Order

The existing bootstrap `fresh()` predicate requires an unbound admission
session. An early successful BIND would therefore prevent later memory setup.
The new gate permits BIND only when the selected six commands have completed,
no bootstrap operation remains in flight, and retained-region metadata is
exactly 0x1e. Failed or invalid bootstrap/common state returns a binding fault;
incomplete setup returns BUSY. The ordinary admission check still rejects an
active handler.

The gate is applied only after V2 identity validation, session reservation and
sequence consumption. It cannot overwrite an existing protocol error. Early
BIND leaves admission unbound and does not mutate bootstrap progress, so the
setup sequence can still finish. Replaying that abandoned request afterward
returns REPLAY, not a delayed successful bind. The failed host client remains
terminal. There is no automatic retry or nonce replacement.

The intended caller order is discovery/version inspection, the six selected
bootstrap commands, then BIND/STOP/STATUS. Discovery does not bind a session.
After binding, the legacy bootstrap/version path remains closed by the original
freshness predicate; V2 supplies the supported diagnostic path.

The retained mask means four memory regions have been published. It is not the
barrier's physical drain mask, and completing the six commands does not prove
full firmware, ring, ownership or engine readiness. SAFE_RECLAIM and RESTART
remain absent. STOP/STATUS cannot authorize cleanup.

## Evidence Scope

The test runner executes reset and strict IRQ8 installation, early native
version query, all six original bootstrap wrappers/setters, and the original
56 KiB TX-check clear to the existing core-0 boundary at 0x8400e330. V2 control
replies and state are compared with compiled native C; the host helper executes
as both x86 and AArch64 code. Native callback-return failures are explicit fault
injections, not observed device errors.

Pure policy cases compare x86/RV32 execution with expected whole-arena state.
They reuse an emulator with a fully reset data arena; they are not cold-reset
proof. Native reset scenarios use separate fresh instances. ASan/UBSan models
callback success separately from the original RV32 callback tests.

Standalone V2 regressions include the earlier saved-worker-context tests, but
that is a separate profile. The first checkpoint did not compose every later
retained firmware detour with the new cold binding or prove all-hart postgate
boot. MMIO, interrupt invocation, scheduling, loader identity and coherent
storage remain modeled. Production placement, real loader publication,
shared-provider/mt76 integration, physical drains and recovery/rearm remain open.

## Subsequent Composition Checkpoint

`tests/npu/test_bootstrap_v2_composition.py` now checks this binding with all 50
retained detours installed before native reset. Four banked-PLIC profiles reach
all eight initial parking gates, with V2 binding before or after worker arrival.
Six cold rejections, three allocator failures, seven missing-hook controls and
a stale-link control pass. The full ring, checked allocator/reset ordering and
68 KiB bridge definition remain selected; no postgate packet work executes.

A fifth profile deliberately uses flat PLIC storage and loses mailbox enable
while direct handler invocation still succeeds. Thus software control replies
do not establish real interrupt delivery. The checkpoint closes initial
all-hart composition only, not complete boot, production placement/publication,
provider lifetime or physical ownership/drain/recovery. See
`research/checkpoints/2026-09-16-npu-bootstrap-composition/REPORT.md`.
