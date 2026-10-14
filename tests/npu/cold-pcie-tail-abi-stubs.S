    /* ABI probe only. Real ownership guards are not linked by this fixture. */
    .option norvc
    .text
    .global npu_emulation_pcie_tail_reserve
npu_emulation_pcie_tail_reserve:
    li a0, 0
    ret
    .global npu_emulation_pcie_tail_publish
npu_emulation_pcie_tail_publish:
    li a0, 0
    ret
