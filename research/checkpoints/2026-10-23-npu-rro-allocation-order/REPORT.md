# Checked TX Ownership Before RRO Init

Date: 2026-10-23. Base commit: `47f5f6f`. Previous goal turn: concrete progress.
This checkpoint advances the real allocation path; full NPU reverse engineering
and implementation remains active and incomplete.

## Dependency And Change

The previous real initializer called RRO init during hardware initialization,
then allocated its six TX buffers later during registration. The retained RRO
journal requires all protected TX spans before opening. Wiring it directly to
the old order could not supply those identities.

The checked provider's existing retained TX allocator now runs after MCU init,
before `mt7996_wed_rro_init`. The caller saves successful handles only after
the full operation succeeds. A second preparation cannot overwrite that lease.
An unmarked provider's EOPNOTSUPP result leaves its buffers unallocated and its
existing later managed fallback unchanged.

At the later `mt7996_npu_hw_init`, a prepared lane validates the exact retained
TX handles and sizes, provider/endpoint/boot/nonce, captured TX serial, mailbox
records and RX state under the provider mutex. Failure has no hardware entry,
new allocation or managed fallback. A successful validation consumes the
prepared hardware attempt before setup, including an attempt that later fails.
This is a host lease check, not IRQ/DMA/firmware quiescence or free authority.

## Evidence

- Current actual provider/caller C: 223 ASan/UBSan/leak cases and 12 compiled
  controls pass. Coverage includes all six allocation-failure prefixes, one-shot
  and concurrent preparation, 82 stale-record cases, exact serial and mailbox
  checks, missing/closed providers, missing validator, sticky IRQ faults and
  failed/repeated late hardware entry. Framework/IRQ locks, DMA backing, device
  references and transport delivery remain explicit test models.
- Original selected host C: 113 applicable cases pass in the same current test
  driver. New-only cases are enabled only for the new preparer. This is not a
  claim of identical full traces or native instruction A/B execution.
- RX/early-TX composition: 168 cases and seven compiled RX controls pass.
  Actual provider RX allocation, inline wrappers, mt76 queue allocation hooks,
  current TX preparation and late entry execute. The new composition verifies
  both normal handoff and a changed RX handle between early and late entry.
- Complete selected RRO caller fixture: 1,040 cases, three teardown controls
  and one missing-early-preparation control pass. The full higher initializer
  must successfully cross its modeled TX-preparation boundary before the first
  RRO allocation. The removed-call mutant compiles and fails at that exact
  assertion. Actual TX preparation executes independently in the suites above;
  this is not one full joint kernel initialization execution.
- All 134 RRO frame bytes remain identical to the prior actual-caller capture.
  The metadata journal reruns all 5,279 cases/three controls successfully.
- Genuine pinned GCC14.4.0/Linux6.18.52 final links pass for provider, mt76,
  connac and mt7996, using the same new public callback definition. Five
  reconstructed kernel source and 329 mt76 source identities match the new
  producer; original prepared kernel/mt76 inventories remain unchanged.
- All 23 ELF32 RV32 objects/archive members match exactly; archive bytes are
  identical to the previous 23-object build. Current export verification and
  all 116 focused tooling units pass, zero skips. New unified-diff context has
  required patch-prefix whitespace; patches are applied with fuzz0 and checked
  against exact source hashes, separately from ordinary-file whitespace checks.

Current source lock:
`13b5bba636839d6e477bfa91f7c10f360bff2068cbd4f4b9edd075157f53057a3`.
Current four-module producer receipt:
`c72f31d71652663a61bf1c142a71dc1d93f098b60ce528fadfd12bb5f1bac0b5`.
Provider SHA256: `573b56d51cfc49d33538809c6dd54e6f0009f7315b92b72d00ba2384b6355341`.
See `EVIDENCE.json` and its private hash-bound receipt for actual artifacts,
service observations, source generations and preservation mappings.

## Limits And Failure History

The first new early-preparation fixture configured its missing-callback generic
case with the checked-provider flag still set. It compiled, then failed at
case117's retained-owner assertion. Those bytes and outputs are preserved.
Correcting this newly added fixture did not loosen production behavior. The
later 199-case and final 223-case runs remain separate receipts; earlier inputs
and source versions are retained, not overwritten to manufacture a pass.

The fresh Jev source batch supports most stated boundaries, but its prepared
EOPNOTSUPP fallback judgment is uncertain at 0.52 and pre-attempt consumption is
0.74. Exact C missing-validator/failed-entry cases and the intended mutants
supply covered-behavior evidence instead. Probabilities remain advisory, never
physical approval. The earlier plan-requirement judgment0.57 is also retained
as uncertain, not promoted to a dependency proof.

No new host-function or journal target-instruction execution is claimed. These
are host C executions and real target compilation/final links, not module load,
physical DMA/radio behavior or full NPU acceptance.

## Preservation

Only the reviewed cumulative kernel/mt76 patches and their source-lock hashes
advance. The selected generated sources are reconstructed from those patches;
old snapshots and source locks are retained independently. This does not make
older receipt-bound working pathnames current again. Original builds, cache
cleanup keepers/restoration maps, old failures and protected images remain.

The normal RV32 sources/archive and raw4e43de6f/a282ca7a pair are unchanged.
MT7996 NPU driver paths changed; UI and radio-policy configuration did not.
There is no new full image. Imagea3f1d04b remains qualified only for its older
source and callback layout; do not mix the new modules into that old image.

The compact default replay still executes frozen2f85e54 with its original
controller/native start ticks. Its 2,865 frozen inputs, 14 protected project
image path bindings and one external object are checked when sealing. It is
not restarted or upgraded to the new sources. A live process is not a terminal
full-cold verdict. No hardware/flash, VM/swap/global policy change or subagents.

## Remaining Full Scope

Actual RRO buffers still follow the old managed allocation path. The portable
RRO journal is **not yet invoked by actual RRO callers**. Connect provider-owned
RRO allocation/reference retention, early teardown handoff, process/atomic
transport, retained MCU work and exact reset generation/ticket completion.
Propagate initialization failures and establish physical IRQ/DMA/firmware/
cache/PMA drain and retirement before granting reclamation or operational RRO
admission. Existing checked RRO denials are not the final intended state.

The future admitted RRO protocol must explicitly coordinate its serial advance
with late prepared-TX validation, not bypass that validator. Rebuild and qualify
a full current-source image; complete original default, separate HIF2/full-fault
replays, hot ownership/lifecycle/whole-stack, and physical boot/radios/client/
performance/stability acceptance. The full objective remains unchanged.
