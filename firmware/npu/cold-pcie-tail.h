#ifndef W1700K_NPU_COLD_PCIE_TAIL_H
#define W1700K_NPU_COLD_PCIE_TAIL_H

#include "cold-rx-pcie.h"
#include "cold-tx.h"

#define NPU_COLD_PCIE_TAIL_MAGIC 0x31545043u
#define NPU_COLD_PCIE_TAIL_STAGES 3u
#define NPU_COLD_PCIE_TAIL_STORES 9u

struct npu_cold_pcie_tail_plan {
    struct npu_cold_rx_pcie_plan prior;
    struct npu_cold_tx_plan tx;
};

struct npu_cold_pcie_tail_context {
    const struct npu_cold_rx_pcie_state *pcie;
    const struct npu_cold_tx_state *tx;
    struct npu_cold_rx_pcie_context prior;
    npu_cold_txdone_read_fn read;
    void *opaque;
    uint32_t pcie_readback;
};

struct npu_cold_pcie_tail_store {
    uint32_t address, bytes, value;
};

enum npu_cold_pcie_tail_status {
    NPU_COLD_PCIE_TAIL_OK, NPU_COLD_PCIE_TAIL_ARGUMENT, NPU_COLD_PCIE_TAIL_PLAN,
    NPU_COLD_PCIE_TAIL_REINITIALIZE, NPU_COLD_PCIE_TAIL_STALE,
    NPU_COLD_PCIE_TAIL_ORDER, NPU_COLD_PCIE_TAIL_READ, NPU_COLD_PCIE_TAIL_PUBLISH
};

/* Caller retains native session, original locks, mapped spans and exclusion.
 * Possible effects are committed before stores; no reset or retirement API.
 */
struct npu_cold_pcie_tail_state {
    uint32_t magic, epoch, fault, active, stage, reserved, completed;
    uint32_t committed, published, captured;
    struct npu_cold_pcie_tail_plan plan;
    uint32_t before[NPU_COLD_PCIE_TAIL_STORES];
};

int npu_cold_pcie_tail_plan_valid(const struct npu_cold_pcie_tail_plan *);
uint32_t npu_cold_pcie_tail_selector(uint32_t stage);
uint32_t npu_cold_pcie_tail_value(const struct npu_cold_pcie_tail_plan *, uint32_t stage);
uint32_t npu_cold_pcie_tail_recipe(const struct npu_cold_pcie_tail_plan *,
                                  uint32_t index, struct npu_cold_pcie_tail_store *);
void npu_cold_pcie_tail_fault(struct npu_cold_pcie_tail_state *);
uint32_t npu_cold_pcie_tail_begin(struct npu_cold_pcie_tail_state *,
    const struct npu_cold_pcie_tail_plan *, uint32_t epoch,
    const struct npu_cold_pcie_tail_context *, uint32_t selector, uint32_t value);
uint32_t npu_cold_pcie_tail_reserve(struct npu_cold_pcie_tail_state *,
    const struct npu_cold_pcie_tail_plan *, uint32_t epoch,
    const struct npu_cold_pcie_tail_context *, uint32_t address, uint32_t bytes,
    uint32_t value, uint32_t before);
uint32_t npu_cold_pcie_tail_publish(struct npu_cold_pcie_tail_state *,
    const struct npu_cold_pcie_tail_plan *, uint32_t epoch,
    const struct npu_cold_pcie_tail_context *, uint32_t address, uint32_t bytes, uint32_t readback);
uint32_t npu_cold_pcie_tail_finish(struct npu_cold_pcie_tail_state *,
    const struct npu_cold_pcie_tail_plan *, uint32_t epoch,
    const struct npu_cold_pcie_tail_context *);
int npu_cold_pcie_tail_live(const struct npu_cold_pcie_tail_state *,
    const struct npu_cold_pcie_tail_plan *, uint32_t epoch,
    const struct npu_cold_pcie_tail_context *);

#endif
