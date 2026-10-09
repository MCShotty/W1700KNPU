# Native Cold Page Claim Composition - 2026-10-10

Continued from GitHub/local main `87a8a2eab65f25d25f0dfe9cbae9b6e3694565c2`.
The full NPU implementation remains incomplete. No flash or hardware changes.

## Implemented

The shared `cold-page.c/.h` now exposes `npu_cold_page_queue_take()`. It checks
queue geometry before reading an ID, preserves stale-epoch isolation, claims
ownership, verifies the unchanged head/tail/ID snapshot, publishes the native
head with ordering and readback, and rechecks fault closure. A committed claim
is retained even if its native head cannot be published. A late-fault committed
claim advances an unchanged native queue but never authorizes a descriptor or
readiness. Queue pointers/backing and exclusion remain platform obligations.
The existing 1052-byte ownership-state ABI is unchanged.

The native emulation binding composes that actual C with original dispatcher
`0x8400dd82`, initializer `0x8400bc02` and DESC5/6/7 descriptor stores. The getter
detour at `0x8400bb9c` selects the reviewed initializer return site. The callback
requires an explicitly held coordinator lease, all workers parked, cold epoch1,
an immutable validated BA backing plan and the native pool/arena snapshots.
It checks selected count limits and translates native inner failure into outer
callback failure. Three guards prevent readiness publication after a known fault.
Other selectors delegate to the existing callback; unrelated getter users replay
the displaced native instruction. Successful allocation statistics are preserved.

This composition has 54 installed sites: 49 prior sites are unchanged, the prior
callback entry delegates through the new binding, and four getter/readiness sites
are added. The normal RV32 archive includes the extended shared core. The native
binding is compiled and executed with original firmware instructions in the
canonical test composition, not installed in the vendor blob or physical loader.
No helper return is injected to make the selected initializer pass.

## Verified

- `native-result.json`: three nominal rings consume IDs0..1791, publish exactly
  256/512/1024 descriptors with expected pointers/status/IDs, preserve statistics,
  and set each selected ready flag once. All 54 detours remain installed.
- Forty-eight controls cover empty/partial pools, duplicates, bad IDs/counts,
  changed arena/backing, missing parked workers, stale lifetime, claim/native-head
  faults, changed queue snapshots and a fault immediately before readiness.
  Partial exhaustion retains 17 claims/descriptors/head17 and returns failure.
  Claim and post-head faults retain one claim/head1 with zero descriptors/ready.
  A changed native head remains changed with its private claim retained; it is
  never silently repaired. Fault cases preserve the active lease and close
  admission rather than release/reclaim resources.
- Six deliberate mutants are rejected by callback-result, publication or
  readiness checks: omitted head store, snapshot check, late-fault check,
  getter lifetime recheck, unconditional outer success and omitted ready branch.
- `archive-result.json`: actual host C and the exact built `-Os` RV32 object
  pass 5,702 differential calls/294 controls/ten core mutants. ASan/UBSan/leak
  checks include the new queue API's nominal/argument/stale/invalid cases.
- `page-regression.json`: unchanged original-page behavior still passes four
  nominal cases, 48 controls, five native mutants and four strict denials.
- The final full-world build succeeds, all 60 locked source files compare, and
  eight build-runner tests pass. Fresh offline FIT/board/218-package/78-module
  checks pass. Eleven RV32 objects compile; the core object has no undefined
  helper symbols. The exact archive member matches the replayed object.
  FIT remains `230e03a7b87cb9e14e0464b53d324bb2c4eb650b3c9a64a63514b30dde4458fe`.
- Loader-memory/retry/V2 regression passes 273 loader cases, 165 added load
  cases, nine mutants, 6,174 retry and 44 V2 cases with leak checks.

Raw final receipts are `native-result.json`, `archive-result.json`,
`page-regression.json`, `memory-regression.json`, `source-result.json`,
`image-result.json` and `world-result.json`. `verification.json` records
independent input/artifact hash readback and archive-member identity.

An initial patch-record-only harness installation error was fixed before the
passing native runs. Exact `-Os` linking then exposed compiler-emitted `memcpy`
for a 24-byte aggregate initializer; explicit field initialization removes that
freestanding dependency. A source-replay receipt name collided with the image
verification directory; a fresh name was used. Those failed exploratory outputs
remain local and are not passing receipts. The earlier 36-control native receipt
predates the final arena checks/mutants and is also not the final source proof.

Jev pre-checks select native claim publication and BA backing. Final semantic
checks use official `jev-1.13.0`: partial and committed late-fault retention each
Noul0.91; unrelated-selector delegation0.97; native-emulated-composition Choice
probability0.88/confidence0.84. Neither physical completion nor strict setup is
selected. Raw questions/results are retained; tests and hash readback are the
deterministic evidence, not these semantic judgments.
Current API/model syntax was checked against the official
[API](https://docs.typesafe.ai/api) and [models](https://docs.typesafe.ai/models).

## Next Gates

Complete actual loader/storage and strict DISCOVER/setup/BIND publication, native
worker/postgate consumers, remaining RX statistics allocator paths, and hot-page
lifecycle/error handling. Establish real backing reservation/exclusion/cache
coherency and physical DMA drains/teardown/rearm before recovery or client claims.
Snapshot restoration and injected fault flags are test controls, not a safe
hardware reset protocol. No replacement vendor blob, firmware flash, physical
containment or real-client acceptance is claimed. Protected/private inputs and
generated binaries remain local; only source and text receipts are published.

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_cold_page_native.py --name fresh-native
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_cold_page.py --name fresh-member --core-object .build/merged-openwrt/bin/npu/cold-page.o
```
