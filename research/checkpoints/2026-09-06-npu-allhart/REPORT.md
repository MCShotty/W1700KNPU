# Cold-Start Hart Parking And RX Callback Closure

2026-09-06, source checkpoint `bc82345173efec5049e4cfc6e399966ab82b08f5`.
New instruction-level integration tests and evidence only. Firmware sources,
platform bindings, packaged patches/configuration, router state and release
images are unchanged. Neither full Wi-Fi nor NPU goal is complete.

## All-Hart Integration

`test_multihart_cold_boot.py --suite` installs all 26 existing test-only detours
before execution: two cold-start, two coordinator/IRQ, one strict mailbox
registration, twenty worker gates and the GDMA helper guard. The compiled ELF
is unchanged:
`bdb64d12d738bdef85a747d0b638e6b148c1c534410fd893348fbaf5908e2931`.
Linking the helpers alone is not counted as installing the original-code hooks.

Each hart enters the actual original reset and main dispatch, with its own
saved CPU context and native stack. Harts arriving before core 0 remain inside
the candidate cold-start wait; their saved interrupt-disabled state is retained
when resumed. Only core 0 initializes the candidate barrier and admission state.
Core 0 executes the previously proved native Wi-Fi initialization and reaches
its idle adapter. The other harts execute their original prologues through the
first installed startup gate, then publish their own parked acknowledgement.

| Hart | First Startup Gate | Native Path Reached |
| --- | --- | --- |
| 0 | Main return `0x84000188` | Full core-0 Wi-Fi initialization, then idle |
| 1 | `0x8400ce1c` | `0x84000190 -> 0x8400cdc6` |
| 2 | `0x8400ec7e` | `0x840001a0 -> 0x8400ee0a -> 0x8400ec48` |
| 3 | `0x8400e440` | `0x840009bc ->` chip/module prologue `-> 0x8400e3fc` |
| 4 | `0x8400d0ea` | `0x84000a82 -> 0x8400d0ae` |
| 5 | `0x8400cb3e` | `0x84000aa6 -> 0x8400cb0e` |
| 6 | `0x8400cd3e` | `0x84000aca -> 0x8400cd1a` |
| 7 | `0x84000b24` | `0x84000aee`, before tunnel initialization |

Fourteen complete model scenarios pass: eight reset-order rotations covering
every core-0 arrival position, plus six chip-feature/peripheral-input profiles.
Every nonzero parked-slot write is checked against the executing hart and its
interrupt-disabled state. Each hart writes its own slot three times: initial
parking and two retained-context polling passes. There are no Python calls to
initialize or advance the barrier, record drains, prepare, release or arm it.

Actual strict mailbox calls bind a session, issue STOP as workers arrive and
report the growing parked mask. STOP is idempotent while the initial epoch has
not been released: request and all final parked slots remain 1. The final mask
is `0xff`; all eight ready slots, five physical drain slots, released and armed
remain zero. Capabilities remain `0x7`, without safe-reclaim or restart.
The complete 256 KiB L2 image remains unchanged from the core-0 oracle.

## Explicit Hardware Models

The reused printf, UART printf, hart-ID and delay substitutions remain visible.
Two additional **CSR result models**, already used in the earlier reset test,
supply the selected hart ID at the compiled startup adapter instructions.
Unicorn otherwise reports hart 0 there even when original-code hart reads are
modeled correctly. No native initializer or allocator is stubbed to succeed.

Hart 3 reads `0x1fb00064` and `0x1fb00284` to select a native chip-feature row.
The tested raw values are synthetic, not observed W1700K register contents.
Profiles exercise the distinct module-fallback combinations, including absent
peripheral `0xdeadbeef` reads and native indirect writes derived from nonzero
synthetic register inputs. The two fixed zero stores at `0x84000982` and
`0x8400098c`, and the tail call at `0x84000996`, are additionally checked against
GNU RV32 disassembly because the earlier Ghidra export lacks separate functions
for those tiny entry points. Register storage is not physical power-down proof.

The native per-hart common routine uses the same numeric PLIC address window.
Two hypotheses are explicitly tested, without selecting a hardware truth:

- **Shared flat storage:** late worker initialization clears core 0's source-8
  enable bit. The strict callback pointer still survives. Manually driven saved
  IRQ frames do not prove that a physical mailbox interrupt would arrive.
- **Per-hart storage:** core 0's source-8 enable bit remains set while other
  harts configure their own banks. This is a model, not verified address-window
  banking, arbitration or interrupt delivery.

Both hypotheses reach the same software parked state. Physical PLIC mapping,
native trap/IRQ timing, simultaneous harts, cache coherency and hardware DMA
ownership remain open. Original core-0 initialization already writes DMA-enable
controls before parking; all-eight software acknowledgement does not drain
those engines or establish physical containment.

## Negative Controls

- Seven missing-startup-gate controls reach the displaced native continuation
  with no acknowledgement from the target hart. No downstream helper return is
  fabricated to make these controls pass.
- Four missing-register models stop at the chip-ID read, power-down input,
  indirect target write and fixed module-control write.
- An unknown synthetic chip reaches the native reboot path; the unmodeled
  `0x1fb00040` write at `0x84005a22` stops execution before any acknowledgement.
  No physical reboot is emulated or performed.
- Omitting the compiled-entry hart-ID model reproduces a harness defect:
  Unicorn misidentifies a late worker as the coordinator and the candidate
  faults while retaining bootstrap resources. This is not a firmware bug fix.

The final suite therefore contains 14 positive scenarios, seven missing-gate
controls and six input/model controls. Imported project sources are hashed
before and after execution; the immutable ELF is checked before use.
Independent review replayed one flat and one banked case, matched the final
receipt, checked all 39 input hashes, saved contexts and owner writes, and found
no actionable issue within first-gate scope. See `ALLHART_REVIEW.md`.

## RX Callback Closure

The separate bounded sidecar closes original SET DESC API1 selectors 0 and 2,
with the host's 1,536 and 1,024 descriptor counts. Every native initializer,
lookup, allocator and mutex helper executes. Independent complete-memory and
byte-write-footprint checks cover 2,560 RX descriptors, 2,560 software IDs,
1,024 slow records, 256 auxiliary records and 2,000 statistics bytes.

Two valid callbacks, 21 negative controls and two strict-rejection checks pass;
parent replay matches the 318,165-byte saved JSON exactly. Allocation exhaustion
can leave partial ownership while the wrapper returns success; zero packet
bases/counts and oversized counts are not reliably rejected by native helpers.
Unchecked dynamic allocation extents can cross the modeled SRAM boundary.
These are conditional emulator findings, not identified live-client failures.

This is direct original callback execution, **not** permission to send API1
through the candidate. Strict admission still rejects it. Eleven of the prior
thirteen pending callback cases remain; two other API21 cases still use modeled
allocator returns. Full details, prerequisites, exact extents and controls:
`../2026-09-06-npu-attachrx/RX_CALLBACKS.md`.

## Remaining Work

Workers are parked before their consuming loops and, in hart 7, before tunnel
initialization. Complete post-gate initialization, remaining DESC/TX/TXBUFSPACE
callbacks, checked host attachment and partial-failure ownership are still open.
Opening these APIs from successful native return values alone would be unsafe.

The production loader/placement/cache/request-lifetime contract, physical drains
and containment, Linux L1/full-reset/removal recovery, complete TX/RX/TXFREE/RRO/
PPE parity and actual-client Wi-Fi acceptance remain required. R1 is still the
last router-tested release with WLAN NPU compiled out. No protected calibration,
recovery or private inputs were changed or uploaded.

## Replay

```sh
cd /home/captain/W1700KNPU
export PYTHONPATH=.local/npu-reset/python-lib
python3 -B tests/npu/test_multihart_cold_boot.py --suite
python3 -B tests/npu/test_attach_rx_callbacks.py --check
python3 -B tests/npu/verify_allhart_evidence.py
```

The canonical ledger, current reference, logging session and remaining-work
checklist record the new software proof and its remaining boundaries.
