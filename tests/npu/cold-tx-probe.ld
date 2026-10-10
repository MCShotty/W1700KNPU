ENTRY(npu_cold_tx_begin)
SECTIONS {
    . = 0x84090000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. <= 0x84094000, "cold TX probe overflow")
}
