#ifndef W1700K_NPU_COLD_TX_BUFFER_H
#define W1700K_NPU_COLD_TX_BUFFER_H

#include "bootstrap.h"
#include "cold-descriptor.h"

#define NPU_COLD_TXBUF_MAGIC 0x31425443u
#define NPU_COLD_TXBUF_STEPS 6u
#define NPU_COLD_TXBUF_MAILBOXES 8u
#define NPU_COLD_TXBUF_STORES 53260u
#define NPU_COLD_TXBUF_RECORDS (NPU_COLD_TXBUF_MAILBOXES + NPU_COLD_TXBUF_STEPS)
#define NPU_COLD_TXBUF_SELECTORS {0, 5, 10, 2, 7, 12}

static inline uint32_t npu_cold_txbuf_step(uint32_t selector)
{
    static const uint32_t values[] = NPU_COLD_TXBUF_SELECTORS;
    uint32_t i;

    for (i = 0; i < NPU_COLD_TXBUF_STEPS; i++)
        if (values[i] == selector)
            break;
    return i;
}

struct npu_cold_txbuf_plan {
    uint32_t arena, endpoint_base, endpoint_bytes;
    uint32_t host[NPU_COLD_TXBUF_STEPS], mailbox[NPU_COLD_TXBUF_MAILBOXES];
    struct npu_bootstrap_plan boot;
};

struct npu_cold_txbuf_store {
    uint32_t address, bytes, value;
};

enum npu_cold_txbuf_status {
    NPU_COLD_TXBUF_OK, NPU_COLD_TXBUF_ARGUMENT, NPU_COLD_TXBUF_PLAN,
    NPU_COLD_TXBUF_REINITIALIZE, NPU_COLD_TXBUF_FAULT,
    NPU_COLD_TXBUF_STALE, NPU_COLD_TXBUF_CORRUPT,
    NPU_COLD_TXBUF_ORDER, NPU_COLD_TXBUF_PUBLISH
};

/* The caller owns exclusion and the exact mapped preimage spans. No operation
 * rolls back, resets or retires this boot's claimed stores or host buffers.
 */
struct npu_cold_txbuf_state {
    uint32_t magic, epoch, fault, active, next, completed, reserved;
    uint32_t committed, published, from, until;
    struct npu_cold_txbuf_plan plan;
    uint32_t preimages[NPU_COLD_TXBUF_STORES];
};

uint32_t npu_cold_txbuf_selector(uint32_t step);
uint32_t npu_cold_txbuf_bytes(uint32_t step);
uint32_t npu_cold_txbuf_count(uint32_t step);
int npu_cold_txbuf_plan_valid(const struct npu_cold_txbuf_plan *);
int npu_cold_txbuf_dma_valid(const struct npu_cold_txbuf_plan *, uint32_t enrolled);
void npu_cold_txbuf_plan_copy(struct npu_cold_txbuf_plan *, const struct npu_cold_txbuf_plan *);
int npu_cold_txbuf_plan_equal(const struct npu_cold_txbuf_plan *, const struct npu_cold_txbuf_plan *);
uint32_t npu_cold_txbuf_recipe(const struct npu_cold_txbuf_plan *, uint32_t step,
    uint32_t index, struct npu_cold_txbuf_store *);
uint32_t npu_cold_txbuf_begin(struct npu_cold_txbuf_state *,
    const struct npu_cold_txbuf_plan *, uint32_t epoch, uint32_t selector,
    uint32_t host, const volatile uint32_t *metadata, const volatile uint32_t *records);
uint32_t npu_cold_txbuf_reserve(struct npu_cold_txbuf_state *,
    const struct npu_cold_txbuf_plan *, uint32_t epoch, uint32_t address,
    uint32_t bytes, uint32_t value, uint32_t before);
uint32_t npu_cold_txbuf_publish(struct npu_cold_txbuf_state *,
    const struct npu_cold_txbuf_plan *, uint32_t epoch, uint32_t address,
    uint32_t bytes, uint32_t readback);
uint32_t npu_cold_txbuf_finish(struct npu_cold_txbuf_state *,
    const struct npu_cold_txbuf_plan *, uint32_t epoch,
    const volatile uint32_t *metadata, const volatile uint32_t *records);
void npu_cold_txbuf_fault(struct npu_cold_txbuf_state *);

#endif
