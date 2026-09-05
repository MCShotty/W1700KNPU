#include "gdma.h"

#define GDMA_BASE 0x1fb30000u
#define GDMA_DONE (GDMA_BASE + 0x204u)
#define GDMA_ENABLE 2u

static uint32_t read32(uint32_t address)
{
    return *(volatile uint32_t *)(uintptr_t)address;
}

static void write32(uint32_t address, uint32_t value)
{
    *(volatile uint32_t *)(uintptr_t)address = value;
}

static void io_fence(void)
{
#ifdef __riscv
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
#else
    __atomic_thread_fence(__ATOMIC_SEQ_CST);
#endif
}

enum npu_gdma_result npu_gdma_copy(uint32_t hart, uint32_t channel,
                                   uint32_t source, uint32_t destination,
                                   uint32_t length, uint32_t poll_limit)
{
    uint32_t base, bit, left, done;

    if (!poll_limit || length > 0xffffu ||
        !((hart == 2 && channel == 1) || (hart == 3 && (channel == 0 || channel == 3))))
        return NPU_GDMA_INVALID;
    base = GDMA_BASE + channel * 16;
    bit = 1u << channel;
    for (left = poll_limit; left; left--)
        if (!(read32(base + 8) & GDMA_ENABLE))
            break;
    if (!left)
        return NPU_GDMA_BUSY;
    io_fence();
    write32(GDMA_DONE, bit);
    io_fence();
    if (read32(GDMA_DONE) & bit)
        return NPU_GDMA_STALE_DONE;
    io_fence();
    write32(base, source);
    write32(base + 4, destination);
    io_fence();
    write32(base + 8, length << 16 | 0x23u);
    io_fence();
    for (left = poll_limit; left; left--) {
        done = read32(GDMA_DONE);
        /* Stock WAIT uses ENABLE clear; DONE alone can be stale or early. */
        if ((done & bit) && !(read32(base + 8) & GDMA_ENABLE))
            break;
    }
    if (!left)
        return NPU_GDMA_TIMEOUT;
    io_fence();
    write32(GDMA_DONE, bit);
    io_fence();
    if (read32(GDMA_DONE) & bit)
        return NPU_GDMA_ACK_FAILED;
    return NPU_GDMA_OK;
}
