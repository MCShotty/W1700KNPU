/* Separate emulator reservation, not a production code or SRAM placement. */
ENTRY(npu_emulation_allocator_reset_prepare)
original_allocator_reset_prerequisite = 0x8400fb12;
SECTIONS {
    . = 0x8404c000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. <= 0x8404d000, "allocator reset emulation text overflow")
}
