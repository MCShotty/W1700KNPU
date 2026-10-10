    .option norvc
    .section .text.cold_indication,"ax",@progbits

    .macro save
    addi sp, sp, -80
    sw ra, 0(sp)
    sw t0, 4(sp)
    sw t1, 8(sp)
    sw t2, 12(sp)
    sw t3, 16(sp)
    sw t4, 20(sp)
    sw t5, 24(sp)
    sw t6, 28(sp)
    sw a0, 32(sp)
    sw a1, 36(sp)
    sw a2, 40(sp)
    sw a3, 44(sp)
    sw a4, 48(sp)
    sw a5, 52(sp)
    sw a6, 56(sp)
    sw a7, 60(sp)
    .endm

    .macro restore
    lw ra, 0(sp)
    lw t0, 4(sp)
    lw t1, 8(sp)
    lw t2, 12(sp)
    lw t3, 16(sp)
    lw t4, 20(sp)
    lw t5, 24(sp)
    lw t6, 28(sp)
    lw a0, 32(sp)
    lw a1, 36(sp)
    lw a2, 40(sp)
    lw a3, 44(sp)
    lw a4, 48(sp)
    lw a5, 52(sp)
    lw a6, 56(sp)
    lw a7, 60(sp)
    addi sp, sp, 80
    .endm

    .global npu_emulation_indication_read
npu_emulation_indication_read:
    save
    lw a0, 52(sp)
    call npu_emulation_indication_reserve
    beqz a0, .Lfailed
    restore
    /* Replay the displaced load and index increment only after reservation. */
    lw a3, 4(a5)
    addi a4, a4, 1
    j original_indication_bb14

    .global npu_emulation_indication_store
npu_emulation_indication_store:
    save
    lw a0, 52(sp)
    lw a1, 44(sp)
    call npu_emulation_indication_pending
    beqz a0, .Lfailed
    lw t0, 44(sp)
    lw t1, 52(sp)
    fence iorw, iorw
    sw t0, 4(t1)
    fence iorw, iorw
    lw a0, 52(sp)
    call npu_emulation_indication_publish
    beqz a0, .Lfailed
    restore
    mv a5, a4
    j original_indication_bb1e
.Lfailed:
    restore
    /* Return failure through the original initializer's saved frame. */
    lw ra, 12(sp)
    lw s0, 8(sp)
    addi sp, sp, 16
    li a0, 1
    ret
