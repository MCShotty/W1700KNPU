ENTRY(npu_emulation_rx_pcie_callback)
original_rx_pcie_fdc8 = 0x8400fdc8;
original_rx_pcie_ba8c = 0x8400ba8c;
SECTIONS {
    . = 0x840e4000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. <= 0x840e8000, "native RX PCIe composition overflow")
}
