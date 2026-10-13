ENTRY(npu_emulation_rx_event_callback)
original_rx_event_fbb8 = 0x8400fbb8;
original_rx_event_b5f0 = 0x8400b5f0;
SECTIONS {
    . = 0x840d0000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. <= 0x840d4000, "native RX event composition overflow")
}
