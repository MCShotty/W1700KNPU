# Next RX-Event And Activation Contract

The actual MT7996 initializer calls offload, RX descriptors, TX descriptors,
RX-event, PCIe addresses, TXDONE/INODE and final IRQ enables in that order.
This checkpoint covers the replay through TX descriptors only. Authoritative
prepared source: mt76-merged/mt7996/npu.c functions mt7996_npu_rx_event_init,
mt7996_npu_set_pcie_addr, mt7996_npu_tx_done_init and __mt7996_npu_hw_init.

## RX Event

For MT7996, use q_rx[MT_RXQ_TXFREE_BAND0]: selector0/API22 with actual desc_dma,
then selector10/API1 with MT7996_RX_MCU_RING_SIZE512, then selector10/API0 with
BAR plus the queue ring base plus0x90.

test_api22_original.py executes64 stock vectors against CODE SHAe743d1b5.
Wrapper8400fbb4/helper8400b5c6 accept selectors0/5/6/7, each writing one32-bit
metadata word at DATA offsets3964/2a94/2aa4/4638. Zero/unaligned/high values
are accepted and match (value & 0x3fffffff) | 0x40000000. Unsupported selectors
return1 without stores. Other DATA/CODE remain unchanged; no allocator/lock.
These are validation counterexamples, not candidate admission or DMA proof.

Before pointer exposure, retain the real queue's CPU/DMA/extent and device/
session identity across failure/detach. Derive extent from actual descriptor
type/count. Validate alignment, aliases/overlap, mailbox/protected separation
and exact enrollment. Wire API22 after complete TX-buffer setup; own metadata
reservation/readback with unchanged held/prior-owner context.

DESC10 must use the shared retained PKT owner and original TXDONE/SKB paths,
not a fabricated lease or direct init. Historical direct512-claim TXDONE does
not prove authenticated current transport or host lifetime. Cover complete
allocation/error/unwind, count/bitmap/record/publication and partial faults.

## Later Setup

PCIe selectors0/2 use RX ring register windows; selector2 has an HIF2 offset.
Selector15/value0 initializes indexes through earlier stored queue pointers.
Own every affected host register span and dependency, not just a nonzero BAR.
Check complete original bodies and exact resulting writes.

INODE selectors2/7 follow. Its original wrapper reads24 bytes even for short
commands; effects include worker flags and memory clears. Preserve existing
framing correction. Activation needs reviewed held/live lifecycle transitions
and complete owner/IRQ/worker prerequisites. SET success never grants drain,
retirement, reset or engine-start permission on its own.

Physical prior-user exclusion, exclusive backing/cache/DMA visibility, actual
drains/retirement/removal/rearm/recovery, exact-image boot and clients remain
independent requirements. This document grants no hardware authorization.
