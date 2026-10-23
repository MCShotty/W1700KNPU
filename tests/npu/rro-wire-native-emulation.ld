ENTRY(npu_emulation_rro_mailbox_veneer)
SECTIONS {
    . = 0x84100000;
    .rro_veneers : { KEEP(*(.rro_veneers)) }
    ASSERT(SIZEOF(.rro_veneers) == 8, "RRO veneers must remain two four-byte jumps")
    ASSERT(npu_emulation_rro_mailbox_veneer == 0x84100000,
           "RRO mailbox veneer moved")
    ASSERT(npu_emulation_rro_cold_ready_veneer == 0x84100004,
           "RRO cold-ready veneer moved")
    .text : { *(.text .text.*) }
    .rodata : { *(.rodata .rodata.*) }
    .data : { *(.data .data.* .sdata .sdata.*) }
    . = ALIGN(16);
    .bss (NOLOAD) : { *(.bss .bss.* .sbss .sbss.*) *(COMMON) }
    ASSERT(SIZEOF(.bss) == 30588, "RRO session BSS size changed")
    ASSERT(npu_emulation_rro_session_state >= ADDR(.bss) &&
           npu_emulation_rro_session_state + 30588 <= ADDR(.bss) + SIZEOF(.bss),
           "RRO session outside boot-owned BSS")
    ASSERT(. <= 0x84200000, "RRO component exceeds two-MiB CODE aperture")
    /DISCARD/ : { *(.comment .note.* .eh_frame .riscv.attributes) }
}
