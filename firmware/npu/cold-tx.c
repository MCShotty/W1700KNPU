#include "cold-tx.h"

_Static_assert(sizeof(struct npu_cold_tx_state) == 80, "TX owner changed");

static uint32_t load(const uint32_t *p)
{
    return __atomic_load_n(p, __ATOMIC_ACQUIRE);
}

void npu_cold_tx_fault(struct npu_cold_tx_state *s)
{
    if (s)
        __atomic_store_n(&s->fault, 1, __ATOMIC_RELEASE);
}

static uint32_t fail(struct npu_cold_tx_state *s, uint32_t status)
{
    npu_cold_tx_fault(s);
    return status;
}

static uint32_t start(uint32_t stage)
{
    return stage * 5;
}

static uint32_t end(uint32_t stage)
{
    return stage == 2 ? NPU_COLD_TX_WRITES : start(stage) + 5;
}

static int plan_valid(const struct npu_cold_tx_plan *p)
{
    uint32_t offset;

    if (!p || (p->arena & 31) || p->arena < 0x3e800000u ||
        p->arena > 0x3e878000u - NPU_COLD_TX_ARENA_BYTES ||
        p->arena_bytes != NPU_COLD_TX_ARENA_BYTES || !p->endpoint_base ||
        (p->endpoint_base & 4095) || (p->endpoint_bytes & 4095) ||
        p->endpoint_base >= 0xc0000000u || p->endpoint_bytes < 0xd442cu ||
        p->endpoint_bytes > 0xc0000000u - p->endpoint_base ||
        p->host0 != p->endpoint_base + 0xd4420u)
        return 0;
    if (!p->host2)
        return 1;
    offset = p->host2 - p->endpoint_base;
    return (offset == 0xd4450u || offset == 0xd8450u) &&
           offset <= p->endpoint_bytes - 12;
}

static int same(const struct npu_cold_tx_plan *a, const struct npu_cold_tx_plan *b)
{
    uint32_t i;

    if (a->arena != b->arena || a->arena_bytes != b->arena_bytes ||
        a->endpoint_base != b->endpoint_base || a->endpoint_bytes != b->endpoint_bytes ||
        a->host0 != b->host0 || a->host2 != b->host2 || a->token_before != b->token_before)
        return 0;
    for (i = 0; i < 4; i++)
        if (a->register_before[i] != b->register_before[i])
            return 0;
    return 1;
}

static void copy_plan(struct npu_cold_tx_plan *to, const struct npu_cold_tx_plan *from)
{
    volatile unsigned char *destination = (volatile void *)to;
    const volatile unsigned char *source = (const volatile void *)from;
    uint32_t i;

    for (i = 0; i < sizeof(*to); i++)
        destination[i] = source[i];
}

static uint32_t valid(struct npu_cold_tx_state *s, const struct npu_cold_tx_plan *p,
                      uint32_t epoch, uint32_t active)
{
    if (!s)
        return NPU_COLD_TX_ARGUMENT;
    if (load(&s->fault))
        return NPU_COLD_TX_FAULT;
    if (!plan_valid(p) || s->magic != NPU_COLD_TX_MAGIC || s->epoch != 1 ||
        s->active != active || s->stage > 2 || !same(&s->plan, p) ||
        s->reserved != (1u << (s->stage + 1)) - 1 ||
        s->completed != (active ? (1u << s->stage) - 1 : s->reserved) ||
        (s->stage ? !s->plan.host2 : !!s->plan.host2) ||
        s->committed < start(s->stage) || s->committed > end(s->stage) ||
        s->published < start(s->stage) || s->published > s->committed ||
        s->committed - s->published > 1 ||
        (!active && (s->committed != end(s->stage) || s->published != s->committed)))
        return fail(s, NPU_COLD_TX_CORRUPT);
    return epoch == s->epoch ? NPU_COLD_TX_OK : NPU_COLD_TX_STALE;
}

uint32_t npu_cold_tx_begin(struct npu_cold_tx_state *s, const struct npu_cold_tx_plan *p,
                         uint32_t epoch, uint32_t stage)
{
    struct npu_cold_tx_plan previous;
    uint32_t i, status;

    if (!s)
        return NPU_COLD_TX_ARGUMENT;
    if (!s->magic) {
        const unsigned char *bytes = (const unsigned char *)s;

        for (i = 0; i < sizeof(*s); i++)
            if (bytes[i])
                return NPU_COLD_TX_REINITIALIZE;
        if (epoch != 1 || stage || !plan_valid(p) || p->host2)
            return fail(s, NPU_COLD_TX_PLAN);
        s->epoch = 1;
        copy_plan(&s->plan, p);
        s->active = s->reserved = 1;
        __atomic_store_n(&s->magic, NPU_COLD_TX_MAGIC, __ATOMIC_RELEASE);
        return load(&s->fault) ? NPU_COLD_TX_FAULT : NPU_COLD_TX_OK;
    }
    if (!p)
        return fail(s, NPU_COLD_TX_PLAN);
    copy_plan(&previous, p);
    if (stage == 1)
        previous.host2 = s->plan.host2;
    status = valid(s, &previous, epoch, 0);
    if (status)
        return status;
    if (stage != s->stage + 1 || stage > 2 || !plan_valid(p) || !p->host2)
        return fail(s, NPU_COLD_TX_ORDER);
    copy_plan(&s->plan, p);
    s->stage = stage;
    s->active = 1;
    s->reserved |= 1u << stage;
    return load(&s->fault) ? NPU_COLD_TX_FAULT : NPU_COLD_TX_OK;
}

struct write {
    uint32_t address, value, bytes, before;
};

static struct write expected(const struct npu_cold_tx_state *s, uint32_t index)
{
    struct write w = {0, 0, 4, 0};
    uint32_t band = s->stage, offset = index - start(band);

    if (band == 2) {
        w.address = 0x3e900bc0u;
        w.value = NPU_COLD_TX_TOKEN_LIMIT;
        w.before = s->plan.token_before;
    } else if (!offset) {
        w.address = band ? 0x3e9046fcu : 0x3e904700u;
        w.value = band ? s->plan.host2 : s->plan.host0;
    } else if (offset < 3) {
        w.address = offset == 1 ? 0x3e903978u : 0x3e9021f4u;
        w.bytes = 2;
    } else {
        w.address = (band ? 0x1fc48030u : 0x1fc08030u) + (offset - 3) * 4;
        w.value = (s->plan.arena + (band ? offset == 3 ? 0x22020u : 0x4a040u :
                                                 offset == 3 ? 0u : 0x22020u)) & 0x1fffffffu;
        w.before = s->plan.register_before[band * 2 + offset - 3];
    }
    return w;
}

uint32_t npu_cold_tx_reserve(struct npu_cold_tx_state *s, const struct npu_cold_tx_plan *p,
    uint32_t epoch, uint32_t address, uint32_t value, uint32_t bytes, uint32_t before)
{
    uint32_t status = valid(s, p, epoch, 1);
    struct write w;

    if (status)
        return status;
    if (s->committed != s->published || s->committed == end(s->stage))
        return fail(s, NPU_COLD_TX_ORDER);
    w = expected(s, s->committed);
    if (address != w.address || value != w.value || bytes != w.bytes || before != w.before)
        return fail(s, NPU_COLD_TX_ORDER);
    __atomic_store_n(&s->committed, s->committed + 1, __ATOMIC_RELEASE);
    return load(&s->fault) ? NPU_COLD_TX_FAULT : NPU_COLD_TX_OK;
}

uint32_t npu_cold_tx_publish(struct npu_cold_tx_state *s, const struct npu_cold_tx_plan *p,
    uint32_t epoch, uint32_t address, uint32_t bytes, uint32_t readback)
{
    uint32_t status = valid(s, p, epoch, 1);
    struct write w;

    if (status)
        return status;
    if (s->committed != s->published + 1 || s->published == end(s->stage))
        return fail(s, NPU_COLD_TX_PUBLISH);
    w = expected(s, s->published);
    if (address != w.address || bytes != w.bytes || readback != w.value)
        return fail(s, NPU_COLD_TX_PUBLISH);
    __atomic_store_n(&s->published, s->published + 1, __ATOMIC_RELEASE);
    return load(&s->fault) ? NPU_COLD_TX_FAULT : NPU_COLD_TX_OK;
}

uint32_t npu_cold_tx_finish(struct npu_cold_tx_state *s, const struct npu_cold_tx_plan *p,
                          uint32_t epoch, const uint32_t *readback)
{
    uint32_t status = valid(s, p, epoch, 1), i;

    if (status)
        return status;
    if (!readback || ((uintptr_t)readback & 3) ||
        s->committed != end(s->stage) || s->published != s->committed)
        return fail(s, NPU_COLD_TX_PUBLISH);
    for (i = start(s->stage); i < end(s->stage); i++)
        if (readback[i - start(s->stage)] != expected(s, i).value)
            return fail(s, NPU_COLD_TX_PUBLISH);
    s->completed = s->reserved;
    s->active = 0;
    return load(&s->fault) ? NPU_COLD_TX_FAULT : NPU_COLD_TX_OK;
}
