/* Component-test reservation only, not a production SRAM/code layout. */
ENTRY(npu_allocator_test_allocate)
SECTIONS {
    . = 0x8404a000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. < 0x84050000, "allocator component test image overflow")
}
