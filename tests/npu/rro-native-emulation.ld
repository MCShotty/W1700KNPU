ENTRY(rro_emulation_init)
SECTIONS {
  . = 0x84100000;
  .text : { *(.text .text.*) }
  .rodata : { *(.rodata .rodata.*) }
  .data : { *(.data .data.* .sdata .sdata.*) }
  . = ALIGN(16);
  .bss (NOLOAD) : { *(.bss .bss.* .sbss .sbss.*) *(COMMON) }
  /DISCARD/ : { *(.comment .note.* .eh_frame .riscv.attributes) }
}
