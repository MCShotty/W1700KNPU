# Next Strict TX Buffer Contract

Continuation trace with six original RV32 lookup controls, not API21 admission
or a hardware acceptance claim.
Authority is the hash-pinned original decompilation/assembly:
`research/checkpoints/2026-09-05-npu-admission/ghidra-mailbox/en7581_MT7996_npu_rv32.bin.txt`,
SHA256 `1536a9972838ca7c02da77629e784b392af919c5d25368478aff4d0c2422e2ca`.
Current host source is Linux6.18.52 / mt76 `01367e60` in the source lock.

## Actual Caller Order

`mt7996_npu_txd_init()` gets selector5, publishes its descriptor base to the
first endpoint TX queue, then sends API21 selectors0,5,10 with three separately
allocated addresses. It gets selector7 and repeats API21 selectors2,7,12.
Current checked setup rejects the first API21 without a native callback. GET7
in the descriptor qualification follows manually, not through successful full
TX initialization. Future admission must preserve this interleaving rather than
requiring all eight GETs before the first API21.

## Original Effects

SET table begins at DATA0x178; API21 entry0x1cc points to0x8400fbca. The wrapper
calls the thunk0x8400f0c2 of helper0x8400ef36, then unconditionally returns1.
The helper logs an out-of-range address but continues. Unsupported selectors
also log and return without propagating rejection. Outer success is not proof
of a valid effect.

| Selector | Original Effect |
| --- | --- |
| 0 | Store `(address & 0x3fffffff) \| 0x40000000` at0x3e902cf8 |
| 2 | Store the same alias at0x3e902ab4 |
| 5 | Select arena type10, publish0x3e901f38, initialize512 internal128-byte records |
| 7 | Select arena type11, publish0x3e902abc, initialize1024 internal128-byte records |
| 10 | Publish the alias at0x3e903960, then call0x8400a5fa with0 |
| 12 | Publish the alias at0x3e902a88, then call0x8400a5fa with1 |

Selectors5/7 log the supplied address but do not use it as the initializer
destination. Their common loop sets the first word to0x100000, clears the
intermediate words and sets the last word to0x10000. Native type10/type11
subregions start at arena+0x8020 / arena+0x2a040, respectively. They are distinct
from GET5/7's16-byte TX descriptor rings.

Helper0x8400a5fa waits for0x3e902ab8 to become nonzero. That slot is set by
bootstrap API23 from the captured TXPKT region; nonzero alone is not an exact
plan/extent or physical readiness witness. Reject a missing/changed prerequisite
before entering the original unbounded delay loop.

Its calls to0x84005200 with0x100/0x101 take the static CODE table lookup path,
not the dynamic allocator at0x84004ff8. CODE offsets0x1cf70/0x1cf78 are eight-byte
entries for type0x100 ->0x3e8a2000 and type0x101 ->0x3e8a4020. These destinations
are outside the0x3e800000..0x3e878000 heap, in the modeled L2 region. No dynamic
lock18 call occurs on these two original lookup paths; a future binding must
still check all callback/replay lock interactions instead of assuming that a
typed function always allocates.

Six isolated original RV32 executions verify both table results without dynamic
allocation or memory writes. A missing table returns0; corrupted entries return
unaligned1/out-of-backing0xffffffff without rejection. Thus the original lookup
is not a pointer/extent admission check. Receipt: `tx-buffer-lookup.json` after
checkpoint sealing; runner: `tests/npu/test_tx_buffer_lookup.py`.

The helper publishes the lookup result and emits512 sixteen-byte records.
It writes32-bit words at offsets0/4/8 and a single zero byte at12; bytes13..15
remain unchanged. Host buffer addresses advance by256, with the0x80000000 alias.
Before that loop it clears two16-bit counters: selector10 at0x3e90462c/
0x3e90395a, selector12 at0x3e902a8c/0x3e90390c. It publishes the32-bit ring
pointer at0x3e902acc/0x3e9021e8. Retain and guard these width-specific metadata
preimages too; checking only the descriptor span would miss earlier mutations.
Guard exact table contents and full8192-byte destinations, retain arbitrary
record preimages, reserve before stores and check readback/publication. This is
a separate fixed-record ownership contract, not a blanket API21 whitelist or a
new dynamic allocator requirement. Physical L2 backing/exclusion remains open.

## Host Lifetime

`mt7996_npu_hw_init()` allocates six buffers with `dmam_alloc_coherent()` before
setup, stores only their DMA handles and lets managed cleanup own release.
Current `kernel/dma/mapping.c` documents release on detach; `dmam_release()`
calls `dma_free_attrs()`. Retention of the provider's own mailboxes does not
retain these endpoint allocations.

Before API21 exposure, bind a one-shot host buffer owner to the exact DMA device,
provider lifetime, boot/session and six address/extent records. Preserve CPU
pointers, DMA handles and allocation sizes for actual coherent free operations.
Validate full extents/widths/overlap before truncating to the32-bit wire. Latch
exposure before the first ambiguous publication; detach/error/parking cannot
free exposed buffers without an independent retirement witness. Integrate the
contract with the actual allocator/caller rather than merely registering an
unowned numeric address. Host endpoint descriptor publication is a distinct
exposure that also needs the physical cold-containment contract.

After that, finish remaining PCIe-address, event/INODE/TXDONE/final IRQ setup,
other owners/workers/hot/postgate and physical exclusion/backing/coherency/
drains/retirement/recovery, exact-image boot and actual clients. The full NPU
objective remains open; no hardware contact was performed for this trace.
