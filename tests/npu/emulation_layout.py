"""Conservative test map, not a hardware reservation or cache-coherency proof."""

CODE = 0x84000000
SRAM = 0x3e900000
SRAM_BYTES = 0x8000
HEAP = 0x3e800000
HEAP_BYTES = 0x78000
STATE = SRAM + 0x6000
SCRATCH = SRAM + 0x7000
RING = HEAP + 0x10000
STATS = HEAP + 0x12000
ICV = HEAP + 0x14000
OLD = HEAP + 0x30000
NEW = HEAP + 0x31000


def map_sram(cpu):
    cpu.mem_map(SRAM, SRAM_BYTES)
    cpu.mem_map(HEAP, HEAP_BYTES)
