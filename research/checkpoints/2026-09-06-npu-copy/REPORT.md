# Guarded NPU Copy Completion

Date: 2026-09-06. Status: **unpromoted source/ELF candidate; not a hardware drain**.
Both full goals remain open. Packaged source/config and patch 926 are unchanged
from `f48c25da94f4d1d33fdc509b3e22a209267ca1b4`; no image or module was installed.

## Implementation

Added `firmware/npu/gdma.c/.h`, a bounded-observation copy sequence based on the
pristine RV32 helper and the actual stock kernel GDMA accessors/WAIT contract:

1. Reject unsupported owner/channel pairs, oversized lengths and zero poll limits.
2. Observe CT0.ENABLE clear before changing source/destination or launching work.
3. Clear the channel's old DONE, fence and verify the clear by readback.
4. Publish source/destination and the original `(length << 16) | 0x23` control
   value with explicit I/O fences. CT1 and other channels are not modified.
5. Require both DONE and CT0.ENABLE clear, then clear/read back DONE before success.

Separate return codes identify invalid input, existing busy work, unsuccessful
preclear, incomplete completion and unsuccessful acknowledgement. Poll limits
count register observations, **not elapsed microseconds**. Length zero preserves
the original programmed control value; zero-length hardware behavior is not
established by these tests.

The test-only legacy binding detours `0x840053a6` to the new implementation. It
gates local MSTATUS.MIE, obtains the native hart identity, and restores incoming
MSTATUS only on success. Failure atomically latches the common barrier fault and
holds the context indefinitely, without returning to the legacy void caller,
acknowledging a worker stop, refreshing caches, or freeing anything. This
fail-stop hold intentionally needs independently proved containment/recovery;
it is not itself a working restart implementation.

Review caught and corrected an initial integration mistake: worker harts must
not call the coordinator-only admission failure routine. The new
`npu_barrier_fail()` latches only the shared fault word with release ordering.
Coordinator-owned admission fields remain untouched. Native coordinator control
reports the fault and denies new handlers, while reclaim/restart capabilities
stay clear. Cross-hart SRAM ordering still requires hardware validation.

## Known Owners

The hash-bound 427-function firmware export has three immediate copy callers:

- Hart 2: root `0x840001a0` -> `0x8400ee0a` -> fast worker `0x8400ec48` ->
  `0x8400e87a` -> channel 1 at `0x8400eb32`.
- Hart 3: root `0x840009bc` -> slow worker `0x8400e3fc` -> `0x8400f638` ->
  `0x8400f0c4` -> channel 0 at `0x8400f198`.
- Hart 3: slow worker -> `0x8400f8be` -> `0x8400f528` -> channel 3 at
  `0x8400f58e`. The intermediate `0x8400a3f6` route is also in this worker.

The guard enforces only these owner/channel pairs. The route inventory follows
known direct calls and tail calls, not every indirect callback, missing function,
computed MMIO access, CPU module or independent bus master. It therefore does
not establish complete copy-engine ownership closure.

## Instruction Tests

- 48 successful cases cover the three owner/channel pairs, old and early DONE,
  and lengths 0, 76, 1792 and 65535. Synthetic DMA writes copy actual buffer bytes
  inside emulator memory; the guard and caller instructions are native RV32.
- 65 invalid-owner/limit cases perform no MMIO. Nine failure/retention cases cover
  preexisting busy work, failed preclear, DONE while active, missing DONE, idle
  without DONE, failed postclear, wrong hart, an existing fault and a fault during
  copy. Late modeled completion cannot resume descriptor publication.
- The original `0x8400f0c4` caller reads stale `0xa5a5` metadata and publishes READY
  under the explicit stale/early-DONE model; the guarded caller waits and reads
  `0x3344`. Both `0x8400e87a` band branches and `0x8400f528` fragment/clamp paths
  also execute: 14 additional success/failure cases retain source/descriptor and
  producer-index ownership on failure. All three original caller paths have
  conditional early-completion counterexamples. Hardware start/visibility rules
  remain unverified, so these are **not proven live-device Wi-Fi root causes**.
- A stop injected after launch permits the already-admitted copy to finish but
  receives no premature hart ACK from the copy helper. Other-hart polls and the
  initial startup witnesses are modeled; the test does not invent a physical drain.
- Six ABI cases preserve callee-saved registers, GP, SP and incoming MIE. MMIO in
  the binding occurs with local IRQ admission gated. Coordinator C functions see
  the shared fault and refuse new work without a worker modifying their state.
- Eight compiled negative controls reject DONE-only completion, overwriting busy
  channels, missing owner checks, timeout-as-success, missing fault publication,
  cross-owner admission writes, missing IRQ gating and returning from failure hold.

All twelve suites pass, including the prior worker/admission tests against the
combined guard ELF, all eight saved contexts, register/refresh/in-flight checks
and earlier mutation controls. Four linker placement controls also pass.
The 64-poll and default 65,536-poll ELFs each reproduce byte-for-byte. Two default
budget tests reach exactly 65,536 observations, hold the original caller and
remain held after late modeled completion.

## Final ELF Review

The default ELF SHA256 is
`6397a75c3ee80cac0a80de478eb9ac41dc4584c223c394deca0605b7dd6f8fa0`.
Ghidra fully analyzes that extension ELF, discovers 50 executable functions and
exports all three selected new functions without failure. Shared SRAM and GDMA
registers are marked volatile before analysis. Assembly confirms owner checks,
bounded ENABLE/DONE polling, clear/readback ordering, MIE gating/restoration,
the fault-word-only store and the permanent failure branch. The extension's
allocated text is `[0x84040000, 0x8404246a)`, still an unpromoted reservation.

This is review of the extension ELF, not a claim of complete original firmware
coverage or full boot. The raw original code/data remain the pristine inputs
identified in the previous layout checkpoint. No deployable firmware blob is
emitted by this workflow.

## Read-Only Router Check

Pinned SSH bound to the existing Ethernet address confirms
`Gemtek W1700K (OpenWrt U-Boot layout)`, `gemtek,w1700k-ubi`, kernel 6.18.44 and
revision `r1001+23-c1992346fc`. WLAN NPU remains compiled out; the provider is
present but not attached to mt76. All three radios are reported up by ubus;
that is not beacon, association or throughput proof. No cpufreq policy exists.

No raw MMIO read was performed: the `devmem` command is absent. No workaround,
helper installation, radio/association/configuration change, module load or
flash was attempted. `router-readonly.json` records scope. A separate-client
failure reproduction was requested; no fresh client result is available here.

## Replay And Remaining Work

```sh
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/run_copy_regressions.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/verify_copy_evidence.py
python3 tools/migration/verify_source_export.py --output research/checkpoints/2026-09-06-npu-copy/source-export-verification.json
```

Current packaged source reconstruction passes for 34 OpenWrt and three LuCI
files. Earlier checkpoint receipts remain unchanged. The new verifier binds
sources, result inventory, ELFs and Ghidra exports; the manifest seals this report
and evidence. Existing earlier verifiers bind their historical source versions.

Do not advertise physical reclaim/restart or deploy this guard before complete
boot/placement/cache and all-producer/device drain closure. In particular, verify
that ENABLE clear implies completion visibility on the actual mapped memory and
close every other writer/reset domain. Implement the common Linux L1/full-reset,
probe-unwind/removal retention and validated restart policy. Full host-adapter
TX/RX/TXFREE/RRO/PPE parity, service acceptance and actual-client Wi-Fi/throughput
validation remain open; the R1 baseline is not substituted for those goals.
