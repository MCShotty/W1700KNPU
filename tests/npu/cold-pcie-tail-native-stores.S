    .option norvc
    .section .text.pcie_tail_stores,"ax",@progbits

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

    .macro restore_regs
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
    .endm

    /* Unwind modes:0=full original frame,1=s0 restored,2=ra/s0 restored,
       3=all saved registers restored. The16-byte frame is still allocated. */
    .macro tail_store name, site, base, offset, value, unwind, continuation
    .global npu_emulation_pcie_tail_\name
npu_emulation_pcie_tail_\name:
    save
    addi a0, \base, \offset
    mv a1, \value
    li a2, 4
    sw a0, 64(sp)
    sw a1, 68(sp)
    call npu_emulation_pcie_tail_reserve
    beqz a0, .Lfailure\@
    restore_regs
    fence iorw, iorw
    .global npu_emulation_pcie_tail_\name\()_store
npu_emulation_pcie_tail_\name\()_store:
    .option push
    .option rvc
    sw \value, \offset(\base)
    .option pop
    fence iorw, iorw
    lw a0, 64(sp)
    li a1, 4
    call npu_emulation_pcie_tail_publish
    beqz a0, .Lfailure\@
    restore_regs
    addi sp, sp, 80
    /* Relocate the complete instruction displaced after compressed stores. */
    .if \site == 0xb9ae
    li a5, 0x3e9029b0
    .elseif \site == 0xb9c0
    li a5, 0x3e9049c2
    .elseif \site == 0xb9d2
    li a5, 0x3e9029d4
    .elseif \site == 0xb9ea
    li a5, 0x3e9029ec
    .elseif \site == 0xba00
    addi sp, sp, 16
    .elseif \site == 0xba18 || \site == 0xba30
    lw s1, 4(sp)
    .endif
    j \continuation
.Lfailure\@:
    restore_regs
    addi sp, sp, 80
    .if \unwind == 0
    lw ra, 12(sp)
    lw s0, 8(sp)
    lw s1, 4(sp)
    .elseif \unwind == 1
    lw ra, 12(sp)
    lw s1, 4(sp)
    .elseif \unwind == 2
    lw s1, 4(sp)
    .endif
    addi sp, sp, 16
    li a0, 0
    ret
    .endm

    tail_store b9ae, 0xb9ae, a5, 8, a4, 1, original_pcie_tail_b9b4
    tail_store b9c0, 0xb9c0, a5, 8, a4, 2, original_pcie_tail_b9c6
    tail_store b9d2, 0xb9d2, a5, 8, a4, 3, original_pcie_tail_b9d8
    tail_store b9ea, 0xb9ea, a5, 8, a4, 3, original_pcie_tail_b9f0
    tail_store ba00, 0xba00, a4, 8, a5, 3, original_pcie_tail_ba04
    tail_store ba0c, 0xba0c, a5, 744, s1, 0, original_pcie_tail_ba10
    tail_store ba18, 0xba18, s1, 8, a5, 2, original_pcie_tail_ba1c
    tail_store ba24, 0xba24, a5, -284, s1, 0, original_pcie_tail_ba28
    tail_store ba30, 0xba30, s1, 8, a5, 2, original_pcie_tail_ba34
