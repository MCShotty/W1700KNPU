#ifndef W1700K_NPU_RRO_LIFETIME_H
#define W1700K_NPU_RRO_LIFETIME_H

#include "barrier.h"

#define NPU_RRO_MAGIC 0x314f5252u
#define NPU_RRO_BLOCKS 128u
#define NPU_RRO_SESSIONS 1025u
#define NPU_RRO_PUBLICATIONS (NPU_RRO_BLOCKS + 1u)
#define NPU_RRO_MAX_EXTENTS 139u
#define NPU_RRO_BLOCK_BYTES 65536u
#define NPU_RRO_SESSION_BYTES 8192u
#define NPU_RRO_DRAIN_DOMAINS NPU_BARRIER_DOMAINS

enum npu_rro_profile {
    NPU_RRO_V3,
    NPU_RRO_V3_1,
    NPU_RRO_V3_1_WED,
};

enum npu_rro_role {
    NPU_RRO_BA,
    NPU_RRO_ELEMENT,
    NPU_RRO_MSDU,
    NPU_RRO_EMI_CPU,
    NPU_RRO_EMI_DMA,
    NPU_RRO_SESSION,
};

enum npu_rro_phase {
    NPU_RRO_BUILDING = 1,
    NPU_RRO_LIVE,
    NPU_RRO_CLOSING,
    NPU_RRO_DRAIN_RECORDED,
};

enum npu_rro_reset_phase {
    NPU_RRO_RESET_IDLE,
    NPU_RRO_RESET_QUEUED,
    NPU_RRO_RESET_NPU_POSSIBLE,
    NPU_RRO_RESET_NPU_CONFIRMED,
    NPU_RRO_RESET_MCU_POSSIBLE,
    NPU_RRO_RESET_COMPLETE,
};

enum npu_rro_exposure {
    NPU_RRO_ALLOCATED = 1u,
    NPU_RRO_NPU_POSSIBLE = 2u,
    NPU_RRO_NPU_CONFIRMED = 4u,
    NPU_RRO_HARDWARE_POSSIBLE = 8u,
};

enum npu_rro_status {
    NPU_RRO_OK,
    NPU_RRO_ARGUMENT,
    NPU_RRO_REINITIALIZE,
    NPU_RRO_STALE,
    NPU_RRO_ORDER,
    NPU_RRO_BUSY,
    NPU_RRO_HELD,
    NPU_RRO_DUPLICATE,
    NPU_RRO_EXHAUSTED,
    NPU_RRO_CORRUPT,
    NPU_RRO_PUBLICATION_FAILED,
    NPU_RRO_NPU_RESET_FAILED,
    NPU_RRO_MCU_RESET_FAILED,
};

struct npu_rro_identity {
    uint32_t provider_lo, provider_hi, endpoint_lo, endpoint_hi;
    uint32_t boot_lo, boot_hi, nonce_lo, nonce_hi, epoch;
};

struct npu_rro_span {
    uint32_t address, bytes;
};

struct npu_rro_plan {
    struct npu_rro_identity identity;
    uint32_t profile;
    struct npu_rro_span mailbox[8], tx[6], rx_event, native[6], bar;
};

struct npu_rro_extent {
    uint32_t role, index, bytes, cpu_lo, cpu_hi, dma_lo, dma_hi;
};

struct npu_rro_publication {
    uint32_t ticket, error;
};

struct npu_rro_reset {
    uint32_t generation, request_generation, ticket, phase, npu_error, mcu_error;
};

/* Caller serialization and real provider/endpoint reference ownership are
 * mandatory. Only error may be latched asynchronously. Opaque CPU/device
 * identities are exact bookkeeping, not proof that references are pinned.
 * No operation frees, cancels, rearms, resets or reinitializes a lease.
 */
struct npu_rro_lifetime {
    uint32_t magic, error, phase, allocated, confirmed, last_ticket;
    uint32_t hardware_exposed, retirement_ticket, retirement_epoch, cpu_joined;
    uint32_t drained[NPU_RRO_DRAIN_DOMAINS];
    struct npu_rro_plan plan;
    struct npu_rro_extent extents[NPU_RRO_MAX_EXTENTS];
    uint32_t exposure[NPU_RRO_MAX_EXTENTS];
    struct npu_rro_publication publication[NPU_RRO_PUBLICATIONS];
    struct npu_rro_reset resets[NPU_RRO_SESSIONS];
};

/* Selectors0/1/3 have four payload words. Scalar constructors2/7 are not part
 * of this interface. A transport must bind each ticket to its actual transfer.
 */
struct npu_rro_command {
    uint32_t selector, words[4];
};

struct npu_rro_retirement {
    struct npu_rro_identity identity;
    uint32_t ticket, epoch, cpu_joined, drained[NPU_RRO_DRAIN_DOMAINS];
    uint32_t allocated, possible_publications, confirmed_publications;
    uint32_t queued_resets, possible_npu_resets, possible_mcu_resets;
    uint32_t error, phase;
};

uint32_t npu_rro_extent_count(uint32_t profile);
uint32_t npu_rro_extent_geometry(uint32_t profile, uint32_t ordinal,
                                struct npu_rro_extent *out);
uint32_t npu_rro_open(struct npu_rro_lifetime *, const struct npu_rro_plan *);
void npu_rro_fault(struct npu_rro_lifetime *, uint32_t error);
uint32_t npu_rro_enroll(struct npu_rro_lifetime *, const struct npu_rro_plan *,
                       const struct npu_rro_extent *);
uint32_t npu_rro_publish_begin(struct npu_rro_lifetime *, const struct npu_rro_plan *,
    uint32_t ordinal, uint32_t *ticket, struct npu_rro_command *);
uint32_t npu_rro_publish_complete(struct npu_rro_lifetime *, const struct npu_rro_plan *,
    uint32_t ordinal, uint32_t ticket, int transport_error);
uint32_t npu_rro_hardware_begin(struct npu_rro_lifetime *, const struct npu_rro_plan *);
uint32_t npu_rro_reset_queue(struct npu_rro_lifetime *, const struct npu_rro_plan *,
    uint32_t session, uint32_t generation, uint32_t *ticket);
uint32_t npu_rro_reset_npu_begin(struct npu_rro_lifetime *, const struct npu_rro_plan *,
    uint32_t session, uint32_t generation, uint32_t ticket, struct npu_rro_command *);
uint32_t npu_rro_reset_npu_complete(struct npu_rro_lifetime *, const struct npu_rro_plan *,
    uint32_t session, uint32_t generation, uint32_t ticket, int transport_error);
uint32_t npu_rro_reset_mcu_begin(struct npu_rro_lifetime *, const struct npu_rro_plan *,
    uint32_t session, uint32_t generation, uint32_t ticket);
uint32_t npu_rro_reset_mcu_complete(struct npu_rro_lifetime *, const struct npu_rro_plan *,
    uint32_t session, uint32_t generation, uint32_t ticket, int transport_error);
uint32_t npu_rro_retirement_begin(struct npu_rro_lifetime *, const struct npu_rro_plan *,
    uint32_t stop_epoch, uint32_t *ticket);
uint32_t npu_rro_retirement_join(struct npu_rro_lifetime *, const struct npu_rro_plan *,
    uint32_t ticket, uint32_t epoch);
uint32_t npu_rro_retirement_record(struct npu_rro_lifetime *, const struct npu_rro_plan *,
    uint32_t ticket, uint32_t epoch, uint32_t domain);
uint32_t npu_rro_retirement_snapshot(const struct npu_rro_lifetime *, const struct npu_rro_plan *,
    struct npu_rro_retirement *);

/* Even all five recorded domains and a CPU join grant NO reclamation authority.
 * Real IRQ/DMA/firmware/cache/PMA witnesses and physical retirement integration
 * are separate obligations. Current operational RRO admission remains closed.
 */
#endif
