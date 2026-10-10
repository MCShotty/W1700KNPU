#ifndef W1700K_NPU_COLD_TX_H
#define W1700K_NPU_COLD_TX_H

#include <stdint.h>

#define NPU_COLD_TX_MAGIC 0x31585443u
#define NPU_COLD_TX_ARENA_BYTES 303168u
#define NPU_COLD_TX_TOKEN_LIMIT 8192u
#define NPU_COLD_TX_WRITES 11u

enum npu_cold_tx_status {
    NPU_COLD_TX_OK, NPU_COLD_TX_ARGUMENT, NPU_COLD_TX_PLAN,
    NPU_COLD_TX_REINITIALIZE, NPU_COLD_TX_FAULT, NPU_COLD_TX_STALE,
    NPU_COLD_TX_CORRUPT, NPU_COLD_TX_ORDER, NPU_COLD_TX_PUBLISH
};

struct npu_cold_tx_plan {
    uint32_t arena, arena_bytes, endpoint_base, endpoint_bytes, host0, host2;
    uint32_t register_before[4], token_before;
};

/* Stages are TX0, TX2, then token publication. Claims never reset or retire. */
struct npu_cold_tx_state {
    uint32_t magic, epoch, fault, active, reserved, completed;
    uint32_t committed, published, stage;
    struct npu_cold_tx_plan plan;
};

uint32_t npu_cold_tx_begin(struct npu_cold_tx_state *, const struct npu_cold_tx_plan *,
                         uint32_t epoch, uint32_t stage);
uint32_t npu_cold_tx_reserve(struct npu_cold_tx_state *, const struct npu_cold_tx_plan *,
    uint32_t epoch, uint32_t address, uint32_t value, uint32_t bytes, uint32_t before);
uint32_t npu_cold_tx_publish(struct npu_cold_tx_state *, const struct npu_cold_tx_plan *,
    uint32_t epoch, uint32_t address, uint32_t bytes, uint32_t readback);
uint32_t npu_cold_tx_finish(struct npu_cold_tx_state *, const struct npu_cold_tx_plan *,
                          uint32_t epoch, const uint32_t *readback);
void npu_cold_tx_fault(struct npu_cold_tx_state *);

#endif
