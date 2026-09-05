/* Emulation-only addresses, not a validated firmware memory reservation. */
ENTRY(npu_barrier_init)
original_cb3e = 0x8400cb3e;
original_cb42 = 0x8400cb42;
original_cbc2 = 0x8400cbc2;
original_cbce = 0x8400cbce;
original_cc10 = 0x8400cc10;
SECTIONS {
    . = 0x84040000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. < 0x84048000, "barrier emulation text overflow")
}
