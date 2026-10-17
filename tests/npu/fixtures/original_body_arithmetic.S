.option norvc
.option norelax
.text
.macro binary name, opcode
.globl case_\name
.type case_\name,@function
case_\name:
\opcode a0,a1,a2
ret
.size case_\name,.-case_\name
.globl case_\name\()_sp
.type case_\name\()_sp,@function
case_\name\()_sp:
\opcode sp,a1,a2
ret
.size case_\name\()_sp,.-case_\name\()_sp
.globl case_\name\()_zero
.type case_\name\()_zero,@function
case_\name\()_zero:
\opcode zero,a1,a2
ret
.size case_\name\()_zero,.-case_\name\()_zero
.endm
binary mul,mul
binary mulh,mulh
binary mulhsu,mulhsu
binary mulhu,mulhu
binary div,div
binary divu,divu
binary rem,rem
binary remu,remu
.globl case_seqz
.type case_seqz,@function
case_seqz:
seqz a0,a1
ret
.size case_seqz,.-case_seqz
.globl case_seqz_sp
.type case_seqz_sp,@function
case_seqz_sp:
seqz sp,a1
ret
.size case_seqz_sp,.-case_seqz_sp
.globl case_seqz_zero
.type case_seqz_zero,@function
case_seqz_zero:
seqz zero,a1
ret
.size case_seqz_zero,.-case_seqz_zero
.globl case_mul_framed
.type case_mul_framed,@function
case_mul_framed:
addi sp,sp,-16
sw ra,12(sp)
mul a0,a1,a2
lw ra,12(sp)
addi sp,sp,16
ret
.size case_mul_framed,.-case_mul_framed
