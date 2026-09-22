ENTRY(npu_emulation_ring_publish)
original_ring_after_payload = 0x8400c970;
original_ring_after_acquire = 0x8400cc22;
original_ring_before_slot_return = 0x8400cc52;
SECTIONS {
    . = 0x84054000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. <= 0x84056000, "command ring ordering sidecar overflow")
}
