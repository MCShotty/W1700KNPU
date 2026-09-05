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

The test linker addresses and state at `0x3e920000` are emulation fixtures, not
validated production reservations. Do not append code at the original blob end:
the next region contains hart stacks. No patched firmware binary is emitted.

## Replay

From the repository in WSL, with clang 21, lld 21, Unicorn 2.1.4 and pyelftools:

```sh
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_barrier_protocol.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_barrier_core5.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_firmware_stop_irqs.py
python3 tests/npu/verify_barrier_evidence.py
```

The runner accepts system `ld.lld`, otherwise the locally unpacked
`.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld`. Proprietary inputs remain in
the existing ignored `.local/npu-quiescence/firmware/` directory with SHA guards.

Next: all-hart startup/steady-state detours; coordinator mailbox/IRQ admission;
copy/PPE/tunnel/DMA drain contracts; production SRAM/code reservations and cache
validation; then common Linux L1/full-reset/probe-unwind/removal retention and
late-completion generation checks. Full host-adapter parity and client Wi-Fi
acceptance remain separate open requirements.
