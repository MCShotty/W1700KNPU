    .option norvc
    .section .text.desc10,"ax",@progbits

    .macro save_all
    addi sp, sp, -80
    sw t0, 0(sp)
    sw t1, 4(sp)
    sw t2, 8(sp)
    sw t3, 12(sp)
    sw t4, 16(sp)
    sw t5, 20(sp)
    sw t6, 24(sp)
    sw a0, 28(sp)
    sw a1, 32(sp)
    sw a2, 36(sp)
    sw a3, 40(sp)
    sw a4, 44(sp)
    sw a5, 48(sp)
    sw a6, 52(sp)
    sw a7, 56(sp)
    sw ra, 76(sp)
    .endm

    .macro restore_all
    lw t0, 0(sp)
    lw t1, 4(sp)
    lw t2, 8(sp)
    lw t3, 12(sp)
    lw t4, 16(sp)
    lw t5, 20(sp)
    lw t6, 24(sp)
    lw a0, 28(sp)
    lw a1, 32(sp)
    lw a2, 36(sp)
    lw a3, 40(sp)
    lw a4, 44(sp)
    lw a5, 48(sp)
    lw a6, 52(sp)
    lw a7, 56(sp)
    lw ra, 76(sp)
    addi sp, sp, 80
    .endm

    .macro argument dst reg
    .ifc \reg,zero
    li \dst, 0
    .exitm
    .endif
    .ifc \reg,t0
    lw \dst, 0(sp)
    .exitm
    .endif
    .ifc \reg,t1
    lw \dst, 4(sp)
    .exitm
    .endif
    .ifc \reg,t2
    lw \dst, 8(sp)
    .exitm
    .endif
    .ifc \reg,t3
    lw \dst, 12(sp)
    .exitm
    .endif
    .ifc \reg,t4
    lw \dst, 16(sp)
    .exitm
    .endif
    .ifc \reg,t5
    lw \dst, 20(sp)
    .exitm
    .endif
    .ifc \reg,t6
    lw \dst, 24(sp)
    .exitm
    .endif
    .ifc \reg,a0
    lw \dst, 28(sp)
    .exitm
    .endif
    .ifc \reg,a1
    lw \dst, 32(sp)
    .exitm
    .endif
    .ifc \reg,a2
    lw \dst, 36(sp)
    .exitm
    .endif
    .ifc \reg,a3
    lw \dst, 40(sp)
    .exitm
    .endif
    .ifc \reg,a4
    lw \dst, 44(sp)
    .exitm
    .endif
    .ifc \reg,a5
    lw \dst, 48(sp)
    .exitm
    .endif
    .ifc \reg,a6
    lw \dst, 52(sp)
    .exitm
    .endif
    .ifc \reg,a7
    lw \dst, 56(sp)
    .exitm
    .endif
    mv \dst, \reg
    .endm

    .macro emit opcode bytes
    .if \bytes == 2
    .2byte \opcode
    .else
    .4byte \opcode
    .endif
    .endm

    .macro store name address offset value width continuation failure shared opcode instruction_bytes extra=0
    .global \name
\name:
    .if \shared
    la t0, npu_emulation_desc10_state
    lw t0, 0(t0)
    bnez t0, .Lowned\@
    la t0, npu_emulation_desc10_running
    lw t0, 0(t0)
    bnez t0, .Lowned\@
    .if \shared == 2
    lw t0, 60(sp)
    .else
    lw t0, 28(sp)
    .endif
    li t2, 0x8400b546
    bne t0, t2, .Lunrelated\@
    .endif
.Lowned\@:
    save_all
    argument a0, \address
    addi a0, a0, \offset
    argument a1, \value
    li a2, \width
    call npu_emulation_desc10_reserve
    beqz a0, .Lfailed\@
    restore_all
    .global \name\()_store
\name\()_store:
    emit \opcode, \instruction_bytes
    save_all
    argument a0, \address
    addi a0, a0, \offset
    li a1, \width
    call npu_emulation_desc10_publish
    beqz a0, .Lfailed\@
    restore_all
    .if \extra
    .2byte \extra
    .endif
    j \continuation
.Lfailed\@:
    restore_all
    j \failure
    .if \shared
.Lunrelated\@:
    emit \opcode, \instruction_bytes
    .if \extra
    .2byte \extra
    .endif
    j \continuation
    .endif
    .endm

    .global npu_emulation_desc10_packet_guard
npu_emulation_desc10_packet_guard:
    lw t0, 12(sp)
    li t1, 0x8400b4e4
    bne t0, t1, npu_emulation_packet_guard
    addi sp, sp, -16
    sw ra, 12(sp)
    call npu_emulation_desc10_take
    lw ra, 12(sp)
    addi sp, sp, 16
    lw ra, 12(sp)
    lw s0, 8(sp)
    addi sp, sp, 16
    ret

    .global npu_emulation_desc10_skb_guard
npu_emulation_desc10_skb_guard:
    lw t0, 28(sp)
    li t2, 0x8400b546
    bne t0, t2, npu_previous_txdone_lock20_guard
    save_all
    argument a0, a0
    call npu_emulation_desc10_skb_prepare
    beqz a0, .Lprepare_failed
    restore_all
    li a1, 0x8401aa3a
    j original_desc10_4a3e
.Lprepare_failed:
    restore_all
    bnez a0, .Lrelease19
    li a0, 0x3e901bc4
    call original_lock_release
.Lrelease19:
    li a0, 0x3e901bb8
    call original_lock_release
    j desc10_skb_return

    .global npu_emulation_desc10_ready_guard
npu_emulation_desc10_ready_guard:
    save_all
    call npu_emulation_desc10_ready
    beqz a0, .Lready_failed
    restore_all
    li a5, 0x3e903546
    j original_desc10_b54a
.Lready_failed:
    restore_all
    j desc10_return

desc10_collector_abort:
    lw ra, 28(sp)
    lw s0, 24(sp)
    lw s1, 20(sp)
    lw s2, 16(sp)
    lw s3, 12(sp)
    lw s4, 8(sp)
    lw s5, 4(sp)
    lw s6, 0(sp)
    addi sp, sp, 32
desc10_skb_abort:
    li a0, 0x3e901bc4
    call original_lock_release
    li a0, 0x3e901bb8
    call original_lock_release
desc10_skb_return:
    lw ra, 28(sp)
    lw s0, 24(sp)
    lw s1, 20(sp)
    lw s2, 16(sp)
    lw s3, 12(sp)
    lw s4, 8(sp)
    addi sp, sp, 32
    ret

desc10_return:
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

    store npu_emulation_desc10_b530, a5, 1360, s0, 2, original_desc10_b534, desc10_return, 0, 0x54879823, 4
    store npu_emulation_desc10_b53c, a5, 1980, a0, 4, original_desc10_b540, desc10_return, 0, 0x7aa7ae23, 4
    store npu_emulation_desc10_b4b6, a4, 4, zero, 4, original_desc10_b4ba, desc10_return, 0, 0x00072223, 4
    store npu_emulation_desc10_b4ba, a4, 0, a5, 4, npu_emulation_desc10_b4bc, desc10_return, 0, 0xc31c, 2
    store npu_emulation_desc10_b4bc, a4, 8, zero, 4, original_desc10_b4c0, desc10_return, 0, 0x00072423, 4
    store npu_emulation_desc10_b4c0, a4, 12, zero, 4, original_desc10_b4c4, desc10_return, 0, 0x00072623, 4
    store npu_emulation_desc10_b4ce, a4, 4, s1, 4, original_desc10_b4d2, desc10_return, 0, 0xc344, 2, 0x0bc2
    store npu_emulation_desc10_b4d6, s8, 0, a0, 2, original_desc10_b4da, desc10_return, 0, 0x00ac1023, 4
    store npu_emulation_desc10_4a62, a5, 0, a3, 2, original_desc10_4a66, desc10_skb_abort, 1, 0x00d79023, 4
    store npu_emulation_desc10_9b04, a4, 0, a5, 2, original_desc10_9b08, desc10_collector_abort, 2, 0x00f71023, 4
    store npu_emulation_desc10_4aac, a5, 0, zero, 2, original_desc10_4ab0, desc10_skb_abort, 1, 0x00079023, 4
    store npu_emulation_desc10_4ad2, a5, 0, a1, 2, original_desc10_4ad6, desc10_skb_abort, 1, 0x00b79023, 4
    store npu_emulation_desc10_4afa, t1, 0, a5, 2, original_desc10_4afe, desc10_skb_abort, 1, 0x00f31023, 4
    store npu_emulation_desc10_4b32, t1, 0, a3, 2, original_desc10_4b36, desc10_skb_abort, 1, 0x00d31023, 4
    store npu_emulation_desc10_4b5c, a5, 92, s4, 2, original_desc10_4b60, desc10_skb_abort, 1, 0x05479e23, 4
    store npu_emulation_desc10_4b60, gp, 2028, zero, 2, original_desc10_4b64, desc10_skb_abort, 1, 0x7e019623, 4
    store npu_emulation_desc10_b54a, a5, 1070, zero, 4, original_desc10_b54e, desc10_return, 0, 0x4207a723, 4
    store npu_emulation_desc10_b558, a4, 422, a5, 1, original_desc10_b55c, desc10_return, 0, 0x1af70323, 4
    store npu_emulation_desc10_b45e, a5, 1570, s0, 2, original_desc10_b462, desc10_return, 0, 0x62879123, 4
    store npu_emulation_desc10_b46a, a5, -1906, a0, 4, original_desc10_b46e, desc10_return, 0, 0x88a7a723, 4
