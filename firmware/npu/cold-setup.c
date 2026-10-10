#include "cold-setup.h"

_Static_assert(sizeof(struct npu_cold_packet) == NPU_COLD_SIZE, "cold wire changed");
_Static_assert(sizeof(struct npu_cold_setup) == 48, "cold owner changed");

static uint32_t load(const uint32_t *word)
{
    return __atomic_load_n(word, __ATOMIC_ACQUIRE);
}

static int held(const struct npu_admission *a, const struct npu_barrier *b,
                const struct npu_bootstrap *boot, uint32_t active)
{
    uint32_t i;

    if (a->closed != 1 || a->active != active || a->fault ||
        !(a->nonce_lo || a->nonce_hi) || load(&b->request) != 1 ||
        load(&b->fault) || load(&b->prepared) || load(&b->released) || load(&b->armed) ||
        boot->magic != NPU_BOOTSTRAP_MAGIC || boot->failed || boot->inflight ||
        boot->step != NPU_BOOTSTRAP_STEPS || boot->retained_mask != 0x1e)
        return 0;
    for (i = 0; i < NPU_BARRIER_WORKERS; i++)
        if (load(&b->parked[i]) != 1 || load(&b->ready[i]))
            return 0;
    for (i = 0; i < NPU_BARRIER_DOMAINS; i++)
        if (load(&b->drained[i]))
            return 0;
    for (i = 0; i < NPU_ADMISSION_IRQ_WORDS; i++)
        if (a->deferred[i])
            return 0;
    return 1;
}

static enum npu_cold_status fail(struct npu_cold_setup *s,
    struct npu_admission *a, struct npu_barrier *b, enum npu_cold_status error)
{
    s->failed = 1;
    npu_admission_fail(a, b);
    return error;
}

static uint32_t command_bit(const struct npu_bootstrap_packet *p)
{
    if (p->header == 0x10 && p->api == 14 && p->value == 2)
        return NPU_COLD_PORT;
    if (p->header == 0x10 && p->api == 1 && p->value && p->value <= 1536)
        return NPU_COLD_RX0;
    if (p->header == 0x12 && p->api == 1 && p->value && p->value <= 1024)
        return NPU_COLD_RX2;
    return 0;
}

enum npu_cold_status npu_cold_setup_begin(struct npu_cold_setup *s,
    struct npu_control_v2_session *session, struct npu_admission *a,
    struct npu_barrier *b, const struct npu_bootstrap *boot,
    const struct npu_cold_packet *packet, uint32_t bytes)
{
    struct npu_cold_packet p;
    uint32_t i, bit;

    if (!packet || bytes != sizeof(p))
        return NPU_COLD_BAD_MESSAGE;
    npu_cold_packet_copy(&p, packet);
    if (p.header != NPU_CONTROL_HEADER || p.api != NPU_COLD_API ||
        p.magic != NPU_COLD_REQUEST || p.version != NPU_COLD_VERSION ||
        p.bytes != sizeof(p) || !p.sequence || p.status)
        return NPU_COLD_BAD_MESSAGE;
    for (i = 0; i < 5; i++)
        if (p.reserved[i])
            return NPU_COLD_BAD_MESSAGE;
    if (!(session->boot_lo || session->boot_hi) ||
        p.boot_lo != session->boot_lo || p.boot_hi != session->boot_hi)
        return NPU_COLD_BAD_BOOT;
    if (!(session->nonce_lo || session->nonce_hi) ||
        p.nonce_lo != session->nonce_lo || p.nonce_hi != session->nonce_hi ||
        a->nonce_lo != session->nonce_lo || a->nonce_hi != session->nonce_hi)
        return NPU_COLD_BAD_SESSION;
    if (p.sequence <= session->last_sequence)
        return NPU_COLD_REPLAY;
    /* Reserve before platform/command checks: abandonment never enables replay. */
    session->last_sequence = p.sequence;
    if (s->failed || s->inflight || (s->completed & ~7u) ||
        p.epoch != 1 || !held(a, b, boot, 0))
        return fail(s, a, b, NPU_COLD_BAD_STATE);
    bit = command_bit(&p.command);
    if (!bit && !(p.command.header == 0x30 && p.command.api == 10 && !p.command.value))
        return fail(s, a, b, NPU_COLD_UNSUPPORTED);
    if ((bit && (s->completed & bit)) ||
        (bit == NPU_COLD_PORT && s->completed) ||
        (bit == NPU_COLD_RX0 && s->completed != NPU_COLD_PORT) ||
        (bit == NPU_COLD_RX2 && s->completed != (NPU_COLD_PORT | NPU_COLD_RX0)))
        return fail(s, a, b, NPU_COLD_BAD_STATE);
    s->command = p.command;
    s->sequence = p.sequence;
    s->boot_lo = p.boot_lo;
    s->boot_hi = p.boot_hi;
    s->nonce_lo = p.nonce_lo;
    s->nonce_hi = p.nonce_hi;
    s->prior_completed = s->completed;
    s->inflight = a->active = 1;
    return NPU_COLD_OK;
}

enum npu_cold_status npu_cold_setup_finish(struct npu_cold_setup *s,
    struct npu_control_v2_session *session, struct npu_admission *a,
    struct npu_barrier *b, const struct npu_bootstrap *boot,
    uint32_t result, const struct npu_bootstrap_packet *reply)
{
    uint32_t bit = command_bit(&s->command);

    if (s->failed || s->inflight != 1 || !held(a, b, boot, 1) ||
        session->last_sequence != s->sequence ||
        session->boot_lo != s->boot_lo || session->boot_hi != s->boot_hi ||
        session->nonce_lo != s->nonce_lo || session->nonce_hi != s->nonce_hi ||
        a->nonce_lo != s->nonce_lo || a->nonce_hi != s->nonce_hi ||
        s->completed != s->prior_completed ||
        !reply || result != 1 || reply->header != s->command.header ||
        reply->api != s->command.api ||
        reply->value != (bit ? s->command.value : 0x457u))
        return fail(s, a, b, NPU_COLD_CALLBACK_FAILED);
    s->completed |= bit;
    s->inflight = a->active = 0;
    return NPU_COLD_OK;
}
