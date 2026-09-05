/* Emulator reservations only, not validated firmware memory. */
ENTRY(npu_barrier_init)
PROVIDE(npu_emulation_barrier_state = 0x3e906000);
PROVIDE(npu_emulation_admission_state = npu_emulation_barrier_state + 0x100);
PROVIDE(npu_emulation_masked_state = npu_emulation_barrier_state + 0x140);
ASSERT((npu_emulation_barrier_state & 63) == 0 &&
       npu_emulation_barrier_state >= 0x3e904754 &&
       npu_emulation_barrier_state + 0x158 <= 0x3e908000,
       "candidate state outside conservative local SRAM or overlaps native BSS")
original_cb3e = 0x8400cb3e;
original_cb42 = 0x8400cb42;
original_cbc2 = 0x8400cbc2;
original_cbce = 0x8400cbce;
original_cc10 = 0x8400cc10;
original_ce20 = 0x8400ce20;
original_ce36 = 0x8400ce36;
original_cf2a = 0x8400cf2a;
original_cf14 = 0x8400cf14;
original_ec82 = 0x8400ec82;
original_ec7e = 0x8400ec7e;
original_ecc6 = 0x8400ecc6;
original_ecea = 0x8400ecea;
original_e444 = 0x8400e444;
original_e432 = 0x8400e432;
original_e4d8 = 0x8400e4d8;
original_d0ee = 0x8400d0ee;
original_d148 = 0x8400d148;
original_d164 = 0x8400d164;
original_cd42 = 0x8400cd42;
original_cd3e = 0x8400cd3e;
original_cd8e = 0x8400cd8e;
original_cda2 = 0x8400cda2;
original_b28 = 0x84000b28;
original_b3a = 0x84000b3a;
original_1472 = 0x84001472;
original_13f6 = 0x840013f6;
SECTIONS {
    . = 0x84040000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. < 0x84048000, "worker detour emulation text overflow")
}
