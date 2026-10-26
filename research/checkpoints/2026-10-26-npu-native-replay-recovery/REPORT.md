# Native Replay Recovery, 2026-10-26

This is storage/process recovery and native-emulation progress, not a complete
native or physical NPU verdict. The replay source checkpoint is `e6d299f`.
Only tracking documents changed after dispatch; replay inputs stayed frozen.

## Storage And Process Audit

D: had independently recovered to 20,846,690,304 free bytes before maintenance,
above the unchanged 3,288,334,336-byte requirement. No compaction, trim, deletion,
Ubuntu shutdown, server termination or permanent configuration change was done.
A subsequent observed boot ID changed from `14d59cc9-846e-454f-bcf3-cdfbc6f111ec`
to `1862d6d4-4c0a-4953-9d16-bbcb5f7c2ffa`. Its cause is not established.

The registered C: scratch distro was started and its bind mounts restored.
Both mounts have ext4 UUID `b0b1bc48-d684-4090-a8cf-1ecb2939c36d`, the retained
marker digest, and the same directory identity. No VHD import, deletion, format,
VM setting change, or old replay restart was used. Neither old original replay
unit is present; absence is not success.

## Retained Outcomes

`rpc-memory-full-q31` launched with verified live guard/child identities on the
prior boot. Its immutable interrupted output records 5,652 positive profile-0
RPCs: OPEN1, ENROLL139, PUBLISH129, HARDWARE1, and 1,794 each RESET/MCU_BEGIN/
MCU_COMPLETE. The driver writes each positive row after mailbox, response,
broker/journal and applicable extent assertions. Complete-publication and first-
generation full-memory markers exist. The final recorded RPC is MCU_COMPLETE,
argument768, generation2, serial5674. There is no profile summary or final
driver/wrapper/controller receipt. Do not combine this prefix with another run.

All 38 prepared input bindings rehash unchanged. The `e6d299f` post-publication
audit of 57,695 files, five complete inventories and 48 retained runtime bindings
is preserved prior evidence; it was not rerun for this recovery.

Separately named `native-replay-full-q4` fails the original 10-second raw-boot
deadline at `0x84004ed6`, before any RPC. Its exit1, logs, inputs and failures
remain intact. It does not establish a firmware defect or the reboot cause.

`native-replay-boot-diag-q5` then completes the raw profile-0 prefix: 1,136,899
instructions, 1,131,289 fast and 5,610 reference dispatches. Its prefix receipt
is byte-identical to q31 profile0, SHA256
`bb2a5e29fd19fbca51cbbe0443eb04ce06670ae133124a99f85ad61bfa117b30`.
The slowest individual call is 8,936,308,784 ns; the whole multi-call diagnostic
takes 42,573,820,976 ns. The 10-second limit applies to each raw emulation call,
not the entire diagnostic. This pass is not a stable host-timing qualification.

## Fresh Full Run

`w1700k-npu-native-replay-full-q7.service` attempted the complete existing recipe
from raw initial state, with new exclusive output under
`.local/npu-build-scratch/native-c2/native-replay-full-q7/`. It does not restore
or splice the interrupted emulator state. Additional preconditions bind the
failed q4 artifacts and the successful exact q5 prefix; no prerequisite was
removed. The finite dispatcher checks actual live guard/child argv and caps.

The intended recipe remains three profiles, 19,261 positive RPC/journal comparisons,
387 publications and 6,150 each RESET/MCU_BEGIN/MCU_COMPLETE. Raw calls retain
3,000,000 instructions/10,000,000 us; RPCs retain100,000,000/60,000,000 us.
Memory is400MiB, swap0, with the same C lock and dual backing/RAM margins.

This run completes boot and 140 positive RPCs, whose recorded prefix matches
q31 except timing. Its first PUBLISH fails at `0x84104abe`, after 60,001,845,304 ns:
24,576 writes, 23,833 readbacks, 7,214,255 blocks and 738,206 metadata writes.
Fault injection is false; the complete table/readback/broker verdict is absent.
The driver, wrapper and controller all fail exit1; MainPID is0. No replay remains
running. This is an emulator deadline failure, not established physical failure.
The failed full run is preserved and is not promoted by the successful boot.

Next reduce faithful host-observer overhead/requalify timing before a separately
named complete recipe. Do not restart these runs, extend budgets, drop counts or
I/O checks, or combine partial outputs into a pass. Future live runs must freeze
their bound inputs. Dispatch, stale logs or missing transient units are not proof.

Jev1.13.0 supplied five scoped checks with raw probabilities retained in
`EVIDENCE.json`: completion0.05, firmware-cause0.08, partial-scope0.83,
physical0.04, fresh-scope0.80. Parsing, exact hashes and executed assertions,
not model confidence, establish the stated covered observations.

Production lock88502ab3, mt76 patchbb457928 and four-module producera840d3cc
remain unchanged. No new router image, module load, router contact or flash.
Full native replay, physical MCU-exit failure/queue/page-pool retention/drain,
firmware BA reuse, hot admission/retirement/rearm, current image/hardware/
actual-client/performance/stability acceptance remain unfinished.
