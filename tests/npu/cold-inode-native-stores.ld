ENTRY(npu_emulation_inode_e178)
original_inode_e0c8 = 0x8400e0c8;
original_inode_e0d2 = 0x8400e0d2;
original_inode_e0dc = 0x8400e0dc;
original_inode_e0e4 = 0x8400e0e4;
original_inode_e0ec = 0x8400e0ec;
original_inode_e0f4 = 0x8400e0f4;
original_inode_e17c = 0x8400e17c;
original_inode_e184 = 0x8400e184;
original_inode_e18e = 0x8400e18e;
original_inode_e19a = 0x8400e19a;
original_inode_e1b8 = 0x8400e1b8;
SECTIONS {
    . = 0x840f0000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(. <= 0x840f8000, "native INODE stores overflow")
}
