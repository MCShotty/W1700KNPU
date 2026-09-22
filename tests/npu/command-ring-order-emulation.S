/* Unpromoted native queue ordering. No cache maintenance or drain witness. */
.option norvc
.section .text

.globl npu_emulation_ring_publish
.globl npu_emulation_ring_producer_acquire
.globl npu_emulation_ring_store_token
.globl npu_emulation_ring_store_command
.globl npu_emulation_ring_producer_release
npu_emulation_ring_publish:
npu_emulation_ring_producer_acquire:
    fence iorw, iorw
npu_emulation_ring_store_token:
    sw s0, 4(a4)
npu_emulation_ring_store_command:
    sw a5, 8(a4)
npu_emulation_ring_producer_release:
    fence iorw, iorw
    j original_ring_after_payload

.globl npu_emulation_ring_consumer_acquire
npu_emulation_ring_consumer_acquire:
    fence iorw, iorw
    lhu a4, 6(sp)
    j original_ring_after_acquire

.globl npu_emulation_ring_consumer_release
.globl npu_emulation_ring_store_read_index
npu_emulation_ring_consumer_release:
    fence iorw, iorw
npu_emulation_ring_store_read_index:
    sh a4, -0x568(a0)
    j original_ring_before_slot_return
