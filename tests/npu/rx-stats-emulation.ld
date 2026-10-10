/* Emulator reservation, not a production loader or DMA ownership contract. */
ENTRY(npu_emulation_rx_stats_callback)
npu_original_rx_dispatch = 0x8400dd82;
original_stats_a3b2 = 0x8400a3b2;
original_stats_a39e = 0x8400a39e;
original_dispatch_ddc4 = 0x8400ddc4;
original_dispatch_ddda = 0x8400ddda;
original_rx_b7cc = 0x8400b7cc;
original_rx_b7ce = 0x8400b7ce;
original_rx_b8fa = 0x8400b8fa;
original_rx_b8fc = 0x8400b8fc;
SECTIONS {
    . = 0x8407c000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. <= 0x84080000, "RX statistics binding overflow")
}
