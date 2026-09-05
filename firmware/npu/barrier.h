#ifndef W1700K_NPU_BARRIER_H
#define W1700K_NPU_BARRIER_H

#include <stdint.h>

#define NPU_BARRIER_WORKERS 8u
#define NPU_BARRIER_DOMAINS 5u

enum npu_barrier_domain {
    NPU_DRAIN_INGRESS,
    NPU_DRAIN_COPY,
    NPU_DRAIN_PPE_TUNNEL,
    NPU_DRAIN_WIFI_DMA,
    NPU_DRAIN_IRQ_PUBLICATION,
};

enum npu_barrier_action {
    NPU_BARRIER_PARK,
    NPU_BARRIER_REFRESH,
    NPU_BARRIER_RUN,
    NPU_BARRIER_FAULT,
};

/* All fields are naturally aligned, shared, coherent 32-bit words. Only the
 * serialized coordinator writes control/domain fields; each hart owns its slots.
 * Any owner may atomically latch fault; only contained cold init clears it.
 * Cold initialization requires independent containment of every previous user. */
struct npu_barrier {
    uint32_t request;
    uint32_t released;
    uint32_t armed;
    uint32_t prepared;
    uint32_t fault;
    uint32_t parked[NPU_BARRIER_WORKERS];
    uint32_t ready[NPU_BARRIER_WORKERS];
    uint32_t drained[NPU_BARRIER_DOMAINS];
};

void npu_barrier_init(struct npu_barrier *state);
void npu_barrier_fail(struct npu_barrier *state);
uint32_t npu_barrier_stop(struct npu_barrier *state);
enum npu_barrier_action npu_barrier_poll(struct npu_barrier *state,
                                       uint32_t hart, uint32_t *epoch);
int npu_barrier_workers_parked(const struct npu_barrier *state, uint32_t epoch);
int npu_barrier_record_drain(struct npu_barrier *state, uint32_t domain,
                             uint32_t epoch);
int npu_barrier_reclaimable(const struct npu_barrier *state, uint32_t epoch);
int npu_barrier_prepare(struct npu_barrier *state, uint32_t epoch);
int npu_barrier_release(struct npu_barrier *state, uint32_t epoch);
int npu_barrier_refreshed(struct npu_barrier *state, uint32_t hart, uint32_t epoch);
int npu_barrier_arm(struct npu_barrier *state, uint32_t epoch);

#endif
