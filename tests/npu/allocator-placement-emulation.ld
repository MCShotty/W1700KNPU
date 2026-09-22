/* Unpromoted code-region placement; no physical cache or alias proof. */
ENTRY(npu_emulation_allocator_startup_dispatch)
original_allocator_getter_5204 = 0x84005204;
SECTIONS {
    . = 0x8404e000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. <= 0x84050000, "startup allocator emulation text overflow")
    . = 0x84060000;
    .command_ring : { KEEP(*(.command_ring)) }
    ASSERT(SIZEOF(.command_ring) == 0x8010, "command ring extent")
    ASSERT(. <= 0x84200000, "firmware code region overflow")
}
