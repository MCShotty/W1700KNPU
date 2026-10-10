ENTRY(npu_emulation_tx_callback)
original_tx_fc1a = 0x8400fc1a;
original_token_fdde = 0x8400fdde;
original_tx_d63c = 0x8400d63c;
original_tx_d670 = 0x8400d670;
original_tx_d4c2 = 0x8400d4c2;
original_tx_d4ca = 0x8400d4ca;
original_tx_d588 = 0x8400d588;
original_tx_d534 = 0x8400d534;
original_tx_d5bc = 0x8400d5bc;
original_tx_dfd4 = 0x8400dfd4;
SECTIONS {
    . = 0x84084000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. <= 0x84088000, "native cold TX composition overflow")
}
