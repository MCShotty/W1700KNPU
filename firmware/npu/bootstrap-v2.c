#include "bootstrap-v2.h"

#define BOOT_RETAINED_MASK 0x1eu
_Static_assert(NPU_BOOTSTRAP_STEPS == 6 && NPU_BOOT_TXCHECK == 1 && NPU_BOOT_BA == 4,
               "review bootstrap binding prerequisites");

static uint32_t load(const uint32_t *word)
{
    return __atomic_load_n(word, __ATOMIC_ACQUIRE);
}

int npu_bootstrap_v2_session_init(struct npu_control_v2_session *s,
                                   struct npu_admission *a, struct npu_barrier *b,
                                   uint32_t boot_lo, uint32_t boot_hi)
{
    uint32_t i;

    if (!(boot_lo || boot_hi) || s->boot_lo || s->boot_hi || s->nonce_lo ||
        s->nonce_hi || s->last_sequence || a->closed != 1 || a->active ||
        a->fault || a->nonce_lo || a->nonce_hi || load(&b->request) != 1 ||
        load(&b->released) || load(&b->prepared) || load(&b->armed) || load(&b->fault))
        goto fault;
    for (i = 0; i < NPU_BARRIER_WORKERS; i++)
        if (load(&b->parked[i]) || load(&b->ready[i]))
            goto fault;
    for (i = 0; i < NPU_BARRIER_DOMAINS; i++)
        if (load(&b->drained[i]))
            goto fault;
    for (i = 0; i < NPU_ADMISSION_IRQ_WORDS; i++)
        if (a->deferred[i])
            goto fault;
    npu_control_v2_init(s, boot_lo, boot_hi);
    return 1;
fault:
    npu_admission_fail(a, b);
    return 0;
}

int npu_bootstrap_v2_transport(const struct npu_bootstrap *s,
                                uint32_t address, uint32_t bytes, uint32_t flags)
{
    const struct npu_bootstrap_range *request = &s->plan.region[NPU_BOOT_REQUEST];

    /* Check the pinned region before dereferencing any wire payload. Failed
     * bootstrap still admits diagnostic control, but never a different buffer. */
    return s->magic == NPU_BOOTSTRAP_MAGIC && flags == 1 &&
           request->bytes == 256 && address == request->base && !(address & 3) &&
           address >= 0x80000000u && address <= 0xc0000000u - 256 &&
           (bytes == NPU_BOOTSTRAP_PACKET_BYTES || bytes == NPU_CONTROL_V2_SIZE);
}

int npu_bootstrap_v2_control(const struct npu_bootstrap *s,
                              struct npu_control_v2_session *session,
                              struct npu_admission *a, struct npu_barrier *b,
                              struct npu_control_v2_packet *packet, uint32_t bytes)
{
    enum npu_control_status status = NPU_CONTROL_OK;

    if (s->magic != NPU_BOOTSTRAP_MAGIC || s->failed || a->fault || load(&b->fault))
        status = NPU_CONTROL_FAULT;
    else if (s->step != NPU_BOOTSTRAP_STEPS || s->inflight ||
             s->retained_mask != BOOT_RETAINED_MASK)
        status = NPU_CONTROL_BUSY;
    return npu_control_v2_dispatch_gate(session, a, b, packet, bytes, status);
}
