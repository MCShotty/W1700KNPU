#ifndef W1700K_NPU_BOOTSTRAP_H
#define W1700K_NPU_BOOTSTRAP_H

#include "admission.h"

#define NPU_BOOTSTRAP_MAGIC 0x31505342u
#define NPU_BOOTSTRAP_STEPS 6u
#define NPU_BOOTSTRAP_PACKET_BYTES 12u

enum npu_bootstrap_region {
    NPU_BOOT_BINARY,
    NPU_BOOT_TXCHECK,
    NPU_BOOT_PKT,
    NPU_BOOT_TXPKT,
    NPU_BOOT_BA,
    NPU_BOOT_REQUEST,
    NPU_BOOT_REGIONS,
};

struct npu_bootstrap_range {
    uint32_t base;
    uint32_t bytes;
};

/* Immutable, cold-loader input for the selected MT7996 firmware, not a wire
 * message. Structural validation is not a full consumer-footprint proof. */
struct npu_bootstrap_plan {
    struct npu_bootstrap_range region[NPU_BOOT_REGIONS];
};

struct npu_bootstrap_packet {
    uint32_t header;
    uint32_t api;
    uint32_t value;
};

/* Only the coordinator with local IRQs disabled may access this state. The
 * loader must establish fresh zeroed storage with prior users contained. */
struct npu_bootstrap {
    uint32_t magic;
    uint32_t failed;
    uint32_t step;
    uint32_t inflight;
    uint32_t retained_mask;
    struct npu_bootstrap_packet packet;
    struct npu_bootstrap_plan plan;
};

int npu_bootstrap_init(struct npu_bootstrap *state, const struct npu_bootstrap_plan *plan);
int npu_bootstrap_transport(const struct npu_bootstrap *state, uint32_t address,
                            uint32_t bytes, uint32_t flags);
int npu_bootstrap_begin(struct npu_bootstrap *state, struct npu_admission *admission,
                        struct npu_barrier *barrier,
                        const struct npu_bootstrap_packet *packet, uint32_t bytes);
int npu_bootstrap_finish(struct npu_bootstrap *state, struct npu_admission *admission,
                         struct npu_barrier *barrier, uint32_t result);

#endif
