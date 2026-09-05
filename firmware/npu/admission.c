#include "admission.h"

_Static_assert(sizeof(struct npu_admission) == 44, "admission layout changed");
_Static_assert(sizeof(struct npu_control_packet) == NPU_CONTROL_SIZE, "control layout changed");

static uint32_t load(const uint32_t *word)
{
    return __atomic_load_n(word, __ATOMIC_ACQUIRE);
}

static int running(const struct npu_barrier *b)
{
    uint32_t epoch = load(&b->request);

    /* Do not call barrier_poll from an IRQ admission check: it would publish
     * the coordinator's acknowledgement before the IRQ had returned. */
    return epoch && !load(&b->fault) && load(&b->released) == epoch &&
           load(&b->prepared) == epoch && load(&b->armed) == epoch &&
           load(&b->ready[0]) == epoch;
}

static int pending(const struct npu_admission *s)
{
    uint32_t i;

    for (i = 0; i < NPU_ADMISSION_IRQ_WORDS; i++)
        if (s->deferred[i])
            return 1;
    return 0;
}

void npu_admission_init(struct npu_admission *s)
{
    uint32_t i;

    s->closed = 1;
    s->active = s->fault = s->nonce_lo = s->nonce_hi = 0;
    for (i = 0; i < NPU_ADMISSION_IRQ_WORDS; i++)
        s->deferred[i] = 0;
}

void npu_admission_fail(struct npu_admission *s, struct npu_barrier *b)
{
    s->closed = s->fault = 1;
    __atomic_store_n(&b->fault, 1, __ATOMIC_RELEASE);
}

uint32_t npu_admission_close(struct npu_admission *s, struct npu_barrier *b)
{
    s->closed = 1;
    return npu_barrier_stop(b);
}

int npu_admission_begin_legacy(struct npu_admission *s, struct npu_barrier *b)
{
    if (s->fault || s->closed || !running(b))
        return 0;
    if (s->active == UINT32_MAX) {
        npu_admission_fail(s, b);
        return 0;
    }
    s->active++;
    return 1;
}

void npu_admission_leave(struct npu_admission *s, struct npu_barrier *b)
{
    if (!s->active) {
        npu_admission_fail(s, b);
        return;
    }
    s->active--;
}

enum npu_irq_admission npu_admission_irq(struct npu_admission *s,
                                        struct npu_barrier *b, uint32_t source)
{
    if (source >= NPU_ADMISSION_IRQS)
        return NPU_IRQ_INVALID;
    if (source == NPU_COORDINATOR_MAILBOX_IRQ)
        return NPU_IRQ_CONTROL;
    if (npu_admission_begin_legacy(s, b))
        return NPU_IRQ_NATIVE;
    /* A late datapath IRQ contradicts a recorded stop-generation drain. */
    if (load(&b->request) && load(&b->released) != load(&b->request) &&
        load(&b->drained[NPU_DRAIN_IRQ_PUBLICATION]) == load(&b->request))
        npu_admission_fail(s, b);
    s->deferred[source / 32] |= 1u << (source % 32);
    return NPU_IRQ_DEFER;
}

enum npu_barrier_action npu_admission_idle(struct npu_admission *s, struct npu_barrier *b)
{
    enum npu_barrier_action action;
    uint32_t epoch;

    if (s->fault)
        return NPU_BARRIER_FAULT;
    if (s->active)
        return NPU_BARRIER_PARK;
    action = npu_barrier_poll(b, 0, &epoch);
    if (action != NPU_BARRIER_RUN)
        s->closed = 1;
    if (action == NPU_BARRIER_REFRESH) {
        /* Deferred device events must be physically retired while old storage
         * is still retained. Merely masking the source cannot make READY. */
        if (!pending(s))
            npu_barrier_refreshed(b, 0, epoch);
        return NPU_BARRIER_PARK;
    }
    return action;
}

int npu_admission_retire_irq(struct npu_admission *s, const struct npu_barrier *b,
                            uint32_t source, uint32_t epoch)
{
    uint32_t mask;

    if (source >= NPU_ADMISSION_IRQS || s->fault || s->active || !s->closed ||
        !npu_barrier_reclaimable(b, epoch))
        return 0;
    mask = 1u << (source % 32);
    if (!(s->deferred[source / 32] & mask))
        return 0;
    /* Platform witness only: this API does not pop a FIFO, retire a buffer ID
     * or prove a device cannot publish another old-generation completion. */
    s->deferred[source / 32] &= ~mask;
    return 1;
}

int npu_admission_open(struct npu_admission *s, const struct npu_barrier *b)
{
    if (s->fault || s->active || pending(s) || !running(b))
        return 0;
    s->closed = 0;
    return 1;
}

static int session(const struct npu_admission *s, const struct npu_control_packet *p)
{
    return (s->nonce_lo || s->nonce_hi) && s->nonce_lo == p->nonce_lo &&
           s->nonce_hi == p->nonce_hi;
}

int npu_admission_control(struct npu_admission *s, struct npu_barrier *b,
                          struct npu_control_packet *p, uint32_t bytes)
{
    uint32_t epoch, i, status = NPU_CONTROL_OK;

    if (bytes != sizeof(*p) || p->header != NPU_CONTROL_HEADER ||
        p->api != NPU_CONTROL_API || p->magic != NPU_CONTROL_REQUEST)
        return 0;
    epoch = load(&b->request);
    if (p->version != NPU_CONTROL_VERSION || p->bytes != sizeof(*p)) {
        status = NPU_CONTROL_BAD_MESSAGE;
    } else if (p->operation == NPU_CONTROL_DISCOVER || p->operation == NPU_CONTROL_STATUS) {
        if (p->operation == NPU_CONTROL_STATUS && (s->fault || load(&b->fault)))
            status = NPU_CONTROL_FAULT;
    } else if (s->fault || load(&b->fault) || !epoch) {
        status = NPU_CONTROL_FAULT;
    } else if (p->epoch != epoch) {
        status = NPU_CONTROL_STALE_EPOCH;
    } else if (p->operation == NPU_CONTROL_BIND) {
        if (!(p->nonce_lo || p->nonce_hi))
            status = NPU_CONTROL_BAD_SESSION;
        else if (s->active)
            status = NPU_CONTROL_BUSY;
        else if (s->nonce_lo || s->nonce_hi) {
            if (!session(s, p))
                status = NPU_CONTROL_BAD_SESSION;
        } else {
            s->nonce_lo = p->nonce_lo;
            s->nonce_hi = p->nonce_hi;
        }
    } else if (p->operation == NPU_CONTROL_STOP) {
        if (!session(s, p))
            status = NPU_CONTROL_BAD_SESSION;
        else if (!npu_admission_close(s, b))
            status = NPU_CONTROL_FAULT;
    } else {
        status = NPU_CONTROL_UNSUPPORTED;
    }
    epoch = load(&b->request);
    p->magic = NPU_CONTROL_REPLY;
    p->version = NPU_CONTROL_VERSION;
    p->bytes = sizeof(*p);
    p->epoch = epoch;
    p->status = status;
    p->capabilities = NPU_CONTROL_CAPS;
    p->parked_mask = p->ready_mask = p->drain_mask = 0;
    for (i = 0; i < NPU_BARRIER_WORKERS; i++) {
        if (epoch && load(&b->parked[i]) == epoch)
            p->parked_mask |= 1u << i;
        if (epoch && load(&b->ready[i]) == epoch)
            p->ready_mask |= 1u << i;
    }
    for (i = 0; i < NPU_BARRIER_DOMAINS; i++)
        if (epoch && load(&b->drained[i]) == epoch)
            p->drain_mask |= 1u << i;
    p->released = load(&b->released);
    p->armed = load(&b->armed);
    return 1;
}
