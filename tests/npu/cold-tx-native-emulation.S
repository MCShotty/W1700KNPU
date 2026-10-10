    .option norvc
    .section .text.cold_tx,"ax",@progbits

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

    .global npu_original_tx_callback
npu_original_tx_callback:
    lw a1, 0(a0)
    lw a0, 8(a0)
    j original_tx_fc1a
    .global npu_original_token_callback
npu_original_token_callback:
    lw a1, 8(a0)
    addi sp, sp, -16
    j original_token_fdde

    /* Save the original field operands, guard/store/read back, then replay. */
    .macro field name, base, offset, value, bytes, kind, continuation
    .global \name
\name:
    save
    addi t0, \base, \offset
    sw t0, 64(sp)
    sw \value, 68(sp)
    li t0, \bytes
    sw t0, 72(sp)
    lw a0, 64(sp)
    lw a1, 68(sp)
    lw a2, 72(sp)
    call npu_emulation_tx_reserve
    beqz a0, .Lfailed\kind
    lw t0, 64(sp)
    lw t1, 68(sp)
    fence iorw, iorw
    .if \bytes == 2
    sh t1, 0(t0)
    .else
    sw t1, 0(t0)
    .endif
    fence iorw, iorw
    lw a0, 64(sp)
    lw a1, 72(sp)
    call npu_emulation_tx_publish
    beqz a0, .Lfailed\kind
    restore
    .ifc \name,npu_emulation_tx_reg0
    and a5, a5, a4
    .endif
    j \continuation
    .endm

    field npu_emulation_tx_meta0, a5, 204, s1, 4, meta, original_tx_d63c
    field npu_emulation_tx_meta2, a5, 148, s1, 4, meta, original_tx_d670
    field npu_emulation_tx_index0, a5, 1214, zero, 2, tx, original_tx_d4c2
    field npu_emulation_tx_index1, a5, -718, zero, 2, tx, original_tx_d4ca
    field npu_emulation_tx_reg0, a3, 48, a0, 4, tx, original_tx_d588
    field npu_emulation_tx_reg1, a3, 52, a5, 4, tx, original_tx_d534
    field npu_emulation_tx_reg2, a4, 48, s2, 4, tx, original_tx_d5bc
    field npu_emulation_tx_reg3, a4, 52, a5, 4, tx, original_tx_d534
    field npu_emulation_tx_token, gp, -2024, s0, 4, token, original_tx_dfd4

.Lfailedtx:
    restore
    lw s2, 0(sp)
    j .Lreturn_meta
.Lfailedmeta:
    restore
.Lreturn_meta:
    lw s1, 4(sp)
    lw s0, 8(sp)
    lw ra, 12(sp)
    addi sp, sp, 16
    ret
.Lfailedtoken:
    restore
    lw s0, 8(sp)
    lw ra, 12(sp)
    addi sp, sp, 16
    ret
