# NPU Generation Barrier Candidate - 2026-09-05

## Status

Concrete implementation progress, **not safe active-NPU recovery or stock
parity**. Added an unpromoted eight-hart barrier protocol and tested four core-5
instruction detours. No packaged source/config change, deployable patched NPU
blob, firmware image build, router contact or flash. Daybreak21 R1 remains the
last router-tested release, with WLAN NPU compiled out; this is not fresh live
readback. Both full project goals remain active.

The source lock is byte-identical to `364b0932749a435705bfa2d0e3ddfc93635d0108`.
Candidate source lives in `firmware/npu/`, outside the packaged OpenWrt overlay
and cumulative patches. Patch 926 remains the packaged-source checkpoint.

## Protocol Implementation

`firmware/npu/barrier.c` implements monotonically increasing, nonzero epochs:

- All eight harts must acknowledge the exact stop generation, including harts
  that have not started a workload. Each hart exclusively owns its slots.
- Five independently recorded drain categories are additionally required:
  ingress, copy engines, PPE/tunnel, Wi-Fi DMA and IRQ publication. This is a
  minimum required inventory, not proof that all hardware masters are covered.
- A drain record is accepted only after all worker acknowledgements match.
  Stale epochs and incomplete acknowledgements cannot authorize reclamation.
- Resource preparation precedes release. Release immediately revokes permission
  to reclaim, even if a subsequent restart fails. Each hart must refresh its
  cached state before the coordinator arms the new generation.
- Stop during partial restart creates a new epoch. Late refresh/drain messages
  cannot satisfy it. Repeated stop during the same outstanding stop is idempotent.
  Generation exhaustion fails closed; cold initialization requires independent
  containment of old users and cannot be a timeout escape hatch.

The contract requires a serialized coordinator, single-writer worker slots,
aligned coherent state and platform-specific safe points. Fences order accesses;
they do not prove DMA drain. There are no real hardware-drain callbacks or Linux
recovery call sites wired to this protocol yet. See `firmware/npu/README.md`.

## Executed Tests

`test_barrier_protocol.py` compiles the actual C both natively and as RV32IMAC.
Results match for **9,351 call pairs**, including 100 complete stop/resume cycles,
each of eight missing workers, each of five missing drain categories, eight
partial-refresh/stop cases, stale completions, invalid arguments and generation
exhaustion. Three mutation controls remove the final worker, drain or refresh
check; each is rejected by the corresponding omission test.

`test_barrier_core5.py` links actual RV32 detours, patches four SHA/preimage-guarded
sites **only in emulator memory**, and executes the original dispatcher and
indirect part-2 worker. The four sites are:

| Site | Boundary | Original 4 bytes |
| --- | --- | --- |
| `8400cb3e` | startup gate | `1c43fddf` |
| `8400cbbe` | outer consumer poll | `83570a00` |
| `8400cbca` | first empty-ring poll | `83576100` |
| `8400cc0c` | repeated empty-ring poll | `83576100` |

All four stop/restart cases pass. After original SET4/GET3 returns zero, the
worker parks with MIE disabled and does not consume the descriptor. Modeled
acknowledgements from the other harts alone still do not permit reclamation;
all five modeled drain witnesses are necessary. After resource replacement,
the native worker refreshes from consumer 0 to 7, leaves the old ring untouched,
and consumes only the new descriptor after arm. Native instructions at
`8400cc4e/8400cc52` advance the new consumer to 8 and mark the new entry `0xfe`.
The enqueue arguments are `[0x2222, 80, 0, 0, 1, 2]`.

An in-flight-helper test withholds core-5 ACK until the helper returns. That
helper's return is modeled, not execution of its device operations. Ten
passthrough cases preserve all integer registers except the replayed instruction's
destination and restore the incoming MIE state. Removing the repeated-empty-loop
detour is detected specifically as a missing park ACK. No production code or
state reservation is claimed: test addresses `84040000`/`3e920000` are synthetic,
and appending at the original blob end would overlap the hart-stack region.

## IRQ Ownership Findings

The earlier 424-function export omitted the registered UART entry `840047a0`:
auto-analysis mistyped its first instruction as a pointer. A separate SHA-guarded
Ghidra import seeds it, retains shared-SRAM volatility and permanent-worker
annotations, and exports **425 discovered functions, zero decompile failures**.
This is a corrected discovery count, not proof of complete code coverage. The
raw bytes never changed. The UART handler tail-jumps to command parser `84004604`;
its argument is visible in native instructions even where C omits the argument.

`test_firmware_stop_irqs.py` executes original registration `84003254`, table
dispatch `840030b2`, and these handlers after original STOP/GET3 zero:

- UART source `0x16`, table slot `3e9018a8`, callback `840047a0`: read and invalid
  command controls leave the RX gate zero; a modeled UART write command changes
  `3e9046ec` from 0 to 1. This path can invalidate a worker-only stop contract.
- PPE source `0x5f`, table slot `3e9019cc`, callback `84008f6e`: the empty-completion
  control does not release anything. A modeled pending completion reaches
  buffer-ID release `84004d0e` with argument `0x1234` after STOP/GET3 zero.
  Execution stops at release entry; physical buffer release is not claimed.

These are conditional software paths with modeled UART/PLIC/PPE registers,
stubbed printf/hart-ID and no physical interrupt delivery. The coordinator must
continue servicing barrier control without admitting UART writes, allocator
commands, ring reconfiguration or PPE ownership work that defeats its ACK.

The verifier locates five direct IRQ-registration call sites and three direct
copy-helper calls (`8400eb32`, `8400f198`, `8400f58e`, channels 1, 0 and 3).
The helper orders channel-register writes, polls a channel completion bit and
acknowledges it before return. Indirect callers, channel arbitration, cache and
bus completion guarantees remain open; no other SoC's HSDMA contract is assumed.

## Replay And Provenance

Run the four commands in `firmware/npu/README.md`. Test results and exact export
hashes are in `protocol-tests.json`, `core5-detour-tests.json`,
`irq-stop-counterexamples.json` and `evidence-verification.json`. The original
pristine code/data hashes remain:

- Code: `e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643`.
- Data: `61a75afb052feed2ceb2f3023e16f50317c05c78f9c8e564bf01924ce39c7ec1`.

Clang 21.1.8 and Unicorn 2.1.4 were used. System lld was absent; sudo required
interactive authentication, so no privileged install occurred. Ubuntu package
`lld-21` version `1:21.1.8-6ubuntu1` was downloaded and unpacked locally under
ignored `.local/npu-barrier/`. An initial deprecated clang linker-path argument
and assembly absolute-jump relocation failed before execution; the runner now
uses `--ld-path` and linker-defined absolute symbols. Final builds/tests pass.
The existing malformed Ghidra `_code_browser.tcd` preference warning remains
untouched; import, analysis, save and export succeeded.

No keys, credentials, stock binary inputs, calibration/recovery backups, package
downloads, compiler outputs or Ghidra projects are intended for publication.

## Required Next Work

- Extend reviewed startup, steady-state and in-flight detours to all harts.
  Core 1 caches ring pointers before its steady loop and must refresh them.
  Include the coordinator's IRQ/control admission and core-7 tunnel path.
- Prove copy/PPE/tunnel/Wi-Fi DMA producer closure and drain before recording
  real domain witnesses. Validate code/state reservations and cross-hart cache
  behavior. Do not treat these emulator results as containment proof.
- Wire a common Linux L1/full-reset/probe-unwind/removal retention policy only
  once the barrier is usable. Existing unchecked L1 failures and early full-reset
  token freeing are still unresolved. Tag/reject late host completions too.
- Continue full host-adapter TX/RX/refill/RRO/token/TXFREE ownership parity, then
  image, serial, fault-recovery and actual-client Wi-Fi/MLO acceptance. The
  disabled baseline is not a substitute for these full requirements.

Current reference, ledger, logging session and remaining-work list are updated.
