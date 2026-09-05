/* Emulator-only worker adapters. IRQ, DMA drain and production placement
 * remain separate integration requirements; no deployable blob is emitted. */
    .option norvc
    .section .text.barrier_workers,"ax",@progbits
#ifndef OMIT_REFILL_SLOT
#define OMIT_REFILL_SLOT -1
#endif
#ifndef OMIT_FAST_SLOT
#define OMIT_FAST_SLOT -1
#endif

    .macro refill_slot global, frame_offset
    li t0, \global
    lw t0, 0(t0)
    addi t0, t0, 12
    sw t0, \frame_offset(sp)
    .endm

    /* kind: 0 = compressed load/branch pair, 1 = LBU, 2 = JAL.
     * cache: 0 = no persistent ownership cache, 1 = refill, 2 = fast RX. */
    .macro gate name, hart, cache, kind, reg, next, alternate=0
    .global \name
\name:
    addi sp, sp, -128
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
    sw s1, 80(sp)
    sw s2, 84(sp)
    sw s3, 88(sp)
    sw s4, 92(sp)
    csrrci t0, mstatus, 8
    sw t0, 64(sp)
1:
    li a0, 0x3e920000
    li a1, \hart
    addi a2, sp, 68
    call npu_barrier_poll
    li t0, 2
    beq a0, t0, 3f
    li t0, 1
    bne a0, t0, 1b
    .if \cache == 1
#ifndef OMIT_REFILL_REFRESH
    /* Replace four saved register pointers and the original stack pointer
     * cache. Startup gates must not access these uninitialized caches. */
#if OMIT_REFILL_SLOT != 0
    refill_slot 0x3e902cf0, 92
#endif
#if OMIT_REFILL_SLOT != 1
    refill_slot 0x3e903904, 88
#endif
#if OMIT_REFILL_SLOT != 2
    refill_slot 0x3e90395c, 84
#endif
#if OMIT_REFILL_SLOT != 3
    refill_slot 0x3e902a80, 80
#endif
#if OMIT_REFILL_SLOT != 4
    refill_slot 0x3e904630, 140
#endif
#endif
    .endif
    .if \cache == 2
#ifndef OMIT_FAST_REFRESH
#if OMIT_FAST_SLOT != 0
    li t0, 0x3e904700
    lw t0, 0(t0)
    lw t0, 12(t0)
    sh t0, 136(sp)
#endif
#if OMIT_FAST_SLOT != 1
    li t0, 0x3e9046fc
    lw t0, 0(t0)
    lw t0, 12(t0)
    sh t0, 138(sp)
#endif
#endif
    .endif
    li a0, 0x3e920000
    li a1, \hart
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
    lw s1, 80(sp)
    lw s2, 84(sp)
    lw s3, 88(sp)
    lw s4, 92(sp)
    addi sp, sp, 128
    .if \kind == 0
    lw a5, 0(\reg)
    beqz a5, 4f
    j \next
4:
    j \alternate
    .elseif \kind == 1
    lbu a5, 0(\reg)
    j \next
    .else
    /* Replay original JAL with its original return address. */
    lui ra, %hi(\next)
    addi ra, ra, %lo(\next)
    j \alternate
    .endif
    .endm

    gate gate_core1_startup, 1, 0, 0, a3, original_ce20, original_ce36
    gate gate_core1_outer, 1, 1, 0, s0, original_cf2a, original_cf14
    gate gate_core1_idle, 1, 1, 0, s0, original_cf2a, original_cf14
#ifdef OMIT_FAST_STARTUP
    gate gate_core2_startup, 2, 0, 0, a4, original_ec82, original_ec7e
#else
    /* Original entry already zeroed both cached indices before this gate. */
    gate gate_core2_startup, 2, 2, 0, a4, original_ec82, original_ec7e
#endif
    gate gate_core2_outer, 2, 2, 1, s2, original_ecc6
    gate gate_core2_idle, 2, 2, 1, s2, original_ecea
    gate gate_core3_startup, 3, 0, 0, a2, original_e444, original_e432
    gate gate_core3_outer, 3, 0, 1, a5, original_e4d8
    gate gate_core4_startup, 4, 0, 1, s0, original_d0ee
    gate gate_core4_outer, 4, 0, 1, s0, original_d148
    gate gate_core4_idle, 4, 0, 1, s0, original_d164
    gate gate_core6_startup, 6, 0, 0, s1, original_cd42, original_cd3e
    gate gate_core6_outer, 6, 0, 0, s1, original_cd8e, original_cda2
    gate gate_core6_retry, 6, 0, 0, s1, original_cd8e, original_cda2
    gate gate_core7_startup, 7, 0, 2, zero, original_b28, original_1472
    gate gate_core7_outer, 7, 0, 2, zero, original_b3a, original_13f6
