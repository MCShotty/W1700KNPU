#include "rro-session.h"

_Static_assert(sizeof(struct npu_rro_session) <= 32768, "review RRO native reservation");

static uint32_t load(const uint32_t *word)
{
    return __atomic_load_n(word, __ATOMIC_ACQUIRE);
}

static void copy(void *destination, const void *source, uint32_t bytes)
{
    volatile unsigned char *to = destination;
    const volatile unsigned char *from = source;
    for (uint32_t i = 0; i < bytes; i++)
        to[i] = from[i];
}

static int equal(const void *x, const void *y, uint32_t bytes)
{
    const unsigned char *a = x, *b = y;
    for (uint32_t i = 0; i < bytes; i++)
        if (a[i] != b[i])
            return 0;
    return 1;
}

static int zero(const void *pointer, uint32_t bytes)
{
    const unsigned char *p = pointer;
    for (uint32_t i = 0; i < bytes; i++)
        if (p[i])
            return 0;
    return 1;
}

static int held(const struct npu_admission *a, const struct npu_barrier *b,
    const struct npu_bootstrap *boot, uint32_t active)
{
    if (a->closed != 1 || a->active != active || a->fault || load(&b->request) != 1 ||
        load(&b->fault) || load(&b->prepared) || load(&b->released) || load(&b->armed) ||
        boot->magic != NPU_BOOTSTRAP_MAGIC || boot->failed || boot->inflight ||
        boot->step != NPU_BOOTSTRAP_STEPS || boot->retained_mask != 0x1e)
        return 0;
    for (uint32_t i = 0; i < NPU_BARRIER_WORKERS; i++)
        if (load(&b->parked[i]) != 1 || load(&b->ready[i]))
            return 0;
    for (uint32_t i = 0; i < NPU_BARRIER_DOMAINS; i++)
        if (load(&b->drained[i]))
            return 0;
    for (uint32_t i = 0; i < NPU_ADMISSION_IRQ_WORDS; i++)
        if (a->deferred[i])
            return 0;
    return 1;
}

static uint32_t fail(struct npu_rro_session *s, struct npu_admission *a,
    struct npu_barrier *b, uint32_t status)
{
    if (!s->error)
        s->error = status;
    if (s->owner.magic == NPU_RRO_MAGIC)
        npu_rro_fault(&s->owner, NPU_RRO_HELD);
    npu_admission_fail(a, b);
    return status;
}

static int plan_matches(const struct npu_rro_plan *p, const struct npu_bootstrap *boot,
    const struct npu_cold_setup *cold)
{
    if (p->bar.address != cold->endpoint_base || p->bar.bytes != cold->endpoint_bytes ||
        p->rx_event.address != cold->rx_event || p->rx_event.bytes != 8192 || !cold->rx_event ||
        cold->txbuf_enrolled != NPU_COLD_TXBUF_RECORDS ||
        !npu_cold_txbuf_dma_valid(&cold->txbuf, NPU_COLD_TXBUF_RECORDS))
        return 0;
    for (uint32_t i = 0; i < 8; i++)
        if (p->mailbox[i].address != cold->txbuf.mailbox[i] || p->mailbox[i].bytes != 256)
            return 0;
    for (uint32_t i = 0; i < 6; i++)
        if (p->tx[i].address != cold->txbuf.host[i] || p->tx[i].bytes != npu_cold_txbuf_bytes(i) ||
            p->native[i].address != boot->plan.region[i].base ||
            p->native[i].bytes != boot->plan.region[i].bytes ||
            cold->txbuf.boot.region[i].base != boot->plan.region[i].base ||
            cold->txbuf.boot.region[i].bytes != boot->plan.region[i].bytes)
            return 0;
    return 1;
}

static int early(const struct npu_cold_setup *c)
{
    return !c->failed && !c->inflight && c->completed ==
        (NPU_COLD_ENDPOINT_BASE | NPU_COLD_ENDPOINT_BYTES) &&
        !c->descriptor_gets && !c->descriptor_arena && !c->txbuf_steps &&
        !c->rx_event_steps && !c->pcie_tail_steps && !c->inode_steps && !c->txbuf.arena;
}

static uint32_t core_status(uint32_t status)
{
    return status ? NPU_RRO_WIRE_CORE + status : NPU_RRO_WIRE_OK;
}

static uint32_t operation(struct npu_rro_session *s, const struct npu_rro_wire_message *m,
    const struct npu_rro_native_context *context)
{
    uint32_t ticket, status, slot;

    switch (m->operation) {
    case NPU_RRO_WIRE_OPEN:
        if (s->magic || s->owner.magic)
            return NPU_RRO_WIRE_STATE;
        copy(&s->plan, &m->plan, sizeof(s->plan));
        status = npu_rro_open(&s->owner, &s->plan);
        if (!status)
            s->magic = NPU_RRO_SESSION_MAGIC;
        return core_status(status);
    case NPU_RRO_WIRE_ENROLL:
        if (m->ordinal != s->owner.allocated)
            return NPU_RRO_WIRE_STATE;
        return core_status(npu_rro_enroll(&s->owner, &s->plan, &m->extent));
    case NPU_RRO_WIRE_PUBLISH:
        slot = m->ordinal == NPU_RRO_BLOCKS ? npu_rro_extent_count(s->plan.profile) - 1 :
            m->ordinal + (s->plan.profile == NPU_RRO_V3 ? 2 : 0);
        if (slot >= s->owner.allocated || s->owner.last_ticket >= UINT32_MAX - 1 ||
            m->ticket != s->owner.last_ticket + 1 ||
            m->command.words[1] != s->owner.extents[slot].dma_lo)
            return NPU_RRO_WIRE_STATE;
        return core_status(npu_rro_native_publish(&s->owner, &s->plan, m->ordinal, context));
    case NPU_RRO_WIRE_HARDWARE:
        return core_status(npu_rro_hardware_begin(&s->owner, &s->plan));
    case NPU_RRO_WIRE_RESET_NPU:
        status = npu_rro_reset_queue(&s->owner, &s->plan, m->session, m->generation, &ticket);
        if (status && status != NPU_RRO_DUPLICATE)
            return core_status(status);
        if (ticket != m->ticket)
            return NPU_RRO_WIRE_STATE;
        return core_status(npu_rro_native_reset(&s->owner, &s->plan,
            m->session, m->generation, ticket, context));
    case NPU_RRO_WIRE_MCU_BEGIN:
        return core_status(npu_rro_reset_mcu_begin(&s->owner, &s->plan,
            m->session, m->generation, m->ticket));
    case NPU_RRO_WIRE_MCU_COMPLETE:
        return core_status(npu_rro_reset_mcu_complete(&s->owner, &s->plan,
            m->session, m->generation, m->ticket, (int32_t)m->mcu_error));
    case NPU_RRO_WIRE_CLOSE:
        status = npu_rro_retirement_begin(&s->owner, &s->plan, m->stop_epoch, &ticket);
        if (status && status != NPU_RRO_DUPLICATE)
            return core_status(status);
        return ticket == m->ticket ? NPU_RRO_WIRE_OK : NPU_RRO_WIRE_STATE;
    default:
        return NPU_RRO_WIRE_BAD_MESSAGE;
    }
}

int npu_rro_session_dispatch(struct npu_rro_session *s, struct npu_control_v2_session *session,
    struct npu_admission *a, struct npu_barrier *b, const struct npu_bootstrap *boot,
    const struct npu_cold_setup *cold, void *packet, uint32_t bytes,
    const struct npu_rro_native_context *context)
{
    struct npu_rro_wire_message message;
    uint32_t status = NPU_RRO_WIRE_OK;

    if (!s || !session || !a || !b || !boot || !cold ||
        npu_rro_wire_decode(&message, packet, bytes, 0))
        return 0;
    if (!(session->boot_lo || session->boot_hi) ||
        message.plan.identity.boot_lo != session->boot_lo || message.plan.identity.boot_hi != session->boot_hi)
        status = NPU_RRO_WIRE_BAD_BOOT;
    else if (!(session->nonce_lo || session->nonce_hi) ||
        message.plan.identity.nonce_lo != session->nonce_lo || message.plan.identity.nonce_hi != session->nonce_hi ||
        a->nonce_lo != session->nonce_lo || a->nonce_hi != session->nonce_hi ||
        message.plan.identity.epoch != 1 ||
        (s->magic && !equal(&message.plan, &s->plan, sizeof(struct npu_rro_identity) + 4)))
        status = NPU_RRO_WIRE_BAD_IDENTITY;
    else if (message.sequence <= session->last_sequence)
        status = NPU_RRO_WIRE_REPLAY;
    else {
        /* Consume correlated sequence before mutable platform/operation checks. */
        session->last_sequence = s->sequence = message.sequence;
        if (message.operation == NPU_RRO_WIRE_CLOSE && s->magic == NPU_RRO_SESSION_MAGIC) {
            status = operation(s, &message, context);
            if (status)
                status = fail(s, a, b, status);
        } else if (s->error || s->inflight || cold->failed || cold->inflight ||
            !held(a, b, boot, 0) ||
            (message.operation == NPU_RRO_WIRE_OPEN ?
                s->magic || !zero(&s->owner, sizeof(s->owner)) || !zero(&s->plan, sizeof(s->plan)) ||
                !early(cold) || !plan_matches(&message.plan, boot, cold) :
                s->magic != NPU_RRO_SESSION_MAGIC || !plan_matches(&s->plan, boot, cold)) ||
            (message.operation <= NPU_RRO_WIRE_HARDWARE && !early(cold)))
            status = fail(s, a, b, NPU_RRO_WIRE_STATE);
        else {
            s->inflight = a->active = 1;
            status = operation(s, &message, context);
            if (status || !held(a, b, boot, 1))
                status = fail(s, a, b, status ? status : NPU_RRO_WIRE_STATE);
            else
                s->inflight = a->active = 0;
        }
    }
    return npu_rro_wire_reply(packet, bytes, status) == NPU_RRO_WIRE_OK;
}

int npu_rro_session_cold_ready(const struct npu_rro_session *s)
{
    struct npu_rro_retirement snapshot;

    if (!s)
        return 0;
    if (!s->magic)
        return zero(s, sizeof(*s));
    return s->magic == NPU_RRO_SESSION_MAGIC && !s->error && !s->inflight &&
        !npu_rro_retirement_snapshot(&s->owner, &s->plan, &snapshot) &&
        snapshot.phase == NPU_RRO_LIVE && !snapshot.error &&
        snapshot.allocated == npu_rro_extent_count(s->plan.profile) &&
        snapshot.confirmed_publications == NPU_RRO_PUBLICATIONS && s->owner.hardware_exposed;
}
