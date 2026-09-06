# Native API21 TXBUFSPACE Callback Closure

2026-09-06. Base: `d41ac7ba1987f2d47a5e95146f8127cd7f7d49e4`.
**Four original callback selectors closed; strict API21 admission stays CLOSED.**
This is serialized RV32 instruction evidence, not hardware or full attachment.

## Scope And Inputs

Only `tests/npu/test_attach_txbuf_callbacks.py`, this report, and
`txbuf-callbacks.json` are deliverables. Scratch is confined to
`.local/npu-attachtxbuf`. Source helpers and the existing ELF are unchanged;
no rebuild, firmware/policy/platform/config/overlay/Git/router/network/flash
operation was performed. The parent-owned ledger was intentionally unchanged.
Other agents' TX-init, DESC10, and DESC5/6/7/8 work is not duplicated here.

The test reuses actual native C0 state from the unchanged RX helper:
`to_wifi -> footprints -> host_publish -> GET10 -> original SET14(port2)`.
This executes native reset, allocator initialization, L2/Wi-Fi initialization,
and synthetic host-register publication. The complete boot L2 oracle passes.
General admission remains closed, bootstrap state is 6, and admission state is 1.
Original DATA `+0x1cc` binds API21 to `0x8400fbca`.

All reached callback memory/lookup/helper bodies execute. The only callback
function-return substitution is the existing diagnostic printf model. Existing
boot-only hart/timer/printf substitutions are separately enumerated in JSON.
No allocator, lookup, record initializer, or delay return is substituted.
Nine native code ranges are compared against pinned CODE; Ghidra function
identities and raw code-range hashes are retained. Ghidra merges the record
initializer into the caller's C; `0x8400ee94..0x8400ef36` is independently pinned
as a 162-byte native range rather than claimed as a separate Ghidra function.

## Exact Host Commands

The four extracted operations are cross-checked against all four pinned
host-sequence JSON success profiles and the unchanged host helper. Each has
12-byte framing; interposed parent/page operations are not executed here.

| Host Position | Words | Host Buffer |
|---|---|---|
| 25 | `0x15, 21, 0x10100000` | `T[1]` |
| 26 | `0x1a, 21, 0x10200000` | `T[2]` |
| 29 | `0x17, 21, 0x10400000` | `T[4]` |
| 30 | `0x1c, 21, 0x10500000` | `T[5]` |

These are the pinned host test's synthetic DMA addresses, not live allocations.

## Native Layout And Ordering

| Selector | Native Destination | Count x Stride | Contract |
|---|---|---|---|
| 5 | `0x3e81f020` | 512 x 128 | Arena subregion 10 |
| 7 | `0x3e841040` | 1024 x 128 | Arena subregion 11 |
| 10 | `0x3e8a2000` | 512 x 16 | Fixed lookup `0x100` |
| 12 | `0x3e8a4020` | 512 x 16 | Fixed lookup `0x101` |

- Native Wi-Fi arena is `0x3e817000`, length 303168. Subregion 10 starts at
  offset 32800 and ends exactly at the next subregion, offset 98336. Subregion
  11 starts at offset 172096 and ends exactly at the arena boundary.
- Each 128-byte record is 32 little-endian words: `0x100000`, thirty zeros,
  then `0x10000`. Native `fab2` scans the immutable subregion table. Selector
  5 stores its result at SRAM `+1f38`; selector 7 uses `+2abc`. Replacing the
  supplied address with zero or `0xdeadbeef` yields byte-identical RAM images;
  the latter adds an out-of-range diagnostic only.
- `a5fa(0/1)` waits for nonzero SRAM `+2ab8`, originally initialized natively
  to `0x8cc00000`. It obtains fixed table `0x100/0x101` through native `5200`.
  Each descriptor writes a 32-bit host pointer, two zero words, and one zero
  byte at offset 12. The final three bytes are preserved. The 32-byte gaps
  after the two 8192-byte descriptor extents are untouched.
- Linked host pointers are `0x90200000 + i*256` and `0x90500000 + i*256` for
  all 512 entries each. Both 131072-byte synthetic pools are explicitly mapped
  and poisoned with repeating `00..ff`. Every pointer's full 256-byte slot
  fits its declared nominal capacity. No native host-pool load/store occurs;
  the pools remain byte-identical. This does not establish physical backing
  or cached/uncached alias coherence.
- Pointers publish **before** record initialization. The original wrapper
  returns `1` only after native completion, but there is no dedicated ready
  publication. `a5fa` is void: selector 12 can leave band0's descriptor pointer
  in A0, which is not a failure status. Direct callbacks leave mailbox flags
  at `1`; this is not a fabricated mailbox completion or readiness witness.

## Oracles And Controls

Every case compares 1048576 bytes: all local SRAM, allocation heap, L2, and
both synthetic host pools. An independent ABI/source-table oracle generates
every ordered successful RAM store `(pc,address,size,value)` and its exact
unique byte footprint, including partial failure prefixes. A separate oracle
checks every non-stack read's PC/address/size/value and multiplicity, including
payload loads, immutable table scans, and startup reloads. Call-frame accesses
are bounded and traced separately; code identity is checked after each case.

Nominal cases check 53258 RAM stores, 47 non-stack reads, 1536 full 128-byte
records, 1024 16-byte descriptors, and 1024 linked host slots. Full valid-case
access aggregates and bounded control counts/digests replace instruction logs.

The 35 controls cover:

- Four supplied-address diagnostic-only cases for selectors 5/7.
- Four missing/one-record arena cases. Unmapped writes stop at `0x8400eeb2`
  after the pointer store, or after that store plus one 128-byte record.
- Four nonzero TX-packet inputs (`0x8a000000` and `1`), accepted without
  validating that base. This flag gates execution, not packet memory validity.
- Eight zero-TX-packet cases: persistent wait, delayed release, frozen cycle
  input, and missing cycle model, for each selector. Persistent waits execute
  two actual delay bodies without entering the lookup. Delayed release then
  completes all 512 descriptors. Frozen/missing cycles produce no callback
  return and no descriptor stores.
- Five explicitly write-protected L2 capacity cases: 0/256 entries for selector
  10 and 0/254/510 for selector 12. These page-boundary choices respect the
  tables' different alignment. The failed store is excluded from successful
  writes, partial RAM matches the oracle, and wrapper success is not reached.
  The inherited error text says `unmapped access=22`; 22 is WRITE_PROT here.
- Four logical host-capacity cases, zero or one slot short. Poisoned backing
  pages remain mapped, but the declared capacity is reduced; accesses outside
  it would be rejected. Callbacks still return `1`, since no host memory is
  accessed. This is absent validation, not an emulator mapping escape.
- Four invalid host-address cases, zero and `0xd0200000`. Address conversion
  continues and the latter warns. Two exhausted-dynamic-heap cases still
  succeed through fixed table lookup. Immutable fixed tables cannot honestly
  be made to return NULL by substituting a dynamic allocator failure.

MCYCLE instructions execute. Unicorn ignores writes to MCYCLE and derives it
from wall time, so the fixture replaces the resulting A5 input immediately
after each CSR instruction, before native code consumes it: increments of
10000000 for advancing cases, zero for the frozen cases. All delay arithmetic,
branches, stack accesses, and returns execute. No PC/A0/RA shortcut or real-time
claim is used. Missing input fails explicitly. No new MMIO model is added.

Four actual strict-transport API21 requests return flags `3`, execute no
original callback, and leave the compared RAM unchanged. No policy changed.

## Replay And Identities

From canonical WSL `/home/captain/W1700KNPU`:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.local/npu-reset/python-lib \
  python3 tests/npu/test_attach_txbuf_callbacks.py --check
```

Fresh generation and byte-identical `--check` both PASS: 4 valid callbacks,
35 controls, 4 strict denials. JSON is 368126 bytes, below the 400000-byte cap.
All imported source helpers are hash-checked before/after execution.

| Input / Evidence | SHA256 |
|---|---|
| Test | `b055a2ae16285f99c0579493de75e0b056cba21c31e5fbbd0902d2ae2a393b82` |
| JSON | `87e05581200864044b3661b52ba8434a5a4ad4114478a095107a9654bac5b0cb` |
| Immutable ELF | `bdb64d12d738bdef85a747d0b638e6b148c1c534410fd893348fbaf5908e2931` |
| Native CODE | `e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643` |
| Native DATA | `61a75afb052feed2ceb2f3023e16f50317c05c78f9c8e564bf01924ce39c7ec1` |
| Ghidra export | `1536a9972838ca7c02da77629e784b392af919c5d25368478aff4d0c2422e2ca` |
| Host-sequence JSON | `7135e05b76218e8f0cd815e9bd3cc13434129ddedb1afe15279f250c038e3739` |

## Remaining Boundary

The two prior allocator-substituted cases and four prior TX-packet wait labels
are replaced by native completion/wait/failure evidence. Relative to the RX
checkpoint, seven original pending labels remain outside this lane: DESC
5/6/7/8/10 and TX-init 0/2. This is not a statement about concurrent agents'
completion status. Full host attachment, post-gate workers, physical loader,
MMIO/cache/DMA ownership, concurrency, recovery, and hardware/client acceptance
remain outside this test. Capacity diagnostics and pointer/return publication
must not be promoted into readiness or strict-admission permission.
