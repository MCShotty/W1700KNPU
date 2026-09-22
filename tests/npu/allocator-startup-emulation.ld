/* Test-only text reservation. No patched firmware or physical layout proof. */
ENTRY(npu_emulation_allocator_startup_dispatch)
original_allocator_getter_5204 = 0x84005204;
SECTIONS {
    . = 0x8404e000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. <= 0x84050000, "startup allocator emulation text overflow")
}
