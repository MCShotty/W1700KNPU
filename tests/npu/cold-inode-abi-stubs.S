    /* Explicit ABI-test guards only; no ownership/admission implementation. */
    .option norvc
    .text
    .global npu_emulation_inode_reserve
npu_emulation_inode_reserve:
    li a0, 0
    ret
    .global npu_emulation_inode_publish
npu_emulation_inode_publish:
    li a0, 0
    ret
