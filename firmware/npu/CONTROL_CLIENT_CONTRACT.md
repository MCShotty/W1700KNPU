# Host Control Client Candidate

`control-client.c/.h` is an **unpromoted, transport-independent host helper** for
the candidate `ADMISSION_ABI.md` V1 protocol. It is not linked into mt76, the
Linux NPU provider, or a firmware image. Existing L1 recovery is not made safe
by adding this helper. No API authorizes buffer reclamation or engine restart.

## State And Wire Behavior

1. Independently contained cold initialization supplies a fresh nonzero 64-bit
   session nonce. There is no warm reinitialization, failure-clear or retry API.
2. Successive `request()` calls produce DISCOVER, BIND, STOP and then STATUS.
   Requests are exactly 64 little-endian bytes, including zeroed output words.
3. Only one request is outstanding. Each receives a monotonically increasing,
   nonzero local completion ticket. Ticket exhaustion holds the client rather
   than wrapping. A concurrent second request leaves client and wire untouched.
4. `complete()` first matches the outstanding ticket, then checks transport
   success, accessible reply length, magic/header/API/version/size, echoed
   operation/nonce, capabilities and remote operation status. Any matched
   failure holds the client permanently. Late/unrelated completions are ignored
   without reading their storage; duplicate successful completions do not advance.
5. BIND must retain the discovered epoch. STOP expects that epoch if already
   unreleased, or exactly the next epoch if released. The latter request is
   refused at `UINT32_MAX`. STATUS must remain in the accepted stop epoch, with
   unreleased/unarmed state and no READY bits. Worker/drain masks cannot lose
   already observed bits; release/arm history cannot change while polling.
6. A complete `0xff` parked mask changes the phase to `PARKED`. This is only the
   last accepted software observation, not a live or durable ownership permit.
   The client remains available for STATUS; it never progresses to cleanup.
7. `abort()` invalidates idle or pending clients after provider loss or caller
   cancellation, preserving any earlier error. It does not cancel firmware work,
   retire a transfer or free its storage.

Capabilities must equal the reviewed V1 value `0x07`. Even a reply claiming
SAFE_RECLAIM or RESTART is rejected. A compile-time assertion requires an
intentional client review if the shared advertised capabilities change.
Synthetic full drain masks still cannot produce host reclamation authority.

## Caller Obligations

- Serialize every call, including completions/timeout/abort, and retain the
  client object for every possible callback. Do not alias the client with its
  request/reply buffers. Initialization is not a recovery escape hatch.
- Bind the client and each local ticket to the exact provider lifetime and
  transfer. Prevent new submissions during detachment and call `abort()` on
  invalidation. Actual RCU/module references, callback synchronization and
  shared-provider coordination remain Linux integration work.
- Supply separately owned, aligned, mapped and pinned mailbox storage. The
  byte codec permits an unaligned local copy, but the firmware transport still
  requires its own aligned 64-byte accessible buffer. This code allocates,
  maps, publishes, cancels and frees nothing.
- Publish requests with the provider's real DMA/cache/ownership protocol. Read
  a stable reply only after the exact transfer's validated synchronous DONE.
  Translate all provider errors to nonzero `transport_error`; raw mailbox DONE
  alone is not a successful structured reply. Never read a timed-out buffer
  merely to pass it to `complete()`.
- Retain timed-out/aborted transport storage until actual retirement, including
  late firmware access. A terminal client does not prove firmware inactivity,
  successful cancellation or DMA containment. Data buffers and callback owners
  have separate lifetimes that this helper cannot release.
- Neither a successful probe, accepted STOP, complete parked mask, nor any
  snapshot can authorize existing L1/full-reset/removal cleanup. Real platform
  drains and a generation-specific ownership contract remain prerequisites.

## Explicit Protocol Limits

V1 has no per-request wire sequence. STATUS echoes the submitted nonce without
checking that it is bound. Consequently, old same-epoch STATUS bytes supplied
with a new local ticket can be accepted, and a newly initialized replacement
provider with the same epoch cannot be identified by STATUS alone. The tests
retain both counterexamples. They are deliberate transport/lifetime contract
violations, not claims that the current Linux provider exhibits either behavior.

The nonce separates sessions for BIND/STOP; it is not authentication. The local
ticket correlates callbacks; it is not wire replay protection. A future stronger
wire contract would need a reviewed firmware incarnation/request identity and
snapshot/fault semantics. Until then the provider must enforce exact transfer
ownership, and this helper remains unsuitable as a destructive recovery permit.

## Verification Scope

`tests/npu/test_control_client.py` executes the same helper natively and as
AArch64 instructions, comparing return values, complete client state and wire
bytes while checking callee-saved registers and stack. RV32 round trips use the
existing strict mailbox adapter and original IRQ/worker instructions, including
eight serialized saved contexts. Initial running-state drain witnesses, helper
returns, coherent memory, interrupt invocation and MMIO are modeled.

The sanitizer harness uses actual host/admission/barrier C with ASan/UBSan and
invalid-address controls for rejected lengths, timeouts and late callbacks.
This is not a Linux kernel/module integration, full native boot, concurrent
hardware scheduling, cache/PMA, physical drain or router validation. Evidence
is in `research/checkpoints/2026-09-14-npu-control-client/control-client.json`.
