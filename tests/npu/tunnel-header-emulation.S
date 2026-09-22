/* Unpromoted bounds adapters. Native copy/encoding routines remain in use. */
.option norvc
.section .text

.globl npu_emulation_vxlan_header
npu_emulation_vxlan_header:
    addi sp, sp, -16
    sw ra, 12(sp)
    sw s0, 8(sp)
    sw s1, 4(sp)
    mv s1, a0
    li a2, 0
    call npu_tunnel_header_decode
.globl npu_emulation_vxlan_decoded
npu_emulation_vxlan_decoded:
    li t0, -1
    beq a0, t0, .Lbad_vxlan
    slli s0, a0, 7
    j original_vxlan_captured
.Lbad_vxlan:
    lw ra, 12(sp)
    lw s0, 8(sp)
    lw s1, 4(sp)
    li a0, 0
    addi sp, sp, 16
    ret

.globl npu_emulation_srv6_header
npu_emulation_srv6_header:
    addi sp, sp, -16
    sw ra, 12(sp)
    sw s0, 8(sp)
    sw s1, 4(sp)
    sw s2, 0(sp)
    mv s1, a0
    li a2, 1
    call npu_tunnel_header_decode
.globl npu_emulation_srv6_decoded
npu_emulation_srv6_decoded:
    li t0, -1
    beq a0, t0, .Lbad_srv6
    mv s0, a0
    mv s2, a1
    j original_srv6_captured
.Lbad_srv6:
    lw ra, 12(sp)
    lw s0, 8(sp)
    lw s1, 4(sp)
    lw s2, 0(sp)
    li a0, 0
    addi sp, sp, 16
    ret

.globl npu_emulation_srv6_consumer
npu_emulation_srv6_consumer:
    addi sp, sp, -32
    sw ra, 28(sp)
    sw a0, 24(sp)
    sw a1, 20(sp)
    sw a2, 16(sp)
    sw a3, 12(sp)
    sw a4, 8(sp)
    mv a0, a3
    li a1, 0x3e904650
    call npu_tunnel_srv6_read_length
    mv t0, a0
    li t1, -1
    beq t0, t1, .Lbad_consumer
    lw ra, 28(sp)
    lw a0, 24(sp)
    lw a1, 20(sp)
    lw a2, 16(sp)
    lw a3, 12(sp)
    lw a4, 8(sp)
    addi sp, sp, 32
    addi sp, sp, -48
    sw ra, 44(sp)
    sw t0, 16(sp)
    j original_srv6_consumer_prologue
.Lbad_consumer:
    lw ra, 28(sp)
    li a0, -1
    addi sp, sp, 32
    ret

.globl npu_emulation_srv6_size_a5
npu_emulation_srv6_size_a5:
    lw a5, 16(sp)
    j original_srv6_size_a5_loaded

.globl npu_emulation_srv6_size_a2
npu_emulation_srv6_size_a2:
    lw a2, 16(sp)
    j original_srv6_size_a2_loaded
