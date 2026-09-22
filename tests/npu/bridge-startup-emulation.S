/* Unpromoted hart-7 guards. No physical containment or buffer-extent proof. */
    .option norvc
    .section .text.bridge_startup,"ax",@progbits

    .macro fault_park name
#ifndef OMIT_BRIDGE_IRQ_MASK
    csrrci zero, mstatus, 8
#endif
#ifndef OMIT_BRIDGE_IO_FENCE
    /* Order issued I/O before the fault; this is not a hardware drain. */
    fence iorw, iorw
#endif
    la a0, npu_emulation_barrier_state
#ifndef OMIT_BRIDGE_FAULT_PUBLICATION
    call npu_barrier_fail
#endif
    .global \name
\name:
    nop
    j \name
    .endm

    .global npu_emulation_bridge_base_guard
    .type npu_emulation_bridge_base_guard, @function
npu_emulation_bridge_base_guard:
#ifndef OMIT_BRIDGE_BASE_CHECK
    beqz a0, 1f
#endif
    mv a5, a0
    mv a1, a0
    j original_bridge_148e
1:
    fault_park npu_emulation_bridge_base_fault_park
    .size npu_emulation_bridge_base_guard, .-npu_emulation_bridge_base_guard

    .global npu_emulation_bridge_channel_guard
    .type npu_emulation_bridge_channel_guard, @function
npu_emulation_bridge_channel_guard:
#ifndef OMIT_BRIDGE_CHANNEL_CHECK
    beqz a5, 2f
#endif
    /* Replay the successful branch; failed channels skip the native write-one. */
    j original_bridge_1504
2:
    fault_park npu_emulation_bridge_channel_fault_park
    .size npu_emulation_bridge_channel_guard, .-npu_emulation_bridge_channel_guard
