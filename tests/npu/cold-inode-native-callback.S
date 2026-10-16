    .option norvc
    .section .text.inode_callback,"ax",@progbits
    .global npu_original_inode_callback
    .type npu_original_inode_callback,@function
npu_original_inode_callback:
    /* Original c.lw a5,0(a0); c.lw a4,20(a0),then the untouched wrapper. */
    .4byte 0x4958411c
    j original_inode_fc30
    .size npu_original_inode_callback, .-npu_original_inode_callback
