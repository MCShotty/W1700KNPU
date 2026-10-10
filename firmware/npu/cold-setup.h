#ifndef W1700K_NPU_COLD_SETUP_H
#define W1700K_NPU_COLD_SETUP_H

#include "bootstrap.h"
#include "control-v2.h"

#define NPU_COLD_REQUEST 0x3253434eu /* NCS2 */
#define NPU_COLD_REPLY 0x3252434eu /* NCR2 */
#define NPU_COLD_VERSION 2u
#define NPU_COLD_SIZE 80u
#define NPU_COLD_API 1u
#define NPU_COLD_PENDING_OPERATION 4u
#define NPU_COLD_PORT 1u
#define NPU_COLD_RX0 2u
#define NPU_COLD_RX2 4u
#define NPU_COLD_ENDPOINT_BASE 8u
#define NPU_COLD_ENDPOINT_BYTES 16u
#define NPU_COLD_ADDR5 32u
#define NPU_COLD_PAGE5 64u
#define NPU_COLD_ADDR6 128u
#define NPU_COLD_PAGE6 256u
#define NPU_COLD_ADDR7 512u
#define NPU_COLD_PAGE7 1024u
#define NPU_COLD_ADDR8 2048u
#define NPU_COLD_INDICATION 4096u
#define NPU_COLD_ACK 8192u
#define NPU_COLD_TX0 16384u
#define NPU_COLD_TX2 32768u
#define NPU_COLD_TOKEN 65536u
#define NPU_COLD_COMPLETED_MASK 131071u
#define NPU_COLD_TX_REG0 0xd4420u
#define NPU_COLD_TX_REG2 0xd4450u
#define NPU_COLD_TX_HIF2 0x4000u
#define NPU_COLD_COUNTS 5u
#define NPU_COLD_IND_REG 0xa040u
#define NPU_COLD_ACK_REG 0xa050u
#define NPU_COLD_BIND_HEADER 0x1fu
#define NPU_COLD_BIND_BASE_API 0x100u
#define NPU_COLD_BIND_BYTES_API 0x101u
#define NPU_COLD_PAGE_REG0 0xd45a0u
#define NPU_COLD_ENDPOINT_MIN_BYTES (NPU_COLD_PAGE_REG0 + 0x20u + 12u)

static inline int npu_cold_endpoint_valid(uint32_t base, uint32_t bytes)
{
    return base && !(base & 4095u) && base < 0xc0000000u &&
           bytes >= NPU_COLD_ENDPOINT_MIN_BYTES && !(bytes & 4095u) &&
           bytes <= 0xc0000000u - base;
}

enum npu_cold_status {
    NPU_COLD_OK,
    NPU_COLD_BAD_MESSAGE,
    NPU_COLD_BAD_BOOT,
    NPU_COLD_BAD_SESSION,
    NPU_COLD_REPLAY,
    NPU_COLD_BAD_STATE,
    NPU_COLD_UNSUPPORTED,
    NPU_COLD_CALLBACK_FAILED,
};

struct npu_cold_packet {
    uint32_t header, api, magic, version, bytes;
    uint32_t epoch, sequence;
    uint32_t nonce_lo, nonce_hi, boot_lo, boot_hi;
    struct npu_bootstrap_packet command;
    uint32_t status, reserved[5];
};

/* Fixed byte access also avoids an unavailable libc call in the raw RV32 build. */
static inline void npu_cold_packet_copy(struct npu_cold_packet *destination,
                                       const struct npu_cold_packet *source)
{
    volatile unsigned char *to = (volatile void *)destination;
    const volatile unsigned char *from = (const volatile void *)source;
    uint32_t i;

    for (i = 0; i < NPU_COLD_SIZE; i++)
        to[i] = from[i];
}

/* Fresh native storage belongs to the boot, not each host attachment. A failed
 * callback retains inflight/active state; no API resets or retires this owner.
 * This is a software cold lane, not physical containment or release authority.
 */
struct npu_cold_setup {
    uint32_t failed, inflight, completed, sequence;
    uint32_t boot_lo, boot_hi, nonce_lo, nonce_hi, prior_completed;
    struct npu_bootstrap_packet command;
    uint32_t endpoint_base, endpoint_bytes, prior_base, prior_bytes;
    uint32_t counts[NPU_COLD_COUNTS], prior_counts[NPU_COLD_COUNTS];
};

enum npu_cold_status npu_cold_setup_begin(struct npu_cold_setup *setup,
    struct npu_control_v2_session *session, struct npu_admission *admission,
    struct npu_barrier *barrier, const struct npu_bootstrap *bootstrap,
    const struct npu_cold_packet *packet, uint32_t bytes);
enum npu_cold_status npu_cold_setup_finish(struct npu_cold_setup *setup,
    struct npu_control_v2_session *session, struct npu_admission *admission,
    struct npu_barrier *barrier, const struct npu_bootstrap *bootstrap,
    uint32_t callback_result, const struct npu_bootstrap_packet *reply);

uint32_t npu_cold_client_request(struct npu_control_v2_client *client,
    void *packet, uint32_t bytes, const struct npu_bootstrap_packet *command);
enum npu_client_result npu_cold_client_complete(struct npu_control_v2_client *client,
    uint32_t ticket, int transport_error, const void *packet, uint32_t bytes,
    const struct npu_bootstrap_packet *command, uint32_t *value);

#endif
