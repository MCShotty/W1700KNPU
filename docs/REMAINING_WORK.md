# Remaining W1700K Work

Updated 2026-09-06 from provider memory preflight, current reference and release
manifest. This is the resume checklist, not an estimate of completion percentage.
The current source includes the detached-provider allocation guard and mailbox
publication/timeout-ownership fix (patch 926) and memory preflight (patch 927,
kernel/ABI/Ghidra verification passed). The last
router-tested release is still Daybreak21 R1 with WLAN NPU compiled out.

## Priority 1: Safe NPU Recovery

- [x] Implement provider memory-layout preflight before WLAN initialization
  messages. Actual-C and DTB tests reject stale short TX-check tables, invalid
  addresses and overlaps; binary code/backup capacity is checked before copy.
  Kernel/ABI/object validation passes. This does not prove all other buffer
  capacities, hardware containment, complete bootstrap or send-failure rollback.
- [x] Correct the MT7996 TX-check reservation: native initialization clears
  56 KiB, not the previously reserved 26 KiB. The MT7996 include now moves BA
  beyond the full table; three affected DTBs and a generic control verify.
  This is source/DTB proof, not a new image or active-NPU hardware acceptance.
- [x] Establish current firmware STOP/GET limits and stock host mailbox ordering.
  Native RV32 emulation reaches core 5 through the hart dispatcher and reproduces
  descriptor consumption after STOP/GET3 zero. Standalone page-loop reachability
  remains unproven; do not count it as a second active ungated worker.
- [x] Fix mailbox publication order and preserve in-flight request buffers after
  timeout; 143 actual-code model assertions, both variants and kernel compile pass.
- [x] Resolve the conditional stock SER/reset registration path through connac_if,
  GE and PCI tables; original AArch64 instruction tests confirm status masking.
  This is static/model evidence, not proof of a live object's binding.
- [ ] Implement and prove all-worker quiescence or hardware containment before
  token/ring reclamation. Include slow path, both indirect workers, startup and
  in-flight work; close shared copy-engine/IRQ/PPE/tunnel ownership boundaries.
  Current STOP/GET cannot supply this guarantee; longer polling is insufficient.
  An unpromoted eight-hart protocol and 20 emulator detours for seven worker
  contexts and two coordinator/IRQ detours now pass tests, including all-eight
  shared-SRAM acknowledgement, cached-state refresh and IRQ admission. The
  versioned control candidate has no physical reclaim/restart capability.
  Complete boot/helper/IRQ closure, real drains, production placement/cache
  proof and host integration remain unimplemented/unproved. Individual legacy
  payload/indirect-call contracts and strict versus legacy transport also remain.
  The candidate now fits a conservative 32 KiB local SRAM test map with separate
  heap fixtures; reset/BSS/stacks, fixed tables and exact retained FIT reservations
  verify, but this is not a production reservation or complete boot/cache proof.
  Native stock GDMA WAIT polls CT0.ENABLE clear while the RV32 helper polls only
  DONE. Close owner/channel/alias/cache and actual start-clear semantics before
  using this as a physical drain witness; conditional stale-DONE tests are not
  a proved live-device fault.
  An unpromoted guard now enforces known hart/channel owners, pre-idle and
  DONE/ENABLE completion, with fault-only cross-hart publication and no return
  to legacy publishers after failure. All three callers and late completions
  pass native tests, but this is not a physical drain or restart implementation.
  The native boot test proves core 0 waits for SET API 32 before main returns;
  do not close bootstrap commands prematurely. Explicit contained barrier-state
  initialization and complete startup/host-adapter negotiation remain required.
- [ ] Handle L1 stop and reinitialization failures without resuming an unsafe
  datapath. Current upstream discards both return values.
- [ ] Correct full-reset ordering: do not release tokens or clean rings before
  NPU quiescence is established. Cover device removal/unload as well as recovery.
- [ ] Define bounded timeout/partial-restart behavior, owner retention on failure,
  reset generation and late-completion rejection. Do not assume an IRQ mask
  proves the independent NPU stopped accessing memory.

## Priority 2: Current-Source Stock-Port Implementation

- [ ] Reconcile the Daybreak19 legacy implementation with current mt76/provider
  interfaces; port justified behavior instead of copying the historical series.
- [ ] Complete dedicated host-adapter TX rings, producer/consumer and doorbell
  ownership, descriptor bookkeeping and completion accounting.
- [ ] Complete SKB/bufid/token lifetime and TXFREE equivalence, scatter mapping,
  DMA handoff, delayed completion, wraparound and teardown/drain behavior.
- [ ] Complete RX/refill and RRO/BA session/free-pool ownership, reset semantics,
  ping-pong packet fate and applicable PPE/FastTX paths.
- [ ] Expose only controls/counters backed by implemented, validated driver ABI.
  Historical numeric NPU modes are currently retired; do not add cosmetic modes.

## Priority 3: Verification and Release

- [ ] Extend actual-code fault tests to busy/timeout, partial initialization,
  late completion, reset, concurrent refill and removal. Separate models from
  kernel/runtime and hardware evidence.
- [ ] Build and inspect an NPU-active image only after the recovery gates pass.
  Verify full module/config consistency, FIT/DTB/layout and source provenance.
- [ ] Run serial-backed synthetic boot, reload, scan, reset, memory and traffic
  tests with known-good rollback. Do not switch the Codex PC's WiFi uplink.
- [ ] Obtain real-client association and throughput evidence for standalone
  2.4/5/6 GHz, two-link and tri-band MLO, including the iPhone/laptop regressions.
  Test client-to-client and wired-to-WiFi directions separately, with repeatable
  channel/width, signal, negotiated rate, NPU state and CPU-load observations.
- [ ] Long-running stability/memory/resource tests and fault recovery before any
  production-reliability claim. No current evidence establishes full stock parity.

## Other Unfinished Checks

- [ ] Resolve the CPU clock SMC readback/cpufreq-policy issue. Actual frequency
  remains unknown; do not reinstate the fabricated 1.2 GHz fallback.
- [ ] Broaden LuCI MLO save/apply and runtime-reporting coverage, including mobile
  layouts, radio combinations and shared-wiphy scan-cache semantics.
- [ ] Validate CPU/NPU realtime monitoring on the final stack. Queue/counter/PC
  activity must not be presented as measured per-core utilization without a
  supported measurement source; verify counter resets, polling and graph wiring.
- [ ] Verify regulatory/channel/width behavior using current driver/regdb data.
  The parked SA/channel161 configuration is not an approved active AP choice.
  Preserve transmit-power policy and do not add unvalidated AFC/advanced MLO.
- [ ] Verify SQM/adblock/SoftEther services end to end on the final image. R1's
  manifest includes SQM, adblock and their LuCI apps, SoftEther server and its
  custom LuCI app, and full wpad-mbedtls. Presence is not service acceptance;
  SoftEther is disabled by first-run defaults. Recheck relay/NAT traversal and
  blocklist-update behavior rather than importing claims from older images.

## Preserve While Cleaning

- Canonical source, patches, tests, ledger/reports and current/rollback releases.
- Factory/calibration, bootloader/recovery dumps, router backups and credentials.
- WSL recovery VHD and the only copies of archived prepared source/Ghidra work.
- Current build toolchain and source needed to resume without reconstructing
  the whole environment. Clean reproducible caches and verified duplicates first.

Detailed evidence: `research/checkpoints/2026-09-06-npu-preflight/REPORT.md`,
`research/checkpoints/2026-09-06-npu-bootmem/REPORT.md`,
`research/checkpoints/2026-09-06-npu-copy/REPORT.md`,
`research/checkpoints/2026-09-06-npu-layout/REPORT.md`,
`research/checkpoints/2026-09-05-npu-admission/REPORT.md`,
`research/checkpoints/2026-09-05-npu-workers/REPORT.md`,
`research/checkpoints/2026-09-05-npu-barrier/REPORT.md`,
`research/checkpoints/2026-09-05-npu-reset/REPORT.md`,
`research/checkpoints/2026-09-05-npu-quiescence/REPORT.md`
and prior `research/checkpoints/2026-09-05-npu-attach/REPORT.md`.
All substantive changes must also be recorded in `W1700K_STOCK_PORT_LEDGER.md`.
