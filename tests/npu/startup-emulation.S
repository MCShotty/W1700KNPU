/* Preserve reset registers and the displaced AUIPC's exact return address. */
#include "startup.h"
    .option norvc
    .section .text.startup_adapter,"ax",@progbits
    .global npu_emulation_before_bss
npu_emulation_before_bss:
    .global npu_emulation_precheck_hart_csr
npu_emulation_precheck_hart_csr:
    csrr t0, mhartid
    bnez t0, .Lprecheck_fault
    la t0, npu_emulation_startup_state
    fence iorw, iorw
    lw t1, 0(t0)
    li t2, NPU_STARTUP_MAGIC
    bne t1, t2, .Lprecheck_fault
    lw t1, 4(t0)
    li t2, NPU_STARTUP_VERSION
    bne t1, t2, .Lprecheck_fault
    lw t1, 8(t0)
    li t2, NPU_STARTUP_BYTES
    bne t1, t2, .Lprecheck_fault
    lw t1, 12(t0)
    bnez t1, .Lprecheck_fault
    lw t1, 16(t0)
    bnez t1, .Lprecheck_fault
    lw t1, 20(t0)
    bnez t1, .Lprecheck_fault
    lw t1, 52(t0)
    lw t2, 56(t0)
    or t1, t1, t2
    lw t2, 60(t0)
    or t1, t1, t2
    bnez t1, .Lprecheck_fault
    lui t0, 0x1ec0c
    lw t1, 0x140(t0)
    li t2, -1
    beq t1, t2, .Lprecheck_fault
    j original_reset_78
.Lprecheck_fault:
    la t0, npu_emulation_startup_state
    li t1, 3
    fence rw, w
    sw t1, 12(t0)
    li t1, 1
    fence rw, w
    sw t1, 16(t0)
    la t0, npu_emulation_barrier_state
    li t1, 1
    fence rw, w
    sw t1, 16(t0)
    fence iorw, iorw
    .global npu_emulation_startup_precheck_fault
npu_emulation_startup_precheck_fault:
    j npu_emulation_startup_precheck_fault

    .global npu_emulation_reset_gate
npu_emulation_reset_gate:
    addi sp, sp, -64
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
    .global npu_emulation_startup_hart_csr
npu_emulation_startup_hart_csr:
    csrr a0, mhartid
    call npu_emulation_cold_start
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
    addi sp, sp, 64
    lui ra, 0x84000
    addi ra, ra, 0xf0
    j original_reset_f4
