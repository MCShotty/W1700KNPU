ENTRY(npu_emulation_desc10_callback)
original_lock_release = 0x8400651c;
SECTIONS {
    . = 0x840d4000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. <= 0x840e4000, "native DESC10 composition overflow")
}
