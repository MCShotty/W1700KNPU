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
- The combined emulator ELF now adds 16 adapters for the other six workers:
  20 detours total, with five refill pointer caches and both fast-RX indices
  refreshed. Fast startup also needs index refresh. New tests pass 16 stop/
  resume, 96 differential register/MSTATUS, 17 missing-startup, six in-flight
  and six interrupted-refresh cases, three shared-SRAM seven-worker cycles,
  and 19 negative controls. Scheduling is serialized; coordinator 0, helper
  returns and physical drains are modeled. See the `2026-09-05-npu-workers`
  checkpoint for exact scope and remaining reachability boundaries.
- Coordinator admission now has two native detours and a strict mailbox-table
  adapter. Eight saved contexts supply actual-code ACKs while control remains
  available. Deferred IRQs, active-handler retention and fault propagation pass
  1,667 native/RV32 pairs plus native-handler tests. Physical reclaim/restart
  capabilities remain clear. See `ADMISSION_ABI.md`; no production integration
  or automatic upgrade of legacy STOP/GET3 is claimed.

The test linker addresses and state at `0x3e906000` are emulation fixtures, not
validated production reservations. Do not append code at the original blob end:
the next region contains hart stacks. No patched firmware binary is emitted.

`startup.c/.h` adds a cold-loader header and coordinator initialization gate.
Two native reset adapters reject stale entries before coordinator BSS clear and
hold workers until candidate state initialization completes. The loader must
independently contain prior users and upload the fresh template coherently.
READY is not full bootstrap, all-hart acknowledgement or physical containment.
Fault/publication races use one authoritative atomic phase; an already-passed
gate is not instantaneously revoked. See the `2026-09-06-npu-startup` checkpoint.

`bootstrap.c/.h` adds a separate MT7996-only, six-command reserved-memory gate
and early version query. The test binding installs its mailbox handler through
native IRQ registration before source 8 is enabled, uses a private validated
payload and retains active/resource state after failure. Late cold workers no
longer misread the coordinator's normal marker update as warm entry. General
mt76 setup remains closed; this is not complete native boot or a physical
ownership witness. See `BOOTSTRAP_CONTRACT.md` and the `2026-09-06-npu-bootstrap`
checkpoint for the limited footprint checks and exact execution boundary.

## Replay

From the repository in WSL, with clang 21, lld 21, Unicorn 2.1.4 and pyelftools:

```sh
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_barrier_protocol.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_barrier_core5.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_firmware_stop_irqs.py
python3 tests/npu/verify_barrier_evidence.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_barrier_workers.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/verify_worker_evidence.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_firmware_mailbox_dispatch.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_admission_protocol.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_admission_native.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/verify_admission_evidence.py
```

The runner accepts system `ld.lld`, otherwise the locally unpacked
`.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld`. Proprietary inputs remain in
the existing ignored `.local/npu-quiescence/firmware/` directory with SHA guards.

Next: complete boot/helper/IRQ path closure; physical copy/PPE/tunnel/DMA drains;
production host integration; validated SRAM/code placement and cache
validation; then common Linux L1/full-reset/probe-unwind/removal retention and
late-completion generation checks. Full host-adapter parity and client Wi-Fi
acceptance remain separate open requirements.
