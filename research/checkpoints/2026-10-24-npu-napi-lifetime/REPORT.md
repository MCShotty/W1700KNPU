# Tracked NAPI And Permanent NPU IRQ Cleanup

Date: 2026-10-24. Full NPU goal: active. No subagents, module load or hardware action.

## Implemented

MT7996 opts into separate NAPI registration and enabled bitmaps, serialized by a
control mutex initialized at device allocation. Existing drivers remain untracked.
Cleanup closes registration/enable, disables only enabled instances, waits for
explicit RCU readers, deletes added instances, and frees/nulls dummy netdevs.
Already-disabled failed-reset and incomplete startup prefixes cannot trigger a
second napi_disable. Full/L1 reset sweeps registered slots rather than guessing
from live-provider/queue flags and joins disabled poll tails before reset/token work.

Core RX, NPU RX and MT7996 TX explicit RCU sections cover completion/rearm tails.
RX budget0 avoids RX/page-pool processing; TX budget0 still cleans TX without
napi_complete_done. The native control contract distinguishes ownership release
from poll callback completion; host fixtures pause precisely across that boundary.

Permanent NPU IRQ close serializes with registration/start under the device
mutex, rejects new registration/start/rearm, suppresses IRQs and removes requested
exact-line/queue-cookie actions. A physical mask/read/ACK error is retained but
cannot bypass CPU unbinding. IRQ zero is not an unrequested sentinel. Normal
unregister orders MCU exit, PCI close, NPU close, NAPI join, then token/DMA cleanup.
PCI-error/core-free fallbacks repeat these CPU controls without duplicate release.

## Current Verification

- Actual selected NAPI controls, three poll bodies and full/L1 RX enable loops:
  44 measured setups,12 compiled intended negative controls, ASan/UBSan/leaks
  and separate GCC TSan.
  Includes partial registration, registered-but-disabled cleanup, retry controls,
  all three paused completion tails before/after an earlier disable, zero/exhausted
  budgets, provider loss, duplicate registration and the non-opt-in control path.
  Actual reset enable-loop fragments also require allocated descriptors as well
  as registered state; a registered-but-unallocated RX queue is not scheduled.
- Actual checked IRQ/controller/provider/registration/close C:360 setups and
  ten compiled negative controls, ASan/UBSan/leaks. New cases cover partial IRQ
  registration, late admission, IRQ0, masking errors and provider disappearance.
  NAPI helpers in this IRQ fixture are modeled; actual controls execute separately.
- Actual selected PCI/remove/unregister C:234 setups/14 intended controls.
  NPU/NAPI internals are modeled here; these are not whole-driver kernel runs.
- Final actual selected detach C:16 setups/two compiled controls, ASan/UBSan/leaks.
  Newly introduced CPU controls require the driver opt-in flag, including absent/
  present provider models. All final regressions/links follow this correction;
  the first successful qualification cohort is retained, not silently relabeled.
- Current BA37/eight/separate TSan, owner23/14, creation19/12, BA18/six, worker23/
  eight, joint6150 resets/three controls, broad456/four, callers1090/seven and142
  tooling/observer/inventory/phase units pass, zero skips. Caller NAPI/IRQ internals
  are explicitly modeled, not promoted to actual joint Linux execution.
- Four AArch64 modules link with GCC14.4.0/Linux6.18.52:producer8582153e,
  lock1177bd53,31 component mappings/5 kernel/330 mt76 source identities/17 fuzz0
  cumulative patch outputs. Core and mt7996e change; the provider is unchanged.
  Original102685 kernel/516 mt76 prepared entries stay intact. Independent copied
  cache, same236MiB/no-swap build cap and256MiB output ceiling. No full current image.

## Terminal Native Replay

The unchanged full RRO native-q3 job ended exit1 at02:58:49 +03, invocation
c51dd850f884429ea9784effab39a7a7, Restart=no/NRestarts0, not OOM (171.1MiB peak
under400MiB). Profiles0/1 each finished6421 positive RPCs,6421 complete journal
comparisons and2050 reset transactions across two journal generations. MCU results
in that recipe remain modeled. Profile2 completed OPEN/137 ENROLL, then its first
PUBLISH timed out at PC0x84104c72 with100M instructions/60M-us per RPC unchanged.
This is two complete profiles plus a failed third, not a complete native pass,
nontermination proof or a device-performance verdict. Input graph/outputs are
retained and rehashed; no restart or limit increase. Compact replay remains live
with its original PID/start/invocation and frozen capsule. No REA PIDs were signaled.

## Proof Boundaries

The NAPI/RCU/poll scheduling, IRQ/devres, DMA/MCU, provider and device frameworks
are explicit host models. Symbol resolution and compilation do not prove Linux
concurrency, physical DMA drain, arbitrary post-free control callers, a complete
cold error-prefix work/MCU unwind, or HIF2 driver/devres binding stability. A device
reference still does not pin that binding. No owner/resource retirement/rearm or
new image/flash/boot/client/throughput/stability acceptance is claimed.

First unseen cookie-less late firmware BA status can still associate with a
replacement despite retained host serials. Qualify current-firmware ordering or a
real cookie/reuse fence, whole hot/cold lifetime and physical drains before reuse.
Diagnose the retained profile2 publication frontier without restarting old jobs.

Initial source-extraction, fixture-path/mutation and17-output installer refusals
remain retained. A second-cohort launcher refused to overwrite an earlier reset
receipt; final outputs use exclusive q3 paths. Jev performed narrow semantic
checks, not planning/code/tests.
The unit runner's historical-reference typo was separately repaired and all
individual successful C suites plus142 units are bound by an aggregate receipt.
The initial read-only module-verifier dispatch was refused before execution by a
shared compile-sized disk reservation. Measured-output profiles reserve128MiB
for that verifier (previous inventory15MiB),16MiB for units,256MiB for broad tests
(previous complete cohorts under32MiB combined), and128MiB for sealing. The2GiB storage
margin and all Windows/guest RAM and native-execution limits remain unchanged.
Lossless completed-cache dedup linked103 exact .o/.ko peers, preserving bytes and
mode/mtime/owner/xattrs. The24043520-byte guest-block release estimate is not a
claim of equal Windows-host free-space recovery. No live/current cache was touched.
Jev's original RX-tail0.10 judgment conflicted with the literal source; focused
recheck was0.98. The TX budget guard judgment0.27 also conflicts with the literal
guard and compiled budget tests. Raw probabilities remain recorded; neither an
affirmative nor a contradictory judgment overrides deterministic evidence.

Contracts: [NAPI](https://docs.kernel.org/networking/napi.html),
[RCU](https://docs.kernel.org/RCU/whatisRCU.html),
[TypeSafe System One](https://docs.typesafe.ai/api/system-one).
Exact hashes and transitive/private proof bindings are in EVIDENCE.json.
