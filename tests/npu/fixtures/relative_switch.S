.option rvc
.option norelax
.text

/* Synthetic, bounded relative dispatches; no router instructions are copied. */
.macro dispatch name, variant=0
.balign 4
.globl case_\name
.type case_\name,@function
case_\name:
.if \variant == 10
    beq a1,zero,.Lload_\name
.elseif \variant == 11
    j .Ldone_\name
.elseif \variant == 19
    addi sp,sp,-16
.else
    c.nop
.endif
.if \variant != 2
    c.mv a5,a0
.endif
.Llimit_\name:
.if \variant == 1
    c.li a3,3
.elseif \variant == 4
    c.li a4,-1
.elseif \variant == 5
    addi a4,zero,1024
.else
    c.li a4,3
.endif
.if \variant == 2
    addi a5,a0,-32
.endif
.Lguard_\name:
.if \variant == 3
    blt a4,a5,.Ldefault_\name
.elseif \variant == 1
    bltu a3,a5,.Ldefault_\name
.elseif \variant == 12
    bltu a4,a5,.Lupper_\name
.elseif \variant == 13
    bltu a4,a5,.Loutside
.elseif \variant == 14
    bltu a4,a5,.Llimit_\name
.else
    bltu a4,a5,.Ldefault_\name
.endif
.Lupper_\name:
    auipc a3,%pcrel_hi(.Ltable_\name)
    addi a3,a3,%pcrel_lo(.Lupper_\name)
.if \variant == 6
    c.slli a5,1
.else
    c.slli a5,2
.endif
.if \variant == 7
    c.add a5,a2
.else
    c.add a5,a3
.endif
.Lload_\name:
.if \variant == 8
    c.lw a5,4(a5)
.else
    c.lw a5,0(a5)
.endif
.if \variant == 9
    c.add a5,a2
.else
    c.add a5,a3
.endif
.Ljump_\name:
.if \variant == 15
    c.jalr a5
.else
    c.jr a5
.endif
.Lcase0_\name:
.if \variant == 21
    sw ra,0(sp)
.else
    c.nop
.endif
    j .Ldone_\name
.Lcase1_\name:
    c.nop
    j .Ldone_\name
.Lcase2_\name:
    c.nop
    j .Ldone_\name
.Lcase3_\name:
.if \variant == 20
    addi sp,sp,-16
.else
    c.nop
.endif
    j .Ldone_\name
.Ldefault_\name:
.if \variant == 16
    c.jr a2
.elseif \variant == 17
    ecall
.elseif \variant == 18
    c.jalr a2
.endif
    c.nop
.Ldone_\name:
.if \variant == 19
    addi sp,sp,16
.endif
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

dispatch basic
dispatch bound_alias,1
dispatch biased,2
dispatch signed_guard,3
dispatch negative_max,4
dispatch oversized_max,5
dispatch wrong_shift,6
dispatch wrong_base,7
dispatch wrong_load,8
dispatch wrong_post_add,9
dispatch bypass,10
dispatch unreachable,11
dispatch identical_guard_edges,12
dispatch external_default,13
dispatch prefix_default,14
dispatch call_not_internal,15
dispatch unknown_tail,16
dispatch trap,17
dispatch unknown_call,18
dispatch framed,19
dispatch stack_leak,20
dispatch stack_overrun,21
.Loutside:
    ret
