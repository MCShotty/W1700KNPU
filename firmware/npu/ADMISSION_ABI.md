# Coordinator Admission Candidate

This is an **unpromoted candidate**, not the packaged firmware/driver ABI.
Neither physical reclaim nor restart capability is implemented. Do not deploy
these adapters with an unmodified host driver or infer safety from legacy
STOP/GET3. Production boot, memory placement and hardware ownership remain open.

## Ownership Contract

- Only serialized hart 0 with local interrupts disabled accesses admission
  state. Other harts disable their datapath IRQs before acknowledging the common
  barrier. Initialization of both states requires independently contained cold
  startup; it is not a timeout/reset shortcut.
- Close admission before publishing a stop generation. Native IRQ and legacy
  mailbox calls hold an active count until their complete callback/dispatch
  returns. The coordinator acknowledges only from its idle boundary, never
  from an IRQ-entry predicate. Its idle loop restores incoming MSTATUS so the
  control mailbox can still run.
- While closed, source 8 remains available for the strict control mailbox.
  Other sources are deferred, masked and read back before completing the PLIC
  claim. Device FIFO entries are not consumed by this path. A mask failure or
  active-count fault propagates into the common barrier fault, invalidating
  reclamation. A datapath IRQ after a stop-generation IRQ drain similarly faults.
- `retire_irq()` records an actual platform retirement witness only while the
  stop generation is reclaimable. It does not retire a FIFO or buffer ID itself.
  Pending events prevent coordinator READY/open. Deferred events after release
  require a new full stop before they can be retired. Remembered enable bits are
  restored only after arm and successful admission opening.
- IRQ publication drain excludes the still-functional barrier control mailbox.
  Its coherent request buffer has separate ownership and must remain pinned
  until DONE, including timeout/late completion handling from provider patch 926.

## Transport

The test platform binding accepts synchronous, dynamic requests only. It rejects
static-buffer registration, no-wait flags, function indices outside the eight
callback slots, unaligned/zero addresses and payload sizes outside 8..256 before
dispatch. It does **not** validate every individual legacy command's payload
schema, pointer range or indirect callee. Legacy callbacks run only while
admission is open; their original STOP/GET semantics are not upgraded implicitly.

The new control packet uses mailbox function 0 (Wi-Fi), WLAN GET API 0 (NPU info)
with selector 15. On the SHA-pinned original firmware, this selector is explicitly
unsupported: native execution writes zero to the first output word without
changing the remaining request. That is a failed probe, not capability support.
The candidate recognizes only its complete versioned 64-byte envelope.

All fields are aligned little-endian 32-bit words:

| Word | Request | Reply |
| --- | --- | --- |
| 0 | `0x3f`: GET operation, selector 15 | Unchanged |
| 1 | API 0 | Unchanged |
| 2 | `0x3143514e`, bytes `NQC1` | `0x3152514e`, bytes `NQR1` |
| 3 | Version 1 | Supported version 1 |
| 4 | Size 64 | Size 64 |
| 5 | Operation | Unchanged |
| 6 | Expected generation for mutation | Current generation |
| 7..8 | Host-chosen nonzero session nonce | Echoed request nonce |
| 9 | Ignored | Status |
| 10 | Ignored | Capabilities |
| 11 | Ignored | Parked-hart mask for current generation |
| 12 | Ignored | Ready-hart mask for current generation |
| 13 | Ignored | Physical-drain witness mask for current generation |
| 14 | Ignored | Released generation |
| 15 | Ignored | Armed generation |

Operations are DISCOVER=0, BIND=1, STOP=2 and STATUS=3. Discovery/status are
read-only and remain callable while faulted; STATUS reports the fault. BIND
establishes one session nonce, requires the current generation and no active
handler, and is idempotent for the same nonce. It cannot replace an existing
session. STOP requires that nonce and the current generation; it requests stop,
not completion or permission to free anything. Old-generation retransmissions
are rejected, with current generation reported. The nonce is ownership/session
separation, not authentication against an untrusted host.

Status values: OK=0, BAD_MESSAGE=1, BAD_SESSION=2, STALE_EPOCH=3,
UNSUPPORTED=4, BUSY=5, FAULT=6. The mailbox transport reports success for a
recognized structured reply even when its operation status is an error.
The host must check both levels, magic/version/size, echoed operation/session
and generation; old firmware's mailbox success alone is insufficient.

Capabilities currently equal `0x07`: discovery/status, stop request and IRQ
admission. `NPU_CAP_SAFE_RECLAIM=0x08` and `NPU_CAP_RESTART=0x10` remain clear.
A production host must require the relevant physical capabilities and a complete
generation-specific ownership contract before enabling active-NPU recovery.
There is no wire operation to submit fake drain bits, retire events, prepare,
release, arm or bypass a fault. Those require real platform integration first.

## Limits

The adapters use emulator reservations for barrier/admission state and code.
They replace the core-0 return and IRQ dispatcher and rebind its mailbox table
entry after modeled initialization. Full boot, retained SRAM, simultaneous
cross-hart/cache behavior, actual interrupt/trap delivery, physical DMA/FIFO
retirement and Linux recovery/removal are not validated. The strict transport
is not full legacy static/no-wait compatibility. Tests are in the
`2026-09-05-npu-admission` checkpoint; the common barrier protocol is unchanged.
