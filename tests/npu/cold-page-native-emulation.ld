/* Emulator-only code/state reservation, not a production loader contract. */
ENTRY(npu_emulation_page_callback)
original_page_get_bba0 = 0x8400bba0;
npu_original_page_dispatch = 0x8400dd82;
original_page_return_bd12 = 0x8400bd12;
original_page_bd66 = 0x8400bd66;
original_page_bd8a = 0x8400bd8a;
original_page_bd4c = 0x8400bd4c;
SECTIONS {
    . = 0x84078000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. <= 0x8407c000, "native cold page composition overflow")
}
