# RRO Ownership Journal

Status: implemented portable bookkeeping, not an operational RRO ABI or a
physical retirement mechanism. `rro-lifetime.c` is part of the normal RV32
archive and the canonical provider Kbuild. Compiling it does not connect any
provider, mt76, native transport or MCU caller. Current selectors0/1/3 remain
denied by operational admission.

## Identity And Storage

The caller supplies an initially zeroed, exclusively owned lifetime object and
an immutable plan. Serialize every operation on that object. Only the sticky
first-error latch may be written asynchronously. Plan identity includes exact
64-bit provider and endpoint identities, boot and nonce identities, an epoch,
and the V3, V3.1 or V3.1-WED profile. These opaque values do not acquire real
device references. The integrating code must hold those references and the
backing allocation storage independently.

Enroll the actual allocation prefix, in selected-source order. The complete
profiles have 139, 139 and 137 extents: 128 element blocks of 65,536 bytes,
eight MSDU blocks and an 8,192-byte session table, with the profile-specific BA
or EMI allocations. Preserve the full CPU pointer, DMA handle and byte length.
Reject CPU overflow/overlap, unrepresentable high DMA bits, alias overlaps and
overlap with declared mailbox, TX, RX-event, native or BAR spans. The alias
check models the selected firmware's address window; it does not prove physical
PMA/cache correctness or exclusive reservation of undeclared memory.

The journal stores metadata, not the allocation bytes. Its integrity checks
assume readable, writable caller-owned storage. They do not make arbitrary
unmapped pointers safe or establish cross-thread synchronization.

## Publication And Reset

`publish_begin` constructs the exact four payload words for each of the 128
element publications followed by the session-table publication. It latches
possible exposure and allocates a nonzero ticket before returning a command.
The actual transport must bind that ticket to its particular transfer. A
transport error retains the ambiguous extent and a sticky error; it is not
permission to free or retry from a new identity. An exact late completion can
update bookkeeping before the CPU join but cannot clear the sticky error.

All 1,025 session IDs, including the special final ID, have separate reset
generations. Requeuing an outstanding generation returns its existing ticket.
NPU completion must match that generation and ticket before the MCU phase can
begin. Each transport has one in-flight credit. Failures retain the phase,
ticket and first transport error. Successful MCU completion advances the
generation; old completions cannot complete a newer request. Scalar
constructors2/7 are not interchangeable with these commands.

The request counter never wraps and reserves the final representable ticket
for retirement. Real generation creation, work-item retention, process/atomic
context handoff and completion authentication are integration obligations.

## Closing Is Not Reclamation

`retirement_begin` blocks new work and records the current or immediately next
stop epoch. Closing does not discard pending publications, reset requests or
extent metadata. An exact ticket/epoch CPU join must be recorded before any of
the five domain observations. After that join, transport completions are stale.
Only the complete set reaches `NPU_RRO_DRAIN_RECORDED`.

That state records caller assertions. It is not proof that a physical IRQ,
DMA engine, native firmware, cache or PMA domain is quiescent. There is no free,
reset, cancellation, rearm, reinitialization or reclamation-capability API.
Even a fully recorded retirement retains every extent. The actual handoff
must precede the selected explicit RRO frees, not merely final mt76 detach.

See `RRO_LIFETIME_REQUIREMENTS.md` for the remaining operational and physical
contract. Never use a successful journal call as a substitute for it.

## Executed Coverage

`tests/npu/test_rro_owner.py --name <fresh-name>` compiles the selected mt7996
geometry into the host harness. Its 5,279 ASan/UBSan/leak cases cover complete
profiles, every allocation/publication prefix, all session IDs, reset ordering,
duplicates, ambiguous errors, late completions, credit limits and every subset
of the five domain observations. Addresses and devices are synthetic metadata.
The counter boundary uses injected near-exhaustion state, not billions of calls.

Three controls remove the exposure latch, ticket comparison or join gate.
Each must compile and fail at its specific assertion, without a sanitizer
fault. The 134 emitted frames must exactly match the independently executed
selected caller frames. These are host executions and byte comparisons, not
execution of the new RV32 or AArch64 journal instructions. Consult the dated
checkpoint for the actual compilation, module-link and image qualification
scope; old images do not gain new source merely because their hashes still match.
