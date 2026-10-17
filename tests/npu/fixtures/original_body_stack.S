.option norvc
.option norelax
.text
.macro begin name
.globl \name
.type \name,@function
\name:
.endm
.macro finish name
.size \name,.-\name
.endm
begin case_leaf
ret
finish case_leaf
begin case_frame
addi sp,sp,-16
sw ra,12(sp)
lw ra,12(sp)
addi sp,sp,16
ret
finish case_frame
begin case_tail
j callee
finish case_tail
begin case_tail_leak
addi sp,sp,-16
j callee
finish case_tail_leak
begin case_merge
beqz a0,1f
addi sp,sp,-16
1: ret
finish case_merge
begin case_growth
1: addi sp,sp,-16
bnez a0,1b
addi sp,sp,16
ret
finish case_growth
begin case_dynamic
add sp,sp,a0
ret
finish case_dynamic
begin case_load_sp
lw sp,0(a0)
ret
finish case_load_sp
begin case_indirect
jr a0
finish case_indirect
begin case_trap
ecall
ret
finish case_trap
begin case_stack_overrun
addi sp,sp,-16
sw ra,16(sp)
addi sp,sp,16
ret
finish case_stack_overrun
begin case_absolute_sp
li sp,0
ret
finish case_absolute_sp
begin case_wrong_link
jal s0,callee
ret
finish case_wrong_link
begin case_balanced_loop
addi sp,sp,-16
1: nop
bnez a0,1b
addi sp,sp,16
ret
finish case_balanced_loop
begin case_call
addi sp,sp,-16
sw ra,12(sp)
jal ra,callee
lw ra,12(sp)
addi sp,sp,16
ret
finish case_call
begin case_csr_sp
csrr sp,mstatus
ret
finish case_csr_sp
