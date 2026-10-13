ENTRY(npu_cold_txdone_begin)
SECTIONS
{
    . = 0x84000000;
    .text : { *(.text .text.*) }
    .rodata : { *(.rodata .rodata.*) }
    .data : { *(.data .data.*) }
    .bss (NOLOAD) : { *(.bss .bss.*) *(COMMON) }
    /DISCARD/ : { *(.comment) *(.riscv.attributes) }
}
