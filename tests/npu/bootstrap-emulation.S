/* Replace the source-8 argument before native registration unmasks it. */
    .option norvc
    .section .text.bootstrap_adapter,"ax",@progbits
    .global npu_emulation_mailbox_register
    .type npu_emulation_mailbox_register, @function
npu_emulation_mailbox_register:
    li ra, 8
    bne a0, ra, 1f
    la a1, npu_emulation_mailbox
1:
    li ra, 0x84003f32
    j original_mailbox_register
    .size npu_emulation_mailbox_register, .-npu_emulation_mailbox_register
