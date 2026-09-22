ENTRY(npu_emulation_egress_channel)
original_egress_channel_loaded = 0x84001586;
original_egress_submit = 0x840015a2;
original_egress_extent_prologue = 0x84001792;
SECTIONS {
    . = 0x84058000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. <= 0x8405a000, "egress sidecar overflow")
}
