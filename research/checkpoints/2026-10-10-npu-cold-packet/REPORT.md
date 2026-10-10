# Checked Cold RX Packet Ownership

Date: 2026-10-10. Base main: `59d9202938d3e385121814259bd4a66ccd887d44`.

## Scope

The normal RV32 archive now includes `cold-packet.c/.h`: a fixed 16,384-ID,
2,048-byte PKT profile of the retained-claim algorithm, distinct from the
8,192-ID/128-byte BA-page profile. Packet state is 2,076 bytes; page state/ABI
and the compiled page object are unchanged. No release, recycle, fault-clear or
existing-lifetime reinitialization API is added. Fresh storage, reserved backing,
coherency and exclusion remain platform contracts, not consequences of geometry.

The selected native binding composes this actual C with original RX0/RX2 and
lock28 instructions. It verifies the checked allocator's type-0x8a ID-table
record, alignment/extent and a retained pointer snapshot; the initial table is
`0x3e800020`, not the older fixture's `0x3e800000`. Type1 is the descriptor arena.
PKT backing is `0x8a000000` with the existing plan span, not the BA page region.
The held callback lease, already-bound V2 nonce, disabled local IRQs and all
eight parked workers are explicit emulation inputs/contracts.

The six-byte getter entry detour covers the original two-byte stack instruction
and four-byte AUIPC without splitting either. Reviewed RX return PCs use a
private constant lock28 ID; original acquire/release bodies execute. A failed
acquisition never claims or releases. Granted takes retain ownership before
verified native head publication, release once and recheck lifetime before
descriptor/readiness exposure. Public lock mutation cannot change release ID.
Unrelated callers replay the displaced entry and retain the earlier TXDONE route.
The unrelated-getter control is restored before owned RX replay; its allocations
are not claimed by this selected RX binding.

There are 61 installed sites: the prior 60-site composition, three replaced
getter/readiness guards, and one new entry site. The binding's independent
`0x84080000..0x84084000` storage is checked for emulation overlap, not installed
by a real loader. The library is not a bootable replacement for the vendor blob.

## Verified

- `core-result.json`: actual host C and the exact built `-Os` RV32 packet object
  pass 8,243 comparisons, 7,680 nominal claims across three plans, 546 controls,
  committed late-fault retention and five rejected sanitizer mutants.
  Address/undefined/leak checks pass. Wrap coverage uses independently seeded
  state, not 16,383 actual native allocations.
- `native-result.json`: final full-size RX0/RX2 instruction replay passes
  1,536/1,024 descriptors and 2,560 retained claims. Exact descriptor bytes,
  statistics clears, allocator metadata, queue heads and lock request/release
  counts match. Each successful callback publishes readiness once.
- Fifty controls cover denial, invalid lock/table/backing/ID/metadata/plan/cursor,
  duplicates and partial exhaustion, late claim/publication/release faults,
  changed queue snapshots, changed public lock ID, missing lifetime/guard and a
  fault before readiness. Partial exhaustion retains 17 claims/head/descriptors,
  returns outer failure, keeps the active lease and never writes readiness-one.
  Committed late faults retain the claim/head while denying descriptor exposure.
  A changed native head stays changed, with its private claim retained.
- Six initialized mutants fail behavioral checks: omitted grant denial, table
  identity, post-release lifetime check, readiness branch and entry gate, plus
  mutable-lock release. The last is rejected at wrong-lock MMIO, not a generic
  early fault. Mutation initialization asserts fresh magic and zero claims.
- Separate original DESC5/6/7 replay retains 1,792 BA claims/descriptors and
  verifies the entire 2,076-byte packet state remains unchanged. An unrelated
  native getter returns its original ID without touching packet ownership.
- `page-core-result.json`: 5,702 comparisons/294 controls/ten mutants still pass
  with sanitizers and exact page object. `rx-regression.json`: the original
  60-site statistics suite passes both full RX rings, 26 controls and six mutants.
  Its default whole-heap oracle remains strict; only the packet subclass adds
  independently predicted success/failure counter writes.
- `world-result.json`, `source-result.json`, `image-result.json`: twelve RV32
  objects and the complete world build pass, all 60 pinned source files replay,
  and FIT/board/218-package/78-module offline checks pass. Eight build-runner
  tests pass. No undefined helper appears in the packet object.

Exact packet object/archive-member SHA256:
`b0cbd168f7a9ff06a3f4c97fe2d3091a764337ca7af9c345f635bdc9ce076792`.
Unchanged page object SHA256:
`ad56a45923b200fd048bdebe31f2d3e238951acf86b9b164c667e081ffae0772`.
Unchanged FIT SHA256:
`230e03a7b87cb9e14e0464b53d324bb2c4eb650b3c9a64a63514b30dde4458fe`.
`verification.json` independently reads back proof input/artifact hashes and the
archive member. `file-manifest.json` records the published text receipt set.

Exploratory failures remain local and are not acceptance receipts: an omitted
history mutant survived an insufficient sanitizer fixture; fixed-address/type
assumptions failed against actual allocator records; the statistics-only heap
oracle needed the packet failure-counter prediction; a mutant needed compile
hygiene; reloading mutant BSS initially erased its ownership state and masked
the target defect. Each was corrected before final full-size/initialized proof.
`--quick` is explicitly exploratory and records `full_nominal=false`; the final
published native receipt is the default full-size run.

Jev uses official `jev-1.13.0`. The broad seven-question claim batch was uncertain
about several controls, so it is retained rather than presented as approval.
Focused field/injection questions return Noul0.95 for denied grant,0.82 each for
late retention/exposure denial,0.89 for snapshot retention,0.68 for private release
and0.03 for physical acceptance. The lower private-release judgment is checked
against actual constant source, exact lock28 MMIO and the mutable-release mutant;
it is not a physical grant/release witness. The broad scope Choice selects native
emulation with confidence0.88. Raw questions, probabilities/model/usage are in
the pre, broad-post and focused-post receipts. Tests and source review establish
their covered behavior, not Jev confidence.

## Remaining

Full packet ownership for other users, including TXDONE, still needs integration.
Complete real loader/storage and strict DISCOVER/setup/BIND, remaining native
worker/postgate consumers, hot free/refill/recycle and completion lifetimes are
unfinished. Physical reservation/exclusion/coherency, real grant/release and DMA
drains, teardown/recovery/rearm and actual-client acceptance remain unproved.
No vendor CODE/DATA replacement, flash or hardware operation occurred. Protected
backups, rollback and earlier images were not changed. The full NPU goal remains
active; this checkpoint closes only the selected cold RX packet prerequisite.
