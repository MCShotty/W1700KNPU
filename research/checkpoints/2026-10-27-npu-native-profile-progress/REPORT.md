# Original Native Replay: Two Profiles Complete

## Current Result

The original full-q16 invocation `20c8f1ab62d74236bf977c134d09b059` has completed
profiles 0 and 1 and entered profile 2. The guard137794, wrapper137812 and
driver137844/start5470636 remain the original live processes. This is progress
within one unchanged three-profile replay, not a completed full-recipe verdict.
Source parent: `61b5d2ed5d444f691a9526961030c509ad43b94f`.

Profile 1's completed artifacts independently verify 6,421 positive RPC records,
6,421 complete-journal comparisons, 2,179 extent comparisons and four full-memory
comparisons. Its complete ordered OPEN/139 ENROLL/129 PUBLISH/HARDWARE/two
generations of 1,025 RESET-MCU_BEGIN-MCU_COMPLETE triplets/CLOSE recipe matches
the retained transcript. Positive serials increase strictly. Final broker,
oracle-journal and transcript hashes agree with its summary. Five final artifacts,
including the complete transcript, are copied read-only onto Ubuntu storage.

The independent verifier reads saved artifacts; it does not execute another
emulator or repeat the native comparisons. Those per-RPC comparisons were
executed by the original source-bound driver. The summary's four full-memory
records each cover the 12,582,912-byte modeled DMA arena and native SRAM range.
The saved final DMA digest agrees with the last complete-memory record; SRAM
digests agree across those four records. These are retained comparison records,
not an independent recapture of all intermediate memory.

Profile 0's prior completed-artifact receipt remains valid with its own 6,421
positive RPCs. Its earlier verifier did not add this new exact event-order check;
the new verifier specifically audits profile 1. Do not add this audit as another
6,421 executed cases or combine it with an older run as full native acceptance.

## Evidence And Boundaries

Profile 1 audit SHA256:
`3f5b580374583187a45cc8c411148a0f5f171f423ae051138e1940898a73e2ae`.
Private receipt: `.local/npu-native-profile-audit-20261027/profile1-verified-q1.json`.
Verifier SHA256:
`5a532037145a5f78ba0413799b804325d3ddb13a9580bea6d177b12d055e7f39`.
The public `EVIDENCE.json` records the selected receipt and artifact hashes.

All 454 frozen queued-build inputs, 332 original replay inputs and their 332
read-only retained versions verify. The driver SHA256 remains
`9e336bb92dcc7b1b33c9111d1ac5fbf3aa556a3596c28a4007cc109942294a4b`.
No original input, instruction/time limit, memory cap, output reserve or storage
lock changes. No restart, competing compilation or extra native sampling occurs.

Provider publication/backing, IRQ delivery, MCU results and physical effects
remain models. The operation named HARDWARE is a protocol operation, not board
access. Profile 1 includes 2,050 modeled MCU completions. This does not establish
physical DMA drain, complete consumer/devres/context lifetime or safe BA reuse.

The existing Windows controller PID17788/plan e67d5198 still waits for actual
original-process/cgroup termination. No target phase has started. Current FW-TXP
source fix/lock cc128c3b remains compile/execution pending; old producer92c75156
is not relabeled current. Preserve the current queue and rerun the three newer
token/status suites against fresh matching modules after qualification.

## Next Work

Finish and inspect the same full three-profile/19,261-RPC result, including its
own terminal receipt and all artifacts. The already queued fresh module build
and regressions follow only after real termination. Failed termination is not
native acceptance. Full consumer ownership/physical containment and drain,
reuse/hot lifetime, current image/board/actual-client acceptance remain required.

Ethernet stays disconnected. No module load, router contact, image, flash,
Wi-Fi change, subagent, shutdown, compaction or protected-file cleanup occurs.
The full NPU reverse-engineering and implementation goal remains active.
