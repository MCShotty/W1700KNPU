#ifndef W1700K_NPU_CONTROL_CLIENT_H
#define W1700K_NPU_CONTROL_CLIENT_H

#include "admission.h"

enum npu_client_phase {
    NPU_CLIENT_NEW,
    NPU_CLIENT_DISCOVERED,
    NPU_CLIENT_BOUND,
    NPU_CLIENT_STOPPING,
    NPU_CLIENT_PARKED,
    NPU_CLIENT_FAILED,
};

enum npu_client_error {
    NPU_CLIENT_NO_ERROR,
    NPU_CLIENT_ARGUMENT,
    NPU_CLIENT_TRANSPORT,
    NPU_CLIENT_ENVELOPE,
    NPU_CLIENT_CAPABILITY,
    NPU_CLIENT_REMOTE,
    NPU_CLIENT_GENERATION,
    NPU_CLIENT_SNAPSHOT,
    NPU_CLIENT_EXHAUSTED,
    NPU_CLIENT_ABORTED,
};

enum npu_client_result {
    NPU_CLIENT_IGNORED,
    NPU_CLIENT_ACCEPTED,
    NPU_CLIENT_REJECTED,
};

/* One serialized client per provider lifetime. Initialize only after independent
 * cold containment, with a fresh nonzero nonce. No API frees or rearms anything.
 * PARKED is a software observation, not a durable ownership/drain certificate. */
struct npu_control_client {
    uint32_t phase;
    uint32_t error;
    uint32_t nonce_lo;
    uint32_t nonce_hi;
    uint32_t serial;
    uint32_t pending;
    uint32_t operation;
    uint32_t epoch;
    uint32_t released;
    uint32_t armed;
    uint32_t parked_mask;
    uint32_t ready_mask;
    uint32_t drain_mask;
    uint32_t capabilities;
};

void npu_client_init(struct npu_control_client *client, uint32_t nonce_lo,
                     uint32_t nonce_hi);

/* Provider loss or caller cancellation; does not retire outstanding storage. */
void npu_client_abort(struct npu_control_client *client);

/* Returns a nonzero local completion ticket, or zero without writing the
 * request. Only one request may be outstanding. The caller must use a separately
 * owned, aligned, pinned transport buffer; this byte codec does not map it. */
uint32_t npu_client_request(struct npu_control_client *client, void *request,
                            uint32_t bytes);

/* transport_error is nonzero for ANY transport failure, including timeout.
 * A failed request permanently holds this client; late replies are ignored.
 * The caller retains timed-out transport storage until independently retired.
 * The ticket is local correlation, not a wire nonce or replay-proof mailbox. */
enum npu_client_result npu_client_complete(struct npu_control_client *client,
                                          uint32_t ticket, int transport_error,
                                          const void *reply, uint32_t bytes);

#endif
