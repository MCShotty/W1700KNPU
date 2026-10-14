#ifndef W1700K_NPU_COLD_TXDONE_H
#define W1700K_NPU_COLD_TXDONE_H

#include "cold-packet.h"
#include "cold-rx-event.h"

#define NPU_COLD_TXDONE_MAGIC 0x31445443u
#define NPU_COLD_TXDONE_PREFIX 2560u
#define NPU_COLD_TXDONE_IDS 512u
#define NPU_COLD_TXDONE_OCCUPIED 2048u
#define NPU_COLD_TXDONE_IDS_POOL 0x3e8adc70u
#define NPU_COLD_TXDONE_CAPACITY 8192u
#define NPU_COLD_TXDONE_BITMAP_WORDS (NPU_COLD_TXDONE_CAPACITY / 32u)
#define NPU_COLD_TXDONE_DESCRIPTOR_STORES (2u + NPU_COLD_TXDONE_IDS * 6u)
#define NPU_COLD_TXDONE_STORES (NPU_COLD_TXDONE_DESCRIPTOR_STORES + \
    NPU_COLD_TXDONE_OCCUPIED * 3u + NPU_COLD_TXDONE_CAPACITY * 2u + 4u)

struct npu_cold_txdone_plan {
    struct npu_cold_rx_event_plan prior;
    uint32_t packet_pool, ids_pool, temporary, skb_queue;
};

struct npu_cold_txdone_store {
    uint32_t address, bytes, value;
};

enum npu_cold_txdone_status {
    NPU_COLD_TXDONE_OK, NPU_COLD_TXDONE_ARGUMENT, NPU_COLD_TXDONE_PLAN,
    NPU_COLD_TXDONE_REINITIALIZE, NPU_COLD_TXDONE_STALE,
    NPU_COLD_TXDONE_CORRUPT, NPU_COLD_TXDONE_ORDER, NPU_COLD_TXDONE_PUBLISH
};

/* The native caller supplies original locks, exact typed allocations, immutable
 * TX descriptor inputs, prior-owner liveness and readback at every bound store.
 * This records possible effects before stores and never resets or retires them.
 * It is not DMA visibility, physical containment or a release authority.
 */
struct npu_cold_txdone_state {
    uint32_t magic, epoch, fault, active, reserved, committed, published;
    uint32_t claims_reserved, claims_committed, claims_published, skb_reserved, next_free;
    uint32_t before, pending_value, pending_address, pending_bytes;
    struct npu_cold_txdone_plan plan;
    uint32_t prefix[NPU_COLD_PACKET_WORDS], ids[NPU_COLD_TXDONE_IDS];
    uint32_t occupied[NPU_COLD_TXDONE_OCCUPIED], occupied_bitmap[NPU_COLD_TXDONE_BITMAP_WORDS];
};

int npu_cold_txdone_plan_valid(const struct npu_cold_txdone_plan *);
void npu_cold_txdone_plan_copy(struct npu_cold_txdone_plan *, const struct npu_cold_txdone_plan *);
int npu_cold_txdone_plan_equal(const struct npu_cold_txdone_plan *, const struct npu_cold_txdone_plan *);
void npu_cold_txdone_fault(struct npu_cold_txdone_state *);
uint32_t npu_cold_txdone_begin(struct npu_cold_txdone_state *, const struct npu_cold_txdone_plan *,
    uint32_t epoch, const struct npu_cold_rx_event_state *, uint32_t rx_readback,
    const struct npu_cold_packet_state *);
uint32_t npu_cold_txdone_claim_reserve(struct npu_cold_txdone_state *,
    const struct npu_cold_txdone_plan *, uint32_t epoch, const struct npu_cold_packet_state *);
uint32_t npu_cold_txdone_claim_publish(struct npu_cold_txdone_state *,
    const struct npu_cold_txdone_plan *, uint32_t epoch, const struct npu_cold_packet_state *,
    const struct npu_cold_packet_queue_result *);
int npu_cold_txdone_packets_live(const struct npu_cold_txdone_state *,
    const struct npu_cold_txdone_plan *, uint32_t epoch, const struct npu_cold_packet_state *);
uint32_t npu_cold_txdone_skb_begin(struct npu_cold_txdone_state *, const struct npu_cold_txdone_plan *,
    uint32_t epoch, const struct npu_cold_rx_event_state *, uint32_t rx_readback,
    const struct npu_cold_packet_state *, const volatile uint32_t *occupied);
uint32_t npu_cold_txdone_recipe(const struct npu_cold_txdone_state *, struct npu_cold_txdone_store *);
uint32_t npu_cold_txdone_reserve(struct npu_cold_txdone_state *, const struct npu_cold_txdone_plan *,
    uint32_t epoch, uint32_t address, uint32_t bytes, uint32_t value, uint32_t before);
uint32_t npu_cold_txdone_publish(struct npu_cold_txdone_state *, const struct npu_cold_txdone_plan *,
    uint32_t epoch, uint32_t address, uint32_t bytes, uint32_t readback);
uint32_t npu_cold_txdone_finish(struct npu_cold_txdone_state *, const struct npu_cold_txdone_plan *,
    uint32_t epoch, const struct npu_cold_rx_event_state *, uint32_t rx_readback,
    const struct npu_cold_packet_state *, uint32_t ready);
int npu_cold_txdone_live(const struct npu_cold_txdone_state *, const struct npu_cold_txdone_plan *,
    uint32_t epoch, const struct npu_cold_rx_event_state *, uint32_t rx_readback,
    const struct npu_cold_packet_state *, uint32_t ready);
typedef int (*npu_cold_txdone_read_fn)(void *, uint32_t address, uint32_t bytes, uint32_t *value);
/* The reader must enforce mapped spans and exclusion. This inspects final
 * values, not every transient constructor store, and never retires ownership.
 */
int npu_cold_txdone_memory_live(const struct npu_cold_txdone_state *,
    const struct npu_cold_txdone_plan *, uint32_t epoch,
    const struct npu_cold_rx_event_state *, uint32_t rx_readback,
    const struct npu_cold_packet_state *, uint32_t ready,
    npu_cold_txdone_read_fn, void *);

#endif
