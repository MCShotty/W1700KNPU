/* Separate emulator-only code reservation; not part of a deployable image. */
ENTRY(npu_emulation_bridge_base_guard)
original_bridge_148e = 0x8400148e;
original_bridge_1504 = 0x84001504;
SECTIONS {
    . = 0x84048000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. <= 0x84049000, "bridge guard emulation text overflow")
}
