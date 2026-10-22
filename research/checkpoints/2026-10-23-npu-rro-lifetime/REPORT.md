# Complete RRO Caller Lifetime Characterization

This advances the retained-RRO port by executing the previously source-only
higher callers and managed-DMA bookkeeping. It does **not** implement retained
ownership, admit checked RRO, establish a physical use-after-free or complete NPU.

## Actual Selected C

`tests/npu/test_rro_lifetime_callers.py` compiles complete current RRO init,
free and worker functions, higher hardware initialization and unregister,
sender, public forwarding inline, provider dispatcher and raw mailbox framing.
Selected source bodies are verbatim. The current combined-module producer
`90abc8f3` rehashes its inputs/four actual AArch64 artifacts before selection.
Kernel managed allocation/free/match/release bodies and coherent inlines match
the locked Linux6.18.52 archive, not an assumed devres implementation.

The host-C fixture models low-level DMA, two device/devres registries, list/RCU/
locks, MCU/MMIO and unselected framework APIs. It executes real dmam bookkeeping
and release callbacks, not the kernel devres framework or concurrent hardware.
All128 blocks retain their real64KiB size; the session is8KiB. ASan, UBSan and
leak detection pass **1,021 characterization cases**:

- 830 devres/DMA allocation-prefix failures across V3/V3.1/WED profiles.
- 21 higher startup-stage failures, propagating their actual return paths.
- 24 checked/raw transport-status cases and three no-NPU ownership controls.
- Nine reset-worker combinations, including NPU/MCU errors and seven injected IDs.
- All129 raw-frame allocation failures, each ignored by the higher initializer.
- Disconnect between active check/RCU lookup, injected64-bit DMA narrowing,
  RRO-off, non-MT7996 active-NPU worker and full captured caller sequence.

These assertions describe existing behavior, not desired regression invariants:
checked0/1/3 are denied before transport, yet higher initialization can return0;
the reset worker frees its items despite NPU/MCU errors. CPU-only reset skips
MCU for the two injected invalid IDs, whereas the active-NPU branch sends them.
Injection does not establish actual producer/allocator/scheduling reachability.

Current source explicitly sets `dma_dev=npu->dev`. In the fixture, endpoint
cleanup leaves provider-owned allocations; provider cleanup later invokes real
managed release callbacks. Explicit RRO free removes the matching provider
records. Whole selected unregister calls RRO free after the modeled
`mt76_unregister_device` boundary and before MCU-exit/DMA-cleanup boundaries.
Their unexecuted internals may contain relevant quiescence: this order alone
does not prove the absence of a physical drain or a physical use-after-free.

Receipt `.local/npu-rro-lifetime-callers/lifetime-q3/result.json`, SHA256
`7d48599704c4fc362dec78a8f9450a5d29d625e5460a47fe407bee571feed627`.
The earlier892-case transport-boundary run and extraction failure are retained;
neither is substituted for the complete current framing run.

## Same Frames, Two Binary Scopes

The raw-mode actual caller/sender/dispatcher/framing chain emits134 real24-byte
frames:128 blocks, one session table and resets0/7/8/1023/1024. This bypasses
checked Linux admission only inside the declared fixture; it changes no guard.
`test_rro_lifetime_native.py` consumes those exact bytes in order:

- **Stock e743d1b5/61a75afb:** all134 reproduce exact whole-SRAM and synthetic
  alias projections, exact original store footprints, callee-saved/GP/TP/SP and
  MSTATUS. 6,344,077 instructions across116 distinct PCs match original stock
  bytes. Original clear runs normally; stock CODE stays unchanged.
- **Current4e43de6f/a282ca7a:** all134 return0 through the manifest/ELF-bound
  checked API24 hook. No original constructor or RRO alias write occurs. The
  complete SRAM/CODE projections allow only exact fault/phase/running fields
  and the declared256-byte modeled stack window. Actual headers compile the
  field offsets. ABI/MSTATUS and instruction bytes are checked.

An initial current-pair attempt stopped at the identity assertion at0x8400fc2c:
its four bytes are the checked jump, not the original wrapper's first bytes.
The split fixtures correct that assumption; no hook was removed or old receipt
rewritten. Current rejection uses absent cold context and synthetic memory,
not an admitted complete cold setup. It is not stock-effect qualification of
the current checked lane. The original Ghidra export is rehashed/reused, not
new disassembler analysis. No helper result is substituted. Existing call
limits2M/3M-us and the separate live original replay limits are unchanged.

Final receipt `.local/npu-rro-lifetime-native/stock-current-q3/result.json`, SHA256
`6e029ad77d0fafe46acd285c95050f32f8f3794c12ad3842c37628b7062a52fb`.
The prior complete q2 composition is historical; q3 adds full header/input and
generated-artifact identity coverage without changing the executed scopes.

## Remaining Implementation

Implement provider/endpoint-bound retained extents, identity/generation/order,
atomic/process handoff, higher error handling, partial/ambiguous publication,
late completion, reset/IRQ/DMA drain and retirement together. Concrete requirements
are in `firmware/npu/RRO_LIFETIME_REQUIREMENTS.md`. Merely propagating errors or
keeping RRO permanently denied does not meet the full goal.

All56 build-tool units pass, zero skips. Fresh real Windows-D capacity checks
retain the old jobs'1GiB output budget,64MiB new-output allowance and2GiB margin;
guest free space is not treated as host space. Jev's six bounded claim checks
distinguish modeled effects, current denial and unfinished/physical scope;
probabilities remain in private evidence, not test proof.

No production firmware/source-lock/raw-pair/UI/WiFi, protected image, hardware,
flash, module load, native job limits/checkpoints or subagent work changed.
Image a3f1d04b remains the offline-qualified checked-IRQ image, not boot proof.
The full NPU objective stays active. `EVIDENCE.json` binds the final seal,
preservation checks and separately observed original job state.

## Original Replay Service OOM Failure

The final audit supersedes earlier live-job observations: systemd reports
`w1700k-npu-bytewise-callers-q2.service` failed with `Result=oom-kill`,
`OOMPolicy=stop`, main process SIGTERM and memory peak7,589,953,536 bytes.
The journal explicitly records the kernel OOM killer and a1.6G swap peak.
All old replay/controller/guard PIDs are now absent and the guard FLOCK is gone.
The system has roughly8GB configured guest RAM/2GB swap at this observation.
The retained kernel ring did not supply an individual victim/allocation record;
do not invent a precise culprit, cross-clock elapsed time or causal attribution.

Both logs now pass PCIe-tail0/1/2, then command31. Both output directories
contain `inode-prefix-0`, but neither a final result nor a controller terminal
receipt exists. Prefix evidence is not an INODE/caller verdict. Logs, native
observations, prefixes and process/journal diagnostics are retained and hashed.
This is a confirmed resource termination, not a completed test or demonstrated
firmware assertion. Our134-frame RRO probes are separate completed executions.

Do not describe the old jobs as still running or automatically restart them.
Next inspect/profile the retained INODE-prefix replay's memory requirement,
budget RAM as well as storage and use controlled nonconcurrent full-scope
replays if sufficient. Preserve source identity, full sizes, limits and fault
coverage; do not lower checks or substitute a partial result. Full current cold
and checked-IRQ caller qualification remains required after that recovery.
