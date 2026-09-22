/* Cold, independently contained reset only. Retain the control-word allocation
 * made by the native initializer instead of forgetting it after publication. */
    .option norvc
    .section .text.allocator_reset,"ax",@progbits

    .global npu_emulation_allocator_reset_prepare
    .type npu_emulation_allocator_reset_prepare, @function
npu_emulation_allocator_reset_prepare:
    li t0, 0x3e901bcc
#ifndef OMIT_RESET_COUNT
    sw zero, 8(t0)
#endif
#ifndef OMIT_RESET_CURSOR
    sw zero, 20(t0)
#endif
    j original_allocator_reset_prerequisite
    .size npu_emulation_allocator_reset_prepare, .-npu_emulation_allocator_reset_prepare
