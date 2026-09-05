# NPU Coordinator Admission Candidate - 2026-09-05

## Status

Implemented unpromoted coordinator admission and a versioned control envelope.
The original UART-write and PPE-free stop counterexamples are blocked by the
candidate's emulator adapters while control status remains available. Eight
saved RV32 contexts now acknowledge one stop generation in shared modeled SRAM.
This is **not physical quiescence, full NPU parity or a completed Wi-Fi fix**.

Packaged source/config is unchanged from `37a8352`; patch 926 remains current.
No router contact, image build, flash, radio association or configuration change.
R1 with WLAN NPU compiled out remains last router-tested, not fresh live readback.
Both full project goals remain active.

## Recovered Dispatch

The earlier 425-function Ghidra export missed two registered code entries:

- Wi-Fi dispatcher `84003a9c`, written by native common mailbox initialization
  to callback slot `3e900d2c`. It maps the payload to the `40000000` DRAM alias,
  decodes operation bits 4..7 and indexes 34 SET / 11 GET callbacks.
- Tunnel adapter `84003a86`, written to the following callback slot. It performs
  a payload-indexed indirect tail jump. Its payload index has no local bound.

A new SHA-guarded project seeds both entries and the prior UART handler. Full
analysis/export completes with **427 discovered functions, zero failures**.
This count is not complete code coverage. The original binary is unchanged.

Native execution confirms the complete route:
`840030b2 -> 84003cd6 -> 84003a9c -> 8400fc2c -> 8400e084`.
Original STOP, idle GET and restart callbacks execute through that route.
Three additional protocol hazards are reproducible in modeled memory:

- Reported length zero still dispatches SET and reads its payload, because
  the Wi-Fi dispatcher overwrites the length argument with the header.
- No-wait mode publishes DONE before callback payload reads. The test stops
  at host-notifier entry after the callback, not at a physical host interrupt.
- Static-buffer function index 12 overwrites the Wi-Fi callback pointer because
  its unchecked four-bit index crosses into the callback portion of the table.

These are software/protocol findings, not evidence that a live client triggered
these malformed requests. The current host's normal path uses synchronous
requests; individual legacy payload and indirect-call validation remains open.

## Candidate Implementation

`firmware/npu/admission.c/.h` implements serialized coordinator state:

- Admission closes before the stop generation is published. Native IRQ and
  legacy mailbox callbacks hold an active count; idle cannot acknowledge until
  all admitted calls return. IRQ admission reads state without calling poll.
- Mailbox IRQ 8 remains available while closed or faulted. Other coordinator
  IRQs are deferred, masked, read back and then PLIC-completed without running
  their device handler. PPE FIFO entries and UART input remain unconsumed.
- Deferred events block READY/open until real platform retirement is recorded
  during a reclaimable stop. Retirement is not implemented by that record API.
  A new event after release requires another stop. Mask/active-count faults and
  a post-drain IRQ propagate into the common barrier fault, revoking authority.
- The coordinator's idle loop disables local IRQs for the state operation and
  restores MSTATUS to leave a control-service window. Saved IRQ enable bits
  are restored only after arm/open; cold initialization clears that saved mask.

Two test-only four-byte detours replace IRQ entry `840030b2` and core-0 return
`84000188`; the mailbox IRQ table slot is rebound to the strict adapter. The
combined ELF also contains all 20 existing worker detours. Native stock handlers
and mask helpers execute where admitted. No deployable patched blob is emitted.

The candidate wire ABI uses a 64-byte WLAN GET-info selector-15 envelope with
`NQC1` request / `NQR1` reply magic, version, expected epoch and a bound 64-bit
session nonce. Native original firmware rejects this selector by writing zero;
it cannot be mistaken for a supported response by a checking host. Discovery,
binding, stop request and status are implemented. Physical reclaim/restart bits
remain **clear**, and there is no wire operation to fabricate drain witnesses.
See `firmware/npu/ADMISSION_ABI.md` for fields and ownership rules.

The strict test transport rejects static registration, no-wait mode, out-of-range
callback indices, zero/unaligned addresses and lengths outside 8..256 before
dispatch. It does not validate every legacy command's complete payload schema
or physical pointer range. An unmodified legacy host must not use this candidate
as a safe-recovery replacement; old STOP/GET3 is not upgraded implicitly.

## Executed Tests

- **1,667 native/RV32 call pairs**, all 192 IRQ sources, 257 wire lengths,
  session/epoch/version faults, nested active calls, deferred refresh/open,
  late IRQ after drain, and propagated fault behavior. Six removed-check
  mutations fail with specific admission/ownership assertions.
- Original UART write and PPE pending-entry cases are blocked after versioned
  stop. Mailbox status and errors still return. Legacy restart stays denied
  until modeled platform retirement, refresh, arm and admission opening.
- An admitted native PPE handler holds its lease at bufid-free entry. Idle ACK
  remains old until a modeled free-body return, native FIFO pop and full
  handler/dispatcher return. This does not execute the physical free body.
- Eight contexts execute against one SRAM image: all seven worker ACKs and
  the coordinator ACK come from actual RV32 code. Wire status reports `0xff`;
  absent physical drain witnesses still reject reclamation. Scheduling is
  serialized, not simultaneous or a hardware cache/coherency test.
- Two stuck mask-register readback cases fault the barrier while status remains
  available. Ten IRQ-number boundaries, 16 static-registration rejections,
  malformed length/address/no-wait cases, five callee-saved/SP/GP/RA ABI cases
  and dirty saved-mask cold initialization pass. Omitting the IRQ detour
  reproduces the UART write and fails the negative control.
- Same combined ELF passes prior worker regressions: 96 register cases,
  16 stop/resume, six in-flight and six interrupted-refresh cases; core 5's
  four stop/resume, ten register cases and in-flight case also pass.

Exact sources/results/ELFs and original preimages are bound by
`evidence-verification.json`. The combined ELF SHA256 is
`891af9bd8dbf0e551edac9f29cb57c52cc650977baff78419cab0e69b7b0481a`.
Original code/data hashes remain `e743d1b5...4643` / `61a75afb...7ec1`.
Clang 21/lld 21 and Unicorn 2.1.4 execute the tests. No full image was built.

## Replay

```sh
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_firmware_mailbox_dispatch.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_admission_protocol.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_admission_native.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/verify_admission_evidence.py
```

The unsigned PowerShell Ghidra wrapper was blocked by RemoteSigned on the UNC
path. The installed headless CLI was invoked directly; execution policy was
not changed. Analysis, save and export succeeded. The existing malformed
`_code_browser.tcd` preference warning is unchanged and was not repaired here.
All 34 OpenWrt and three LuCI changed source files reconstruct successfully.
Private firmware inputs, compiler/mutation binaries and Ghidra projects remain
ignored; no keys, calibration, recovery data or raw stock blobs are published.

## Required Next Work

- Prove physical ingress/copy/PPE/tunnel/Wi-Fi DMA and IRQ-publication drain,
  including pending and late completions. Completing/masking a PLIC interrupt
  is not retiring a device event. The candidate cannot supply physical witnesses.
- Validate full boot and pre-worker paths, remaining helper/indirect/IRQ routes,
  production code/SRAM reservation, stack headroom and cache/bus ordering. Tests
  start at worker entries/core-0 return and invoke IRQ functions on a separate
  modeled stack; they do not execute a complete hardware trap/boot sequence.
- Implement the production host negotiation and shared L1/full-reset/probe-
  unwind/removal retention policy. Ignored L1 errors and premature full-reset
  token freeing remain unresolved in packaged source. Preserve mailbox-buffer
  ownership independently while control remains available.
- Finish host-adapter TX/RX/refill/RRO/token/TXFREE parity and legacy command
  contracts, then full-image, serial/fault, actual-client Wi-Fi/MLO, throughput,
  stability and service acceptance. The disabled R1 baseline is not completion.

Current reference, ledger, logging session and remaining-work list are updated.
