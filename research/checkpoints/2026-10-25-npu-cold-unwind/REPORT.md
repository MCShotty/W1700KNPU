# Cold Probe Work And Error Cleanup

Goal turn: progress toward full NPU reverse engineering and implementation,
not completion. Base commit: `bbca4d529b39ef6df2bcc61f58b5fd8a6aadcae4`.
Continued without subagents. No module load, image build, flash or hardware test.

## Findings And Source Change

The original selected C characterizes four failures: late registration failure
reaches free without unregistering mac80211; a cold MCU timeout can queue
recovery before full registration; a conditional memdump allocation failure
leaves freed metadata published; and a TX-worker creation error is ignored before
passing its null task to the scheduler. These are executable host/source findings,
not observed router crashes or an actual kernel null-task panic.

The nonzero memdump-buffer failure belongs to the modeled MT7996 memory layout.
The current W1700K MT7990 layout has zero memdump length. Debugfs error coverage
is injected contract testing: the actual current debugfs initializer returns zero.
Allocator tombstones remain allocated until fixture disposal; separate liveness
checks characterize ownership. They are not a demonstrated host ASan use-after-free.

The integrated mt76 patch now:

- Constructs driver work, lists, locks and primary PHY software state before
  live IRQ registration. Reset/dump work stays disabled until all registration
  steps succeed. A cold timeout cannot queue those unready recovery callbacks.
- Routes failed PCI registration and normal unregister through one stage-aware
  cleanup helper. Driver-core serialization protects its once-only cleanup latch.
  It closes owned RRO admission, disables/joins init/dump/WED/reset/RC work and
  scan/mac work, and disables ROC only after its registration construction marker.
- Unregisters radio/framework state, parks TX, unregisters coredump data, and
  attempts MCU exit only when MCU initialization began after DMA attachment.
  `mcu_ops` is an attempt marker, not proof that firmware boot succeeded.
- Closes PCI and NPU IRQs, joins tracked NAPI, then purges responses that arrived
  after MCU exit's earlier purge. Token cleanup follows; DMA cleanup requires
  attachment, and RRO resource release follows DMA cleanup.
- Publishes coredump metadata only after required allocations succeed and tolerates
  absent metadata during cleanup. Shared mt76 registration rolls back hw/LED state
  and returns the original TX-worker creation error instead of scheduling null.
- Uses a standalone readiness bool with paired WRITE_ONCE/READ_ONCE. The moved
  constructor has a forward declaration for its later-defined WED callback.

The [kernel workqueue contract](https://docs.kernel.org/core-api/workqueue.html)
defines disable-and-join behavior and rejection of future queues while disabled.
The pinned Linux6.18.52 definitions/exports and ARM64 links are checked. The host
fixture models these APIs; it does not execute the Linux workqueue implementation.
MCU exit remains void and can log failure. Its return to the caller, call ordering,
IRQ masking and DMA cleanup are not physical shutdown/drain witnesses.

## Verification

- Original characterization: four measured findings, not a repair pass.
- Corrected candidate:608 measured setups and14 compiled, intended mutation
  controls with ASan/UBSan/leak detection; a separate TSan run also passes.
  Each LED configuration executes304 setups:12 modeled family/HIF2/memdump
  profiles times25 registration stages, three early resource prefixes and one
  running-init callback test. The separate TSan count is not added to608.
- Actual selected constructor, init work, hardware/driver/core registration,
  cleanup/unregister, coredump and MCU-exit C execute. The MCU timeout branch
  and PCI registration/error tail are selected verbatim, not their complete
  outer functions. Framework, lower hardware/MCU/DMA, IRQ/NAPI and work APIs
  remain models. The fixture joins one held init callback and rejects its
  self-requeue; it does not qualify concurrent cleanup callers or actual Linux.
- Installed-source aggregate: cold608/14, HIF26/14, PCI288/15, detach16/2,
  NAPI44/12, IRQ360/10, BA-join37/8, owner23/14, creation19/12, BA18/6,
  worker23/8,6150 resets/3, broad456/4 and callers1090/7. Cold/NAPI/BA-join
  have separate passing TSan runs. The tooling suite passes147 tests, zero skips.
  Counts are measured setups/compiled controls, not physical acceptance totals.
- Older PCI and caller fixtures execute the new complete cleanup helper, rather
  than replacing it with a stub. Their framework boundaries remain modeled.
  Actual caller-order assertions now follow cleanup and verify unregister/error
  paths reach it before base free. DMA-before-RRO event order is checked.
- The first aggregate stops after four completed suites at a test-side exact
  caller spelling mismatch. Its failure remains. A fresh tail corrects only the
  source assertion, completes the remaining suites and rehashes all earlier inputs.
  Aggregate SHA256:
  `1c87dbcb82a1fb0434770fc215437f56f07ac3a7395c6863b69f255b4fc0b86f`.
- All18 cumulative patch outputs reconstruct at zero fuzz;31 component mappings
  and330 mt76 source identities remain. Source lock:
  `88502ab3798b2ccdf01e6fd3c8779bcd2ad0f24a970c080f97ac9992b97f740a`.
- Four GCC14.4.0/Linux6.18.52 AArch64 modules link. Provider and connac bytes
  stay unchanged; shared core and mt7996e change. All102685 original kernel,
  516 original mt76 and prior qualified cache inventory entries compare unchanged.

Current producer:
`.local/npu-build-scratch/native-c2/cold-unwind-modules-q20/modules/result.json`
SHA256 `a840d3cccb1d0bd8cc60a856d1a1bb9723dfc05af73484d955a33978a458d22f`.

| Module | SHA256 |
| --- | --- |
| mt76.ko | `3011a7968e1e0f206571b4057bbd6f66a8ade65021e6e546b59ca855595cd834` |
| mt76-connac-lib.ko | `c3a1dfffdd3481bb79b7d08f30d22f082a9711f5a971193325b94044be7aeed3` |
| mt7996e.ko | `af458b048f32b015e550dc523f3706d00b5a650030e000c0bbf878f4186045bb` |
| airoha_npu.ko | `3c5cff3e179928729d4ab1680b24545add77e8a231401b5935579862babb46e5` |

## Retained Failures And Resources

The initial installer had a receipt-field mismatch. A later monitor encountered
a vanished patch temporary file and interrupted installation after five private
source replacements, before canonical patch/lock changes. A retry refused that
partial state. Reconciliation accepted only exact preserved or tested bytes.
The build export check then caught the empty interrupted temporary; it was moved
to preserved private evidence, not ignored or deleted. The first actual target
compile caught the missing forward declaration and invalid bitfield WRITE_ONCE.
Those inputs/failures remain, and the corrected candidate, patch and links are fresh.

New phases use400MiB/no swap, including resident controllers and file cache.
Dual backing checks conservatively retain1GiB old future output plus64MiB phase
output and the unchanged2GiB D margin. Native C outputs hold the existing storage
lock; module reserve is512MiB and full regression reserve768MiB, each with the
unchanged C margin. Module monitoring measures155636177 bytes including metadata.
The regression tail uses195273270 bytes; the earlier four-suite output remains
separately preserved. The768MiB reserve is a ceiling, not measured usage.
No original cap, replay, VM/swap/global policy or system launcher changed.

Actual Jev1.13.0 checks retain all probabilities, including0.14 for the original
dangling-publication finding and0.19 for the corrected allocation-failure claim.
Those disagree with the explicit selected C and executable branch tests; they
are not presented as agreement or proof. Other candidate checks range0.86-0.96.
The official [System One API](https://docs.typesafe.ai/api/system-one) was used;
no credential value is in prompts or public artifacts.

## Remaining

Qualify actual Linux work-disable/registration-failure teardown and managed HIF2
unbind. Complete cold-prefix physical/MCU-exit-failure handling still needs a
real drain/retention contract. Establish current-firmware BA ordering/cookie or
a real late/reuse fence, then finish hot admission, production retirement/rearm,
physical ownership/drains and current-image/hardware/actual-client/performance/
stability acceptance. Both complete native replay verdicts remain unproved.

The fresh WSL boot has no old replay handles. Missing is not success; neither
replay was restarted and the retained native q3 failure remains. The separate
60-second diagnostic boot-budget question is unanswered. No new firmware image
or hardware/client acceptance follows from this checkpoint; the full goal stays active.
