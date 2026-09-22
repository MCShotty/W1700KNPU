# Full-Capacity Command Ring Placement

Date: 2026-09-09. Status: implemented and tested, **unpromoted**.

The selected core0/bridge sequence now fits without shrinking descriptor,
SKB or command-ring capacity. This is an allocator implementation and an
emulator placement profile, not a complete firmware image or NPU parity claim.

## Implementation

`firmware/npu/allocator.c/.h` supports optional immutable typed placements.
Each placement uses the original definition's complete extent, must be aligned
and non-wrapping, and must not overlap the primary heap or another placement.
Unknown/duplicate types, reserved fields, absent arrays and excessive counts
reject before acquisition. Under the allocation lock, cached records must
match the selected placement. Fixed records retain native count/attempt/cache
semantics but do not advance the primary heap cursor. Failures preserve state.

The native 824-byte metadata and eight-byte result ABI are unchanged. The
RV32 layout descriptor grows from 24 to 32 bytes. Backing, initialization,
immutable ownership and one non-aliasing address namespace remain caller
contracts; arithmetic checks do not prove physical address equivalence.

The alternate startup binding reserves the original type `0x19` extent of
32,784 bytes at `0x84060000..0x84068010`. It is a PROGBITS section, explicitly
loaded by the ELF fixture. Native initializer `0x8400baae` publishes the actual
checked allocation and writes 0xfe to all 2,048 sixteen-byte slots. The extra
sixteen bytes remain present and unused. Cached lookup does not reinitialize
the object. The default startup binding has no placements.

The profile also changes the bridge definition from 58,879 to 69,632 bytes
in emulator memory. This table change is not packaged into a raw firmware
image. Linker/ELF checks compare the new section against the selected sidecars,
native stack envelope and provider backup region. The retained W1700K FIT/DTB
and current provider source verify the 10 MiB binary reservation, 2 MiB code
limit and separate backup. These are source/artifact checks, not live mapping
or cache proof.

## Native Evidence

- Seven actual checked core0 allocations succeed. Primary use is 397,528
  bytes. Compared with the preceding cold layout, the complete heap changes
  only where the old command ring disappears; complete SRAM changes only in
  its pointer and allocator metadata. Fixed L2 contents remain identical.
- The larger bridge initializes at `0x3e8610e0`, leaving 24,352 heap bytes.
  All four selected VXLAN/SRv6 header stores remain inside that allocation.
  Complete heap/SRAM/L2/ring comparisons and exact header-write sets pass.
- Eight original native cached-getter calls preserve metadata and payloads,
  including the relocated ring. Subsequent compiled allocator requests for
  types 2, 9 and 10 on the captured state succeed and leave 16,152 heap bytes.
  This is a selected sequence, not an exhaustive allocation-profile budget.
- Native statistics initializer `0x8400a364(0)` allocates and publishes type 10
  before the ring-consumer probes. Its metadata matches the independent
  oracle and its 1,000-byte counter area is zeroed; the pointer is not seeded.
- Producer slice `0x8400c756..0x8400c5f6` and consumer slice
  `0x8400cb7e..0x8400cc72` execute with explicit caller registers. Both old
  and relocated addresses pass 2,048 alternating producer/consumer pairs.
  Complete ring contents agree; each case checks 14,336 ordered writes,
  whole heap/SRAM, wraparound, canaries and unused trailing bytes.
- Both placements also hold 2,048 simultaneously owned slots. A blocked
  producer does not overwrite the full queue. Native consumption frees one
  slot, the saved producer resumes, and all queued records drain in order.
  Each case covers 2,049 pairs and 14,344 ordered writes. The final empty
  consumer reads only the slot status, not payload.
- Total positive ring coverage is 8,194 pairs. Four instruction-removal
  mutants detect missing publication, slot return and each index wrap.
- All 37 prior detours installed before reset still park all eight harts
  with the larger bridge definition and relocated ring present. No bridge
  allocation or TXDONE ready publication occurs through those retained gates.

The pinned existing Ghidra export names three direct users of the ring global
at `0x3e901f3c`: initializer `0x8400baae`, producer `0x8400c284` and consumer
`0x8400cb0e`. This is not a complete pointer-alias closure proof. The producer
and consumer contain no publication fences. Serialized emulator memory cannot
establish cross-hart ordering or coherence after DRAM relocation.

## Allocator Regression

- 995 placement cases and all 1,367 legacy native/RV32 differential cases pass.
  Cases include overlap/wrap/alignment, full heap/cache, cached identity,
  under-lock mutation, denial and mixed allocation order. Sixteen allocator
  mutation controls fail at their expected assertions.
- Two ASan/UBSan pthread runs each complete 32,000 calls across eight threads.
  The heap-only control retains 100 records/3,200 heap bytes. The mixed run
  retains 50 fixed plus 50 heap records/1,600 heap bytes. Cached addresses,
  exhaustion and denial checks pass.
- The default startup regression passes seven allocations, eighteen failure
  cases, 52 control replies, 36 unaffected lookups, five bridge cases, the
  retained 31-detour control and eight startup mutation controls. Its ELF
  contains 1,978 text bytes plus 32 read-only data bytes within the reservation.

All three receipts replay byte-for-byte. The allocator, native-layout and
startup receipts bind 7, 85 and 75 current inputs respectively. Earlier
receipts remain historical: this checkpoint intentionally revises the shared
allocator and supporting tests and does not claim their old input hashes are
unchanged.

## Artifacts

| Artifact | SHA256 |
| --- | --- |
| `allocator-placement.json` | `0497ba37cb99ac79d4f1b6c8937b9c8be6f087cf52d29a68c30d5b470b374f20` |
| `command-ring-layout.json` | `d8a28d53537285a24fea97c23b537968e8c0b75d2d22185c961ae3da7da2d587` |
| `startup-regression.json` | `12dbf282e6578bf1288fbe90c764af7abe720df9d706a6f7274a7dfdba5925a0` |
| Ignored placement ELF | `2f2ec443f6eae840fd837f2147ffb47466d3d6132d7fb219c72e5c11742d0781` |

Reproduce from the canonical WSL checkout:

```sh
export PYTHONPATH=.local/npu-reset/python-lib:tests/npu
python3 tests/npu/test_allocator_placement.py --check
python3 tests/npu/test_command_ring_layout.py --check
python3 tests/npu/test_allocator_startup.py --check --output research/checkpoints/2026-09-09-npu-command-ring/startup-regression.json
```

## Remaining Work

- Close all ring-pointer aliases and prove the address/cache/PMA contract.
  Resolve producer publication, consumer acquisition and slot-return ordering;
  native instruction compatibility alone does not establish that contract.
- Validate backing and fresh initialization in a complete loader/image layout,
  including every code/state reservation and repeated-start lifetime. The new
  PROGBITS section is loaded only by the explicit ELF test fixture today.
- Close every allocation profile and consumer index/length bound, including
  all bridge header consumers and the initial/later SKB-count contract.
- Integrate remaining allocation callers, full callback/worker/IRQ paths,
  physical containment/drains, recovery and Linux lifecycle ownership. Full
  post-gate boot, host-adapter parity and real-client acceptance remain open.

No source-lock, overlay, package, raw firmware image, router, Wi-Fi, physical
test, subagent or protected-data change. No previously restricted operation
was retried or rerouted. The unpromoted source and tests plus all four trackers
and the NPU README are the changes. Scoped whitespace checks pass; the broad
worktree check still flags pre-existing patch-file context whitespace, which
was left untouched.
