/* Original displaced instructions, with absolute targets supplied by linker. */
    .option norvc
    .section .text.admission_adapters,"ax",@progbits
    .global npu_original_irq_trampoline
npu_original_irq_trampoline:
    addi sp, sp, -16
    sw s0, 8(sp)
    j original_irq_30b6

    .global npu_coordinator_main_return
npu_coordinator_main_return:
    lw ra, 12(sp)
    li a0, 0
    addi sp, sp, 16
    j npu_emulation_idle
