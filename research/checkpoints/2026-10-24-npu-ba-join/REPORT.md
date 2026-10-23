# Accepted Owned BA Writer And Callback Join

Date: 2026-10-24. Base: `c3e88986f06d148d0a21622e7dad3d358ccd0ac8`.
Classification: progress toward full NPU implementation, not full completion.

## Implementation

`mt7996_npu_rro_reset_join` requires closed admission under the owner lock,
releases that lock, independently cancels/joins `wed_rro.work`, waits an RCU grace
period, then records joined under lock only if inflight is clear. An open owner
gets sticky EUCLEAN without starting process waits. The existing three outer
cancellations are retained for legacy WED; no teardown order changes or new free.

Successful owned BA status admission already runs in the same RCU read-side
section as the final TID ID write. It can be accepted before close, release the
owner lock, and still be writing afterward. Closing alone did not join it.
Similarly, inflight can clear before the outer WED callback actually returns.
The two added waits address those distinct CPU completion conditions.

The upstream [RCU contract](https://docs.kernel.org/RCU/whatisRCU.html) covers
preexisting readers, not necessarily later readers. The upstream
[work cancellation contract](https://docs.kernel.org/core-api/workqueue.html)
requires absence of racing enqueues for a quiescent return. The owned admission
lock prevents later successful owned queue/ID admission; it does not stop every
future metadata callback. These API contracts are design evidence, not proof of
kernel execution or DMA drain in our build.

## Validation

- New selected actual RX creation/AMPDU/per-link BA/event/full-owner C fixture:
  37 measured setups, including32 paused accepted writers and a callback tail
  paused after actual helper inflight clears. Eight independently compiled
  mutations hit their intended assertions, not sanitizer faults/timeouts.
  Clang ASan/UBSan/leak detection and a separate GCC ThreadSanitizer run pass.
- Open admission, late metadata without new ID/work, missing owner and corrupted
  inflight are checked. The pthread RW lock and work-thread join are explicit
  framework models. Three full outer teardown/reset bodies are source-bound
  close/cancel/join-before-mutex checks, not jointly executed kernel call paths.
- Current retained BA owner23/14 controls, creation19/12, BA18/six and worker23/
  eight pass. The separate worker prior BA enrollment remains modeled; actual
  creation/event/full-owner execution is supplied by the joint fixtures.
- Joint6150 reset transactions across3 profiles/two journal generations,
  12 negatives/three controls; broad456/four controls/387 publications and native
  effects/11 negative joint/12 late TX; callers1090/seven controls (1040 optional,
  50 modeled-owned); all142 tooling/observer/inventory/phase units, zero skips.
- Four AArch64 modules link with GCC14.4.0/Linux6.18.52, produceraa15d714,
  lock1c1573cb,31 component mappings/5 kernel/330 mt76 sources/16 fuzz0 cumulative
  outputs. Cancellation and RCU imports resolve. Only mt7996e changes; original
  102685 kernel/516 mt76 entries remain unchanged. The build reuses an independent
  qualified copied cache, at236MiB/no swap and a256MiB output ceiling, not a world.

Exact receipts, source versions, artifact hashes, process identities and Jev
probabilities are in `EVIDENCE.json` and its preserved private evidence graph.
The design-summary close-before-grace check was uncertain (Noul0.29); exact code
follow-up gives0.97 for rejecting open admission before waits and0.96 for joined
following both waits. Compiled controls/test observations, not these semantic
judgments, establish the covered behavior. Other source checks give0.91 for
closed metadata/no new ID admission and0.03 for a whole-device/drain claim.

## Preservation And Limits

Several build/verifier/test host-RAM checks refused dispatch; fresh checks
preceded retries at unchanged limits and2GiB margins. Failed receipts stay kept.
Four small16MiB maintenance units requested clean file-cache release: initial
zero-byte dd hints, then direct read-only per-file posix_fadvise for prepared
kernel files/completed copied build cohorts. No data was read, changed or deleted,
and no VM policy changed; precise reclaimed bytes are not claimed.
The same bounded per-file advice follows evidence hashing to retain the Windows
margin; it does not weaken the RAM checks or qualify a previously refused launch.

Both
original live replays keep their PID/starttick/invocation/input graphs, caps and
recipes; partial RPC observations are not complete verdicts. No observation
timeout restart occurred. The original capsule, prior evidence and14 project
images/one external image are rehashed. REA PIDs104034/666864 are absent; no signal
was needed or sent. No subagents, new REA/Ghidra/decryption, module load, image
build/promotion, flash, hardware or VM/global-policy changes occurred.

Late metadata still reaches the independent retained owner after joined. This
does not establish full RX/NAPI/IRQ/PCIe/device CPU lifetime, safe owner/device
free, firmware BA association/reuse fencing or physical drain/retirement/rearm.
The first unseen cookie-less late status still binds a replacement in the host
model, without proving real firmware reachability/order. Parked transport guards
remain; current full native replay, image/cold-fault/HIF2/hardware/client/
performance/stability gates are open. The full NPU objective remains active.
