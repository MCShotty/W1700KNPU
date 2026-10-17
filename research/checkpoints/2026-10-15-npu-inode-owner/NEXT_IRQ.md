# Final IRQ Contract

The two calls after mt7996_npu_tx_done_init are host/provider MMIO operations,
not additional RV32 mailbox commands. Do not invent a native callback selector
for them or count INODE flags as completing their separate host contract.

## Exact Current Source

- .local/merge-nonoc-20260923/mt76-merged/mt7996/npu.c:
  __mt7996_npu_hw_init checks seven initializer results, then calls
  airoha_npu_wlan_enable_irq for queues0/1 and returns0.
- The provider's airoha_npu_wlan_irq_enable directly calls regmap_set_bits:
  queue0 register0x30d034/mask0x10000; queue1 register0x30d038/mask0x20000.
  Both the ops member and inline wrapper return void; regmap errors are lost.
- The kernel header and mt76 compatibility header both carry that void ABI.
- mt7996/mmio.c:mt7996_rx_poll_complete is another caller. Any ABI/lifetime
  change must cover the runtime re-enable path, not only initialization.

## Actual-C Evidence

.local/npu-inode-next-20261014/final-irq-contract-q1/result.json compiles the
exact extracted provider, inline wrapper and __mt7996_npu_hw_init bodies with
explicit initializer/regmap fixtures. ASan/UBSan/leak passes21 cases:

- Seven initializer failures propagate their exact error with no final IRQ
  calls, preserving the existing early-error behavior.
- Thirteen final-IRQ cases exercise success and error/no-effect/possible-effect
  combinations. Both queue enables are attempted and the actual caller returns0
  in all of them;12 cases have modeled IRQ write errors lost by the void ABI.
- A null provider returns0 without initialization or IRQ calls.

The register failures/partial effects are synthetic fixtures, not observed
physical bus faults. This establishes current C error-loss behavior, not that
the physical router has suffered these errors or that any engine is drained.
No current source was changed by this test.

## Hot Poll Caller Characterized

The canonical fixture now also compiles exact mt7996_rx_poll_complete and the
actual mt76_rxq_id enum, rather than merely checking for a call-site string.
.local/npu-final-irq-contract/hot-poll-q1/result.json passes the original21
startup cases plus31 poll cases with address/undefined/leak sanitizers:

- Ten NPU poll cases exercise both queues with success, EIO/timeout and no/
  possible write effects. Eight modeled errors are lost through the void ABI.
- Two null-provider NPU polls perform no IRQ write.
- All19 other valid queue values route to the ordinary IRQ stub without a
  provider access. Its mask is an explicitly modeled unique routing token;
  this is not verification of the physical ordinary-queue interrupt masks.

Receipt SHA2561efa0c69db1813d0602dc2ef03bbb89c87750d950f0136f7f6e8a21424b868ff.
RCU reads, initializer dependencies and register effects/errors remain modeled.
This does not establish NAPI/RCU lifetime, concurrency, physical routing or an
IRQ fix. Production C/headers are unchanged. The previous canonical test driver
is hash-preserved in the earlier producing-inputs-q1 archive. Current native
desc10-plan-q1 does not consume this test driver; its actual production inputs
remain frozen while the caller/fault runs execute.

## Required Implementation

Further2026-10-17 evidence:the status getter's uninitialized error return is
fixed/host-MSan checked. Actual5778 read/ack/mask fixtures still show148 NAPI
schedules after errors and5624 silent bulk errors. All four register operations
must join the checked contract,not only enable/re-enable. Zero status and bulk
disable are not error/quiescence certificates. Read the irq-status checkpoint.

2026-10-17 follow-up:the hot callback now explicitly brackets provider lookup/
use with RCU. Actual-C52 cases/five compiled RCU mutants and two isolated
AArch64 objects pass;the source patch is exported. This does not fix the void
IRQ ABI or the12 startup/eight hot modeled errors,and does not establish actual
kernel concurrency,physical lifetime or drain. Read the poll-rcu checkpoint.
Existing native cold runs use an unchanged frozen source view while main moves.

1. Preserve any currently live replay inputs until terminal, then add checked
   host/provider error handling
   across the real ops/header/wrapper and initialization caller. Keep the two
   headers, NPU-in/out builds and module interfaces consistent. Cover the hot
   poll re-enable caller explicitly; do not silently leave an unchecked path.
2. Require the independently completed cold setup/PCIe/INODE and fresh matching
   held session/lifetime before initial enablement. Validate queue0/1, exact
   masks/register geometry and ownership before effects; a mutable ready bit
   or successful INODE reply is not sufficient.
3. Retain per-queue possible effects before writes and verify exact readback
   before publication. Surface failure to the caller and quarantine the unsafe
   lane without releasing memory or resuming unchecked producers.
4. A first-queue success followed by second-queue failure is partial ownership,
   not an all-or-nothing rollback. Even attempted masking can fail; preserve
   ambiguity/resources until separately verified quiescence/drain witnesses.
5. Cover both success directions, errors, ambiguous partial writes/readback,
   stale session/detach, bounds, NAPI re-enable and native mutation controls.
   Extend actual-code, normal cross-build/world/provider/FIT and source closure.
6. Physical IRQ routing, worker startup/exclusion, DMA/cache visibility and full
   drain/reset/removal/rearm/recovery/client acceptance remain open requirements.

This is the next checked contract, not permission to enable the router's IRQs,
release workers, reclaim memory or perform a flash/reset.
