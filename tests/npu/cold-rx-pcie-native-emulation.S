    .option norvc
    .section .text.cold_rx_pcie,"ax",@progbits
    .global npu_original_rx_pcie_callback
npu_original_rx_pcie_callback:
    lw a1, 0(a0)
    lw a0, 8(a0)
    j original_rx_pcie_fdc8

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

    .global npu_emulation_rx_pcie_ba88
npu_emulation_rx_pcie_ba88:
    save
    addi a0, a5, 12
    mv a1, s1
    li a2, 4
    sw a0, 64(sp)
    sw a1, 68(sp)
    call npu_emulation_rx_pcie_reserve
    beqz a0, .Lfailure
    lw a5, 52(sp)
    fence iorw, iorw
    .global npu_emulation_rx_pcie_ba88_store
npu_emulation_rx_pcie_ba88_store:
    sw s1, 12(a5)
    fence iorw, iorw
    lw a0, 64(sp)
    li a1, 4
    call npu_emulation_rx_pcie_publish
    beqz a0, .Lfailure
    restore
    j original_rx_pcie_ba8c
.Lfailure:
    restore
    /* The original helper already restored ra/s0 before this store. */
    lw s1, 4(sp)
    addi sp, sp, 16
    li a0, 0
    ret
