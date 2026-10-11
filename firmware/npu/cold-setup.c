#include "cold-setup.h"

_Static_assert(sizeof(struct npu_cold_packet) == NPU_COLD_SIZE, "cold wire changed");
_Static_assert(sizeof(struct npu_cold_setup) == 120, "cold owner changed");

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

static int window(uint32_t base, uint32_t bytes, const struct npu_bootstrap *boot)
{
    uint32_t i;

    if (!npu_cold_endpoint_valid(base, bytes))
        return 0;
    for (i = 0; i < NPU_BOOT_REGIONS; i++) {
        const struct npu_bootstrap_range *r = &boot->plan.region[i];

        if (r->bytes && base < r->base + r->bytes && r->base < base + bytes)
            return 0;
    }
    return 1;
}

static int history(const struct npu_cold_setup *s, const struct npu_bootstrap *boot)
{
    static const uint32_t prefixes[] = {0, 8, 24, 25, 27, 31, 63, 127, 255, 511,
        1023, 2047, 4095, 8191, 16383, 32767, 65535, 131071};
    static const uint32_t bits[NPU_COLD_COUNTS] = {NPU_COLD_RX0, NPU_COLD_RX2,
        NPU_COLD_PAGE5, NPU_COLD_PAGE6, NPU_COLD_PAGE7};
    static const uint32_t limits[NPU_COLD_COUNTS] = {1536, 1024, 256, 512, 1024};
    uint32_t i;

    if (s->descriptor_gets > NPU_COLD_DESCRIPTOR_STEPS ||
        (s->descriptor_gets ? s->completed != NPU_COLD_COMPLETED_MASK ||
         !npu_cold_descriptor_arena_valid(s->descriptor_arena) : !!s->descriptor_arena))
        return 0;
    for (i = 0; i < sizeof(prefixes) / sizeof(prefixes[0]); i++)
        if (s->completed == prefixes[i])
            break;
    if (i == sizeof(prefixes) / sizeof(prefixes[0]))
        return 0;
    for (i = 0; i < NPU_COLD_COUNTS; i++) {
        if (s->completed & bits[i]) {
            if (!s->counts[i] || s->counts[i] > limits[i] ||
                ((s->completed & NPU_COLD_ADDR8) && s->counts[i] != limits[i]))
                return 0;
        } else if (s->counts[i]) {
            return 0;
        }
    }
    if (!(s->completed & NPU_COLD_ENDPOINT_BASE))
        return !s->endpoint_base && !s->endpoint_bytes;
    if (!s->endpoint_base || (s->endpoint_base & 4095u) || s->endpoint_base >= 0xc0000000u)
        return 0;
    return s->completed & NPU_COLD_ENDPOINT_BYTES ?
           window(s->endpoint_base, s->endpoint_bytes, boot) : !s->endpoint_bytes;
}

static uint32_t command_bit(const struct npu_bootstrap_packet *p,
                            const struct npu_cold_setup *s, const struct npu_bootstrap *boot)
{
    static const uint32_t limits[] = {256, 512, 1024};
    uint32_t i;

    if (p->header == NPU_COLD_BIND_HEADER && p->api == NPU_COLD_BIND_BASE_API &&
        p->value && !(p->value & 4095u) && p->value < 0xc0000000u)
        return NPU_COLD_ENDPOINT_BASE;
    if (p->header == NPU_COLD_BIND_HEADER && p->api == NPU_COLD_BIND_BYTES_API &&
        window(s->endpoint_base, p->value, boot))
        return NPU_COLD_ENDPOINT_BYTES;
    if (p->header == 0x10 && p->api == 14 && p->value == 2)
        return NPU_COLD_PORT;
    if (p->header == 0x10 && p->api == 1 && p->value && p->value <= 1536)
        return NPU_COLD_RX0;
    if (p->header == 0x12 && p->api == 1 && p->value && p->value <= 1024)
        return NPU_COLD_RX2;
    for (i = 0; i < 3; i++) {
        if (p->header != 0x15u + i)
            continue;
        if (p->api == 0 && window(s->endpoint_base, s->endpoint_bytes, boot) &&
            p->value == s->endpoint_base + NPU_COLD_PAGE_REG0 + 0x10u * i)
            return NPU_COLD_ADDR5 << (i * 2);
        if (p->api == 1 && p->value && p->value <= limits[i])
            return NPU_COLD_PAGE5 << (i * 2);
    }
    if (p->header == 0x18 && p->api == 0 &&
        window(s->endpoint_base, s->endpoint_bytes, boot) &&
        p->value == s->endpoint_base + NPU_COLD_IND_REG)
        return NPU_COLD_ADDR8;
    if (p->header == 0x18 && p->api == 1 && p->value == 1536)
        return NPU_COLD_INDICATION;
    if (p->header == 0x13 && p->api == 19 &&
        window(s->endpoint_base, s->endpoint_bytes, boot) &&
        p->value == s->endpoint_base + NPU_COLD_ACK_REG)
        return NPU_COLD_ACK;
    if (p->api == 19 && window(s->endpoint_base, s->endpoint_bytes, boot)) {
        if (p->header == 0x10 && p->value == s->endpoint_base + NPU_COLD_TX_REG0)
            return NPU_COLD_TX0;
        if (p->header == 0x12 &&
            (p->value == s->endpoint_base + NPU_COLD_TX_REG2 ||
             p->value == s->endpoint_base + NPU_COLD_TX_REG2 + NPU_COLD_TX_HIF2) &&
            p->value - s->endpoint_base <= s->endpoint_bytes - 12)
            return NPU_COLD_TX2;
    }
    if (p->header == 0x10 && p->api == 33 && p->value == 8192)
        return NPU_COLD_TOKEN;
    return 0;
}

static uint32_t prior(uint32_t bit)
{
    switch (bit) {
    case NPU_COLD_ENDPOINT_BASE: return 0;
    case NPU_COLD_ENDPOINT_BYTES: return NPU_COLD_ENDPOINT_BASE;
    case NPU_COLD_PORT: return NPU_COLD_ENDPOINT_BASE | NPU_COLD_ENDPOINT_BYTES;
    case NPU_COLD_RX0: return 25;
    case NPU_COLD_RX2: return 27;
    default: return bit - 1;
    }
}

enum npu_cold_status npu_cold_setup_begin(struct npu_cold_setup *s,
    struct npu_control_v2_session *session, struct npu_admission *a,
    struct npu_barrier *b, const struct npu_bootstrap *boot,
    const struct npu_cold_packet *packet, uint32_t bytes)
{
    struct npu_cold_packet p;
    static const uint32_t limits[NPU_COLD_COUNTS] = {1536, 1024, 256, 512, 1024};
    uint32_t i, bit, descriptor;

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
    if (s->failed || s->inflight || !history(s, boot) ||
        p.epoch != 1 || !held(a, b, boot, 0))
        return fail(s, a, b, NPU_COLD_BAD_STATE);
    bit = command_bit(&p.command, s, boot);
    descriptor = npu_cold_descriptor_command_step(&p.command);
    if (!bit && descriptor == NPU_COLD_DESCRIPTOR_STEPS &&
        !(p.command.header == 0x30 && p.command.api == 10 && !p.command.value))
        return fail(s, a, b, NPU_COLD_UNSUPPORTED);
    if (descriptor < NPU_COLD_DESCRIPTOR_STEPS &&
        (s->completed != NPU_COLD_COMPLETED_MASK || descriptor != s->descriptor_gets))
        return fail(s, a, b, NPU_COLD_BAD_STATE);
    if (bit && s->completed != prior(bit))
        return fail(s, a, b, NPU_COLD_BAD_STATE);
    for (i = 0; i < NPU_COLD_COUNTS; i++) {
        if (bit == NPU_COLD_ADDR8 && s->counts[i] != limits[i])
            return fail(s, a, b, NPU_COLD_BAD_STATE);
        s->prior_counts[i] = s->counts[i];
    }
    s->command = p.command;
    s->sequence = p.sequence;
    s->boot_lo = p.boot_lo;
    s->boot_hi = p.boot_hi;
    s->nonce_lo = p.nonce_lo;
    s->nonce_hi = p.nonce_hi;
    s->prior_completed = s->completed;
    s->prior_base = s->endpoint_base;
    s->prior_bytes = s->endpoint_bytes;
    s->prior_descriptor_gets = s->descriptor_gets;
    s->prior_descriptor_arena = s->descriptor_arena;
    s->inflight = a->active = 1;
    return NPU_COLD_OK;
}

enum npu_cold_status npu_cold_setup_finish(struct npu_cold_setup *s,
    struct npu_control_v2_session *session, struct npu_admission *a,
    struct npu_barrier *b, const struct npu_bootstrap *boot,
    uint32_t result, const struct npu_bootstrap_packet *reply)
{
    static const uint32_t bits[NPU_COLD_COUNTS] = {NPU_COLD_RX0, NPU_COLD_RX2,
        NPU_COLD_PAGE5, NPU_COLD_PAGE6, NPU_COLD_PAGE7};
    uint32_t bit = command_bit(&s->command, s, boot), i;
    uint32_t descriptor = npu_cold_descriptor_command_step(&s->command), arena = 0;

    if (reply && descriptor < NPU_COLD_DESCRIPTOR_STEPS)
        arena = npu_cold_descriptor_reply_arena(descriptor, reply->value, s->descriptor_arena);

    for (i = 0; i < NPU_COLD_COUNTS; i++)
        if (s->counts[i] != s->prior_counts[i])
            return fail(s, a, b, NPU_COLD_CALLBACK_FAILED);

    if (s->failed || s->inflight != 1 || !held(a, b, boot, 1) ||
        session->last_sequence != s->sequence ||
        session->boot_lo != s->boot_lo || session->boot_hi != s->boot_hi ||
        session->nonce_lo != s->nonce_lo || session->nonce_hi != s->nonce_hi ||
        a->nonce_lo != s->nonce_lo || a->nonce_hi != s->nonce_hi ||
        s->completed != s->prior_completed || s->endpoint_base != s->prior_base ||
        s->descriptor_gets != s->prior_descriptor_gets ||
        s->descriptor_arena != s->prior_descriptor_arena ||
        s->endpoint_bytes != s->prior_bytes || !history(s, boot) ||
        (bit && s->completed != prior(bit)) ||
        (descriptor < NPU_COLD_DESCRIPTOR_STEPS &&
         (descriptor != s->descriptor_gets || s->completed != NPU_COLD_COMPLETED_MASK || !arena)) ||
        (!bit && descriptor == NPU_COLD_DESCRIPTOR_STEPS &&
         !(s->command.header == 0x30 && s->command.api == 10 && !s->command.value)) ||
        !reply || result != 1 || reply->header != s->command.header ||
        reply->api != s->command.api ||
        (descriptor == NPU_COLD_DESCRIPTOR_STEPS && reply->value != (bit ? s->command.value : 0x457u)))
        return fail(s, a, b, NPU_COLD_CALLBACK_FAILED);
    if (descriptor < NPU_COLD_DESCRIPTOR_STEPS) {
        s->descriptor_arena = arena;
        s->descriptor_gets++;
    }
    if (bit == NPU_COLD_ENDPOINT_BASE)
        s->endpoint_base = s->command.value;
    if (bit == NPU_COLD_ENDPOINT_BYTES)
        s->endpoint_bytes = s->command.value;
    for (i = 0; i < NPU_COLD_COUNTS; i++)
        if (bit == bits[i])
            s->counts[i] = s->command.value;
    s->completed |= bit;
    s->inflight = a->active = 0;
    return NPU_COLD_OK;
}
