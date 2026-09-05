#ifndef W1700K_NPU_ADMISSION_H
#define W1700K_NPU_ADMISSION_H

#include "barrier.h"

#define NPU_ADMISSION_IRQS 192u
#define NPU_ADMISSION_IRQ_WORDS 6u
#define NPU_COORDINATOR_MAILBOX_IRQ 8u

enum npu_irq_admission {
    NPU_IRQ_DEFER,
    NPU_IRQ_NATIVE,
    NPU_IRQ_CONTROL,
    NPU_IRQ_INVALID,
};

/* Only hart 0, with local interrupts disabled, may access this state. Other
 * harts must gate their own IRQs before their barrier acknowledgement. */
struct npu_admission {
    uint32_t closed;
    uint32_t active;
    uint32_t fault;
    uint32_t nonce_lo;
    uint32_t nonce_hi;
    uint32_t deferred[NPU_ADMISSION_IRQ_WORDS];
};

void npu_admission_init(struct npu_admission *state);
uint32_t npu_admission_close(struct npu_admission *state, struct npu_barrier *barrier);
int npu_admission_begin_legacy(struct npu_admission *state, struct npu_barrier *barrier);
void npu_admission_leave(struct npu_admission *state, struct npu_barrier *barrier);
enum npu_irq_admission npu_admission_irq(struct npu_admission *state,
                                        struct npu_barrier *barrier, uint32_t source);
void npu_admission_fail(struct npu_admission *state, struct npu_barrier *barrier);
enum npu_barrier_action npu_admission_idle(struct npu_admission *state, struct npu_barrier *barrier);
int npu_admission_retire_irq(struct npu_admission *state, const struct npu_barrier *barrier,
                            uint32_t source, uint32_t epoch);
int npu_admission_open(struct npu_admission *state, const struct npu_barrier *barrier);

/* Candidate ABI. Transport must supply exactly 64 accessible, aligned bytes
 * in a pinned request buffer. All words are little-endian. No hardware drain
 * or restart capability is advertised by this implementation. */
#define NPU_CONTROL_HEADER 0x3fu /* WLAN GET, info selector 15. */
#define NPU_CONTROL_API 0u
#define NPU_CONTROL_REQUEST 0x3143514eu /* NQC1 */
#define NPU_CONTROL_REPLY 0x3152514eu /* NQR1 */
#define NPU_CONTROL_VERSION 1u
#define NPU_CONTROL_SIZE 64u
#define NPU_CAP_DISCOVERY_STATUS (1u << 0)
#define NPU_CAP_STOP_REQUEST (1u << 1)
#define NPU_CAP_IRQ_ADMISSION (1u << 2)
#define NPU_CAP_SAFE_RECLAIM (1u << 3)
#define NPU_CAP_RESTART (1u << 4)
#define NPU_CONTROL_CAPS (NPU_CAP_DISCOVERY_STATUS | NPU_CAP_STOP_REQUEST | NPU_CAP_IRQ_ADMISSION)

enum npu_control_operation {
    NPU_CONTROL_DISCOVER,
    NPU_CONTROL_BIND,
    NPU_CONTROL_STOP,
    NPU_CONTROL_STATUS,
};

enum npu_control_status {
    NPU_CONTROL_OK,
    NPU_CONTROL_BAD_MESSAGE,
    NPU_CONTROL_BAD_SESSION,
    NPU_CONTROL_STALE_EPOCH,
    NPU_CONTROL_UNSUPPORTED,
    NPU_CONTROL_BUSY,
    NPU_CONTROL_FAULT,
};

struct npu_control_packet {
    uint32_t header;
    uint32_t api;
    uint32_t magic;
    uint32_t version;
    uint32_t bytes;
    uint32_t operation;
    uint32_t epoch;
    uint32_t nonce_lo;
    uint32_t nonce_hi;
    uint32_t status;
    uint32_t capabilities;
    uint32_t parked_mask;
    uint32_t ready_mask;
    uint32_t drain_mask;
    uint32_t released;
    uint32_t armed;
};

int npu_admission_control(struct npu_admission *state, struct npu_barrier *barrier,
                          struct npu_control_packet *packet, uint32_t bytes);

#endif
