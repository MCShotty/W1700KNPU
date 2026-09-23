#include "bootstrap-v2.h"

_Static_assert(sizeof(struct npu_control_v2_packet) == NPU_CONTROL_V2_SIZE,
               "V2 control layout changed");

void npu_control_v2_init(struct npu_control_v2_session *s,
                         uint32_t boot_lo, uint32_t boot_hi)
{
    s->boot_lo = boot_lo;
    s->boot_hi = boot_hi;
    s->nonce_lo = s->nonce_hi = s->last_sequence = 0;
}

int npu_control_v2_dispatch_gate(struct npu_control_v2_session *s,
                             struct npu_admission *a, struct npu_barrier *b,
                             struct npu_control_v2_packet *p, uint32_t bytes,
                             enum npu_control_status bind_status)
{
    uint32_t operation, status = NPU_CONTROL_OK;

    if (bytes != sizeof(*p) || p->v1.header != NPU_CONTROL_HEADER ||
        p->v1.api != NPU_CONTROL_API || p->v1.magic != NPU_CONTROL_V2_REQUEST)
        return 0;
    operation = p->v1.operation;
    if (p->v1.version != NPU_CONTROL_V2_VERSION || p->v1.bytes != sizeof(*p) ||
        p->reserved || !p->sequence || !(p->v1.nonce_lo || p->v1.nonce_hi)) {
        status = NPU_CONTROL_BAD_MESSAGE;
    } else if (!(s->boot_lo || s->boot_hi)) {
        status = NPU_CONTROL_FAULT;
    } else if (operation == NPU_CONTROL_DISCOVER) {
        if (p->boot_lo || p->boot_hi)
            status = NPU_CONTROL_BAD_BOOT;
    } else if (operation > NPU_CONTROL_STATUS) {
        status = NPU_CONTROL_UNSUPPORTED;
    } else if (p->boot_lo != s->boot_lo || p->boot_hi != s->boot_hi) {
        status = NPU_CONTROL_BAD_BOOT;
    } else if (s->nonce_lo || s->nonce_hi) {
        if (p->v1.nonce_lo != s->nonce_lo || p->v1.nonce_hi != s->nonce_hi)
            status = NPU_CONTROL_BAD_SESSION;
    } else if (operation != NPU_CONTROL_BIND) {
        status = NPU_CONTROL_BAD_SESSION;
    } else {
        /* Reserve the session even if BIND subsequently fails. An abandoned
         * BUSY/error request must not become effective when replayed later. */
        s->nonce_lo = p->v1.nonce_lo;
        s->nonce_hi = p->v1.nonce_hi;
    }
    if (status == NPU_CONTROL_OK && operation != NPU_CONTROL_DISCOVER) {
        if (p->sequence <= s->last_sequence) {
            status = NPU_CONTROL_REPLAY;
        } else {
            s->last_sequence = p->sequence;
            /* Unlike V1's diagnostic STATUS, V2 requires an actual binding. */
            if (operation != NPU_CONTROL_BIND &&
                (a->nonce_lo != s->nonce_lo || a->nonce_hi != s->nonce_hi))
                status = NPU_CONTROL_BAD_SESSION;
        }
    }

    if (status == NPU_CONTROL_OK && operation == NPU_CONTROL_BIND)
        status = bind_status;

    /* Reuse the original serialized admission/barrier operation, not its wire
     * admission. Rejected requests and discovery obtain only a STATUS snapshot. */
    p->v1.magic = NPU_CONTROL_REQUEST;
    p->v1.version = NPU_CONTROL_VERSION;
    p->v1.bytes = NPU_CONTROL_SIZE;
    if (status != NPU_CONTROL_OK || operation == NPU_CONTROL_DISCOVER)
        p->v1.operation = NPU_CONTROL_STATUS;
    npu_admission_control(a, b, &p->v1, NPU_CONTROL_SIZE);
    if (status != NPU_CONTROL_OK)
        p->v1.status = status;
    p->v1.operation = operation;
    p->v1.magic = NPU_CONTROL_V2_REPLY;
    p->v1.version = NPU_CONTROL_V2_VERSION;
    p->v1.bytes = sizeof(*p);
    p->v1.capabilities = NPU_CONTROL_V2_CAPS;
    p->boot_lo = s->boot_lo;
    p->boot_hi = s->boot_hi;
    p->reserved = 0;
    return 1;
}

int npu_control_v2_dispatch(struct npu_control_v2_session *s,
                             struct npu_admission *a, struct npu_barrier *b,
                             struct npu_control_v2_packet *p, uint32_t bytes)
{
    return npu_control_v2_dispatch_gate(s, a, b, p, bytes, NPU_CONTROL_OK);
}
