SECTIONS
{
  . = 0x84094000;
  .text : { *(.text*) }
  .rodata : { *(.rodata*) }
  .data : { *(.data*) }
  .bss : { *(.bss*) *(COMMON) }
  ASSERT(. < 0x84098000, "descriptor probe overflow")
}
