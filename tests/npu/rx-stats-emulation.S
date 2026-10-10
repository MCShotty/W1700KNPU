    .option norvc
    .section .text.rx_stats,"ax",@progbits

    .macro statistics name type pointer continuation
    .global \name
\name:
    addi sp, sp, -16
    sw ra, 12(sp)
    sw a0, 8(sp)
    li a1, \type
    call npu_emulation_rx_stats_valid
    mv t0, a0
    lw a0, 8(sp)
    lw ra, 12(sp)
    addi sp, sp, 16
    beqz t0, .Lstats_fail\@
    li a5, \pointer
    j \continuation
.Lstats_fail\@:
    lw ra, 12(sp)
    addi sp, sp, 16
    li a0, 0
    ret
    .endm
    statistics npu_emulation_rx_stats0, 10, 0x3e9023ae, original_stats_a3b2
    statistics npu_emulation_rx_stats2, 9, 0x3e90239a, original_stats_a39e

    .macro dispatch name selector continuation
    .global \name
\name:
    addi sp, sp, -16
    sw ra, 12(sp)
    li a0, \selector
    call npu_emulation_rx_dispatch_live
    mv t0, a0
    lw ra, 12(sp)
    addi sp, sp, 16
    beqz t0, .Ldispatch_fail\@
    mv a0, s0
    lw s0, 8(sp)
    j \continuation
.Ldispatch_fail\@:
    lw s0, 8(sp)
    lw ra, 12(sp)
    lw s1, 4(sp)
    addi sp, sp, 16
    li a0, 1
    ret
    .endm
    dispatch npu_emulation_rx_dispatch0, 0, original_dispatch_ddc4
    dispatch npu_emulation_rx_dispatch2, 2, original_dispatch_ddda

    .macro ready name selector address continuation return_site
    .global \name
\name:
    addi sp, sp, -16
    sw ra, 12(sp)
    li a0, \selector
    call npu_emulation_rx_dispatch_live
    lw ra, 12(sp)
    addi sp, sp, 16
    beqz a0, .Lready_fail\@
    fence iorw, iorw
    li a4, \address
    li a5, 1
    sw a5, 0(a4)
    j \continuation
.Lready_fail\@:
    li a0, 1
    j \return_site
    .endm
    ready npu_emulation_rx_ready0, 0, 0x3e902a84, original_rx_b7cc, original_rx_b7ce
    ready npu_emulation_rx_ready2, 2, 0x3e904588, original_rx_b8fa, original_rx_b8fc
