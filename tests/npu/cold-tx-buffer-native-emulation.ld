ENTRY(npu_emulation_txbuf_callback)
original_txbuf_fbce = 0x8400fbce;
SECTIONS {
    . = 0x84090000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. <= 0x840d0000, "native TX buffer composition overflow")
}
