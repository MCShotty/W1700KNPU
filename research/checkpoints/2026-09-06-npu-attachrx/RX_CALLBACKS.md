# Native SET DESC0/2 Callback Closure

Base: `bc82345173efec5049e4cfc6e399966ab82b08f5`.

## Result And Boundary

**Two original callback paths are newly closed:** SET API1 selector0 with 1536
entries, followed by selector2 with 1024 entries. Both execute original
`8400fe34 -> dd82`, with `d2d4` followed by `b6ba/b7e8`, through return, including every
initializer, fixed/dynamic/subregion lookup, bufid allocator and mutex helper.
No successful initializer/allocator/helper return is substituted.

The valid sequence verifies 2,560 RX descriptors, 2,560 software ID entries,
1,024 slow-queue records, 256 auxiliary records and 2,000 statistics bytes.
Twenty-one bounded negative controls and two strict rejection checks pass.
Each completed callback is compared against an independently constructed
786,432-byte SRAM/heap/L2 image and its exact byte-write footprint. Ready
publication must follow every other consumer RAM write.

**This is direct original callback closure, not strict-bootstrap admission.**
The inner helpers return 0, the callback forces return 1, and the respective
ready flags become 1. Direct invocation leaves mailbox flags at 1; it does not
produce a transport completion. Actual strict dispatch rejects both API1
requests with flags 3, no callback and no allocations. No policy change is made.

Of the original 13 pending cases in the parent host-sequence test, **11 remain**:
five DESC entry stops (selectors5/6/7/8/10), two API19 entry stops (selectors0/2),
and four API21 wait/post-wait fixtures (selectors10/12, each with zero/nonzero
TX-packet base). Separately, the parent's two API21 selectors5/7 cases still
substitute allocator returns; they are unchanged and not full native closure.
No existing pending result has been relabeled as a pass in the parent artifacts.

## Native Prerequisites

The test calls the existing `to_wifi`, `footprints` and `host_publish` functions
on a real `NativeWifi` instance using the already-built, SHA-pinned combined
ELF. Original core0 initialization runs before any RX callback. Its whole L2
initial footprint and all 16,384 entries of the native bufid free table are
checked. It retains the parent's synthetic host-register publication fixture,
then executes GET10 and the original SET14 callback with port2. The two RX
requests are the next two messages in the pinned host sequence. Their counts
are also checked against the parent's four HIF/port host profiles; this is one
native port2 sequence, not four new native host-profile runs.

Negative cases restore emulator memory and CPU snapshots taken after this
actual native initialization, or after its successful selector0 callback for
selector2. No initialized tables are injected in place of native initialization.
Each negative injection changes only the explicitly named emulator prerequisite.

Required initialized objects and scalar state are:

- Original DATA callback slot `SRAM+0x17c = 0x8400fe34`; native GP/stack state.
- Fixed lookup table `8401cf70`, subregion table `8401cf18` and dynamic sizes
  `8401cfc8`, all within the pinned original CODE bytes.
- Wi-Fi arena pointer `3e9030fc = 3e817000`, established by native allocation
  type1; its size is 303,168 bytes and its end is `3e861040`.
- Native dynamic allocator cache/cursors at `SRAM+1bd4/1bdc/1be0/1be4` with
  capacity for the 1,000-byte, 32-byte-aligned type10/type9 statistics objects.
- Bufid table pointer `3e901b88 = 3e800000`, containing IDs0..16383;
  cursor `3e901ba4` starts at 0 and advances to 1536, then 2560. The
  comparison cursor `3e901b80` is 0. Allocation stops when the next read cursor
  equals that comparison cursor, leaving one slot unavailable.
- Packet base `3e90396c = 8a000000` and the provider packet reservation ending
  at `8cc00000`. Descriptors reference 2,048-byte slots with a 128-byte data
  offset. Packet payload memory is never accessed or emulated by these callbacks.
- Native bufid statistics pointer `3e901f08 = 3e861040` and lock ID28 at
  `3e901b9c`, plus the existing dynamic allocator lock18 model.

The one newly admitted register triplet is direction-specific:

| Address | Native access | Explicit model |
|---|---|---|
| `1ec031f0` | Write `0x40` | Bufid lock28 acquire-request storage |
| `1ec03070` | Read seeded `0x10000` | Hart0 owner-readback storage |
| `1ec03270` | Write `0` | Bufid lock28 release-request storage |

These are register storage models, not mutex arbitration, concurrency, or
physical ownership witnesses. Each missing model fails closed at its first
access. Inherited named register models are unchanged. The callback phase
substitutes only printf output and hart-ID reads. The reused boot fixture also
retains its documented cache/timing/CSR substitutions; no physical cache or
clock behavior is claimed. JSON records the boot substitutions and all native
callback function entries and allocator returns.

## Exact Initialized Extents

All ends below are exclusive. Fixed table starts and native dynamic allocation
results are checked independently of the observed consumer-write stream.

| Object | Selector0 | Selector2 |
|---|---|---|
| RX descriptors, stride16 | `3e817000..3e81d000`, 1536 | `3e839020..3e83d020`, 1024 |
| Software IDs, stride2 | `3e90397c..3e90457c`, IDs0..1535 | `3e903100..3e903900`, IDs1536..2559 |
| Slow queue, 512 x 12 | `3e8a6040..3e8a7840` | `3e8a7858..3e8a9058` |
| Auxiliary, 128 x 12 | `3e8a9070..3e8a9670` | `3e8a9670..3e8a9c70` |
| Statistics, 1000 bytes | `3e8690e0..3e8694c8` | `3e8694e0..3e8698c8` |
| Referenced packet slots | `8a000000..8a300000` | `8a300000..8a500000` |
| Final ready flag | `3e902a84 = 1` | `3e904588 = 1` |

Every RX record is independently checked as four words:

```text
[((packet_base + bufid*2048) & 0x3fffffff | 0x80000000) + 128,
 0x07000100, bufid << 16, 0]
```

The native sequence first clears descriptor word1 and later publishes its
`0x07000100` value. Slow records contain `ffffffff` followed by eight zero
bytes. Auxiliary records define only their first nine bytes (`ffffffff`, zero
word, zero byte); the final three bytes of every 12-byte record must remain
unchanged. They are not falsely counted as a full 1,536-byte clear.

The full-image oracle also covers the allocator cache entry, aligned cursor,
pool success/failure statistics, saved descriptor/table pointers, reset
counters, software ID writes and ready flags. It rejects writes outside the
expected byte footprint even if the value equals the preexisting byte. Selector2 preserves
selector0's initialized contents apart from their shared allocator counters.

Valid callbacks produce 29,352 and 20,648 native writes respectively, including
stack and register storage. They access 28,360 and 19,146 reads. Repeated
accesses are aggregated by PC/direction/size/address space with lossless
address runs, repetition counts, value bounds, access-order bounds and hashes;
there is no repeated instruction log. The JSON is 318,165 bytes and the test
enforces a 400,000-byte bound. Control traces retain compact aggregates/digests
and exact rejected accesses rather than duplicating all successful traces.

## Negative Controls

These are conditional emulator-state counterexamples, not observed router
failures. Missing accesses are stopped by the harness, not by invented firmware
error handling. No helper is made to return success or failure by a hook.

| Cases | Mutation | Native outcome |
|---|---|---|
| 4 | Bufid comparison cursor permits 0 or 17 allocations, each selector | Actual allocator returns `ffffffff`; inner helper returns1; wrapper still returns1; ready stays0. Partial descriptors/IDs and consumed ownership remain. |
| 2 | Packet base becomes0 | Full callback returns1 and ready becomes1 with invalid low-address packet references; no payload access validates them. |
| 2 | Requested descriptor count0 | Diagnostic only; no bufids consumed; callback returns1 and ready becomes1. |
| 2 | Counts1539/1027 | Initialization completes across the next descriptor subregion boundary by16 bytes. Selector0 logs the nominal range diagnostic; selector2 logs none because its helper uses the same upper limit1536. |
| 2 | Wi-Fi arena pointer becomes0 | Fails closed at write `0x4` / `0x22024` after other initialization and initial ownership consumption. |
| 2 | Bufid table pointer becomes0 | Fails closed at read `0x0` / `0xc00`; allocation counters have already changed. |
| 2 | Dynamic heap cursor reaches `0x78000` | Native allocation returns sentinel, lookup converts it to0, and unchecked statistics clear faults at0. |
| 2 | Dynamic heap cursor becomes `0x77fe0` | Native allocation returns the last32 mapped bytes without checking its 1000-byte extent; clear stops at `3e878000`. |
| 3 | Omit each lock28 register model | First acquire write / owner read / release write fails closed; no callback completion. |

The capacity controls use the next starts in the original subregion table:
`3e81d020` and `3e83d040`. These establish adjacent named regions, not a newly
asserted production allocator length. Both nominal host requests remain below
those starts with 32-byte gaps. Oversized software-ID writes also exceed the
nominal 1536/1024-entry spans. In the selector2 control, the last extra halfword
reaches `3e903904`, the cached PCIe-base slot that a later host command would
publish. No live ring, hardware DMA, or exploitability claim follows.

## Replay And Provenance

From the canonical WSL repository, with no shared rebuild:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.local/npu-reset/python-lib:tests/npu \
  python3 tests/npu/test_attach_rx_callbacks.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.local/npu-reset/python-lib:tests/npu \
  python3 tests/npu/test_attach_rx_callbacks.py --check
```

The second command requires byte-identical fresh replay of the saved JSON.
The original CODE/DATA, Ghidra export, DTB and combined ELF are hash-pinned;
target function bytes are checked against original CODE. All loaded project
Python dependencies are hashed and checked unchanged across execution. No
ELF is copied or rebuilt, and no parent suite with build side effects is run.

| Artifact | SHA256 |
|---|---|
| Immutable combined ELF | `bdb64d12d738bdef85a747d0b638e6b148c1c534410fd893348fbaf5908e2931` |
| Original CODE | `e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643` |
| Original DATA | `61a75afb052feed2ceb2f3023e16f50317c05c78f9c8e564bf01924ce39c7ec1` |
| Ghidra export | `1536a9972838ca7c02da77629e784b392af919c5d25368478aff4d0c2422e2ca` |
| New test | `c7b04924b71e9a09fef3eeba3c1143381a5a1e67157f51b1e341a1910e37f100` |
| Evidence JSON | `4c125b631d5d98aa72c96a4785927780b63d55280941cde4a7cea255d8f67daf` |

The only deliverables are `tests/npu/test_attach_rx_callbacks.py` and this
directory's `RX_CALLBACKS.md` / `rx-callbacks.json`; the bounded exploratory
script remains in `.local/npu-attachrx/`. No existing test, firmware,
binding, source lock, config, overlay, build tree, staging or commit is changed.
The ledger is intentionally unchanged because the parent owns integration.
All-hart boot/reset and gate integration remain parent-owned. General mt76
admission, remaining callback consumers, packet capacity/lifetimes, production
placement/cache/containment, recovery and full parity remain open. There was
no router, physical MMIO, network, image, or flash action.
