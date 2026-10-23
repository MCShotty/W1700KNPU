#include "rro-lifetime.h"
#include "cold-setup.h"

#ifdef __KERNEL__
#include <linux/atomic.h>
#endif

typedef __UINTPTR_TYPE__ address_t;

_Static_assert(sizeof(struct npu_rro_identity) == 36, "RRO identity layout");
_Static_assert(sizeof(struct npu_rro_plan) == 216, "RRO plan layout");
_Static_assert(sizeof(struct npu_rro_extent) == 28, "RRO extent layout");
_Static_assert(sizeof(int) == 4, "RRO error width");

static void copy(void *destination, const void *source, uint32_t bytes)
{
    volatile unsigned char *to = destination;
    const volatile unsigned char *from = source;
    for (uint32_t i = 0; i < bytes; i++)
        to[i] = from[i];
}

static int equal(const void *a, const void *b, uint32_t bytes)
{
    const volatile unsigned char *x = a, *y = b;
    for (uint32_t i = 0; i < bytes; i++)
        if (x[i] != y[i])
            return 0;
    return 1;
}

static int zero(const void *p, uint32_t bytes)
{
    const volatile unsigned char *data = p;
    for (uint32_t i = 0; i < bytes; i++)
        if (data[i])
            return 0;
    return 1;
}

/* Volatile stores keep the freestanding RV32 object independent of memset. */
static void clear(void *p, uint32_t bytes)
{
    volatile unsigned char *data = p;
    for (uint32_t i = 0; i < bytes; i++)
        data[i] = 0;
}

static int aligned(const void *p)
{
    return p && !((address_t)p & 3u);
}

static int disjoint(const void *a, uint32_t an, const void *b, uint32_t bn)
{
    address_t x = (address_t)a, y = (address_t)b;
    return x && y && an <= ~(address_t)0 - x && bn <= ~(address_t)0 - y &&
           (x + an <= y || y + bn <= x);
}

static uint32_t maximum(uint32_t a, uint32_t b)
{
    return a > b ? a : b;
}

uint32_t npu_rro_extent_count(uint32_t profile)
{
    return profile <= NPU_RRO_V3_1_WED ? profile == NPU_RRO_V3_1_WED ? 137u : 139u : 0;
}

uint32_t npu_rro_extent_geometry(uint32_t profile, uint32_t ordinal,
                                struct npu_rro_extent *out)
{
    struct npu_rro_extent result;
    uint32_t index = ordinal;

    if (!aligned(out) || ordinal >= npu_rro_extent_count(profile))
        return NPU_RRO_ARGUMENT;
    clear(&result, sizeof(result));
    result.bytes = NPU_RRO_BLOCK_BYTES;
    if (profile == NPU_RRO_V3 && index < 2) {
        result.role = NPU_RRO_BA;
        result.index = index;
    } else {
        if (profile == NPU_RRO_V3)
            index -= 2;
        if (index < NPU_RRO_BLOCKS) {
            result.role = NPU_RRO_ELEMENT;
            result.index = index;
        } else if ((index -= NPU_RRO_BLOCKS) < 8) {
            result.role = NPU_RRO_MSDU;
            result.index = index;
        } else if (profile == NPU_RRO_V3_1 && index < 10) {
            result.role = index == 8 ? NPU_RRO_EMI_CPU : NPU_RRO_EMI_DMA;
            result.bytes = 16;
        } else {
            result.role = NPU_RRO_SESSION;
            result.bytes = NPU_RRO_SESSION_BYTES;
        }
    }
    copy(out, &result, sizeof(result));
    return NPU_RRO_OK;
}

static uint64_t cpu_address(const struct npu_rro_extent *r)
{
    return ((uint64_t)r->cpu_hi << 32) | r->cpu_lo;
}

static int span_valid(struct npu_rro_span span)
{
    return span.address && span.bytes &&
           (uint64_t)span.address + span.bytes <= ((uint64_t)UINT32_MAX + 1);
}

static int aliases_overlap(uint32_t a, uint32_t an, uint32_t b, uint32_t bn)
{
    uint64_t x = a & 0x3fffffffu, y = b & 0x3fffffffu;
    const uint64_t window = 0x40000000u;

    if (an >= window || bn >= window)
        return 1;
    if (y + bn > window)
        return x < y + bn - window || x + an > y;
    return x < y + bn && y < x + an;
}

static struct npu_rro_span protected_span(const struct npu_rro_plan *p, uint32_t index)
{
    if (index < 8)
        return p->mailbox[index];
    if (index < 14)
        return p->tx[index - 8];
    if (index == 14)
        return p->rx_event;
    return index < 21 ? p->native[index - 15] : p->bar;
}

static int plan_valid(const struct npu_rro_plan *p)
{
    const struct npu_rro_identity *id = &p->identity;

    if (!(id->provider_lo | id->provider_hi) || !(id->endpoint_lo | id->endpoint_hi) ||
        (id->provider_lo == id->endpoint_lo && id->provider_hi == id->endpoint_hi) ||
        !(id->boot_lo | id->boot_hi) || !(id->nonce_lo | id->nonce_hi) || !id->epoch ||
        !npu_rro_extent_count(p->profile) ||
        !npu_cold_endpoint_valid(p->bar.address, p->bar.bytes) ||
        p->rx_event.bytes != NPU_COLD_RX_EVENT_BYTES)
        return 0;
    for (uint32_t i = 0; i < 22; i++) {
        struct npu_rro_span span = protected_span(p, i);
        if (!span_valid(span))
            return 0;
        if (i >= 8 && i < 14 && span.bytes != (i < 10 ? 0x20000u : 0x40000u))
            return 0;
    }
    return 1;
}

static uint32_t publication_slot(uint32_t profile, uint32_t ordinal)
{
    return ordinal == NPU_RRO_BLOCKS ? npu_rro_extent_count(profile) - 1 :
           ordinal + (profile == NPU_RRO_V3 ? 2u : 0u);
}

static uint32_t error(const struct npu_rro_lifetime *s)
{
#ifdef __KERNEL__
    return smp_load_acquire(&s->error);
#else
    return __atomic_load_n(&s->error, __ATOMIC_ACQUIRE);
#endif
}

void npu_rro_fault(struct npu_rro_lifetime *s, uint32_t status)
{
    if (aligned(s) && s->magic == NPU_RRO_MAGIC && status) {
#ifdef __KERNEL__
        (void)cmpxchg_release(&s->error, 0, status);
#else
        uint32_t expected = 0;
        __atomic_compare_exchange_n(&s->error, &expected, status, 0, __ATOMIC_RELEASE, __ATOMIC_RELAXED);
#endif
    }
}

static int record_valid(const struct npu_rro_lifetime *s, uint32_t ordinal,
                         const struct npu_rro_extent *r)
{
    struct npu_rro_extent shape;
    uint64_t cpu = cpu_address(r);
    uint32_t low = r->dma_lo & 0x3fffffffu;

    if (npu_rro_extent_geometry(s->plan.profile, ordinal, &shape) ||
        r->role != shape.role || r->index != shape.index || r->bytes != shape.bytes ||
        !cpu || (cpu & 3u) || r->bytes > ~(uint64_t)0 - cpu ||
        r->dma_hi || !r->dma_lo || (r->dma_lo & 3u) || r->bytes > 0x40000000u - low)
        return 0;
    for (uint32_t i = 0; i < 22; i++) {
        struct npu_rro_span span = protected_span(&s->plan, i);
        if (aliases_overlap(r->dma_lo, r->bytes, span.address, span.bytes))
            return 0;
    }
    for (uint32_t i = 0; i < ordinal; i++) {
        const struct npu_rro_extent *held = &s->extents[i];
        uint64_t before = cpu_address(held);
        if ((cpu < before + held->bytes && before < cpu + r->bytes) ||
            aliases_overlap(r->dma_lo, r->bytes, held->dma_lo, held->bytes))
            return 0;
    }
    return 1;
}

static int state_valid(const struct npu_rro_lifetime *s)
{
    uint32_t highest = 0, count = npu_rro_extent_count(s->plan.profile), npu = 0, mcu = 0;
    if (s->magic != NPU_RRO_MAGIC || !plan_valid(&s->plan) ||
        s->phase < NPU_RRO_BUILDING || s->phase > NPU_RRO_DRAIN_RECORDED ||
        s->allocated > count || s->confirmed > NPU_RRO_PUBLICATIONS ||
        s->hardware_exposed > 1 || s->cpu_joined > 1 ||
        (s->hardware_exposed && (s->allocated != count || s->confirmed != NPU_RRO_PUBLICATIONS)) ||
        (s->phase == NPU_RRO_BUILDING && s->hardware_exposed) ||
        (s->phase == NPU_RRO_LIVE && !s->hardware_exposed))
        return 0;
    for (uint32_t i = 0; i < NPU_RRO_MAX_EXTENTS; i++) {
        if (i >= s->allocated) {
            if (s->exposure[i] || !zero(&s->extents[i], sizeof(s->extents[i])))
                return 0;
        } else if (!record_valid(s, i, &s->extents[i]) ||
                   !(s->exposure[i] & NPU_RRO_ALLOCATED) || s->exposure[i] & ~15u ||
                   !!(s->exposure[i] & NPU_RRO_HARDWARE_POSSIBLE) != !!s->hardware_exposed ||
                   ((s->extents[i].role != NPU_RRO_ELEMENT && s->extents[i].role != NPU_RRO_SESSION) &&
                    s->exposure[i] != (NPU_RRO_ALLOCATED | (s->hardware_exposed ? NPU_RRO_HARDWARE_POSSIBLE : 0u)))) {
            return 0;
        }
    }
    for (uint32_t i = 0; i < NPU_RRO_PUBLICATIONS; i++) {
        const struct npu_rro_publication *p = &s->publication[i];
        uint32_t slot = publication_slot(s->plan.profile, i);
        uint32_t flags = i < s->confirmed ? 7u : p->ticket ? 3u : 1u;
        if ((i < s->confirmed && !p->ticket) || (i > s->confirmed && (p->ticket || p->error)) ||
            (p->ticket && p->ticket != i + 1) || (p->error && !error(s)) ||
            (!p->ticket && p->error) || (p->ticket && slot >= s->allocated))
            return 0;
        if (slot < s->allocated && s->exposure[slot] != (flags | (s->hardware_exposed ? 8u : 0u)))
            return 0;
        highest = maximum(highest, p->ticket);
    }
    for (uint32_t i = 0; i < NPU_RRO_SESSIONS; i++) {
        const struct npu_rro_reset *r = &s->resets[i];
        if (!r->generation || r->phase > NPU_RRO_RESET_COMPLETE ||
            (!r->phase && (r->generation != 1 || r->ticket || r->request_generation || r->npu_error || r->mcu_error)) ||
            (r->phase && (r->ticket <= NPU_RRO_PUBLICATIONS || r->ticket == UINT32_MAX ||
                !r->request_generation || r->request_generation == UINT32_MAX || !s->hardware_exposed)) ||
            (r->phase && (r->phase == NPU_RRO_RESET_COMPLETE ?
                r->request_generation == UINT32_MAX || r->generation != r->request_generation + 1 :
                r->generation != r->request_generation)) ||
            (r->npu_error && r->phase < NPU_RRO_RESET_NPU_POSSIBLE) ||
            (r->mcu_error && r->phase < NPU_RRO_RESET_MCU_POSSIBLE) ||
            ((r->npu_error || r->mcu_error) && !error(s)))
            return 0;
        highest = maximum(highest, r->ticket);
        npu += r->phase == NPU_RRO_RESET_NPU_POSSIBLE;
        mcu += r->phase == NPU_RRO_RESET_MCU_POSSIBLE;
    }
    if (s->phase < NPU_RRO_CLOSING) {
        if (s->retirement_ticket || s->retirement_epoch || s->cpu_joined ||
            !zero(s->drained, sizeof(s->drained)))
            return 0;
    } else {
        uint32_t complete = s->cpu_joined;
        if (!s->retirement_ticket || s->retirement_ticket <= highest || !s->retirement_epoch ||
            (s->retirement_epoch != s->plan.identity.epoch &&
             (s->plan.identity.epoch == UINT32_MAX || s->retirement_epoch != s->plan.identity.epoch + 1)))
            return 0;
        for (uint32_t i = 0; i < NPU_RRO_DRAIN_DOMAINS; i++) {
            if (s->drained[i] && (!s->cpu_joined || s->drained[i] != s->retirement_epoch))
                return 0;
            complete &= !!s->drained[i];
        }
        if ((s->phase == NPU_RRO_DRAIN_RECORDED) != !!complete)
            return 0;
        highest = maximum(highest, s->retirement_ticket);
    }
    return highest == s->last_ticket && npu <= 1 && mcu <= 1;
}

static uint32_t check(const struct npu_rro_lifetime *s, const struct npu_rro_plan *p)
{
    if (!aligned(s) || !aligned(p) || !disjoint(s, sizeof(*s), p, sizeof(*p)))
        return NPU_RRO_ARGUMENT;
    if (!state_valid(s))
        return NPU_RRO_CORRUPT;
    return equal(&s->plan, p, sizeof(*p)) ? NPU_RRO_OK : NPU_RRO_STALE;
}

static int output(const struct npu_rro_lifetime *s, const struct npu_rro_plan *p,
                   const void *out, uint32_t bytes)
{
    return aligned(out) && disjoint(s, sizeof(*s), out, bytes) &&
           disjoint(p, sizeof(*p), out, bytes);
}

uint32_t npu_rro_open(struct npu_rro_lifetime *s, const struct npu_rro_plan *p)
{
    if (!aligned(s) || !aligned(p) || !disjoint(s, sizeof(*s), p, sizeof(*p)))
        return NPU_RRO_ARGUMENT;
    if (!zero(s, sizeof(*s)))
        return NPU_RRO_REINITIALIZE;
    if (!plan_valid(p))
        return NPU_RRO_ARGUMENT;
    copy(&s->plan, p, sizeof(*p));
    for (uint32_t i = 0; i < NPU_RRO_SESSIONS; i++)
        s->resets[i].generation = 1;
    s->phase = NPU_RRO_BUILDING;
    s->magic = NPU_RRO_MAGIC;
    return NPU_RRO_OK;
}

uint32_t npu_rro_enroll(struct npu_rro_lifetime *s, const struct npu_rro_plan *p,
                       const struct npu_rro_extent *r)
{
    uint32_t status = check(s, p);
    if (status)
        return status;
    if (!aligned(r) || !disjoint(s, sizeof(*s), r, sizeof(*r)))
        return NPU_RRO_ARGUMENT;
    if (error(s))
        return NPU_RRO_HELD;
    if (s->phase != NPU_RRO_BUILDING)
        return NPU_RRO_ORDER;
    if (s->allocated == npu_rro_extent_count(p->profile) || !record_valid(s, s->allocated, r))
        return NPU_RRO_ARGUMENT;
    copy(&s->extents[s->allocated], r, sizeof(*r));
    s->exposure[s->allocated++] = NPU_RRO_ALLOCATED;
    return NPU_RRO_OK;
}

uint32_t npu_rro_publish_begin(struct npu_rro_lifetime *s, const struct npu_rro_plan *p,
    uint32_t ordinal, uint32_t *ticket, struct npu_rro_command *command)
{
    struct npu_rro_command frame;
    uint32_t status = check(s, p), slot;
    if (status)
        return status;
    if (ordinal >= NPU_RRO_PUBLICATIONS || !output(s, p, ticket, sizeof(*ticket)) ||
        !output(s, p, command, sizeof(*command)) || !disjoint(ticket, sizeof(*ticket), command, sizeof(*command)))
        return NPU_RRO_ARGUMENT;
    if (error(s))
        return NPU_RRO_HELD;
    if (s->phase != NPU_RRO_BUILDING || ordinal != s->confirmed)
        return NPU_RRO_ORDER;
    if (s->publication[ordinal].ticket)
        return NPU_RRO_BUSY;
    slot = publication_slot(p->profile, ordinal);
    if (slot >= s->allocated)
        return NPU_RRO_ORDER;
    if (s->last_ticket >= UINT32_MAX - 1)
        return NPU_RRO_EXHAUSTED;
    clear(&frame, sizeof(frame));
    frame.selector = ordinal == NPU_RRO_BLOCKS ? 1 : 0;
    frame.words[0] = ordinal == NPU_RRO_BLOCKS ? 0 : ordinal;
    frame.words[1] = s->extents[slot].dma_lo;
    s->publication[ordinal].ticket = ++s->last_ticket;
    s->exposure[slot] |= NPU_RRO_NPU_POSSIBLE;
    copy(command, &frame, sizeof(frame));
    *ticket = s->last_ticket;
    return NPU_RRO_OK;
}

uint32_t npu_rro_publish_complete(struct npu_rro_lifetime *s, const struct npu_rro_plan *p,
    uint32_t ordinal, uint32_t ticket, int transport_error)
{
    uint32_t status = check(s, p);
    if (status)
        return status;
    if (ordinal >= NPU_RRO_PUBLICATIONS || !ticket)
        return NPU_RRO_ARGUMENT;
    if (s->cpu_joined)
        return NPU_RRO_STALE;
    if (s->publication[ordinal].ticket != ticket)
        return NPU_RRO_STALE;
    if (ordinal < s->confirmed)
        return NPU_RRO_DUPLICATE;
    if (ordinal != s->confirmed)
        return NPU_RRO_ORDER;
    if (transport_error) {
        if (!s->publication[ordinal].error)
            s->publication[ordinal].error = (uint32_t)transport_error;
        npu_rro_fault(s, NPU_RRO_PUBLICATION_FAILED);
        return NPU_RRO_HELD;
    }
    s->exposure[publication_slot(p->profile, ordinal)] |= NPU_RRO_NPU_CONFIRMED;
    s->confirmed++;
    return NPU_RRO_OK;
}

uint32_t npu_rro_hardware_begin(struct npu_rro_lifetime *s, const struct npu_rro_plan *p)
{
    uint32_t status = check(s, p);
    if (status)
        return status;
    if (error(s))
        return NPU_RRO_HELD;
    if (s->phase != NPU_RRO_BUILDING || s->allocated != npu_rro_extent_count(p->profile) ||
        s->confirmed != NPU_RRO_PUBLICATIONS)
        return NPU_RRO_ORDER;
    s->hardware_exposed = 1;
    for (uint32_t i = 0; i < s->allocated; i++)
        s->exposure[i] |= NPU_RRO_HARDWARE_POSSIBLE;
    s->phase = NPU_RRO_LIVE;
    return NPU_RRO_OK;
}

uint32_t npu_rro_reset_queue(struct npu_rro_lifetime *s, const struct npu_rro_plan *p,
    uint32_t session, uint32_t generation, uint32_t *ticket)
{
    uint32_t status = check(s, p);
    struct npu_rro_reset *r;
    if (status)
        return status;
    if (session >= NPU_RRO_SESSIONS || !generation || !output(s, p, ticket, sizeof(*ticket)))
        return NPU_RRO_ARGUMENT;
    if (error(s))
        return NPU_RRO_HELD;
    if (s->phase != NPU_RRO_LIVE)
        return NPU_RRO_ORDER;
    r = &s->resets[session];
    if (r->generation != generation)
        return NPU_RRO_STALE;
    if (r->phase && r->phase != NPU_RRO_RESET_COMPLETE) {
        *ticket = r->ticket;
        return NPU_RRO_DUPLICATE;
    }
    if (generation == UINT32_MAX || s->last_ticket >= UINT32_MAX - 1)
        return NPU_RRO_EXHAUSTED;
    *r = (struct npu_rro_reset){generation, generation, ++s->last_ticket, NPU_RRO_RESET_QUEUED, 0, 0};
    *ticket = r->ticket;
    return NPU_RRO_OK;
}

static uint32_t reset_check(const struct npu_rro_lifetime *s, const struct npu_rro_plan *p,
    uint32_t session, uint32_t generation, uint32_t ticket)
{
    uint32_t status = check(s, p);
    if (status)
        return status;
    if (session >= NPU_RRO_SESSIONS || !generation || !ticket)
        return NPU_RRO_ARGUMENT;
    if (s->cpu_joined)
        return NPU_RRO_STALE;
    return s->resets[session].ticket == ticket && s->resets[session].request_generation == generation ?
           NPU_RRO_OK : NPU_RRO_STALE;
}

uint32_t npu_rro_reset_npu_begin(struct npu_rro_lifetime *s, const struct npu_rro_plan *p,
    uint32_t session, uint32_t generation, uint32_t ticket, struct npu_rro_command *command)
{
    struct npu_rro_command frame;
    uint32_t status = reset_check(s, p, session, generation, ticket);
    if (status)
        return status;
    if (!output(s, p, command, sizeof(*command)))
        return NPU_RRO_ARGUMENT;
    if (error(s))
        return NPU_RRO_HELD;
    if (s->phase != NPU_RRO_LIVE || s->resets[session].phase != NPU_RRO_RESET_QUEUED)
        return NPU_RRO_ORDER;
    for (uint32_t i = 0; i < NPU_RRO_SESSIONS; i++)
        if (s->resets[i].phase == NPU_RRO_RESET_NPU_POSSIBLE)
            return NPU_RRO_BUSY;
    clear(&frame, sizeof(frame));
    frame.selector = 3;
    frame.words[0] = session;
    s->resets[session].phase = NPU_RRO_RESET_NPU_POSSIBLE;
    copy(command, &frame, sizeof(frame));
    return NPU_RRO_OK;
}

uint32_t npu_rro_reset_npu_complete(struct npu_rro_lifetime *s, const struct npu_rro_plan *p,
    uint32_t session, uint32_t generation, uint32_t ticket, int transport_error)
{
    uint32_t status = reset_check(s, p, session, generation, ticket);
    struct npu_rro_reset *r;
    if (status)
        return status;
    r = &s->resets[session];
    if (r->phase > NPU_RRO_RESET_NPU_POSSIBLE)
        return NPU_RRO_DUPLICATE;
    if (r->phase != NPU_RRO_RESET_NPU_POSSIBLE)
        return NPU_RRO_ORDER;
    if (transport_error) {
        if (!r->npu_error)
            r->npu_error = (uint32_t)transport_error;
        npu_rro_fault(s, NPU_RRO_NPU_RESET_FAILED);
        return NPU_RRO_HELD;
    }
    r->phase = NPU_RRO_RESET_NPU_CONFIRMED;
    return NPU_RRO_OK;
}

uint32_t npu_rro_reset_mcu_begin(struct npu_rro_lifetime *s, const struct npu_rro_plan *p,
    uint32_t session, uint32_t generation, uint32_t ticket)
{
    uint32_t status = reset_check(s, p, session, generation, ticket);
    if (status)
        return status;
    if (error(s))
        return NPU_RRO_HELD;
    if (s->phase != NPU_RRO_LIVE || s->resets[session].phase != NPU_RRO_RESET_NPU_CONFIRMED)
        return NPU_RRO_ORDER;
    for (uint32_t i = 0; i < NPU_RRO_SESSIONS; i++)
        if (s->resets[i].phase == NPU_RRO_RESET_MCU_POSSIBLE)
            return NPU_RRO_BUSY;
    s->resets[session].phase = NPU_RRO_RESET_MCU_POSSIBLE;
    return NPU_RRO_OK;
}

uint32_t npu_rro_reset_mcu_complete(struct npu_rro_lifetime *s, const struct npu_rro_plan *p,
    uint32_t session, uint32_t generation, uint32_t ticket, int transport_error)
{
    uint32_t status = reset_check(s, p, session, generation, ticket);
    struct npu_rro_reset *r;
    if (status)
        return status;
    r = &s->resets[session];
    if (r->phase == NPU_RRO_RESET_COMPLETE)
        return NPU_RRO_DUPLICATE;
    if (r->phase != NPU_RRO_RESET_MCU_POSSIBLE)
        return NPU_RRO_ORDER;
    if (transport_error) {
        if (!r->mcu_error)
            r->mcu_error = (uint32_t)transport_error;
        npu_rro_fault(s, NPU_RRO_MCU_RESET_FAILED);
        return NPU_RRO_HELD;
    }
    r->generation++;
    r->phase = NPU_RRO_RESET_COMPLETE;
    return NPU_RRO_OK;
}

uint32_t npu_rro_retirement_begin(struct npu_rro_lifetime *s, const struct npu_rro_plan *p,
    uint32_t stop_epoch, uint32_t *ticket)
{
    uint32_t status = check(s, p);
    if (status)
        return status;
    if (!stop_epoch || !output(s, p, ticket, sizeof(*ticket)) ||
        (stop_epoch != p->identity.epoch &&
         (p->identity.epoch == UINT32_MAX || stop_epoch != p->identity.epoch + 1)))
        return NPU_RRO_ARGUMENT;
    if (s->phase >= NPU_RRO_CLOSING) {
        if (s->retirement_epoch != stop_epoch)
            return NPU_RRO_STALE;
        *ticket = s->retirement_ticket;
        return NPU_RRO_DUPLICATE;
    }
    if (s->last_ticket == UINT32_MAX)
        return NPU_RRO_EXHAUSTED;
    s->retirement_ticket = ++s->last_ticket;
    s->retirement_epoch = stop_epoch;
    s->phase = NPU_RRO_CLOSING;
    *ticket = s->retirement_ticket;
    return NPU_RRO_OK;
}

static uint32_t retirement_check(const struct npu_rro_lifetime *s, const struct npu_rro_plan *p,
    uint32_t ticket, uint32_t epoch)
{
    uint32_t status = check(s, p);
    if (status)
        return status;
    return s->phase >= NPU_RRO_CLOSING && ticket && ticket == s->retirement_ticket &&
           epoch == s->retirement_epoch ? NPU_RRO_OK : NPU_RRO_STALE;
}

static void update_retirement(struct npu_rro_lifetime *s)
{
    if (!s->cpu_joined)
        return;
    for (uint32_t i = 0; i < NPU_RRO_DRAIN_DOMAINS; i++)
        if (s->drained[i] != s->retirement_epoch)
            return;
    s->phase = NPU_RRO_DRAIN_RECORDED;
}

uint32_t npu_rro_retirement_join(struct npu_rro_lifetime *s, const struct npu_rro_plan *p,
    uint32_t ticket, uint32_t epoch)
{
    uint32_t status = retirement_check(s, p, ticket, epoch);
    if (status)
        return status;
    s->cpu_joined = 1;
    update_retirement(s);
    return NPU_RRO_OK;
}

uint32_t npu_rro_retirement_record(struct npu_rro_lifetime *s, const struct npu_rro_plan *p,
    uint32_t ticket, uint32_t epoch, uint32_t domain)
{
    uint32_t status = retirement_check(s, p, ticket, epoch);
    if (status)
        return status;
    if (domain >= NPU_RRO_DRAIN_DOMAINS)
        return NPU_RRO_ARGUMENT;
    if (!s->cpu_joined)
        return NPU_RRO_ORDER;
    s->drained[domain] = epoch;
    update_retirement(s);
    return NPU_RRO_OK;
}

uint32_t npu_rro_retirement_snapshot(const struct npu_rro_lifetime *s, const struct npu_rro_plan *p,
    struct npu_rro_retirement *out)
{
    struct npu_rro_retirement result;
    uint32_t status = check(s, p);
    if (status)
        return status;
    if (!output(s, p, out, sizeof(*out)))
        return NPU_RRO_ARGUMENT;
    clear(&result, sizeof(result));
    copy(&result.identity, &s->plan.identity, sizeof(result.identity));
    result.ticket = s->retirement_ticket;
    result.epoch = s->retirement_epoch;
    result.cpu_joined = s->cpu_joined;
    copy(result.drained, s->drained, sizeof(result.drained));
    result.allocated = s->allocated;
    result.confirmed_publications = s->confirmed;
    result.possible_publications = s->confirmed < NPU_RRO_PUBLICATIONS && s->publication[s->confirmed].ticket ? 1 : 0;
    for (uint32_t i = 0; i < NPU_RRO_SESSIONS; i++) {
        result.queued_resets += s->resets[i].phase == NPU_RRO_RESET_QUEUED;
        result.possible_npu_resets += s->resets[i].phase == NPU_RRO_RESET_NPU_POSSIBLE;
        result.possible_mcu_resets += s->resets[i].phase == NPU_RRO_RESET_MCU_POSSIBLE;
    }
    result.error = error(s);
    result.phase = s->phase;
    copy(out, &result, sizeof(result));
    return NPU_RRO_OK;
}
