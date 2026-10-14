ENTRY(npu_emulation_pcie_tail_ba0c)
original_pcie_tail_b9b4 = 0x8400b9b4;
original_pcie_tail_b9c6 = 0x8400b9c6;
original_pcie_tail_b9d8 = 0x8400b9d8;
original_pcie_tail_b9f0 = 0x8400b9f0;
original_pcie_tail_ba04 = 0x8400ba04;
original_pcie_tail_ba10 = 0x8400ba10;
original_pcie_tail_ba1c = 0x8400ba1c;
original_pcie_tail_ba28 = 0x8400ba28;
original_pcie_tail_ba34 = 0x8400ba34;
SECTIONS {
    . = 0x840e8000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. <= 0x840f0000, "native PCIe tail stores overflow")
}
