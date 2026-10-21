/* Synthetic read-boundary tests, not a physical memory reservation. */
ENTRY(npu_test_snapshot_all)
EXTERN(npu_test_capture_all)
EXTERN(npu_test_equal_boundary)
SECTIONS {
    . = 0x84040000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. < 0x84048000, "snapshot predicate test overflow")
}
