/* Emulator-only reservation; not a production loader/memory contract. */
ENTRY(npu_emulation_txdone_callback)
original_desc_fe38 = 0x8400fe38;
original_bufid_4d96 = 0x84004d96;
original_skb_4a2c = 0x84004a2c;
original_skb_4a2e = 0x84004a2e;
original_skb_4a3e = 0x84004a3e;
original_skb_4b0c = 0x84004b0c;
original_skb_4b1a = 0x84004b1a;
original_txdone_b54a = 0x8400b54a;
original_lock_acquire = 0x840064b4;
original_lock_release = 0x8400651c;
SECTIONS {
    . = 0x84052000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. <= 0x84054000, "TXDONE init emulation text overflow")
}
