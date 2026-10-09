    .option norvc
    .section .text.cold_page,"ax",@progbits

    .global npu_emulation_page_get_dispatch
npu_emulation_page_get_dispatch:
    li t0, 0x8400bca6
    beq ra, t0, npu_emulation_page_get
    /* Replay the displaced AUIPC for unrelated native getter callers. */
    li a3, 0x3e903b9c
    j original_page_get_bba0

    .macro ready name address continuation
    .global \name
\name:
    addi sp, sp, -16
    sw ra, 12(sp)
    call npu_emulation_page_ready
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
    j original_page_return_bd12
    .endm
    ready npu_emulation_page_ready5, 0x3e901f44, original_page_bd66
    ready npu_emulation_page_ready6, 0x3e903954, original_page_bd8a
    ready npu_emulation_page_ready7, 0x3e902ce8, original_page_bd4c
