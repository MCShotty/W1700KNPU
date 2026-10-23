#ifndef W1700K_NPU_RRO_WIRE_H
#define W1700K_NPU_RRO_WIRE_H

#include "control-v2.h"
#include "rro-lifetime.h"

#define NPU_RRO_WIRE_API 2u
#define NPU_RRO_WIRE_REQUEST 0x3151524eu /* NRQ1 */
#define NPU_RRO_WIRE_REPLY 0x3152524eu /* NRR1 */
#define NPU_RRO_WIRE_VERSION 1u
#define NPU_RRO_WIRE_SIZE 256u
#define NPU_RRO_WIRE_WORDS (NPU_RRO_WIRE_SIZE / 4u)
#define NPU_RRO_CLIENT_PENDING 5u

enum npu_rro_wire_operation {
    NPU_RRO_WIRE_OPEN = 1,
    NPU_RRO_WIRE_ENROLL,
    NPU_RRO_WIRE_PUBLISH,
    NPU_RRO_WIRE_HARDWARE,
    NPU_RRO_WIRE_RESET_NPU,
    NPU_RRO_WIRE_MCU_BEGIN,
    NPU_RRO_WIRE_MCU_COMPLETE,
    NPU_RRO_WIRE_CLOSE,
};

enum npu_rro_wire_status {
    NPU_RRO_WIRE_OK,
    NPU_RRO_WIRE_BAD_MESSAGE,
    NPU_RRO_WIRE_BAD_BOOT,
    NPU_RRO_WIRE_BAD_IDENTITY,
    NPU_RRO_WIRE_REPLAY,
    NPU_RRO_WIRE_STATE,
    NPU_RRO_WIRE_CORE = 0x100u,
};

struct npu_rro_wire_packet {
    unsigned char bytes[NPU_RRO_WIRE_SIZE];
};

/* Header words: header/API/tag/version/size/sequence/operation/status.
 * Body words0..9 always carry the exact plan identity and profile.
 * OPEN carries the full216-byte plan. Other operations use these body fields:
 * ENROLL:10 ordinal,11..17 extent in declaration order.
 * PUBLISH:10 ordinal,11 ticket,12 selector,13..16 four payload words.
 * RESET_NPU:10 session,11 generation,12 ticket,13 selector,14..17 payload.
 * MCU_BEGIN:10 session,11 generation,12 ticket; MCU_COMPLETE adds13 error.
 * CLOSE:10 stop_epoch,11 ticket. HARDWARE carries only identity/profile.
 * Every other byte is zero, including the final two words. Reply changes only
 * tag/status. Correlation is not cryptographic authentication or DMA authority.
 */
struct npu_rro_wire_message {
    uint32_t operation, sequence, status;
    struct npu_rro_plan plan;
    uint32_t ordinal, session, generation, ticket, stop_epoch, mcu_error;
    struct npu_rro_extent extent;
    struct npu_rro_command command;
};

/* Shape/echo checks do not authorize extents or perform journal operations.
 * Input/output objects must be readable/writable as appropriate. Codec output
 * must not overlap its input object; errors leave output unchanged. Encoding
 * uses only operation-relevant fields; decoding zeroes all other fields.
 */
uint32_t npu_rro_wire_encode(void *, uint32_t bytes, const struct npu_rro_wire_message *);
uint32_t npu_rro_wire_decode(struct npu_rro_wire_message *, const void *, uint32_t bytes, uint32_t reply);
uint32_t npu_rro_wire_reply(void *, uint32_t bytes, uint32_t status);
int npu_rro_wire_echo(const void *request, const void *reply, uint32_t bytes);

static inline void npu_rro_wire_copy(void *destination, const void *source)
{
    volatile unsigned char *to = destination;
    const volatile unsigned char *from = source;
    for (uint32_t i = 0; i < NPU_RRO_WIRE_SIZE; i++)
        to[i] = from[i];
}

uint32_t npu_rro_client_request(struct npu_control_v2_client *, void *, uint32_t bytes,
    const struct npu_rro_wire_message *);
enum npu_client_result npu_rro_client_complete(struct npu_control_v2_client *, uint32_t ticket,
    int transport_error, const void *request, const void *reply, uint32_t bytes, uint32_t *remote_status);

#endif
