# Next Native API21 Ownership

The host allocation lifetime is now implemented and qualified. Native admission
remains absent; do not whitelist API21 from this checkpoint alone.

1. Enroll the six provider-owned DMA address/extent records into the same native
   boot/nonce/held session before the actual hardware initializer starts. Existing
   cold transport carries identity, but currently has no native copy of those six
   records. Preserve the once-owned attempt and ambiguous-failure retention.
2. Preserve the actual caller order: GET5, API21 selectors 0/5/10, GET7, then
   selectors 2/7/12. Do not require all eight descriptor GETs before selector 0.
3. Own selector 0/2 alias metadata at `0x3e902cf8` / `0x3e902ab4`. Selector 5/7
   supplied addresses are logged, not their write destinations: they initialize
   512/1024 internal 128-byte records at arena+`0x8020` / `0x2a040`. Protect the
   complete original store set and arbitrary preimages before invocation.
4. For selector 10/12, guard the alias publication at `0x3e903960` / `0x3e902a88`
   before entering helper `0x8400a5fa`. Require the exact published TXPKT plan
   prerequisite at `0x3e902ab8`, not merely nonzero; original code otherwise
   enters an unbounded delay loop or accepts an unrelated nonzero value.
5. Validate the static CODE entries at offsets `0x1cf70` / `0x1cf78` and exact
   full 8,192-byte L2 destinations `0x3e8a2000` / `0x3e8a4020`. These type
   0x100/0x101 lookups are not dynamic allocations or lock18 acquisition paths.
6. Reserve the earlier metadata writes too: band0 clears 16-bit counters at
   `0x3e90462c` / `0x3e90395a` and publishes a 32-bit pointer at `0x3e902acc`;
   band1 uses `0x3e902a8c` / `0x3e90390c` and `0x3e9021e8`. Missing table entries
   mutate these fields before faulting at the first null record store.
7. Each band emits 512 records, regardless of the larger host allocation. Store
   widths are 4/4/4/1 at offsets 0/4/8/12; preserve bytes 13-15. Host addresses
   advance by 256 and carry the 0x80000000 alias. Unused allocation tails remain
   retained; they are not automatically reclaimable.
8. Add exact-object, arbitrary-preimage, partial-fault, source-mutant and raw
   original-caller composition checks. Keep callback/lock interactions and
   readiness-last/error propagation explicit. Fixture snapshot restores are
   not production rollback/reset/retirement.

The original instruction trace is `original-tx-records.json`; the reproducible
runner is `tests/npu/test_tx_buffer_records.py`. It proves modeled store effects,
not physical L2/backing exclusion. Native enrollment and record ownership must
be wired into the unified mainline, followed by the remaining full-objective
setup, owners/hot/postgate, physical drains/recovery and actual-client work.
