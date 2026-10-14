#ifndef W1700K_NPU_COLD_RX_PCIE_H
#define W1700K_NPU_COLD_RX_PCIE_H

#include "cold-txdone.h"

#define NPU_COLD_RX_PCIE_MAGIC 0x31455052u
#define NPU_COLD_RX_PCIE_METADATA 0x3e902a90u
#define NPU_COLD_RX_PCIE_REGISTER 0xd4590u
#define NPU_COLD_RX_PCIE_REGISTER_BYTES 12u

struct npu_cold_rx_pcie_plan {
    struct npu_cold_txdone_plan prior;
};

/* Borrowed only for a call; native session, typed pools, neighbors, mapped
 * spans and exclusion remain the binding's responsibility, not this reader's.
 */
struct npu_cold_rx_pcie_context {
    const struct npu_cold_txdone_state *done;
    const struct npu_cold_rx_event_state *rx;
    const struct npu_cold_packet_state *packets;
    npu_cold_txdone_read_fn read;
    void *opaque;
    uint32_t rx_readback, ready;
};

enum npu_cold_rx_pcie_status {
    NPU_COLD_RX_PCIE_OK, NPU_COLD_RX_PCIE_ARGUMENT, NPU_COLD_RX_PCIE_PLAN,
    NPU_COLD_RX_PCIE_REINITIALIZE, NPU_COLD_RX_PCIE_STALE,
    NPU_COLD_RX_PCIE_ORDER, NPU_COLD_RX_PCIE_PUBLISH
};

/* Possible effects are retained before the store. No reset/retirement API. */
struct npu_cold_rx_pcie_state {
    uint32_t magic, epoch, fault, active, reserved, committed, published, before;
    struct npu_cold_rx_pcie_plan plan;
};

int npu_cold_rx_pcie_plan_valid(const struct npu_cold_rx_pcie_plan *);
uint32_t npu_cold_rx_pcie_value(const struct npu_cold_rx_pcie_plan *);
void npu_cold_rx_pcie_fault(struct npu_cold_rx_pcie_state *);
uint32_t npu_cold_rx_pcie_begin(struct npu_cold_rx_pcie_state *,
    const struct npu_cold_rx_pcie_plan *, uint32_t epoch,
    const struct npu_cold_rx_pcie_context *, uint32_t before);
uint32_t npu_cold_rx_pcie_reserve(struct npu_cold_rx_pcie_state *,
    const struct npu_cold_rx_pcie_plan *, uint32_t epoch,
    const struct npu_cold_rx_pcie_context *, uint32_t address,
    uint32_t bytes, uint32_t value, uint32_t before);
uint32_t npu_cold_rx_pcie_publish(struct npu_cold_rx_pcie_state *,
    const struct npu_cold_rx_pcie_plan *, uint32_t epoch,
    const struct npu_cold_rx_pcie_context *, uint32_t address,
    uint32_t bytes, uint32_t readback);
uint32_t npu_cold_rx_pcie_finish(struct npu_cold_rx_pcie_state *,
    const struct npu_cold_rx_pcie_plan *, uint32_t epoch,
    const struct npu_cold_rx_pcie_context *, uint32_t readback);
int npu_cold_rx_pcie_live(const struct npu_cold_rx_pcie_state *,
    const struct npu_cold_rx_pcie_plan *, uint32_t epoch,
    const struct npu_cold_rx_pcie_context *, uint32_t readback);

#endif
