# RRO Teardown Characterization And Write-Observer Repair

This continues the full NPU objective, not a smaller completion target. The
previous cleanup turn made concrete storage progress. This checkpoint adds
executed teardown evidence and repairs observation of the complete RRO frame
sequence. Retained RRO admission and retirement are still not implemented.
Results and private evidence bindings are in [EVIDENCE.json](EVIDENCE.json).

## Complete Selected Teardown

The fixture now compiles the actual `mt76_unregister_device`, `mt76_free_device`
and `mt76_npu_deinit` bodies alongside the existing complete selected RRO
init/free/worker/higher-init/unregister callers. Source comes from the genuine
combined `90abc8f3` module producer, not a rewritten receipt or guessed stub.
Managed-DMA bookkeeping and actual sender/dispatcher/framing remain included.

All 1,037 cases pass ASan, UBSan and leak detection. The sixteen added cases
exercise every injected combination of NPU pointer, PPE pointer, registered
state and non-null workqueue. They are framework-state fixtures, not proof that
every combination occurs during a real boot. Recorded counters and assertions
check pointer unpublication, reader join, queue cleanup and reference releases.

Three independent negative controls compile successfully and then abort at the
intended assertion: missing RCU join, missing provider detach and missing NPU
reference release. A compiler error, timeout, sanitizer fault or arbitrary
nonzero exit does not count as a successful control. Intentional assertion
controls do not create core dumps.

The selected unregister sequence is:

1. Earlier mac80211 unregister boundary.
2. Explicit RRO allocation frees.
3. MCU exit, token release and DMA-cleanup boundaries.
4. Actual lower worker/workqueue teardown and `mt76_npu_deinit`.
5. Provider pointer unpublication, conditional `synchronize_rcu`, two queue
   cleanup boundaries, NPU/PPE reference puts and final hardware-object free.

The framework, mac80211 callbacks, low-level DMA/devres, MCU, queue internals,
locks and RCU scheduling remain models. LED cleanup is modeled and disabled
in this fixture. No hardware drain or physical use-after-free is established.
A handoff only in the final `mt76_npu_deinit` cannot retain allocations before
their earlier explicit frees. The actual retained-ownership handoff must occur
before those frees; a CPU reader join is not a firmware/DMA retirement witness.
The canonical RRO requirements now record this integration constraint.

## Full Native Composition

The same 134 actual C-generated frames remain byte-identical to the preceding
capture: all 128 element blocks, the session table and five reset boundaries.
Fresh execution of all frames passes the stock byte/store/ABI/MSTATUS oracles
and separately the current firmware's exact checked denials. The stock run
executes 6,344,077 original instructions at 116 distinct addresses. Current
selectors 0/1/3 remain denied; this is not admitted current RRO or full startup.

All stock observation rows, current denial rows, ordered-write digests,
instruction counts, packet bytes, raw-pair identities, field offsets and hook
identity equal the saved preceding full result. This is a fresh new-observer
run compared with historical full results, not a fresh old/new boot A/B.
Synthetic RAM/aliases and modeled single-hart mutex state remain explicit.
The matching saved Ghidra export was reused, not regenerated.

## Observer Growth And Recovery

The first new workflow passed the C cases and three controls, then failed
before native execution because its launcher omitted the already installed
Unicorn import path. A fresh invocation used that exact existing 2.1.4 runtime.
It then terminated with a confirmed auxiliary cgroup OOM at 400 MiB after the
frame-32 progress record. Both failures and their logs are retained.

A real-runtime weak-reference probe confirms that a deleted per-frame callback
keeps its trace object alive until cyclic GC runs. The new observer installs
one write hook and retains only the currently executing call's trace. It still
forwards every write to the same oracle and rejects writes outside a watched
call; callback errors propagate and nested/wrong-engine calls are rejected.
Six real-Unicorn tests pass, including 128 trace releases with cyclic GC
disabled. No runtime library, GC policy or guest instruction was patched.

The complete fresh run passes under the SAME 400 MiB/no-swap auxiliary cap.
The cgroup peak is 182,042,624 bytes; measured native-child maximum RSS is
138,888 KiB. Full geometry, all 134 frames, full memory/code comparisons,
instruction checks, original callback limits and checkpoints remain intact.
The callback limit remains 2,000,000 instructions / 3,000,000 microseconds.
This measured recovery does not establish the exclusive cause of every OOM.

## Preservation And Remaining Work

Fresh launch budgets include the existing full replay's 4 GiB cap and future
output allowance, the auxiliary cap and a 2 GiB margin. They are point-in-time
checks, not reservations. The original compact default replay remains live at
its original controller/native start ticks; it was not restarted or modified.
Its separate 3M/60M-us engine limits are unchanged. No complete cold verdict
is inferred from the RRO probes.

All executing capsule inputs and protected image bindings are rechecked in the
evidence seal. The prior cleanup's nine mutable source/tracker versions are
preserved at their exact recorded hashes, with fifteen unchanged bindings.
One old reader version was reconstructed from the exact base plus its original
v2 schema hunk and verified against the closed cleanup hash. Old receipts were
not edited, and changed working paths are not claimed to match older hashes.

Jev's source review selected the provider DMA owner and flagged the ignored
publication/reset errors. Its hook-point choice was uncertain (`unknown`,
confidence 0.22); that uncertainty is retained, not treated as approval. Tests
and explicit source ordering support the narrow software conclusions.

Firmware, source lock `cb035741`, raw pair `4e43de6f/a282ca7a` and offline image
`a3f1d04b` are unchanged. No hardware, flash, boot, module load, VM/job restart,
new swap, global policy change or subagents. Next remains the real provider/
endpoint-bound retained RRO context, publication/reset identity and generation,
atomic/process handoff, higher errors, ambiguous/late completion, independently
established exclusion/drain and retirement, then whole-stack and physical/client
acceptance. Permanent denial or early-return-only changes are not completion.
