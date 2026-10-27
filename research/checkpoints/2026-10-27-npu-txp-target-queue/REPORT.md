# FW-TXP Target Validation Queue

## Current State

The integrated FW-TXP DMA source fix at `8e8339b` now has a live dependent
validation controller, Windows PID17788. Its actual executable, command line
and creation time match the retained dispatch record. The controller is waiting
for original full-q16; no target build or native validation phase has started.
This checkpoint does not qualify the source fix as compiled or executed.

Private cohort: `.local/npu-txp-target-20261027/`. Plan SHA256:
`e67d5198b90accba2785cc9ae08b55e4d665d5747df58cce1ce913ee68e23bea`.
The plan freezes454 current target inputs and separately verifies all332
original native replay inputs. Tracking prefixes are outside both sets.
Source lock remains `cc128c3b2dc196c41c3b7db858dd22c3a1c7eb76ed9ca01efe11f060122c9d2d`;
mt76 patch73ccff87 and pre-fix producer92c75156 remain unchanged here.

## Exact Dependency

The predecessor is `w1700k-npu-native-memory-hook-full-q16.service`, invocation
`20c8f1ab62d74236bf977c134d09b059`. Original identities are guard137794/start5470192,
wrapper137812/start5470277 and driver137844/start5470636, with exact argv,
parentage and cgroup membership verified. The queue also observes any remaining
cgroup members. It does not stop, restart or mutate the original job.

An activating unit with its default success result is still live. Observation
timeouts are retries, not termination. A replaced invocation or unexplained
missing unit is refused. A collected unit requires verified same-boot live
history, no original processes or cgroup members, and a durable terminal receipt.
The phase guard rechecks the plan and actual predecessor state before launch.

A terminal failed native replay may permit this independent module build; it
does not become a passing native recipe. Actual native acceptance still requires
the complete fresh three-profile/19261-RPC result and its own final comparisons.
The queue never assembles partial receipts or restarts a failed recipe.

## Planned Validation

After the exact predecessor is terminal, modules-q2 clones the qualified cache
into fresh C-backed output and builds/links the current four-module cohort on
Linux6.18.52. Only the radio module is expected to change. Original kernel,
mt76 and old module caches are checked unchanged. This phase has not executed.

The new producer must then pass five independently source-bound native suites:

- FW-TXP:90 cases/four controls, default correct contract, zero incorrect DMA
  argument cases. Baseline-bug reproduction is expressly not accepted.
- RXWI cache drain:10 cases/three controls, actual source drain present and zero
  modeled live RXWI at context free.
- MCU cleanup:31 cases/three controls.
- Consumer NPU RX cleanup:35 cases/six controls.
- Ordinary RX/TX cleanup:64 cases/seven controls, complete matrix with MT7996
  outer fixtures retaining TXWI_NO_FREE.

Only a successful module phase/controller permits regressions-q3. It runs the
existing15 lifetime/source suites, including167 tooling units with no skips.
These are requirements for future results, not tests already passed here.
Selected compiled-body tests retain their modeled kernel/physical boundaries.

Each new phase uses400MiB/no swap, fresh Windows/Linux RAM and dual-backing
storage checks, the existing C-storage writer lock and source/boot checks.
Module/regression C-output reserves are512/768MiB. The Windows RAM gate reserves
the full new cap plus host margin. Each command must exactly match the frozen
phase command. No baseline-bug flag or different executable can be substituted.

The new Type=oneshot units use TimeoutStartSec3500, TimeoutStopSec20 and
control-group kill, with restart disabled. RuntimeMaxSec does not bound a
oneshot activation; the selected setting follows the
[systemd service manual](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html#RuntimeMaxSec=).
These settings do not alter the original native instruction/time limits.

## Executed Control Checks

All29 existing predecessor-policy tests and15 new driver-control tests pass,
zero skips. The latter execute the real queue main/guard checks with mocked
process launches, covering live/replaced/missing predecessors, cancellation,
observation retries, command binding, full-cap RAM reservation, correct-contract
requirements, deadline configuration and module failure blocking regressions.
They are host control-flow tests, not target compilation or native firmware cases.

The first42-test attempt had three fixture errors because the subprocess mock
lacked STDOUT. Its log and consumed test source remain preserved. The correction
adds the missing mock constants and two explicit observation-timeout tests;
no production guard was weakened. Generated driver versions before command/deadline
strengthening are retained with exact provenance and deltas.

## Live Evidence And Resume

Read-only audit3 verifies advancing original driver CPU,454 target/332 native
inputs and332 read-only retained versions. Its complete-line profile0 prefix
records5181 checked RPCs,129 publications and1637 RESET/MCU_BEGIN/MCU_COMPLETE
each. This is not a finished profile or complete native verdict. Full-q16 keeps
its boot3M/10s, RPC100M/60s,400MiB/no swap,512MiB C-output reserve and writer lock.
No competing compiler or sampling ran.

Resume by inspecting the actual controller PID, queue observations, phase units
and terminal receipts before any manual build. Do not launch a duplicate queue.
`CANCEL` in this private cohort cancels this queue or its own new phase child,
never the original replay. Preserve454 target inputs until the queue terminates;
cancel/reprepare a fresh plan before changing them. Keep332 native inputs frozen
while the predecessor is live. Six old tracking bodies are byte-preserved.

Source-fix target qualification remains pending. Full native, token/RRO/consumer
and devres/context ownership, physical containment/drain, reuse/hot lifecycle,
current image/board and real-client acceptance remain open. Ethernet stays
disconnected. No module load, image/flash, Wi-Fi change, shutdown or compaction
occurred. Full NPU goal remains active. EVIDENCE.json binds immutable startup
evidence; growing live logs are excluded and a complete-line prefix is retained.
