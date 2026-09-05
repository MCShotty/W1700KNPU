/* Test-only detours: neither these addresses nor the reserved state are
 * approved for a firmware image. All four sites precede ownership work. */
    .option norvc
    .section .text.barrier_core5,"ax",@progbits

    .macro gate name, startup, continuation, outer=0
    .global \name
\name:
    addi sp, sp, -96
    sw ra, 0(sp)
    sw t0, 4(sp)
    sw t1, 8(sp)
    sw t2, 12(sp)
    sw a0, 16(sp)
    sw a1, 20(sp)
    sw a2, 24(sp)
    sw a3, 28(sp)
    sw a4, 32(sp)
    sw a5, 36(sp)
    sw a6, 40(sp)
    sw a7, 44(sp)
    sw t3, 48(sp)
    sw t4, 52(sp)
    sw t5, 56(sp)
    sw t6, 60(sp)
    csrrci t0, mstatus, 8
    sw t0, 64(sp)
1:
    la a0, npu_emulation_barrier_state
    li a1, 5
    addi a2, sp, 68
    call npu_barrier_poll
    li t0, 2
    beq a0, t0, 3f
    li t0, 1
    bne a0, t0, 1b
    .if !\startup
    /* The indirect consumer was cached in the original stack. Discard it
     * before READY; the ring base itself is reloaded by the vendor loop. */
    lhu t0, 0(s4)
    sh t0, 102(sp)
    .endif
    la a0, npu_emulation_barrier_state
    li a1, 5
    lw a2, 68(sp)
    call npu_barrier_refreshed
    j 1b
3:
    lw t0, 64(sp)
    csrw mstatus, t0
    lw ra, 0(sp)
    lw t0, 4(sp)
    lw t1, 8(sp)
    lw t2, 12(sp)
    lw a0, 16(sp)
    lw a1, 20(sp)
    lw a2, 24(sp)
    lw a3, 28(sp)
    lw a4, 32(sp)
    lw a5, 36(sp)
    lw a6, 40(sp)
    lw a7, 44(sp)
    lw t3, 48(sp)
    lw t4, 52(sp)
    lw t5, 56(sp)
    lw t6, 60(sp)
    addi sp, sp, 96
    .if \startup
    lw a5, 0(a4)
    bnez a5, 4f
    j original_cb3e
4:
    j original_cb42
    .else
    .if \outer
    lhu a5, 0(s4)
    j original_cbc2
    .else
    lhu a5, 6(sp)
    j \continuation
    .endif
    .endif
    .endm

    gate gate_core5_startup, 1, 0
    gate gate_core5_outer, 0, 0, 1
    gate gate_core5_empty_first, 0, original_cbce
    gate gate_core5_empty_repeat, 0, original_cc10
