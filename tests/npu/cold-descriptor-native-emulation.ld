ENTRY(npu_emulation_descriptor_callback)
original_descriptor_10168 = 0x84010168;
original_descriptor_d8d0 = 0x8400d8d0;
original_descriptor_d900 = 0x8400d900;
SECTIONS {
    . = 0x84088000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. <= 0x8408c000, "native descriptor composition overflow")
}
