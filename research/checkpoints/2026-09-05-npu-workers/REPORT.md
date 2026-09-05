# NPU Worker Barrier Extension - 2026-09-05

## Status

Extended the unpromoted barrier from four core-5 detours to **20 test-only
detours covering seven worker contexts**. These are compiled RV32 adapters in
emulator memory, not a deployable NPU blob. Coordinator IRQ/control admission,
hardware drains, production placement and common Linux recovery remain open.
Both full project goals remain incomplete. No router contact, image build,
flash, radio association or configuration change occurred.

Packaged source/config and patch 926 are unchanged from `657aad1`; Daybreak21 R1
with WLAN NPU compiled out remains the last router-tested release, not a fresh
readback or full stock parity claim. The common C protocol is unchanged.

## Implementation

`tests/npu/barrier-workers-emulation.S` adds 16 SHA/preimage-guarded detours.
The combined linker retains the four original core-5 adapters. Each new adapter
saves caller-clobbered registers, four possible cached-pointer registers and
MSTATUS in an aligned 128-byte frame. It disables MIE before polling, permits
only cache refresh before READY, and restores registers/MSTATUS before replaying
the replaced instruction or branch pair. Core-7 JAL replay preserves the native
return address. All code/state addresses remain emulator-only reservations.

| Hart / Worker | Startup | Outer | Additional Poll | Persistent Refresh |
| --- | --- | --- | --- | --- |
| 1 / refill | `8400ce1c` | `8400cf10` | `8400cf26` idle | Four register pointers and one stack pointer |
| 2 / fast RX | `8400ec7e` | `8400ecc2` | `8400ece6` idle | Two 16-bit stack indices, including startup |
| 3 / slow RX | `8400e440` | `8400e4d4` | Outer also covers idle | No persistent ownership cache identified at this boundary |
| 4 / TX done | `8400d0ea` | `8400d144` | `8400d160` idle | No persistent ownership cache identified at this boundary |
| 5 / indirect part 2 | `8400cb3e` | `8400cbbe` | `8400cbca`, `8400cc0c` empty | Existing consumer-index refresh retained |
| 6 / indirect part 1 | `8400cd3e` | `8400cd8a` | `8400cd9e` retry | No persistent ownership cache identified at this boundary |
| 7 / tunnel | `84000b24` before init | `84000b36` before iteration | Complete iteration returns to outer | No persistent ownership cache identified at this boundary |

Refill's cached producer-register pointers originate in globals `3e902cf0`,
`3e903904`, `3e90395c`, `3e902a80`, `3e904630`, each plus 12. They remain in
`s4`, `s3`, `s2`, `s1` and original stack+12. Refresh replaces all five while
parked. Global slot addresses held in other registers are not ring pointers.

Fast RX caches two producer indices in original stack+8/+10, loaded from
`*3e904700+12` and `*3e9046fc+12`. The first implementation refreshed only steady
and idle gates. The startup test rejected it: entry had already zeroed both
indices before the gate, so a nonzero replacement ring caused spurious copy
requests. The startup adapter now refreshes them too, after host preparation.
A dedicated removal control retains this regression. This assumes prepared
ring slots are valid before release, as required by the protocol.

## Executed Evidence

`worker-tests.json` records the current results:

- 16 new stop/resume cases, one per site; replacement-ring reads and no helper
  work before arm. Refill reads all five replacement producer registers.
- 96 original-versus-detour differential cases: 16 sites, input values 0/1/3,
  MIE off/on, all integer registers and complete modeled MSTATUS compared.
- 17 missing-startup-dependency cases across harts 1/2/3/4/6 acknowledge stop
  without entering a helper. These start at worker entries, not full boot.
- Six in-flight helper cases withhold ACK and drain permission until a modeled
  helper return and the native iteration reach a gate. No asynchronous device
  completion is implied by those modeled returns.
- Six stop-during-refresh cases interrupt the actual adapter immediately before
  READY publication. Epoch-2 completion is rejected after stop-3; the worker
  parks for epoch 3 without arming or granting reclamation.
- Three cycles schedule seven saved native worker contexts against one SRAM
  image, with randomized stop/refresh order and alternating ring locations.
  Unscheduled worker slots remain at the previous epoch. All seven must park
  and refresh; a missing coordinator-0 acknowledgement still rejects progress.
  All observed ring reads use the current cycle's replacement region.
- 19 negative controls are rejected: four missing idle/retry hooks, five missing
  startup hooks, complete refill/fast refresh removal, individual removal of
  each of five refill and two fast caches, and fast-startup refresh removal.
- The prior four core-5 stop/resume cases, in-flight case and ten register/MIE
  cases pass against the same combined ELF. Separate original protocol, core-5
  and UART/PPE counterexample suites also pass unchanged.

This is serialized instruction emulation, not seven simultaneously executing
cores. Helpers for refill, copy, slow-path processing, TX done and tunnel init/
dequeue/processing have controlled returns; modeled refill helpers update their
consumer output slot. Core-7 IRQ registration executes with mapped PLIC memory,
but interrupt delivery is not modeled. Standalone tests model other harts;
the shared test models coordinator 0 and all five physical drain witnesses.

Original code/data hashes are unchanged:

- Code: `e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643`.
- Data: `61a75afb052feed2ceb2f3023e16f50317c05c78f9c8e564bf01924ce39c7ec1`.
- Combined ELF: `0df4cfa2400fbfd4a67e6d8b6ea33ec28423c739e51dd0e01f22971af1d17c71`.

`evidence-verification.json` binds sources, result JSON, allocated ELF sections,
all 16 original four-byte preimages, signed JAL targets and the previously
verified Ghidra assembly export. It inventories results; it is not a separate
whole-program or hardware proof. No new Ghidra reanalysis was needed for these
already recovered worker loops.

## Replay

From the canonical WSL repository, using the existing clang/lld and pinned
Unicorn/pyelftools environment:

```sh
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_barrier_workers.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/verify_worker_evidence.py
```

The existing four replay commands in `firmware/npu/README.md` remain applicable.
Private firmware inputs, compiler outputs and mutation ELFs remain ignored.
No input binary, recovery data, key or credential is published.
Source reconstruction verifies all 34 OpenWrt and three LuCI changed files.
Secret scans find none in the candidate/tests/checkpoint directories; three
unchanged historical documentation prose false positives were reviewed.
See `source-export-verification.json` and `publication-review.json`.

## Remaining Integration

- Coordinator-0 IRQ/control admission must retain a working control mailbox
  while excluding unsafe UART writes, PPE buffer release and mutating mailbox
  commands. The prior native UART/PPE STOP counterexamples remain unfixed.
- Worker-entry tests do not close full boot/pre-worker initialization, all
  helper-internal paths, indirect calls or interrupt routes. Those require
  continued reachability and ownership review before production integration.
- External ingress closure, copy/PPE/tunnel/Wi-Fi DMA completion, coherent state
  placement, code reservation, stack headroom and cache/bus ordering remain
  unproven. IRQ masking and worker ACKs alone do not authorize hardware reuse.
- The old STOP/GET3 ABI does not describe this generation barrier. In particular,
  refill can park before clearing its legacy busy flag. A versioned host/firmware
  contract is required; do not repurpose unused selectors without negotiation.
- Implement common Linux L1/full-reset/probe-unwind/removal failure retention
  and late-completion generations. Ignored L1 errors and full-reset token release
  before NPU quiescence remain unresolved in packaged source.
- Complete host-adapter TX/RX/refill/RRO/token/TXFREE ownership parity, then
  image/serial/fault tests and actual-client Wi-Fi/MLO/stability/service gates.

Current reference, ledger, logging session and remaining-work list are updated.
