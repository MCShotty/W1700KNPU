/* Unpromoted egress guards. A fault retains ownership; it is not a DMA drain. */
.option norvc
.section .text

.globl npu_emulation_egress_channel
npu_emulation_egress_channel:
    li t1, 8
#ifndef OMIT_EGRESS_CHANNEL
    bgeu a0, t1, .Lchannel_fault
#endif
    lui t1, 0x1ec12
    j original_egress_channel_loaded
.Lchannel_fault:
    li t1, 1
    j npu_emulation_egress_fault

.globl npu_emulation_egress_slots
npu_emulation_egress_slots:
#ifndef OMIT_EGRESS_SLOTS
    beqz t3, .Lslots_fault
#endif
    j original_egress_submit
.Lslots_fault:
    li t1, 2
    j npu_emulation_egress_fault

.globl npu_emulation_egress_extent
npu_emulation_egress_extent:
    srli t1, a2, 16
#ifndef OMIT_EGRESS_LENGTH
    bnez t1, .Lextent_fault
#endif
    srli t1, a3, 16
#ifndef OMIT_EGRESS_OFFSET
    bnez t1, .Lextent_fault
#endif
    /* Match the native 29-bit alias, without treating it as backing proof. */
    slli t3, a1, 3
    srli t3, t3, 3
    add t3, t3, a3
    add t3, t3, a2
    li t4, 0x20000000
#ifndef OMIT_EGRESS_APERTURE
    bltu t4, t3, .Lextent_fault
#endif
    addi sp, sp, -16
    slli a3, a3, 16
    j original_egress_extent_prologue
.Lextent_fault:
    li t1, 3

.globl npu_emulation_egress_fault
npu_emulation_egress_fault:
#ifndef OMIT_EGRESS_IRQ_MASK
    csrrci t4, mstatus, 8
#else
    csrr t4, mstatus
#endif
    /* Stable, nonreturning frame: a0..a7, caller, reason, mstatus, reserved. */
    addi sp, sp, -48
    sw a0, 0(sp)
    sw a1, 4(sp)
    sw a2, 8(sp)
    sw a3, 12(sp)
    sw a4, 16(sp)
    sw a5, 20(sp)
    sw a6, 24(sp)
    sw a7, 28(sp)
    sw ra, 32(sp)
    sw t1, 36(sp)
    sw t4, 40(sp)
    sw zero, 44(sp)
#ifndef OMIT_EGRESS_FENCE
    fence iorw, iorw
#endif
    la a0, npu_emulation_barrier_state
#ifndef OMIT_EGRESS_FAULT
    call npu_barrier_fail
#endif
.globl npu_emulation_egress_hold
npu_emulation_egress_hold:
    nop
    j npu_emulation_egress_hold
