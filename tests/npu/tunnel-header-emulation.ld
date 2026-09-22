ENTRY(npu_emulation_vxlan_header)
original_vxlan_captured = 0x84005c40;
original_srv6_captured = 0x84005c96;
original_srv6_consumer_prologue = 0x84001e7c;
original_srv6_size_a5_loaded = 0x84001eee;
original_srv6_size_a2_loaded = 0x84001f04;
SECTIONS {
    . = 0x84056000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. <= 0x84058000, "tunnel header bounds sidecar overflow")
}
