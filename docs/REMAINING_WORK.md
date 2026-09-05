# Remaining W1700K Work

Updated 2026-09-05 from checkpoint `b385f6f`, the current reference and release
manifest. This is the resume checklist, not an estimate of completion percentage.
The current source includes the detached-provider allocation guard. The last
router-tested release is still Daybreak21 R1 with WLAN NPU compiled out.

## Priority 1: Safe NPU Recovery

- [ ] Reverse engineer the stock WiFi/provider mailbox reset coordinator and
  establish exactly what successful stop guarantees about DMA, pending TX/RX,
  completions and host-owned buffers. Stock module exit hooks are insufficient.
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

Detailed evidence: `research/checkpoints/2026-09-05-npu-attach/REPORT.md`.
All substantive changes must also be recorded in `W1700K_STOCK_PORT_LEDGER.md`.
