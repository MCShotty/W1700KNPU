    .option norvc
    .section .text.txdone_init,"ax",@progbits

    .global npu_original_desc_callback
npu_original_desc_callback:
    lw a1, 0(a0)
    lw a0, 8(a0)
    j original_desc_fe38

    .global npu_emulation_txdone_bufid_guard
npu_emulation_txdone_bufid_guard:
    lw t0, 12(sp)
    li t2, 0x8400b4e4
    bne t0, t2, .Lbufid_native
    bnez a0, .Lbufid_failed
    call npu_emulation_txdone_bufid_valid
    bnez a0, .Lbufid_native
    li a0, 0x3e901b9c
    call original_lock_release
.Lbufid_failed:
    lw ra, 12(sp)
    lw s0, 8(sp)
    addi sp, sp, 16
    li a0, -1
    ret
.Lbufid_native:
    li a3, 0x3e901d92
    j original_bufid_4d96

    .macro skb_return
    lw ra, 28(sp)
    lw s0, 24(sp)
    lw s1, 20(sp)
    lw s2, 16(sp)
    lw s3, 12(sp)
    lw s4, 8(sp)
    addi sp, sp, 32
    ret
    .endm

    .global npu_emulation_txdone_lock19_guard
npu_emulation_txdone_lock19_guard:
    lw t0, 28(sp)
    li t2, 0x8400b546
    bne t0, t2, .Llock19_native
    li a0, 0x3e901bb8
    call original_lock_acquire
    beqz a0, .Llock19_owned
    call npu_emulation_txdone_fail
    skb_return
.Llock19_owned:
    j original_skb_4a2e
.Llock19_native:
    sw a3, 0(a4)
    or a5, a5, s0
    j original_skb_4a2c

    .global npu_emulation_txdone_lock20_guard
npu_emulation_txdone_lock20_guard:
    lw t0, 28(sp)
    li t2, 0x8400b546
    bne t0, t2, .Llock20_native
    bnez a0, .Llock20_failed
    call npu_emulation_txdone_skb_valid
    bnez a0, .Llock20_native
    li a0, 0x3e901bc4
    call original_lock_release
.Llock20_failed:
    li a0, 0x3e901bb8
    call original_lock_release
    call npu_emulation_txdone_fail
    skb_return
.Llock20_native:
    li a1, 0x8401aa3a
    j original_skb_4a3e

    .global npu_emulation_txdone_temp_guard
npu_emulation_txdone_temp_guard:
    lw t0, 28(sp)
    li t2, 0x8400b546
    bne t0, t2, .Ltemp_native
    blt a0, s4, .Ltemp_native
    j original_skb_4b1a
.Ltemp_native:
    .global npu_emulation_txdone_temp_load
npu_emulation_txdone_temp_load:
    lh a5, 0(t3)
    j original_skb_4b0c

    .global npu_emulation_txdone_publish_guard
npu_emulation_txdone_publish_guard:
    fence iorw, iorw
    la t0, npu_emulation_barrier_state
    lw t0, 16(t0)
    bnez t0, .Ltxdone_return
    li a5, 0x3e903546
    j original_txdone_b54a
.Ltxdone_return:
    lw ra, 44(sp)
    lw s0, 40(sp)
    lw s1, 36(sp)
    lw s2, 32(sp)
    lw s3, 28(sp)
    lw s4, 24(sp)
    lw s5, 20(sp)
    lw s6, 16(sp)
    lw s7, 12(sp)
    lw s8, 8(sp)
    addi sp, sp, 48
    ret
