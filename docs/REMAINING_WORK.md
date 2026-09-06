# Remaining W1700K Work

Updated 2026-09-06 from Wi-Fi baseline/host queue evidence and release
manifest. This is the resume checklist, not an estimate of completion percentage.
The current source includes the detached-provider allocation guard and mailbox
publication/timeout-ownership fix (patch 926) and memory preflight (patch 927,
kernel/ABI/Ghidra verification passed). The last
router-tested release is still Daybreak21 R1 with WLAN NPU compiled out.

## Resume Blockers

Work is blocked pending the intended AP configuration/current client symptom
and resolution of the NPU tool restrictions. The provider INODE correction and
native DESC5/6/7/8 operations have not been retried or rerouted. The optional
PowerShell collector still awaits approved execution; direct SSH observations
are already complete. Generic goal continuation does not resolve these inputs.

A fresh L1 source review confirms ignored NPU stop/init returns and DMA restart
before NPU reinitialization. A return-check-only change would not establish
quiescence before token release or cover failed restart/removal, so none was
promoted as a safe recovery fix. Outstanding implementation and acceptance
items below remain open. See `research/checkpoints/2026-09-06-work-blockers/BLOCKERS.md`.

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
  The unpromoted cold-loader/reset gate now initializes candidate state through
  actual reset entry and rejects stale coordinator entries before BSS clear.
  Its phase/fault race is corrected and tested; physical fresh-load containment,
  complete native boot/IRQ callback installation and checked bootstrap admission
  remain open. API32/API23 unblock initialization; API18 is a no-op. Do not
  equate these callback replies or software READY with physical containment.
  The next candidate now installs strict IRQ8 through original registration,
  serves early version and an ordered, plan-bound six-command MT7996 memory
  sequence, and retains failed callback ownership. A late-cold-hart marker bug
  is fixed. Original core-0 L2/Wi-Fi initialization now executes through return
  and candidate idle ACK in five instruction schedules, with the entire 256 KiB
  L2 image checked. Three missing-register controls fail closed. A subsequent
  actual-reset test reaches all eight first startup gates in 14 model schedules;
  seven missing-gate and six input controls pass. Only each owner writes its
  parked slot with IRQs disabled; STOP stays epoch1 while unreleased. Ready/drain/
  release/arm remain zero. This is not hardware boot/containment proof; actual
  chip inputs and PLIC banking are unverified and post-gate initialization remains.
  Native success also occurs under forced SKB exhaustion and malformed host-ring
  inputs. Do not treat completion flags or the version fallback as readiness.
  Pinned host traces cover 38 attachment messages; 164 host C and 149 bounded
  callback cases pass. Two native RX descriptor callbacks now execute all helpers
  with 2,560 descriptor/ID and whole-memory checks, 21 negative controls and two
  strict denials. Native TX setup/TXDONE and four API21 selectors now add 17
  valid calls, 73 controls and seven strict denials; all reached allocation,
  lookup, descriptor and SKB-reset helpers execute. Four DESC5/6/7/8 cases remain
  unresolved after a tool restriction; the blocked lane was not retried or
  rerouted. The two separate API21 allocator substitutions are eliminated.
  SKB reset has only modeled lock/storage proof, not physical quiescence.
  INODE now has 16 exact native entry footprints, six complete selector2/7/4
  calls, four controls and three strict denials. Five wrapper loads span24
  bytes even for a 12-byte request; the retained provider allocation is256,
  so this is not a physical allocation-overrun finding. These three selectors
  ignore the extra stale arguments and have identical padded/unpadded memory
  effects. Run flags precede ICV clear and are not initialization witnesses.
  The provider-framing correction was interrupted by a tool restriction;
  unfinished files are preserved outside the firmware overlay and no fix is
  integrated. Do not retry or reroute that blocked operation.
  General mt76 commands remain closed. Close
  remaining callback consumers and failure-status propagation, full post-gate
  worker initialization, single-HIF TX1 publication, INODE 24-byte reads from
  12-byte logical requests, descriptor fallback validation, partial-init owner
  retention and the production cold-loader/request/cache contract.
  Single-HIF TX publication now has executed host-C evidence: 19 functions,
  two TX blocks, 12 traces, 60 controls and four mutants pass with explicit
  framework models. Band1 aliases TX0 and has no assigned physical queue ID;
  removing its alias alone selects ID 0. Resolve TX1 ownership and mapping as
  well as allocation/publication. Framework registration can fail after dual-HIF
  publication; this is not a ready/ownership-release certificate or live cause.
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
  Fresh R1 readbacks on 2026-09-06 found zero configured Wi-Fi networks, zero
  runtime interfaces and zero hostapd interfaces despite all radios reporting
  up. Restore only the user's intended approved network configuration before
  reproduction; it has been requested, not inferred. The new read-only baseline
  collector and fixtures have syntax proof only: unsigned WSL-share execution
  was blocked by RemoteSigned, and a process-only override is awaiting approval.
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

Current official snapshot comparison found no new relevant upstream fix;
our local guard, memory and mailbox corrections remain required.

Detailed evidence: `research/checkpoints/2026-09-06-npu-bootstrap/REPORT.md`,
`research/checkpoints/2026-09-06-wifi-baseline/REPORT.md`,
`research/checkpoints/2026-09-06-npu-hostqueue/HOST_QUEUES.md`,
`research/checkpoints/2026-09-06-npu-inode/INODE_CONTRACT.md`,
`research/checkpoints/2026-09-06-npu-attachtx/TX_CALLBACKS.md`,
`research/checkpoints/2026-09-06-npu-attachtxbuf/TXBUF_CALLBACKS.md`,
`research/checkpoints/2026-09-06-npu-startup/REPORT.md`,
`research/checkpoints/2026-09-06-npu-preflight/REPORT.md`,
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
