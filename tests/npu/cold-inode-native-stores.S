    .option norvc
    .section .text.inode_stores,"ax",@progbits

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

    /* restored=1 only after the original ra/s0 loads; its16-byte frame remains. */
    .macro inode_store name, base, offset, value, bytes, opcode, restored, continuation
    .global npu_emulation_inode_\name
npu_emulation_inode_\name:
    save
    addi a0, \base, \offset
    mv a1, \value
    li a2, \bytes
    sw a0, 64(sp)
    call npu_emulation_inode_reserve
    beqz a0, .Lfailure\@
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
    fence iorw, iorw
    .global npu_emulation_inode_\name\()_store
npu_emulation_inode_\name\()_store:
    .4byte \opcode
    fence iorw, iorw
    lw a0, 64(sp)
    li a1, \bytes
    call npu_emulation_inode_publish
    beqz a0, .Lfailure\@
    restore
    j \continuation
.Lfailure\@:
    restore
    .if !\restored
    lw ra, 12(sp)
    lw s0, 8(sp)
    .endif
    addi sp, sp, 16
    li a0, 0
    ret
    .endm

    inode_store e0c4, a5, 1589, zero, 1, 0x62078aa3, 0, original_inode_e0c8
    inode_store e0ce, a4, 1574, a5, 4, 0x62f72323, 0, original_inode_e0d2
    inode_store e0d8, a3, 1573, a4, 1, 0x62e682a3, 0, original_inode_e0dc
    inode_store e0e0, a3, 1564, a4, 1, 0x60e68e23, 0, original_inode_e0e4
    inode_store e0e8, a4, 1533, a5, 1, 0x5ef70ea3, 0, original_inode_e0ec
    inode_store e0f0, a4, 1524, a5, 1, 0x5ef70a23, 0, original_inode_e0f4
    inode_store e178, a4, 1400, a5, 4, 0x56f72c23, 0, original_inode_e17c
    inode_store e180, a4, 1396, a5, 4, 0x56f72a23, 0, original_inode_e184
    inode_store e18a, a4, 1394, a5, 1, 0x56f70923, 0, original_inode_e18e
    inode_store e196, a5, 0, zero, 4, 0x0007a023, 0, original_inode_e19a
    inode_store e1b4, a5, 1351, zero, 1, 0x540783a3, 1, original_inode_e1b8
