.option rvc
.option norelax
.text

/* Multiple guarded entries, plus hostile deviations, in synthetic code only. */
.macro dispatch name, variant=0
.balign 4
.globl case_\name
.type case_\name,@function
case_\name:
.if \variant == 27
    addi sp,sp,-16
.else
    c.nop
.endif
.if \variant == 28
    c.nop
.else
    c.li a4,3
.endif
    c.mv a5,a0
.if \variant == 29 || \variant == 30
    c.nop
.else
    bnez a1,.Lalt_\name
.endif
.Llimit_\name:
    c.li a4,3
.Lbias_\name:
.if \variant == 2
    addi a5,a0,-32
.endif
.Lguard_\name:
    bltu a4,a5,.Ldefault_\name
.Lupper_\name:
    auipc a3,%pcrel_hi(.Ltable_\name)
.Laddition_\name:
    addi a3,a3,%pcrel_lo(.Lupper_\name)
.Lshift_\name:
    c.slli a5,2
.Lcombine_\name:
    c.add a5,a3
.Lload_\name:
    c.lw a5,0(a5)
.Lpost_\name:
    c.add a5,a3
.Ljump_\name:
    c.jr a5
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
.if \variant == 29 || \variant == 30
    addi a0,a0,1
.elseif \variant == 20
    addi sp,sp,-16
.else
    c.nop
.endif
.if \variant == 29 || \variant == 30
    j .Lalt_\name
.else
    j .Ldone_\name
.endif
.Lalt_\name:
.if \variant == 29 || \variant == 30
    c.mv a5,a0
.if \variant == 30
    c.li a4,4
.endif
.endif
.if \variant == 3
    c.li a4,4
.elseif \variant == 4
    lw a4,0(a2)
.elseif \variant == 5 || \variant == 6
    jal ra,.Lexternal
.if \variant == 6
    c.li a4,3
.endif
.elseif \variant == 25
    jal t0,.Lexternal
.elseif \variant == 26
    li sp,0
.endif
.if \variant == 1
    j .Lguard_\name
.elseif \variant == 2
    j .Lbias_\name
.elseif \variant == 7
    bge a4,a5,.Lupper_\name
.elseif \variant == 8
    bgeu a3,a5,.Lupper_\name
.elseif \variant == 9
    bgeu a4,a2,.Lupper_\name
.elseif \variant == 11
    j .Lupper_\name
.elseif \variant == 12
    j .Laddition_\name
.elseif \variant == 13
    j .Lshift_\name
.elseif \variant == 14
    j .Lcombine_\name
.elseif \variant == 15
    j .Lload_\name
.elseif \variant == 16
    j .Lpost_\name
.elseif \variant == 17
    j .Ljump_\name
.elseif \variant == 18
    beqz a2,.Lguard_\name
    c.li a4,4
    j .Lguard_\name
.elseif \variant == 19
    bgeu a4,a5,.Ltamper_\name
.else
.Lalternate_guard_\name:
    bgeu a4,a5,.Lupper_\name
.endif
.if \variant == 10
    c.nop
.endif
.Ldefault_\name:
.if \variant == 22
    c.jr a2
.elseif \variant == 23
    c.jalr a2
.elseif \variant == 24
    ecall
.else
    c.nop
.endif
.Ldone_\name:
.if \variant == 27
    addi sp,sp,16
.endif
    ret
.if \variant == 19
.Ltamper_\name:
    c.addi a5,1
    j .Lupper_\name
.endif
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

dispatch multi_guard
dispatch guard_reentry,1
dispatch bias_reentry,2
dispatch bound_changed,3
dispatch bound_unknown,4
dispatch call_clobbered,5
dispatch call_restored,6
dispatch signed_alternate,7
dispatch wrong_bound,8
dispatch wrong_index,9
dispatch default_gap,10
dispatch jump_upper,11
dispatch jump_addition,12
dispatch jump_shift,13
dispatch jump_combine,14
dispatch jump_load,15
dispatch jump_post,16
dispatch jump_dispatch,17
dispatch bound_join,18
dispatch index_after_guard,19
dispatch stack_leak,20
dispatch stack_overrun,21
dispatch unknown_tail,22
dispatch unknown_call,23
dispatch trap,24
dispatch non_ABI_call,25
dispatch SP_write,26
dispatch framed,27
dispatch uninitialized_bound,28
dispatch guarded_loop,29
dispatch changed_loop,30
.Lexternal:
    ret
