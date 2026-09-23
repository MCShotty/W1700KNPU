# V2 Control Identity

Started 2026-09-14; original checkpoint completed 2026-09-16. The 2026-09-23
non-OC merge includes the provider transport and Linux client in the main
driver build and folds the bootstrap gate into the canonical V2 server.
V1 remains the comparison baseline. Real loader identity and mt76 recovery
caller wiring remain unfinished; integration does not prove safe recovery.

## Wire Contract

`control-v2.h`, `control-v2.c` and `control-v2-client.c` extend the existing
serialized admission/barrier operations with an 80-byte little-endian envelope.
The first sixteen words retain the V1 field positions, but use request magic
`0x3243514e` (NQC2), reply magic `0x3252514e` (NQR2), version 2 and size 80.
WLAN GET selector 15, API 0 and mailbox function 0 remain unchanged.

| Word | Field | Rule |
| --- | --- | --- |
| 16 | Sequence | Nonzero local ticket, echoed exactly; no wrap |
| 17..18 | Boot identity | Nonzero, immutable loader-supplied identity for this cold boot |
| 19 | Reserved | Must be zero in requests and replies |

Capabilities are exactly `0x27`: V1's discovery/status, stop and IRQ-admission
bits plus request identity. SAFE_RECLAIM and RESTART remain clear. Identity is
correlation under the caller contract, not cryptographic authentication or a
physical containment certificate.

- DISCOVER submits a zero boot identity and receives the current identity. It
  does not reserve a session or advance its sequence. A faulted admission/barrier
  reports FAULT, including during discovery.
- All other supported operations require the exact boot identity. A first
  structurally valid current-boot BIND reserves its nonzero host nonce before
  calling the existing BIND operation, even if that operation later returns
  BUSY, STALE_EPOCH or FAULT. Another nonce cannot replace this reservation.
- Every admitted non-discovery request consumes its sequence before execution.
  The sequence must exceed the previously consumed value. Duplicate/reordered
  requests report REPLAY=8, including an abandoned failed BIND after its original
  BUSY condition clears. An intentionally new sequence is not a duplicate.
- STOP and STATUS additionally require the reserved nonce to match an actual
  successful admission binding. STATUS no longer merely echoes an arbitrary
  session as V1 does. BAD_BOOT=7 identifies a boot mismatch.
- Invalid envelopes, wrong boot identities, foreign sessions and unsupported
  operations do not execute their requested mutation. Recognized errors obtain
  only the original read-only STATUS snapshot before returning their error.
- The host validates the entire V2 identity envelope before normalizing a
  private local copy for the existing V1 epoch/mask validator. No V1 packet is
  sent and no wire downgrade occurs. Callers must use the V2 API, not bypass it
  through the embedded base state.
- The inherited host protocol allows one outstanding request, permanently holds
  on matched errors/timeout/abort, and refuses sequence exhaustion. STOP after
  partial release advances the generation based on `released`, not `armed`.
  PARKED still means only the last accepted all-worker software observation.

## Loader And Lifetime Obligations

Only independently contained cold initialization may initialize the server
session. The real loader must supply a fresh boot identity before any hart or
control callback can use it. It must not repeat an old identity or reinitialize
session/admission state to escape a timeout. Host nonces must likewise be fresh
for distinct clients. Both states require the same serialized hart0 ownership
as the admission state.

The current test binding seeds the identity in modeled SRAM at `0x3e9063a0` and
places the 20-byte session at `0x3e906380`. These are linker/test reservations,
not approved production placement. The test initializer's seed write is not an
implementation or proof of the real loader's uniqueness, publication or
containment obligations.

A retained negative control deliberately reuses a boot identity and replays an
old BIND into a replacement coordinator. That replacement can answer the old
client. This is why loader uniqueness and exact provider/transfer lifetime
remain necessary even with the V2 checks. Ordinary STATUS against an unbound
replacement is rejected, including when its boot identity is wrongly reused.

An accepted snapshot is not durable: firmware can fault or ownership can change
after reply production. Real DMA/cache/bus completion, callback synchronization,
physical engine drains and a generation-specific reclamation/restart contract
remain outside this protocol. Neither counters nor nonces replace them.

## Provider Transport

The pinned `airoha_npu_wlan_msg_get()` allocates a zeroed request and does not
copy the caller's data into its body. That is unsuitable for this bidirectional
control envelope; it is not changed for ordinary legacy GET callers.

Patch 928, now part of `999-w1700k-integrated-npu.patch`, adds the exported `airoha_npu_wlan_control()` entry and a
disabled-NPU stub. It accepts only the complete 80-byte NQC2 prefix, uses the
existing serialized coherent bounce buffer, and returns the complete reply.
No public ops or device struct layout changes. The source fragment and generated
patch are in `research/checkpoints/2026-09-14-npu-control-v2/`.

The caller must retain a valid provider and its own serialized client state.
Transport success still requires the client's structured validation. The
existing mailbox pending-buffer policy retains ambiguous/timed-out transactions;
this transport adds no new cancellation, provider-removal synchronization,
DMA-unmap permission or proof of physical DONE/cache semantics.

## Integration Status

- The original `npu_bootstrap_transport()` remains V1-only. A subsequent V2
  bootstrap implementation admits 12/80-byte requests and gates BIND after the six
  setup commands. Its composition reaches all eight initial parking gates
  with 50 retained detours. See `BOOTSTRAP_V2_CONTRACT.md`; this is not complete
  postgate boot or a production loader.
- The production loader does not yet supply the new boot identity or reserve
  its session storage. Full reset-to-postgate boot and all retained detour
  composition with this endpoint are not proved.
- `linux-control.c/.h` now provide a kernel-bound executor with host fault/race
  tests and two linked AArch64 module profiles. The merged mt76 build compiles
  these shared sources directly. It still requires a caller-
  established cold provider lifetime and is not connected to actual mt76
  setup/L1/full-reset/removal. See `LINUX_CONTROL_CONTRACT.md`.
- Physical drains, ownership-safe cleanup/rearm, cache/PMA/alias correctness,
  provider references and in-flight callback retirement remain required for
  complete recovery. Hardware and client testing remain unperformed.

Replay commands and exact receipts are in the checkpoint `REPORT.md`. The
software tests execute actual x86/AArch64 host code, x86/RV32 server code,
strict-mailbox/worker instructions, and extracted provider C. MMIO, coherent
storage, IRQ invocation, initial drain witnesses, loader identity and scheduling
remain explicitly modeled. No router or restricted-selector operation ran.
