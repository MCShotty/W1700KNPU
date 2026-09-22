#ifndef W1700K_NPU_CONTROL_V2_H
#define W1700K_NPU_CONTROL_V2_H

#include "control-client.h"

#define NPU_CONTROL_V2_REQUEST 0x3243514eu /* NQC2 */
#define NPU_CONTROL_V2_REPLY 0x3252514eu /* NQR2 */
#define NPU_CONTROL_V2_VERSION 2u
#define NPU_CONTROL_V2_SIZE 80u
#define NPU_CAP_REQUEST_IDENTITY (1u << 5)
#define NPU_CONTROL_V2_CAPS (NPU_CONTROL_CAPS | NPU_CAP_REQUEST_IDENTITY)
#define NPU_CONTROL_BAD_BOOT 7u
#define NPU_CONTROL_REPLAY 8u

struct npu_control_v2_packet {
    struct npu_control_packet v1;
    uint32_t sequence;
    uint32_t boot_lo;
    uint32_t boot_hi;
    uint32_t reserved;
};

/* Serialized with admission on hart0. A loader must supply a fresh, nonzero
 * identity for each independently contained cold boot; never reuse it. */
struct npu_control_v2_session {
    uint32_t boot_lo;
    uint32_t boot_hi;
    uint32_t nonce_lo;
    uint32_t nonce_hi;
    uint32_t last_sequence;
};

void npu_control_v2_init(struct npu_control_v2_session *session,
                         uint32_t boot_lo, uint32_t boot_hi);
int npu_control_v2_dispatch(struct npu_control_v2_session *session,
                             struct npu_admission *admission,
                             struct npu_barrier *barrier,
                             struct npu_control_v2_packet *packet, uint32_t bytes);

enum npu_client_v2_error {
    NPU_CLIENT_V2_NO_ERROR,
    NPU_CLIENT_V2_ARGUMENT,
    NPU_CLIENT_V2_ENVELOPE,
    NPU_CLIENT_V2_SEQUENCE,
    NPU_CLIENT_V2_BOOT,
    NPU_CLIENT_V2_CAPABILITY,
};

struct npu_control_v2_client {
    struct npu_control_client base;
    uint32_t boot_lo;
    uint32_t boot_hi;
    uint32_t error;
};

void npu_client_v2_init(struct npu_control_v2_client *client,
                        uint32_t nonce_lo, uint32_t nonce_hi);
void npu_client_v2_abort(struct npu_control_v2_client *client);
uint32_t npu_client_v2_request(struct npu_control_v2_client *client,
                               void *request, uint32_t bytes);
enum npu_client_result npu_client_v2_complete(struct npu_control_v2_client *client,
                                              uint32_t ticket, int transport_error,
                                              const void *reply, uint32_t bytes);

#endif
