/* Only reviewed cold-start call sites enter the checked binding. */
    .option norvc
    .section .text.allocator_startup,"ax",@progbits
    .global npu_emulation_allocator_startup_dispatch
    .type npu_emulation_allocator_startup_dispatch, @function
npu_emulation_allocator_startup_dispatch:
    .macro caller address
    li a4, \address
    beq ra, a4, .Lchecked
    .endm
    caller 0x84005a34
    caller 0x84004eca
    caller 0x84004eee
    caller 0x84004f2c
    caller 0x8400b932
    caller 0x8400a376
    caller 0x8400bab8
    caller 0x8400148a
    /* Replay the displaced first instruction for all unrelated native users. */
    li a4, 0x80
    j original_allocator_getter_5204
.Lchecked:
    mv a1, ra
    j npu_emulation_startup_allocate
    .size npu_emulation_allocator_startup_dispatch, .-npu_emulation_allocator_startup_dispatch
