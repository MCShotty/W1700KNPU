ENTRY(probe_init)
SECTIONS {
    . = 0x84074000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. <= 0x84078000, "cold page probe overflow")
}
