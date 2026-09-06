# External Blockers And L1 Review

2026-09-06, 08:02 UTC. Full goals are not achieved. The critical path needs
external input/access before safe implementation and client acceptance can
proceed. Earlier independent evidence remains valid only within its stated scope.

## Required To Resume

- Wi-Fi reproduction: identify the intended AP configuration and affected
  client/band/symptom. The latest live capture found no configured networks or
  hostapd interfaces. No restoration or activation was authorized by an exact
  configuration, and no current client result was supplied.
- Full NPU work: resolve the tool restriction affecting the INODE provider
  correction and native DESC5/6/7/8 work. Those operations were not retried,
  rephrased or rerouted. The INODE restriction has remained unresolved across
  three consecutive goal continuations; independent work in the intervening
  continuation did not remove it. Generic continuation is not an access grant.
- Optional collector validation: approve the requested process-only PowerShell
  override for the two local read-only scripts, or supply an approved execution
  mechanism. This is not required for the already completed direct SSH reads.
  Collector and fixture runtime remain unverified; machine policy is unchanged.

No completed job is being awaited. Remaining implementation, quiescence,
recovery/removal, full datapath and actual-client gates stay open. They have not
been replaced by source-only or model-only acceptance criteria.

## Fresh L1 Source Review

The pinned mt76 archive still has this order in `mt7996/mac.c`:

| Line | Operation |
| --- | --- |
| 2575 | Discard `mt7996_npu_hw_stop()` return |
| 2612 | Reset DMA after the MCU reset-done condition |
| 2614 | Release TX tokens |
| 2625 | Restart DMA |
| 2647 | Discard `__mt7996_npu_hw_init()` return |
| 2680 | Wake host queues |

Adding return checks alone would not establish NPU quiescence before token
reclamation, undo partial reinitialization, or cover teardown and repeated
recovery. No such partial change was promoted as a safe L1 fix. The established
native STOP/GET limitations and missing physical drain/containment proof remain
prerequisites, including when the legacy stop call returns success.

Input archive: `mt76-2026.09.01~be5ce791.tar.zst`, SHA256
`d1d0f7588c5b9ceafcac341ce19dd206ed9ec106847e672ab77e48bacb57f81a`.
Member `mt7996/mac.c` SHA256:
`57b077b5735a2917cefa3d30ede1dbe37d87511959a69911d57f72a9834dbd15`.
The current three local mt76 patches do not alter this file. This is source
review, not a fresh failure replay, compile, firmware run or hardware finding.

No production code/configuration, shared harness, router, image or flash changed
in this review. No unsigned script or restricted NPU operation was executed.
The next step is to resolve the stated external blockers, not infer permissions
or generate another passing subset as a substitute for either full goal.
