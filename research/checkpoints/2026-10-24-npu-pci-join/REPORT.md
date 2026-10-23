# Explicit PCI Callback And Tasklet Ownership

Date: 2026-10-24. Base: `1b9969f3681d4175977c4673b476a7315a4f590e`.
Classification: progress toward full NPU implementation, not full completion.

## Observed Gap

Normal PCI removal called unregister, which freed consumer-private context,
without first removing its two managed IRQ registrations. Their later automatic
devres release was too late for that context. The actual IRQ handler accesses
consumer fields before testing initialized state, and poll completion could
schedule the tasklet without a permanent teardown-admission latch. This identifies
a source-level lifetime gap; no physical router interrupt race is claimed.

The exact requested IRQ may come from WED rather than pdev->irq. HIF2's stored
physical IRQ likewise does not identify its WED registration. Guessing the ID at
teardown or using an IRQ-positive sentinel is not sufficient ownership tracking.

## Implementation

Probe retains each exact IRQ and independent requested/vector flags. Serialized
PCI lifecycle cleanup closes scheduling under the IRQ lock and masks the primary
and optional HIF2 sources, removes all requested managed IRQ callbacks, then calls
tasklet_kill. Poll-completion enable now updates the mask and schedules only while
holding that same lock and only before permanent shutdown. Normal unregister
joins after MCU exit, before token/DMA cleanup and consumer free. The old outer
tasklet disable remains harmless after the earlier actual join.

Probe errors unwind only acquired actions, vectors and HIF2 references. Primary
vector-allocation failure now releases an already acquired HIF2 reference too.
Normal removal snapshots PCI-device pointers/vector flags before unregister frees
consumer context, and releases the HIF2 reference only after unregister/vector
cleanup. No fields from freed consumer-private storage are read afterward.

The pinned Linux6.18.52 devres implementation routes devm_free_irq to free_irq.
The [upstream IRQ contract](https://docs.kernel.org/core-api/genericirq.html)
requires source masking for shared interrupts and waits for executing handlers
when the action is removed. Tasklet scheduling is closed before those removals,
so tasklet_kill follows the last possible PCI IRQ producer. These API contracts
support the design; our host fixture does not execute Linux IRQ/tasklet code.
Poll callbacks can still touch consumer metadata; this does not join their tails.

## Validation

- Current selected actual PCI probe/remove, IRQ enable/handler/shutdown and full
  unregister bodies pass234 measured setups/13 compiled controls with ASan,
  UBSan and leak detection. Six single/HIF2/WED ownership configurations, three
  domain/IRQ-zero variants and12 injected stages are exercised, including
  unreachable-stage handling. Successful IRQ registration invokes the actual
  handler before initialization completes, not just after probe returns.
- Controls detect missing primary/HIF2 action removal, wrong WED IRQ identities,
  repeated free, disable instead of tasklet join, late enable, scheduling outside
  the shared admission lock, missing shutdown latch, unacquired vector free,
  early HIF2 put, missing unregister join and missing initialization guard.
  They fail intended assertions, not sanitizer faults or timeouts. Earlier
  candidate234/11 and234/12 cohorts remain separately preserved.
- Kernel framework operations, PCI/WED allocations, devres, register effects,
  tasklet execution/join, references and full NPU/mac80211/DMA/MCU internals are
  models. The dedicated fixture executes the selected C bodies jointly; the
  separate1090 caller suite explicitly models this additional PCI boundary.
- Current BA37/eight controls/separate TSan, retained owner23/14, creation19/12,
  BA18/six, worker23/eight, joint6150 resets across3 profiles/two generations plus
  12 negatives/three controls, broad456/four and callers1090/seven pass. All142
  observer/tooling/inventory/phase units pass, zero skips.
- Four AArch64 modules link with GCC14.4.0/Linux6.18.52, producer99e7ac56,
  locke54552fe,31 component mappings/5 kernel/330 mt76 sources/16 fuzz0 cumulative
  outputs. PCI shutdown symbol and tasklet-kill import resolve. Only mt7996e
  changes. Original102685 kernel/516 mt76 inventory entries remain unchanged.
  The independent copied-cache build retains236MiB/no swap and256MiB output
  ceiling, not a fresh world/image build.

Exact artifact/source hashes, process identities, actual Jev probabilities and
resource receipts are retained in EVIDENCE.json and its private preserved graph.
Jev flagged source obligations and checked scope; it is not proof. Its exact-IRQ
retention0.71 and delayed-HIF2-put0.75 judgments remained uncertain; direct source
inspection and compiled wrong-ID/early-put controls establish the covered host
behavior. No probability threshold substituted for deterministic checks.

## Preservation And Remaining Work

The first extractor did not accept irqreturn_t, and a Windows import then exposed
Linux-only resource usage; neither attempt performed inference. Native extraction
and actual API inference succeeded. The first installer incorrectly expected a
new PCI patch member and refused before writes. The corrected installer uses the
existing16 members. Failed attempts stay preserved; no limits/margins are waived.

The original capsule, prior evidence and14 project/one external protected images
are rehashed. Both live native replay identities/input graphs, caps and recipes
remain unchanged. Partial RPC observations are not complete verdicts and no job
is restarted for an observation timeout. Read-only bounded per-file cache advice
may release clean pages after hashing; it changes no file data or VM policy.
No module load, current image, promotion, flash, hardware/client test, new REA/
Ghidra/decryption, subagents or global policy change occurs in this checkpoint.

This does not complete RX/NAPI or separate NPU ingress lifetime. Registered and
enabled NAPI state must be tracked through partial startup and failed reset;
[NAPI controls](https://docs.kernel.org/networking/napi.html) are not idempotent.
Ownership release also is not poll-method return. Actual mt76 RX drops explicit
RCU before its completion callback; MT7996 TX calls IRQ enable after completion.
Those callback tails must be joined before consumer-private storage retirement.
A device reference does not pin a concurrently unbound HIF2 driver's devres, so
that binding/lifetime dependency remains required. Complete cold-prefix work/
NAPI/MCU unwind, firmware BA ordering/reuse fencing, hot transport admission,
physical drains and production retirement/rearm remain. Full native/current-image/
cold-fault/HIF2/hardware/client/performance/stability gates stay open. Full NPU
implementation and qualification remain the objective.
