/* Independent emulator code/state reservation, not a production loader proof. */
ENTRY(npu_emulation_packet_init)
original_packet_4d86 = 0x84004d86;
original_packet_4d8a = 0x84004d8a;
original_rx_b7cc = 0x8400b7cc;
original_rx_b7ce = 0x8400b7ce;
original_rx_b8fa = 0x8400b8fa;
original_rx_b8fc = 0x8400b8fc;
SECTIONS {
    . = 0x84080000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. <= 0x84084000, "cold packet composition overflow")
}
