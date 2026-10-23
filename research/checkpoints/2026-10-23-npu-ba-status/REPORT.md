# BA Status And Delete Integrity

Classification: progress toward full NPU reverse engineering/implementation,
not operational RRO or physical acceptance. Base:71686003aaa4b4cc2504524996ae8796062739a5.

## Implementation

The actual MCU event parser now requires the complete little-endian32 BA status
to equal zero before WCID/TID lookup and session-ID assignment. Rollback, retry
and unknown nonzero statuses cannot rebind the current object. Each rejected
record still advances through the common TLV path, including nonlinear records.
No status3 retry through a cached RX-TID pointer was restored.

Legacy DELETE IDs above MT7996_RRO_MAX_SESSION are rejected before allocation;
the inclusive special ID1024 remains valid. The owned DELETE branch precedes
this legacy-only gate: invalid owned tuples still reach the retained owner and
latch their fault instead of silently disappearing or entering CPU fallback.
No RX token/recycling behavior changes. In particular, the old historical patch's
ambiguous-descriptor recycling hunk was deliberately not copied.

This restores the narrow status/delete rules documented in the retained historical
integrity patch, not every old experiment. The cumulative mt76 patch reconstructs
all15 outputs at fuzz0; the kernel patch is unchanged. Lock961f5a40 retains31
component mappings,5 kernel and330 mt76 source bindings.

## Executed Evidence

- Installed-source BA parser:18 measured fixture setups/six compiled intended-
  assertion controls. Coverage includes full32-bit nonzero statuses, retry then
  success, continuation to later TLVs, legacy1024/1025/65535 boundaries and exact
  invalid owned WLAN/TID/session forwarding. ASan/UBSan/leaks remain enabled.
- Count correction: the earlier harness printed a hardcoded label15. A preserved
  copy of the exact earlier selected C, with only counter instrumentation, passes
  every old assertion and measures14 setup invocations. The new suite retains
  those assertions and adds four setups, yielding18. Historical receipts stay
  unchanged;15 is not an independently measured old fixture count.
- Retained worker:22 selected-C cases/eight compiled controls, including all1025
  IDs, errors, duplicates and close/handoff decisions. Framework locks, references,
  transport and MCU calls remain modeled, not kernel concurrency evidence.
- Actual provider/mt76 bridge/client/codec/broker/journal/native host C:6150 reset
  transactions across three profiles/two journal generations,12 negative cases
  and three controls. Full journal/mapped-array checks remain. Backing, mailbox,
  physical MCU responses and CPU exclusion remain modeled boundaries.
- Refreshed broad provider allocation/fault matrix:456 cases/four controls, all
  three complete geometries,387 native publications/effects,11 negative joint
  cases and12 late TX checks. Fixture frees are not production retirement.
- Refreshed source-bound caller matrix:1090 cases/seven compiled controls,
  explicitly1040 optional-provider and50 modeled-owned cases. This separate
  characterization is not full joint kernel execution or a physical teardown.
- Four current AArch64 modules final-link with GCC14.4.0/Linux6.18.52. Producer
  3b85252f retains all three typed reset import/export edges. Provider,mt76 and
  mt76-connac module bytes match the previous typed producer;mt7996e changes.
  Original102685 kernel/516 mt76 inventory entries remain unchanged. Lean private
  copied-cache build236MiB,154970771 output bytes; not a fresh world build.
- All142 observer/tooling/inventory/phase units pass, zero skips. Fresh full-cap
  RAM/storage guards retain the original2GiB margin, no new swap, no relaxed
  sanitizer, geometry, instruction limit or replay bounds.

The first candidate suite failed only because the new measured counter exposed
17 setups against the intended18; all its C assertions had passed. The missing
fourth new scenario was then added and both candidate and installed suites passed.
That failed cohort and all prior failed/qualified cohorts remain preserved.

## Firmware Provenance And Remaining Work

The historical mapped-live WM archive verifies at96e6f37 but belongs to build
20260311120504. The current encrypted carrier is build20260721003035,99020e57,
with a different region map. The old archive is a related analysis lead, not
proof of the current firmware's BA ordering or reuse fence. No current decryption
or Ghidra binary analysis was performed; no running Ghidra instance or Windows
serial port was observed in the scoped checks.

Status0 is a necessary binding rule, not BA authentication. The current status
handler still resolves whichever WCID/TID object occupies the slot. Create actual
RX-TID BA identity with primary/active-link mapping and qualify a firmware cookie
or genuine late-event/reuse fence. Initial journal generation1 and generic MCU
ACKs cannot provide that identity. The consumer remains one-shot per session ID.

Parked-only transport guards remain unchanged; hot admission/CPU lifetime,
production retirement/rearm and independent physical drain remain open. Both
long replay jobs and their captured input graphs remain untouched; observed
partial traces are not full verdicts. The two previously queried newer REA PIDs
had already exited without an action here; the remaining server was not signaled.

Full current image, complete cold/fault/HIF2 and physical hardware/client/
performance/stability acceptance remain required. No module load, full image,
flash, radio/network change, VM change or global-policy change occurs here.
The full NPU goal remains active.
