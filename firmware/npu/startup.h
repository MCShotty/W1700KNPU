#ifndef W1700K_NPU_STARTUP_H
#define W1700K_NPU_STARTUP_H

#define NPU_STARTUP_MAGIC 0x3153504e
#define NPU_STARTUP_VERSION 1
#define NPU_STARTUP_BYTES 64

#ifndef __ASSEMBLER__
#include "admission.h"

enum npu_startup_phase {
    NPU_STARTUP_FRESH,
    NPU_STARTUP_INITIALIZING,
    NPU_STARTUP_READY,
    NPU_STARTUP_FAILED,
};

enum npu_startup_action {
    NPU_STARTUP_WAIT,
    NPU_STARTUP_INITIALIZE,
    NPU_STARTUP_CONTINUE,
    NPU_STARTUP_FAULT,
};

/* A cold loader supplies this fresh template before releasing any hart. It
 * must independently contain prior users; this header is not that witness. */
struct npu_startup {
    uint32_t magic;
    uint32_t version;
    uint32_t bytes;
    uint32_t phase;
    uint32_t fault;
    uint32_t arrived[NPU_BARRIER_WORKERS];
    uint32_t reserved[3];
};

enum npu_startup_action npu_startup_arrive(struct npu_startup *s,
                                          uint32_t hart, uint32_t warm);
enum npu_startup_action npu_startup_poll(struct npu_startup *s, uint32_t hart);
int npu_startup_publish(struct npu_startup *s, const struct npu_barrier *b,
                        const struct npu_admission *a, const uint32_t *masked,
                        uint32_t hart);

#endif
#endif
