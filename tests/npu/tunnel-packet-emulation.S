/* Runs after the existing header-length snapshot, before packet writes. */
.option norvc
.section .text

.globl npu_emulation_srv6_preflight
npu_emulation_srv6_preflight:
    addi sp, sp, -32
    sw ra, 28(sp)
    call original_tunnel_header_getter
    sw a0, 24(sp)
    mv a0, s4
    mv a1, s5
    mv a2, s1
    mv a3, s2
    mv a4, s0
    lw a5, 48(sp)
    lw a6, 24(sp)
    li a7, 0
    call npu_tunnel_srv6_extent_valid
.globl npu_emulation_srv6_preflight_checked
npu_emulation_srv6_preflight_checked:
    beqz a0, .Lreject
    lw a0, 24(sp)
    lw ra, 28(sp)
    addi sp, sp, 32
    j original_srv6_header_base_ready
.Lreject:
    lw a6, 24(sp)
    lw a5, 48(sp)
    lw ra, 28(sp)
    addi sp, sp, 32
    mv a0, s4
    mv a1, s5
    mv a2, s1
    mv a3, s2
    mv a4, s0
    li a7, 0
    li t1, 4
    j npu_emulation_egress_fault

.globl npu_emulation_srv6_tail
npu_emulation_srv6_tail:
    addi a3, s0, 32
    sub a2, s5, a3
    j original_srv6_tail_submit
