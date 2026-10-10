    .option norvc
    .section .text.cold_packet,"ax",@progbits

    .global npu_emulation_packet_entry
npu_emulation_packet_entry:
    li t0, 0x8400b76a
    beq ra, t0, .Lentry_rx
    li t0, 0x8400b898
    beq ra, t0, .Lentry_rx
    /* Replay the two displaced instructions for unrelated native users. */
    addi sp, sp, -16
    li a0, 0x3e901d82
    j original_packet_4d86
.Lentry_rx:
    addi sp, sp, -16
    sw ra, 12(sp)
    call npu_emulation_packet_begin
    lw ra, 12(sp)
    addi sp, sp, 16
    beqz a0, .Lentry_failed
    addi sp, sp, -16
    la a0, npu_emulation_packet_lock_id
    j original_packet_4d8a
.Lentry_failed:
    li a0, -1
    ret

    .global npu_emulation_packet_guard
npu_emulation_packet_guard:
    lw t0, 12(sp)
    li t1, 0x8400b76a
    beq t0, t1, .Lrx
    li t1, 0x8400b898
    bne t0, t1, npu_previous_txdone_bufid_guard
.Lrx:
    addi sp, sp, -16
    sw ra, 12(sp)
    call npu_emulation_packet_take
    lw ra, 12(sp)
    addi sp, sp, 16
    lw ra, 12(sp)
    lw s0, 8(sp)
    addi sp, sp, 16
    ret

    .macro ready name selector address continuation return_site
    .global \name
\name:
    addi sp, sp, -16
    sw ra, 12(sp)
    li a0, \selector
    call npu_emulation_packet_ready
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
    ready npu_emulation_packet_ready0, 0, 0x3e902a84, original_rx_b7cc, original_rx_b7ce
    ready npu_emulation_packet_ready2, 2, 0x3e904588, original_rx_b8fa, original_rx_b8fc
