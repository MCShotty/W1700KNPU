    .option norvc
    .section .text.cold_descriptor,"ax",@progbits
    .global npu_original_descriptor_callback
npu_original_descriptor_callback:
    addi sp, sp, -16
    sw s0, 8(sp)
    j original_descriptor_10168

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

    .macro status name, continuation
    .global \name
\name:
    save
    addi a0, a5, 4
    sw a0, 64(sp)
    mv a1, a3
    sw a3, 68(sp)
    call npu_emulation_descriptor_reserve
    beqz a0, .Lfailed
    lw t0, 64(sp)
    lw t1, 68(sp)
    fence iorw, iorw
    sw t1, 0(t0)
    fence iorw, iorw
    lw a0, 64(sp)
    call npu_emulation_descriptor_publish
    beqz a0, .Lfailed
    restore
    addi a5, a5, 16
    j \continuation
    .endm

    status npu_emulation_descriptor_status0, original_descriptor_d8d0
    status npu_emulation_descriptor_status2, original_descriptor_d900
.Lfailed:
    restore
    lw s1, 4(sp)
    lw s0, 8(sp)
    lw ra, 12(sp)
    addi sp, sp, 16
    li a0, 0
    ret
