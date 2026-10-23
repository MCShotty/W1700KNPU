    .option norvc
    .option norelax
    .section .rro_veneers,"ax",@progbits
    .balign 4

    .global npu_emulation_rro_mailbox_veneer
    .type npu_emulation_rro_mailbox_veneer, @function
npu_emulation_rro_mailbox_veneer:
    jal zero, npu_emulation_rro_mailbox
    .size npu_emulation_rro_mailbox_veneer, .-npu_emulation_rro_mailbox_veneer

    .global npu_emulation_rro_cold_ready_veneer
    .type npu_emulation_rro_cold_ready_veneer, @function
npu_emulation_rro_cold_ready_veneer:
    jal zero, npu_emulation_rro_cold_ready
    .size npu_emulation_rro_cold_ready_veneer, .-npu_emulation_rro_cold_ready_veneer
