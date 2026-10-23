# RX BA Primary-Link And Shutdown Integrity

Classification: progress toward full NPU reverse engineering/implementation,
not authenticated BA lifetime/reuse, operational hot RRO or physical acceptance.
Base:5d7b0d5c60563bfda4d08b4db17fe4c5e25571aa.

## Implementation

RX BA creation stores software reordering state on the station's persistent
primary WCID. The existing per-link MCU loop sends BA commands to each active
link WCID, and ordinary RX reordering already follows def_wcid. The status parser
previously accessed only the event WCID's own aggr slot. It now follows the same
primary mapping, retaining the direct lookup when def_wcid is NULL and handling
a primary self-pointer without traversal or fallback to a secondary slot.

Status assignment now takes the RX-TID lock and rejects an already stopped
object, using the same lock as actual RX-TID shutdown. RCU still protects lookup
and object lifetime. The full32-bit status0 gate, TLV framing/continuation and
owned-invalid DELETE retention remain unchanged. No cached-pointer status3 retry,
RX recycling, generic allocator or production-retirement change was added.

## Executed Evidence

- New combined fixture:14 measured setups/seven compiled intended-assertion
  controls. It executes verbatim actual RX-TID start/shutdown/stop, AMPDU action,
  per-link RX BA MCU loop and status parser together, with the selected top-level
  RX-TID/wire declarations. Nested kernel types, allocator, RCU, locks, active-link
  iteration/lookup, work cancellation and the physical MCU boundary remain models.
- Coverage includes primary/self/direct/secondary/third-link mapping, missing
  primary slots, one modeled lookup-before-stop interleaving, replacement and
  deferred disposal, allocation failure before MCU enable, partial per-link MCU
  failure and buffered-frame shutdown. ASan/UBSan/leaks remain enabled.
- Existing BA framing/status suite:18 measured setups/six controls. Retained
  worker:22 cases/eight controls. Actual provider/mt76 bridge/client/codec/broker/
  journal/native host C:6150 reset transactions across three profiles/two journal
  generations,12 negatives/three controls. These remain host-modeled boundaries,
  not kernel concurrency, physical MCU, RV32 execution or physical-drain proof.
- Broad allocation/fault regression:456 cases/four controls, three complete
  geometries,387 publications/effects,11 negative joint cases and12 late TX checks.
  Source-bound callers:1090 cases/seven controls,1040 optional-provider and50
  modeled-owned cases. These separate suites do not establish joint kernel use.
- All142 observer/tooling/inventory/phase units pass,zero skips. The candidate
  and installed fixtures both pass. Two GNU nested-flexible-member fixture
  warnings were removed by moving those members last, without changing selected
  C, assertions or flags. The initial fixture versions and receipts remain kept;
  two warnings in unmodified selected production C remain in the host logs.
- All four current AArch64 modules final-link with GCC14.4.0/Linux6.18.52.
  Producer1b9781c2/lock20c1747a binds5 kernel/330 mt76 sources/31 mappings; all15
  mt76 patch outputs reconstruct at fuzz0. Only mt7996e module bytes change from
  the previous producer; provider,mt76 and connac bytes match. Three typed reset
  import/export edges still resolve. Original102685 kernel/516 old mt76 entries
  remain unchanged. Lean private copied-cache build236MiB,154978289 output bytes.
  This is not a fresh world build, module load or hardware execution.

Both full replay jobs/input graphs, the frozen2865-input capsule, previous
evidence versions and protected images are preserved. No old replay was restarted
or its bounds/geometry/cap changed. New phases use fresh full-cap RAM/storage
checks, no new swap and the original2GiB margin. A lighter Windows launcher
allowed the preparation guard to pass after two PowerShell-wrapper RAM refusals;
the threshold itself was unchanged. No subagents were launched.

## What The Fixture Does Not Establish

The real start function stops/unpublishes an old object before allocating its
replacement. Injecting an old-looking status tuple after replacement still
assigns the current object's ID. This characterizes the host parser's inability
to distinguish that tuple; it does not prove the real firmware can produce that
ordering or that a physical race occurred. A firmware cookie or an independently
qualified ordering/reuse fence remains required. No host BA token/generation was
created by this patch, and initial reset journal generation1 is not one.

An injected physical-MCU error also leaves the newly published host context
allocated. A failure after one successful link command prevents later commands
but does not establish physical rollback of earlier links. The fixture observes
current host behavior; it does not grant free or retry authority. Buffered SKB
disposal is software reordering cleanup, not RRO/NPU backing retirement.

The saved mapped-live WM archive remains a different-build lead, not current
firmware-ordering evidence. REA's tool connection is closed; no new Ghidra or
firmware decryption was performed. Passive host checks found no serial port and
a disconnected wired adapter; no network probe, radio association change or
hardware write was attempted. The two queried REA PIDs were not signaled here.

Next establish actual BA creation identity and its primary/active-link association,
qualify current-firmware late/reuse ordering, then hot CPU ownership, production
retirement/rearm and independent physical drain. Full native verdicts/current
image/cold-fault-HIF2/hardware/client/performance/stability acceptance remain.
No full image, flash or VM/global-policy change. Full NPU goal remains active.
