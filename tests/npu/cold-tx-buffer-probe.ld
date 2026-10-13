ENTRY(npu_cold_txbuf_begin)
SECTIONS
{
    . = 0x84040000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    /DISCARD/ : { *(.comment) *(.eh_frame*) *(.riscv.attributes) }
}
