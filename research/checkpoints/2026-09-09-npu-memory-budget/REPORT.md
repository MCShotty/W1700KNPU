# Bridge Allocation And Header Extents

2026-09-09. Native teardown checkpoint. The bridge allocation mismatch is now
reproduced by executed consumers, not just inferred from its printed size.
No complete layout correction or full NPU initialization is claimed.

## Reconstructed Layout

The current MT7996 code, SHA256
`e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643`,
matches both the emulator input and the prepared linux-firmware-20260810 file.
The existing Ghidra mailbox export is hash-checked by the runner.

| Native Object | Evidence |
| --- | --- |
| Dynamic type `0x81` | Definition at `0x8401b22c`, size word `0x8401b230` is `0x0000e5ff`, or 58,879 bytes |
| Bridge initialization `0x84001472` | Allocates type `0x81`, publishes the base at `0x3e90184c` and bridge MMIO base/configuration |
| Header-base getter `0x84001466` | Returns bridge base plus `0x10000` |
| VXLAN store `0x84005c30` | Copies 50 bytes to header base plus index times 128 |
| SRv6 store `0x84005c82` | For index below 8, copies a supplied byte-sized length to header base plus `(index+20)*128`, then stores the length |
| Other inspected consumers | Fragment-header source at header offset `0xe00`; translation scratch at `0xe80`, including a 40-byte native copy |

Relevant Ghidra export lines are 2828/2845 for bridge base/init,
12274/12337 for the two store callbacks, 5268 for fragment-header use,
6237/6337 for translation scratch, and 34063 for the actual copy helper.
The receipt inventories 31 distinct direct calls to the allocation getter and
nine to the header getter in that export. This is not an indirect-call or
complete consumer-closure claim.

The mismatch exists before selecting a header index: the header area's base
is already 6,657 bytes beyond the bridge's declared end. Definition types
`0x84` and `0x85` happen to have size `0x11000`, but that does not establish
that either is the intended bridge type. The test's 68 KiB alternative is
explicitly a sizing hypothesis, not an inferred enum substitution.

## Native Results

`tests/npu/test_bridge_memory_budget.py` passes eight ordered primitive cases
and two core0-first startup cases. A full `--check` replay is byte-identical.

For the ordered primitive, actual allocator initialization and getters allocate
the control word, then actual bridge initialization allocates/publishes the
bridge. Actual `0x8400b928` then allocates/publishes the PCIe descriptor area.
This is a component allocation order, not a proved stock scheduling order.
The tests invoke native VXLAN indices 0/19 and SRv6 indices 0/7 with 128-byte
SRv6 payloads. Original getters and the native `0x840102da` copy execute.

- With the original 58,879-byte size, all four header copies land inside the
  later type-1 descriptor allocation. At index zero, the destination is
  `0x3e810020`, 6,656 bytes into that following allocation after alignment.
  The callback returns success, and the descriptor allocation's sentinel bytes
  change. The metadata still describes distinct non-overlapping allocations.
- With only the bridge size word changed to 69,632 in emulator memory, the
  same four native operations write inside the bridge allocation; the later
  descriptor allocation remains unchanged. This validates those selected
  footprints, not every possible callback index/length or the entire layout.
- Each primitive compares all 524,288 bytes of heap/local SRAM and its exact
  memory-write byte set. The source payload is synthetic. Allocation records,
  native getter/copy entries and write PCs are recorded independently.

The second pair uses actual core0 initialization with the preceding checked
startup/reset bindings, followed by native hart7 bridge initialization:

| Quantity | Observed Value |
| --- | --- |
| Seven core0 allocations | 430,320 used bytes |
| Aligned bridge base | `0x3e869100` |
| Declared heap end | `0x3e878000` |
| Original bridge allocation end | `0x3e8776ff` |
| First header destination | `0x3e879100`, 4,352 bytes beyond the heap |
| 68 KiB alternative end | `0x3e87a100`, 8,448 bytes beyond the heap |

With the original size, initialization accepts the bridge allocation. The
first native VXLAN header copy stops on an unmapped write at `0x84010318`
to `0x3e879100`. It is the emulator's heap boundary, not a native callback
guard. Existing heap bytes remain unchanged before that attempted write.

With the 68 KiB sizing hypothesis, the existing checked allocator rejects
before bridge publication. Allocation metadata and heap remain unchanged,
the prior bridge-base sentinel remains, and no bridge MMIO write occurs.
Simply correcting the bridge size does not make this startup budget fit.

## Remaining Layout Work

Shrinking a different table is not yet a valid correction. The native SKB
initializer `0x84004e76` allocates type `0x12` and explicitly fills 28,672
halfword entries, matching its 57,344-byte definition. The initial token count
at `0x3e900bc0` is also `0x7000`. Later SET33 changes the count through
`0x8400dfb0`; the current host requests 8,192. Allocation, initial fill, later
count changes and all consumers would need one consistent capacity contract.
Changing only the allocation-size table would leave the initializer wrong.

The current heap bound is the native 480 KiB allocation limit and agrees with
the retained reference DTS's explicit SRAM region. The adjacent address gap
has not been established as usable storage. Existing fixed-L2 definitions are
separate live objects, not automatically free capacity. No heap extension,
object relocation, reduced token limit or smaller descriptor profile is applied.

Next requirements are complete consumer/index/length bounds, a consistent
allocation/initialization/host-count contract, a fitting full startup profile,
then integrated callback/worker and lifetime validation. The test does not
claim physical mapping, timer frequency, transport admission or full parity.

## Reproduction And Scope

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_bridge_memory_budget.py
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_bridge_memory_budget.py --check
```

The primitive uses explicit register storage, a zero clock-divider input and
a decreasing synthetic timer. The divider helper itself executes natively.
Diagnostic printing and hart-ID responses use the existing fixture boundary;
allocator, bridge initialization, header getter and copies execute natively.
Core0-first tests retain the existing startup MMIO/timer/lock models.

Ghidra MCP reported no running instance. A read-only cross-reference export
helper and pattern were added, but the local signing policy prevented the
PowerShell helper from executing. It was not retried through another route.
No new Ghidra export is claimed; this checkpoint uses the verified existing
export and original instruction tests.

The receipt binds 83 inputs before/after and replays byte-for-byte:
`b544f127edbb9a59da79f892b4091104a888bcc9b588c707bd0f682d8b1ca759`.
Runner SHA256:
`8e24b6a47aa3923b4da556c510fbae06501d99c109e55c9813772417c2bca799`.

All changes are tests, evidence and tracking documentation. No packaged
firmware, source-lock, overlay, router, Wi-Fi or protected-backup change.
All four trackers and the NPU README are updated. Full NPU implementation
remains in progress.
