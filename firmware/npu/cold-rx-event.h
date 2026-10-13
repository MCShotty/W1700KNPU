#ifndef W1700K_NPU_COLD_RX_EVENT_H
#define W1700K_NPU_COLD_RX_EVENT_H

#include "cold-tx-buffer.h"

#define NPU_COLD_RX_EVENT_MAGIC 0x31455852u
#define NPU_COLD_RX_EVENT_COUNT 512u
#define NPU_COLD_RX_EVENT_STRIDE 16u
#define NPU_COLD_RX_EVENT_BYTES (NPU_COLD_RX_EVENT_COUNT * NPU_COLD_RX_EVENT_STRIDE)
#define NPU_COLD_RX_EVENT_METADATA 0x3e903964u

struct npu_cold_rx_event_plan {
    struct npu_cold_txbuf_plan prior;
    uint32_t ring;
};

enum npu_cold_rx_event_status {
    NPU_COLD_RX_EVENT_OK, NPU_COLD_RX_EVENT_ARGUMENT, NPU_COLD_RX_EVENT_PLAN,
    NPU_COLD_RX_EVENT_REINITIALIZE, NPU_COLD_RX_EVENT_FAULT,
    NPU_COLD_RX_EVENT_STALE, NPU_COLD_RX_EVENT_CORRUPT,
    NPU_COLD_RX_EVENT_ORDER, NPU_COLD_RX_EVENT_PUBLISH
};

/* Exclusion, exact mapped spans and prior-owner liveness belong to the caller.
 * Failed reservations/effects remain retained; no reset or retirement exists.
 */
struct npu_cold_rx_event_state {
    uint32_t magic, epoch, fault, active, reserved, committed, published, before;
    struct npu_cold_rx_event_plan plan;
};

int npu_cold_rx_event_dma_valid(const struct npu_cold_txbuf_plan *, uint32_t enrolled,
                              uint32_t ring);
int npu_cold_rx_event_plan_valid(const struct npu_cold_rx_event_plan *);
void npu_cold_rx_event_plan_copy(struct npu_cold_rx_event_plan *,
                                 const struct npu_cold_rx_event_plan *);
int npu_cold_rx_event_plan_equal(const struct npu_cold_rx_event_plan *,
                                const struct npu_cold_rx_event_plan *);
uint32_t npu_cold_rx_event_value(uint32_t ring);
void npu_cold_rx_event_fault(struct npu_cold_rx_event_state *);
uint32_t npu_cold_rx_event_begin(struct npu_cold_rx_event_state *,
    const struct npu_cold_rx_event_plan *, uint32_t epoch, uint32_t before);
uint32_t npu_cold_rx_event_reserve(struct npu_cold_rx_event_state *,
    const struct npu_cold_rx_event_plan *, uint32_t epoch, uint32_t address,
    uint32_t bytes, uint32_t value, uint32_t before);
uint32_t npu_cold_rx_event_publish(struct npu_cold_rx_event_state *,
    const struct npu_cold_rx_event_plan *, uint32_t epoch, uint32_t address,
    uint32_t bytes, uint32_t readback);
uint32_t npu_cold_rx_event_finish(struct npu_cold_rx_event_state *,
    const struct npu_cold_rx_event_plan *, uint32_t epoch, uint32_t readback);
int npu_cold_rx_event_live(const struct npu_cold_rx_event_state *,
    const struct npu_cold_rx_event_plan *, uint32_t epoch, uint32_t readback);

#endif
