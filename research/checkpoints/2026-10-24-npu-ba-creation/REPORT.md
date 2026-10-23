# W1700K RX-TID Creation Identity

Classification: progress toward the full NPU goal, not completion or hardware
acceptance. Base commit9df785c. Exact receipts and source hashes accompany this
report in EVIDENCE.json; private evidence remains local.

## Implementation

Successful actual mt76 RX-TID allocation now assigns an immutable nonzero u64
creation serial before RCU publication. The device-local sequence is guarded
by the existing device mutex, now lockdep-asserted. All seven in-tree AMPDU
creation callers already hold it, directly or through Connac mutex helpers.
Different TIDs and WCIDs share the sequence; the namespace is one mt76 device,
not a globally unique firmware identity. No stop/recovery counter reset is added.

Allocation failure consumes no identity. The existing stop-before-allocation
behavior remains, so ENOMEM can leave the old slot empty. MCU failure retains
the published context and consumed serial, including partial per-link enable;
this does not prove physical rollback. U64_MAX is usable once; later creation
returns EOVERFLOW before stopping the existing object, allocating or enabling
the MCU. Ordinary stop remains possible after exhaustion.

## Verification

- Combined actual selected RX start/shutdown/stop, AMPDU, per-link MCU BA loop,
  wire structs and event parser:19 measured setups/12 compiled mutation controls,
  retaining every previous14/seven check. Added cross-TID/WCID identity, initial
  allocation retry, MCU-error replacement and final-u64/exhaustion cases.
- Mutations cover missing/reused creation identity, omitted or late exhaustion
  checks, failed-allocation serial consumption and the previous link/shutdown/
  allocation/MCU-loop regressions. Each fails its intended assertion, not a
  sanitizer or compilation error. ASan/UBSan/leak detection remain unchanged.
- Current BA18/six, retained worker22/eight, joint6150 reset transactions across
  three profiles/two reset-journal generations plus12 negatives/three controls,
  broad456 allocation/fault cases/four controls, linked callers1090/seven and
  all142 observer/tooling/inventory/phase units pass; zero skips.
- Four AArch64 modules final-link with GCC14.4.0/Linux6.18.52, producera7cab69b,
  lock06132a68,31 component mappings,5 kernel/330 mt76 sources and16 cumulative
  mt76 patch outputs reconstructed at fuzz0. Exact module byte changes are in
  EVIDENCE. Original102685 kernel/516 prepared-mt76 inventory entries remain
  unchanged. This is a private copied-cache rebuild, not a fresh world image.
- Original236MiB module cap,256MiB output ceiling, zero swap, native instruction/
  time limits and reserved2GiB host/guest margins are unchanged. A concurrent
  module launch was correctly refused by the full-cap RAM guard; launch after
  the other tests finished passes without a waiver. A missing WSL environment
  label failed the first candidate launch before tests; corrected launch passes.
  Failed journals and all previous evidence remain preserved.

## Limits And Next Work

The new serial is not present in current BA firmware messages and is not yet
carried into independently retained status/delete/reset associations. Host event
arrival ordinals and reset-journal generation1 remain different identities.
The host test still injects a cookie-less old-looking status after replacement
and observes the new object receiving it despite distinct creation serials.
This establishes host indistinguishability, not real current-firmware producer
reachability or a physical race. Carry the serial, original active-link/primary
mapping and immutable session tuple into retained BA records next; then qualify
a current-build firmware cookie or actual late/reuse fence. A counter alone
cannot do that job, regardless of how confidently it increments.

RCU scheduling, locks, allocation errors, active-link iteration, work handling,
transport/backing and physical MCU remain explicit models in the host tests.
No kernel concurrency, hot-path admission, owner retirement/rearm, DMA drain or
free authority is established. The complete native replays, current full image,
cold/fault/HIF2, real hardware/client/performance/stability gates remain open.

## Preservation

The user authorized stopping REA PIDs104034 and666864. Both were already absent
on fresh observation, so no signal was needed or sent. No unrelated server was
stopped. Both original replay PIDs/start ticks/invocations/input graphs remain
unchanged and their CPU progress advances. Neither was restarted for observation
timeout. No new hardware access, module load, image/flash, VM/global-policy
change, Ghidra/decryption analysis or subagents occurred. Jev supplied bounded
semantic design/source/report checks; it did not implement code or replace tests.
