ENTRY(npu_emulation_srv6_preflight)
original_tunnel_header_getter = 0x84001466;
original_srv6_header_base_ready = 0x84001e96;
original_srv6_tail_submit = 0x84001f3e;
SECTIONS {
    . = 0x8405a000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. <= 0x8405c000, "tunnel packet sidecar overflow")
}
