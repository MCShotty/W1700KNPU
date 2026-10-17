.text
.option rvc
.globl case_comp_lui
.type case_comp_lui,@function
case_comp_lui:
c.lui a5,1
.option norvc
ret
.size case_comp_lui,.-case_comp_lui
.globl case_neg
.type case_neg,@function
case_neg:
neg a0,a0
ret
.size case_neg,.-case_neg
.globl case_lui_sp
.type case_lui_sp,@function
case_lui_sp:
lui sp,1
ret
.size case_lui_sp,.-case_lui_sp
.globl case_neg_sp
.type case_neg_sp,@function
case_neg_sp:
neg sp,a0
ret
.size case_neg_sp,.-case_neg_sp
.globl case_snez
.type case_snez,@function
case_snez:
snez a0,a0
ret
.size case_snez,.-case_snez
.globl case_snez_sp
.type case_snez_sp,@function
case_snez_sp:
snez sp,a0
ret
.size case_snez_sp,.-case_snez_sp
