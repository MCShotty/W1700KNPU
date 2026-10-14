#ifndef W1700K_NPU_COLD_INODE_H
#define W1700K_NPU_COLD_INODE_H

#include "cold-pcie-tail.h"

#define NPU_COLD_INODE_MAGIC 0x31444e49u
#define NPU_COLD_INODE_ICV 0x3e8bc470u
#define NPU_COLD_INODE_ICV_BYTES 4104u
#define NPU_COLD_INODE_FIRST_STORES 1030u
#define NPU_COLD_INODE_STORES 1036u

struct npu_cold_inode_plan {
    struct npu_cold_pcie_tail_plan prior;
    uint32_t icv, icv_bytes;
};

struct npu_cold_inode_context {
    const struct npu_cold_pcie_tail_state *pcie;
    struct npu_cold_pcie_tail_context prior;
    npu_cold_txdone_read_fn read;
    void *opaque;
};

struct npu_cold_inode_store {
    uint32_t address, bytes, value;
};

/* No worker/IRQ/reclaim authority. Caller retains original locks, native
 * identity, stack capacity and exclusive mapped storage across each operation. */
struct npu_cold_inode_state {
    uint32_t magic, epoch, fault, active, stage, reserved, completed;
    uint32_t committed, published, captured;
    struct npu_cold_inode_plan plan;
    uint32_t before[NPU_COLD_INODE_STORES];
};

enum npu_cold_inode_status {
    NPU_COLD_INODE_OK, NPU_COLD_INODE_ARGUMENT, NPU_COLD_INODE_PLAN,
    NPU_COLD_INODE_REINITIALIZE, NPU_COLD_INODE_STALE,
    NPU_COLD_INODE_ORDER, NPU_COLD_INODE_READ, NPU_COLD_INODE_PUBLISH
};

int npu_cold_inode_plan_valid(const struct npu_cold_inode_plan *);
uint32_t npu_cold_inode_selector(uint32_t stage);
uint32_t npu_cold_inode_recipe(const struct npu_cold_inode_plan *, uint32_t index,
                              struct npu_cold_inode_store *);
void npu_cold_inode_fault(struct npu_cold_inode_state *);
uint32_t npu_cold_inode_begin(struct npu_cold_inode_state *, const struct npu_cold_inode_plan *,
    uint32_t epoch, const struct npu_cold_inode_context *, uint32_t selector, uint32_t value);
uint32_t npu_cold_inode_reserve(struct npu_cold_inode_state *, const struct npu_cold_inode_plan *,
    uint32_t epoch, const struct npu_cold_inode_context *, uint32_t address,
    uint32_t bytes, uint32_t value, uint32_t before);
uint32_t npu_cold_inode_publish(struct npu_cold_inode_state *, const struct npu_cold_inode_plan *,
    uint32_t epoch, const struct npu_cold_inode_context *, uint32_t address,
    uint32_t bytes, uint32_t readback);
uint32_t npu_cold_inode_finish(struct npu_cold_inode_state *, const struct npu_cold_inode_plan *,
    uint32_t epoch, const struct npu_cold_inode_context *);
int npu_cold_inode_live(const struct npu_cold_inode_state *, const struct npu_cold_inode_plan *,
    uint32_t epoch, const struct npu_cold_inode_context *);

#endif
