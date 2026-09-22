ENTRY(npu_client_init)
SECTIONS
{
    . = 0x100000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. < 0x110000, "client test code exceeds reservation")
    /DISCARD/ : { *(.comment) *(.eh_frame*) *(.note*) }
}
