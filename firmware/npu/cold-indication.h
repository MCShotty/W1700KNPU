#ifndef W1700K_NPU_COLD_INDICATION_H
#define W1700K_NPU_COLD_INDICATION_H

#include <stdint.h>

#define NPU_COLD_INDICATION_MAGIC 0x31444e49u
#define NPU_COLD_INDICATION_COUNT 1536u
#define NPU_COLD_INDICATION_BYTES (NPU_COLD_INDICATION_COUNT * 8u)
#define NPU_COLD_INDICATION_STATUS 0xe0000000u

struct npu_cold_indication_plan {
    uint32_t base, bytes;
};

struct npu_cold_indication_state {
    uint32_t magic, epoch, fault, active;
    uint32_t committed, published, base, count;
};

enum npu_cold_indication_status {
    NPU_COLD_INDICATION_OK,
    NPU_COLD_INDICATION_ARGUMENT,
    NPU_COLD_INDICATION_PLAN,
    NPU_COLD_INDICATION_REINITIALIZE,
    NPU_COLD_INDICATION_FAULT,
    NPU_COLD_INDICATION_STALE,
    NPU_COLD_INDICATION_CORRUPT,
    NPU_COLD_INDICATION_FRESHNESS,
    NPU_COLD_INDICATION_ORDER,
    NPU_COLD_INDICATION_PUBLISH,
};

/* The coordinator supplies an immutable reserved span and its valid, nonaliasing
 * word view under a held epoch1 lease. Reserve precedes the native store; publish
 * follows readback. Faults retain the reservation/committed prefix. No reset,
 * retirement, DMA grant, cache or earlier-user exclusion is established here. */
uint32_t npu_cold_indication_begin(struct npu_cold_indication_state *state,
    const struct npu_cold_indication_plan *plan, uint32_t epoch,
    const volatile uint32_t *words);
uint32_t npu_cold_indication_reserve(struct npu_cold_indication_state *state,
    const struct npu_cold_indication_plan *plan, uint32_t epoch,
    uint32_t address, uint32_t value, const volatile uint32_t *words);
uint32_t npu_cold_indication_publish(struct npu_cold_indication_state *state,
    const struct npu_cold_indication_plan *plan, uint32_t epoch,
    uint32_t address, const volatile uint32_t *words);
uint32_t npu_cold_indication_pending(struct npu_cold_indication_state *state,
    const struct npu_cold_indication_plan *plan, uint32_t epoch,
    uint32_t address, uint32_t value, const volatile uint32_t *words);
uint32_t npu_cold_indication_finish(struct npu_cold_indication_state *state,
    const struct npu_cold_indication_plan *plan, uint32_t epoch,
    const volatile uint32_t *words);
void npu_cold_indication_fault(struct npu_cold_indication_state *state);

#endif
