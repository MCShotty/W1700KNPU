.option rvc
.option norelax
.text

.macro dispatch name, variant=0
.balign 4
.globl case_\name
.type case_\name,@function
case_\name:
    c.mv a5,a0
    c.li a4,3
.if \variant == 1
    addi a6,a0,1
.elseif \variant == 2
    addi a5,a0,-32
    xor a2,s4,s5
    addi a6,a0,1
.elseif \variant == 3
    addi a4,a0,1
.elseif \variant == 4
    xor a5,s4,s5
.elseif \variant == 5
    addi a3,a0,1
.elseif \variant == 6
    addi sp,sp,-16
.elseif \variant == 7
    addi ra,a0,1
.elseif \variant == 8
    addi zero,a0,1
.elseif \variant == 9
    xor a2,s4,s5
    addi a6,a0,1
    addi a7,a0,2
.elseif \variant == 10
    lw a2,0(a0)
.elseif \variant == 11
    sw a2,0(a0)
.elseif \variant == 12
    jal ra,.Lexternal
.else
    xor a2,s4,s5
    addi a6,a0,1
.endif
.Lguard_\name:
    bltu a4,a5,.Ldefault_\name
.Lupper_\name:
    auipc a3,%pcrel_hi(.Ltable_\name)
    addi a3,a3,%pcrel_lo(.Lupper_\name)
    c.slli a5,2
    c.add a5,a3
    c.lw a5,0(a5)
    c.add a5,a3
    c.jr a5
.Lcase0_\name:
    c.nop
    j .Ldone_\name
.Lcase1_\name:
    c.nop
    j .Ldone_\name
.Lcase2_\name:
    c.nop
    j .Ldone_\name
.Lcase3_\name:
    c.nop
    j .Ldone_\name
.Ldefault_\name:
    c.nop
.Ldone_\name:
    ret
.size case_\name,.-case_\name
.pushsection .rodata
.balign 4
.Ltable_\name:
    .word .Lcase0_\name-.Ltable_\name
    .word .Lcase1_\name-.Ltable_\name
    .word .Lcase2_\name-.Ltable_\name
    .word .Lcase3_\name-.Ltable_\name
.popsection
.endm

dispatch two_setup
dispatch one_setup,1
dispatch biased_setup,2
dispatch bound_clobber,3
dispatch index_clobber,4
dispatch base_clobber,5
dispatch SP_clobber,6
dispatch RA_clobber,7
dispatch zero_write,8
dispatch third_setup,9
dispatch memory_read,10
dispatch memory_write,11
dispatch call,12
.Lexternal:
    ret
