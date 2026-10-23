#include "rro-wire.h"

typedef __UINTPTR_TYPE__ address_t;

static int disjoint(const void *a, uint32_t an, const void *b, uint32_t bn)
{
    address_t x = (address_t)a, y = (address_t)b;
    return x && y && an <= ~(address_t)0 - x && bn <= ~(address_t)0 - y &&
           (x + an <= y || y + bn <= x);
}

static enum npu_client_result fail(struct npu_control_v2_client *s, uint32_t error)
{
    if (s->base.phase != NPU_CLIENT_FAILED) {
        s->error = error;
        npu_client_v2_abort(s);
    }
    return NPU_CLIENT_REJECTED;
}

static int parked(const struct npu_control_v2_client *s)
{
    return s->base.phase == NPU_CLIENT_PARKED && s->base.epoch == 1 &&
           !s->base.error && !s->error && !s->base.released && !s->base.armed &&
           !s->base.ready_mask && !s->base.drain_mask && s->base.parked_mask == 0xff &&
           (s->boot_lo || s->boot_hi) && (s->base.nonce_lo || s->base.nonce_hi);
}

static int identity(const struct npu_control_v2_client *s, const struct npu_rro_wire_message *m)
{
    return m->plan.identity.boot_lo == s->boot_lo && m->plan.identity.boot_hi == s->boot_hi &&
           m->plan.identity.nonce_lo == s->base.nonce_lo && m->plan.identity.nonce_hi == s->base.nonce_hi &&
           m->plan.identity.epoch == s->base.epoch;
}

uint32_t npu_rro_client_request(struct npu_control_v2_client *s, void *packet, uint32_t bytes,
    const struct npu_rro_wire_message *message)
{
    struct npu_rro_wire_message snapshot;

    if (!s || s->base.phase == NPU_CLIENT_FAILED || s->base.pending)
        return 0;
    if (!message || ((address_t)message & 3u) || bytes != NPU_RRO_WIRE_SIZE ||
        !disjoint(s, sizeof(*s), packet, bytes) ||
        !disjoint(message, sizeof(*message), packet, bytes) ||
        !disjoint(s, sizeof(*s), message, sizeof(*message)) ||
        !parked(s) || !identity(s, message) || s->base.serial == UINT32_MAX) {
        fail(s, NPU_CLIENT_V2_ARGUMENT);
        return 0;
    }
    volatile unsigned char *to = (volatile void *)&snapshot;
    const volatile unsigned char *from = (const volatile void *)message;
    for (uint32_t i = 0; i < sizeof(snapshot); i++)
        to[i] = from[i];
    snapshot.sequence = s->base.serial + 1;
    snapshot.status = 0;
    if (npu_rro_wire_encode(packet, bytes, &snapshot)) {
        fail(s, NPU_CLIENT_V2_ARGUMENT);
        return 0;
    }
    s->base.operation = NPU_RRO_CLIENT_PENDING;
    s->base.pending = ++s->base.serial;
    return s->base.pending;
}

enum npu_client_result npu_rro_client_complete(struct npu_control_v2_client *s, uint32_t ticket,
    int transport_error, const void *request, const void *reply, uint32_t bytes, uint32_t *remote_status)
{
    struct npu_rro_wire_message sent, received;

    if (!s || !ticket || ticket != s->base.pending || s->base.phase == NPU_CLIENT_FAILED)
        return NPU_CLIENT_IGNORED;
    if (transport_error)
        return fail(s, NPU_CLIENT_V2_ENVELOPE);
    if (!remote_status || ((address_t)remote_status & 3u) || !parked(s) ||
        s->base.operation != NPU_RRO_CLIENT_PENDING ||
        s->base.serial != ticket || bytes != NPU_RRO_WIRE_SIZE ||
        !disjoint(s, sizeof(*s), request, bytes) || !disjoint(s, sizeof(*s), reply, bytes) ||
        !disjoint(s, sizeof(*s), remote_status, sizeof(*remote_status)) ||
        !disjoint(request, bytes, remote_status, sizeof(*remote_status)) ||
        !disjoint(reply, bytes, remote_status, sizeof(*remote_status)))
        return fail(s, NPU_CLIENT_V2_ARGUMENT);
    if (npu_rro_wire_decode(&sent, request, bytes, 0) ||
        npu_rro_wire_decode(&received, reply, bytes, 1) ||
        !npu_rro_wire_echo(request, reply, bytes))
        return fail(s, NPU_CLIENT_V2_ENVELOPE);
    if (sent.sequence != ticket || received.sequence != ticket ||
        !identity(s, &sent) || !identity(s, &received))
        return fail(s, NPU_CLIENT_V2_SEQUENCE);
    *remote_status = received.status;
    if (received.status)
        return fail(s, NPU_CLIENT_V2_ENVELOPE);
    s->base.pending = 0;
    return NPU_CLIENT_ACCEPTED;
}
