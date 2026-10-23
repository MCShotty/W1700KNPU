#ifndef W1700K_NPU_RRO_NATIVE_H
#define W1700K_NPU_RRO_NATIVE_H

#include "rro-lifetime.h"

#define NPU_RRO_NATIVE_BLOCK_TABLE 0x3e901fdcu
#define NPU_RRO_NATIVE_SESSION_TABLE 0x3e90458cu

typedef int (*npu_rro_native_read_fn)(void *, uint32_t address, uint32_t bytes, uint32_t *value);
typedef int (*npu_rro_native_write_fn)(void *, uint32_t address, uint32_t bytes, uint32_t value);

/* The caller owns the journal, immutable plan/context, actual mapped backing
 * and CPU exclusion for the entire call. These callbacks are not DMA drain or
 * allocation capabilities. A failed/partial operation never releases backing.
 */
struct npu_rro_native_context {
    npu_rro_native_read_fn read;
    npu_rro_native_write_fn write;
    void *opaque;
};

uint32_t npu_rro_native_publish(struct npu_rro_lifetime *, const struct npu_rro_plan *,
    uint32_t ordinal, const struct npu_rro_native_context *);
uint32_t npu_rro_native_reset(struct npu_rro_lifetime *, const struct npu_rro_plan *,
    uint32_t session, uint32_t generation, uint32_t ticket, const struct npu_rro_native_context *);

#endif
