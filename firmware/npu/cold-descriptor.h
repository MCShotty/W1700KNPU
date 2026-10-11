#ifndef W1700K_NPU_COLD_DESCRIPTOR_H
#define W1700K_NPU_COLD_DESCRIPTOR_H

#include <stdint.h>

#define NPU_COLD_DESCRIPTOR_MAGIC 0x31445343u
#define NPU_COLD_DESCRIPTOR_STEPS 8u
#define NPU_COLD_DESCRIPTOR_WRITES 1536u
#define NPU_COLD_DESCRIPTOR_STATUS 0x80000000u
#define NPU_COLD_DESCRIPTOR_ARENA_BYTES 303168u

static inline uint32_t npu_cold_descriptor_selector(uint32_t step)
{
    static const uint32_t selectors[] = {0, 2, 10, 11, 12, 8, 5, 7};

    return step < NPU_COLD_DESCRIPTOR_STEPS ? selectors[step] : UINT32_MAX;
}

static inline uint32_t npu_cold_descriptor_step(uint32_t selector)
{
    uint32_t i;

    for (i = 0; i < NPU_COLD_DESCRIPTOR_STEPS; i++)
        if (npu_cold_descriptor_selector(i) == selector)
            break;
    return i;
}

static inline uint32_t npu_cold_descriptor_offset(uint32_t step)
{
    static const uint32_t offsets[] = {0, 0x22020, 0x18020, 0x19020,
                                      0x1b020, 0x1f020, 0x6020, 0x26040};

    return step < NPU_COLD_DESCRIPTOR_STEPS ? offsets[step] : UINT32_MAX;
}

static inline int npu_cold_descriptor_arena_valid(uint32_t arena)
{
    return !(arena & 31) && arena >= 0x3e800000u &&
           arena <= 0x3e878000u - NPU_COLD_DESCRIPTOR_ARENA_BYTES;
}

/* A zero expected arena permits initial capture, not physical ownership proof. */
static inline uint32_t npu_cold_descriptor_reply_arena(uint32_t step,
                                                       uint32_t value, uint32_t arena)
{
    uint32_t offset = npu_cold_descriptor_offset(step), captured;

    if (step >= NPU_COLD_DESCRIPTOR_STEPS || value >= 0x20000000u || value < offset)
        return 0;
    captured = (value - offset) | 0x20000000u;
    return npu_cold_descriptor_arena_valid(captured) && (!arena || captured == arena) ? captured : 0;
}

enum npu_cold_descriptor_status {
    NPU_COLD_DESCRIPTOR_OK, NPU_COLD_DESCRIPTOR_ARGUMENT, NPU_COLD_DESCRIPTOR_PLAN,
    NPU_COLD_DESCRIPTOR_REINITIALIZE, NPU_COLD_DESCRIPTOR_FAULT,
    NPU_COLD_DESCRIPTOR_STALE, NPU_COLD_DESCRIPTOR_CORRUPT,
    NPU_COLD_DESCRIPTOR_ORDER, NPU_COLD_DESCRIPTOR_PUBLISH
};

/* Each boot owns one immutable arena and eight one-shot lookups. TX preimages
 * are captured under the caller's lock; partial writes never reset or retire.
 */
struct npu_cold_descriptor_state {
    uint32_t magic, epoch, fault, active, next, completed, arena;
    uint32_t reserved_tx, completed_tx, committed, published;
    uint32_t preimages[NPU_COLD_DESCRIPTOR_WRITES];
};

uint32_t npu_cold_descriptor_begin(struct npu_cold_descriptor_state *, uint32_t arena,
    uint32_t epoch, uint32_t selector, const volatile uint32_t *descriptors);
uint32_t npu_cold_descriptor_reserve(struct npu_cold_descriptor_state *, uint32_t arena,
    uint32_t epoch, uint32_t address, uint32_t value, uint32_t before);
uint32_t npu_cold_descriptor_publish(struct npu_cold_descriptor_state *, uint32_t arena,
    uint32_t epoch, uint32_t address, uint32_t readback);
uint32_t npu_cold_descriptor_finish(struct npu_cold_descriptor_state *, uint32_t arena,
    uint32_t epoch, uint32_t reply, const volatile uint32_t *descriptors);
void npu_cold_descriptor_fault(struct npu_cold_descriptor_state *);

#endif
