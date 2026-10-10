#include "cold-indication.h"

_Static_assert(sizeof(struct npu_cold_indication_state) == 32, "indication state changed");

static uint32_t load(const uint32_t *word)
{
    return __atomic_load_n(word, __ATOMIC_ACQUIRE);
}

void npu_cold_indication_fault(struct npu_cold_indication_state *s)
{
    if (s)
        __atomic_store_n(&s->fault, 1, __ATOMIC_RELEASE);
}

static uint32_t fail(struct npu_cold_indication_state *s, uint32_t error)
{
    npu_cold_indication_fault(s);
    return error;
}

static int plan_valid(const struct npu_cold_indication_plan *p,
                      const volatile uint32_t *words)
{
    return p && words && !((uintptr_t)words & 3) &&
           !(p->base & 31) && p->base >= 0x3e800000u &&
           p->base <= 0x3e878000u - NPU_COLD_INDICATION_BYTES &&
           p->bytes == NPU_COLD_INDICATION_BYTES;
}

static uint32_t valid(struct npu_cold_indication_state *s,
    const struct npu_cold_indication_plan *p, uint32_t epoch,
    const volatile uint32_t *words)
{
    if (!s)
        return NPU_COLD_INDICATION_ARGUMENT;
    if (load(&s->fault))
        return NPU_COLD_INDICATION_FAULT;
    if (!plan_valid(p, words) || s->magic != NPU_COLD_INDICATION_MAGIC ||
        s->epoch != 1 || s->active != 1 || s->base != p->base ||
        s->count != NPU_COLD_INDICATION_COUNT ||
        s->committed > s->count || s->published > s->committed ||
        s->committed - s->published > 1)
        return fail(s, NPU_COLD_INDICATION_CORRUPT);
    return epoch == s->epoch ? NPU_COLD_INDICATION_OK : NPU_COLD_INDICATION_STALE;
}

uint32_t npu_cold_indication_begin(struct npu_cold_indication_state *s,
    const struct npu_cold_indication_plan *p, uint32_t epoch,
    const volatile uint32_t *words)
{
    uint32_t i;

    if (!s)
        return NPU_COLD_INDICATION_ARGUMENT;
    if (s->magic || s->epoch || load(&s->fault) || s->active ||
        s->committed || s->published || s->base || s->count)
        return NPU_COLD_INDICATION_REINITIALIZE;
    if (epoch != 1 || !plan_valid(p, words))
        return fail(s, NPU_COLD_INDICATION_PLAN);
    for (i = 0; i < NPU_COLD_INDICATION_COUNT * 2; i++)
        if (words[i])
            return fail(s, NPU_COLD_INDICATION_FRESHNESS);
    s->epoch = epoch;
    s->base = p->base;
    s->count = NPU_COLD_INDICATION_COUNT;
    s->active = 1;
    __atomic_store_n(&s->magic, NPU_COLD_INDICATION_MAGIC, __ATOMIC_RELEASE);
    return load(&s->fault) ? NPU_COLD_INDICATION_FAULT : NPU_COLD_INDICATION_OK;
}

uint32_t npu_cold_indication_reserve(struct npu_cold_indication_state *s,
    const struct npu_cold_indication_plan *p, uint32_t epoch,
    uint32_t address, uint32_t value, const volatile uint32_t *words)
{
    uint32_t status = valid(s, p, epoch, words), index;

    if (status)
        return status;
    index = s->committed;
    if (index != s->published || index == s->count ||
        address != s->base + index * 8 || value != NPU_COLD_INDICATION_STATUS ||
        words[index * 2] || words[index * 2 + 1])
        return fail(s, NPU_COLD_INDICATION_ORDER);
    /* A store can become visible before readback or a later caller check. */
    __atomic_store_n(&s->committed, index + 1, __ATOMIC_RELEASE);
    return load(&s->fault) ? NPU_COLD_INDICATION_FAULT : NPU_COLD_INDICATION_OK;
}

uint32_t npu_cold_indication_pending(struct npu_cold_indication_state *s,
    const struct npu_cold_indication_plan *p, uint32_t epoch,
    uint32_t address, uint32_t value, const volatile uint32_t *words)
{
    uint32_t status = valid(s, p, epoch, words), index;

    if (status)
        return status;
    index = s->published;
    if (s->committed != index + 1 || index == s->count ||
        address != s->base + index * 8 || value != NPU_COLD_INDICATION_STATUS ||
        words[index * 2] || words[index * 2 + 1])
        return fail(s, NPU_COLD_INDICATION_ORDER);
    return NPU_COLD_INDICATION_OK;
}

uint32_t npu_cold_indication_publish(struct npu_cold_indication_state *s,
    const struct npu_cold_indication_plan *p, uint32_t epoch,
    uint32_t address, const volatile uint32_t *words)
{
    uint32_t status = valid(s, p, epoch, words), index;

    if (status)
        return status;
    index = s->published;
    if (s->committed != index + 1 || index == s->count ||
        address != s->base + index * 8 || words[index * 2] ||
        words[index * 2 + 1] != NPU_COLD_INDICATION_STATUS)
        return fail(s, NPU_COLD_INDICATION_PUBLISH);
    __atomic_store_n(&s->published, index + 1, __ATOMIC_RELEASE);
    return load(&s->fault) ? NPU_COLD_INDICATION_FAULT : NPU_COLD_INDICATION_OK;
}

uint32_t npu_cold_indication_finish(struct npu_cold_indication_state *s,
    const struct npu_cold_indication_plan *p, uint32_t epoch,
    const volatile uint32_t *words)
{
    uint32_t status = valid(s, p, epoch, words), i;

    if (status)
        return status;
    if (s->committed != s->count || s->published != s->count)
        return fail(s, NPU_COLD_INDICATION_ORDER);
    for (i = 0; i < s->count; i++)
        if (words[i * 2] || words[i * 2 + 1] != NPU_COLD_INDICATION_STATUS)
            return fail(s, NPU_COLD_INDICATION_PUBLISH);
    s->active = 0;
    return load(&s->fault) ? NPU_COLD_INDICATION_FAULT : NPU_COLD_INDICATION_OK;
}
