    .option norvc
    .section .text.cold_tx_buffer,"ax",@progbits
    .global npu_original_txbuf_callback
npu_original_txbuf_callback:
    lw a1, 0(a0)
    lw a0, 8(a0)
    j original_txbuf_fbce

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

    .macro one base, data, offset, width, failure
    save
    mv a1, \data
    addi a0, \base, \offset
    li a2, \width
    sw a0, 64(sp)
    sw a1, 68(sp)
    sw a2, 72(sp)
    call npu_emulation_txbuf_reserve
    beqz a0, \failure
    lw t0, 64(sp)
    lw t1, 68(sp)
    fence iorw, iorw
    .if \width == 1
    sb t1, 0(t0)
    .elseif \width == 2
    sh t1, 0(t0)
    .else
    sw t1, 0(t0)
    .endif
    fence iorw, iorw
    lw a0, 64(sp)
    lw a1, 72(sp)
    call npu_emulation_txbuf_publish
    beqz a0, \failure
    restore
    .endm

    .macro hook name, base, data, offset, width, continuation, failure
    .global npu_emulation_txbuf_\name
npu_emulation_txbuf_\name:
    one \base, \data, \offset, \width, \failure
    j \continuation
    .endm

    hook ef98, a5, s0, -0x50c, 4, original_txbuf_ef9c, .Lframed_failure
    hook efba, a5, s0, -0x2be, 4, original_txbuf_efbe, .Lframed_failure
    hook efd8, a5, s0, -0x520, 4, original_txbuf_efdc, .Lframed_failure
    hook f014, s0, a5, -0xd8, 4, original_txbuf_f018, .Lframed_failure
    hook f062, s0, a5, -0x5a2, 4, original_txbuf_f066, .Lframed_failure
    hook f092, a5, s0, -0x72e, 4, original_txbuf_f096, .Lframed_failure
    hook a630, a5, zero, 0, 2, original_txbuf_a634, .Lframed_failure
    hook a638, a5, zero, 0x326, 2, original_txbuf_a63c, .Lframed_failure
    hook a644, a5, a0, 0x48c, 4, original_txbuf_a648, .Lframed_failure
    hook a6a6, a5, zero, 0x3ea, 2, original_txbuf_a6aa, .Lframed_failure
    hook a6ae, a5, zero, 0x262, 2, original_txbuf_a6b2, .Lframed_failure
    hook a6c6, a5, a1, -0x4da, 4, original_txbuf_a6ca, .Lframed_failure

    .global npu_emulation_txbuf_eeb2
npu_emulation_txbuf_eeb2:
    one a0, a2, 0, 4, .Lleaf_failure
    one a0, zero, 4, 4, .Lleaf_failure
    j original_txbuf_eeb8

    hook eeb8, a0, zero, 8, 4, original_txbuf_eebc, .Lleaf_failure
    hook eebc, a0, zero, 0xc, 4, original_txbuf_eec0, .Lleaf_failure
    hook eec0, a0, zero, 0x10, 4, original_txbuf_eec4, .Lleaf_failure
    hook eec4, a0, zero, 0x14, 4, original_txbuf_eec8, .Lleaf_failure
    hook eec8, a0, zero, 0x18, 4, original_txbuf_eecc, .Lleaf_failure
    hook eecc, a0, zero, 0x1c, 4, original_txbuf_eed0, .Lleaf_failure
    hook eed0, a0, zero, 0x20, 4, original_txbuf_eed4, .Lleaf_failure
    hook eed4, a0, zero, 0x24, 4, original_txbuf_eed8, .Lleaf_failure
    hook eed8, a0, zero, 0x28, 4, original_txbuf_eedc, .Lleaf_failure
    hook eedc, a0, zero, 0x2c, 4, original_txbuf_eee0, .Lleaf_failure
    hook eee0, a0, zero, 0x30, 4, original_txbuf_eee4, .Lleaf_failure
    hook eee4, a0, zero, 0x34, 4, original_txbuf_eee8, .Lleaf_failure
    hook eee8, a0, zero, 0x38, 4, original_txbuf_eeec, .Lleaf_failure
    hook eeec, a0, zero, 0x3c, 4, original_txbuf_eef0, .Lleaf_failure
    hook eef0, a0, zero, 0x40, 4, original_txbuf_eef4, .Lleaf_failure
    hook eef4, a0, zero, 0x44, 4, original_txbuf_eef8, .Lleaf_failure
    hook eef8, a0, zero, 0x48, 4, original_txbuf_eefc, .Lleaf_failure
    hook eefc, a0, zero, 0x4c, 4, original_txbuf_ef00, .Lleaf_failure
    hook ef00, a0, zero, 0x50, 4, original_txbuf_ef04, .Lleaf_failure
    hook ef04, a0, zero, 0x54, 4, original_txbuf_ef08, .Lleaf_failure
    hook ef08, a0, zero, 0x58, 4, original_txbuf_ef0c, .Lleaf_failure
    hook ef0c, a0, zero, 0x5c, 4, original_txbuf_ef10, .Lleaf_failure
    hook ef10, a0, zero, 0x60, 4, original_txbuf_ef14, .Lleaf_failure
    hook ef14, a0, zero, 0x64, 4, original_txbuf_ef18, .Lleaf_failure
    hook ef18, a0, zero, 0x68, 4, original_txbuf_ef1c, .Lleaf_failure
    hook ef1c, a0, zero, 0x6c, 4, original_txbuf_ef20, .Lleaf_failure
    hook ef20, a0, zero, 0x70, 4, original_txbuf_ef24, .Lleaf_failure
    hook ef24, a0, zero, 0x74, 4, original_txbuf_ef28, .Lleaf_failure
    hook ef28, a0, zero, 0x78, 4, original_txbuf_ef2c, .Lleaf_failure
    .global npu_emulation_txbuf_ef2c
npu_emulation_txbuf_ef2c:
    one a0, a3, 0x7c, 4, .Lleaf_failure
    mv a0, a5
    j original_txbuf_ef30

    .global npu_emulation_txbuf_a672
npu_emulation_txbuf_a672:
    one a5, a3, 0, 4, .Lframed_failure
    one a5, zero, 4, 4, .Lframed_failure
    j original_txbuf_a678
    hook a678, a5, zero, 8, 4, original_txbuf_a67c, .Lframed_failure
    hook a67c, a5, zero, 0xc, 1, original_txbuf_a680, .Lframed_failure

.Lframed_failure:
    restore
    lw s1, 4(sp)
    lw s0, 8(sp)
    lw ra, 12(sp)
    addi sp, sp, 16
    li a0, 0
    ret
.Lleaf_failure:
    restore
    li a0, 0
    ret
