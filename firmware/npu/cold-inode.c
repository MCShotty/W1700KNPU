#include "cold-inode.h"

_Static_assert(sizeof(struct npu_cold_inode_plan) == 188, "INODE plan changed");
_Static_assert(sizeof(struct npu_cold_inode_state) == 4372, "INODE owner changed");

static uint32_t load(const uint32_t *p)
{
    return __atomic_load_n(p, __ATOMIC_ACQUIRE);
}

void npu_cold_inode_fault(struct npu_cold_inode_state *s)
{
    if (s)
        __atomic_store_n(&s->fault, 1, __ATOMIC_RELEASE);
}

static uint32_t fail(struct npu_cold_inode_state *s, uint32_t status)
{
    npu_cold_inode_fault(s);
    return status;
}

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

static uint32_t start(uint32_t stage)
{
    return stage ? NPU_COLD_INODE_FIRST_STORES : 0;
}

static uint32_t end(uint32_t stage)
{
    return stage ? NPU_COLD_INODE_STORES : NPU_COLD_INODE_FIRST_STORES;
}

int npu_cold_inode_plan_valid(const struct npu_cold_inode_plan *p)
{
    return p && npu_cold_pcie_tail_plan_valid(&p->prior) &&
           p->icv == NPU_COLD_INODE_ICV && p->icv_bytes == NPU_COLD_INODE_ICV_BYTES;
}

uint32_t npu_cold_inode_selector(uint32_t stage)
{
    return stage < 2 ? stage ? 7 : 2 : UINT32_MAX;
}

uint32_t npu_cold_inode_recipe(const struct npu_cold_inode_plan *p, uint32_t index,
                              struct npu_cold_inode_store *out)
{
    static const struct npu_cold_inode_store first[] = {
        {0x3e9046ec, 4, 1}, {0x3e9046f0, 4, 1}, {0x3e9046f8, 1, 3}
    };
    static const struct npu_cold_inode_store last[] = {
        {0x3e9046f5, 1, 0}, {0x3e9046f0, 4, 1}, {0x3e9046f9, 1, 3},
        {0x3e9046f8, 1, 3}, {0x3e9046e1, 1, 1}, {0x3e9046e0, 1, 1}
    };

    if (!out || !npu_cold_inode_plan_valid(p) || index >= NPU_COLD_INODE_STORES)
        return NPU_COLD_INODE_ARGUMENT;
    if (index < 3)
        *out = first[index];
    else if (index < NPU_COLD_INODE_FIRST_STORES - 1)
        *out = (struct npu_cold_inode_store){p->icv + (index - 3) * 4, 4, 0};
    else if (index == NPU_COLD_INODE_FIRST_STORES - 1)
        *out = (struct npu_cold_inode_store){0x3e9046f7, 1, 0};
    else
        *out = last[index - NPU_COLD_INODE_FIRST_STORES];
    return NPU_COLD_INODE_OK;
}

static int read_equal(const struct npu_cold_inode_context *c,
                      uint32_t address, uint32_t bytes, uint32_t expected)
{
    uint32_t value;

    return c->read(c->opaque, address, bytes, &value) && value == expected;
}

static int prior_live(const struct npu_cold_inode_plan *p, uint32_t epoch,
                      const struct npu_cold_inode_context *c)
{
    struct npu_cold_pcie_tail_state prior;
    struct npu_cold_inode_plan plan;

    if (!c || !c->pcie || !c->read || !c->opaque || epoch != 1 || !npu_cold_inode_plan_valid(p))
        return 0;
    copy(&prior, c->pcie, sizeof(prior));
    copy(&plan, p, sizeof(plan));
    return npu_cold_pcie_tail_live(c->pcie, &p->prior, epoch, &c->prior) &&
           read_equal(c, 0x8401cfb8, 4, 0x109) &&
           read_equal(c, 0x8401cfbc, 4, NPU_COLD_INODE_ICV) &&
           read_equal(c, 0x3e902ac0, 4, p->icv) &&
           npu_cold_pcie_tail_live(c->pcie, &p->prior, epoch, &c->prior) &&
           equal(c->pcie, &prior, sizeof(prior)) && equal(p, &plan, sizeof(plan));
}

static int state_valid(const struct npu_cold_inode_state *s,
    const struct npu_cold_inode_plan *p, uint32_t epoch)
{
    if (!s || !p || s->stage >= 2 || load(&s->magic) != NPU_COLD_INODE_MAGIC ||
        s->epoch != epoch || load(&s->fault) || s->active > 1 ||
        s->reserved != (1u << (s->stage + 1)) - 1 ||
        s->completed != (s->active ? (1u << s->stage) - 1 : s->reserved) ||
        s->captured != end(s->stage) || s->committed < start(s->stage) ||
        s->committed > end(s->stage) || s->published < start(s->stage) ||
        s->published > s->committed || s->committed - s->published > 1 ||
        (!s->active && (s->committed != end(s->stage) || s->published != s->committed)) ||
        !equal(&s->plan, p, sizeof(*p)))
        return 0;
    for (uint32_t i = end(s->stage); i < NPU_COLD_INODE_STORES; i++)
        if (s->before[i])
            return 0;
    return 1;
}

static int context(const struct npu_cold_inode_state *s,
    const struct npu_cold_inode_plan *p, uint32_t epoch,
    const struct npu_cold_inode_context *c)
{
    struct npu_cold_inode_state held;
    struct npu_cold_pcie_tail_state prior;
    struct npu_cold_inode_store store;

    if (!state_valid(s, p, epoch) || !c || !c->pcie)
        return 0;
    copy(&held, s, sizeof(held));
    copy(&prior, c->pcie, sizeof(prior));
    if (!prior_live(p, epoch, c))
        return 0;
    for (uint32_t i = 0; i < held.published; i++)
        if (npu_cold_inode_recipe(p, i, &store) || !read_equal(c, store.address, store.bytes, store.value))
            return 0;
    return equal(s, &held, sizeof(held)) && equal(c->pcie, &prior, sizeof(prior)) && state_valid(s, p, epoch);
}

uint32_t npu_cold_inode_begin(struct npu_cold_inode_state *s, const struct npu_cold_inode_plan *p,
    uint32_t epoch, const struct npu_cold_inode_context *c, uint32_t selector, uint32_t value)
{
    uint32_t stage = selector == 2 ? 0 : selector == 7 ? 1 : 2;
    struct npu_cold_inode_store store;

    if (!s || !p || !c)
        return fail(s, NPU_COLD_INODE_ARGUMENT);
    if (stage == 2 || value || !prior_live(p, epoch, c))
        return fail(s, NPU_COLD_INODE_PLAN);
    if (!s->magic) {
        const volatile unsigned char *bytes = (const volatile void *)s;

        for (uint32_t i = 0; i < sizeof(*s); i++)
            if (bytes[i])
                return fail(s, NPU_COLD_INODE_REINITIALIZE);
        if (stage)
            return fail(s, NPU_COLD_INODE_ORDER);
        copy(&s->plan, p, sizeof(*p));
        s->epoch = epoch;
        __atomic_store_n(&s->magic, NPU_COLD_INODE_MAGIC, __ATOMIC_RELEASE);
    } else if (!context(s, p, epoch, c) || s->active || stage != s->stage + 1) {
        return fail(s, NPU_COLD_INODE_ORDER);
    }
    s->stage = stage;
    s->active = 1;
    s->reserved |= 1u << stage;
    for (uint32_t i = start(stage); i < end(stage); i++) {
        if (npu_cold_inode_recipe(p, i, &store) ||
            !c->read(c->opaque, store.address, store.bytes, &s->before[i]))
            return fail(s, NPU_COLD_INODE_READ);
        s->captured++;
    }
    return context(s, p, epoch, c) ? NPU_COLD_INODE_OK : fail(s, NPU_COLD_INODE_STALE);
}

uint32_t npu_cold_inode_reserve(struct npu_cold_inode_state *s, const struct npu_cold_inode_plan *p,
    uint32_t epoch, const struct npu_cold_inode_context *c, uint32_t address,
    uint32_t bytes, uint32_t value, uint32_t before)
{
    struct npu_cold_inode_store store;

    if (!context(s, p, epoch, c))
        return fail(s, NPU_COLD_INODE_STALE);
    if (!s->active || s->committed != s->published || s->committed == end(s->stage) ||
        npu_cold_inode_recipe(p, s->committed, &store) || address != store.address ||
        bytes != store.bytes || value != store.value || before != s->before[s->committed] ||
        !read_equal(c, address, bytes, before))
        return fail(s, NPU_COLD_INODE_ORDER);
    __atomic_store_n(&s->committed, s->committed + 1, __ATOMIC_RELEASE);
    return context(s, p, epoch, c) ? NPU_COLD_INODE_OK : fail(s, NPU_COLD_INODE_STALE);
}

uint32_t npu_cold_inode_publish(struct npu_cold_inode_state *s, const struct npu_cold_inode_plan *p,
    uint32_t epoch, const struct npu_cold_inode_context *c, uint32_t address,
    uint32_t bytes, uint32_t readback)
{
    struct npu_cold_inode_store store;

    if (!context(s, p, epoch, c))
        return fail(s, NPU_COLD_INODE_STALE);
    if (!s->active || s->committed != s->published + 1 ||
        npu_cold_inode_recipe(p, s->published, &store) || address != store.address ||
        bytes != store.bytes || readback != store.value || !read_equal(c, address, bytes, readback))
        return fail(s, NPU_COLD_INODE_PUBLISH);
    __atomic_store_n(&s->published, s->published + 1, __ATOMIC_RELEASE);
    return context(s, p, epoch, c) ? NPU_COLD_INODE_OK : fail(s, NPU_COLD_INODE_STALE);
}

uint32_t npu_cold_inode_finish(struct npu_cold_inode_state *s, const struct npu_cold_inode_plan *p,
    uint32_t epoch, const struct npu_cold_inode_context *c)
{
    if (!context(s, p, epoch, c) || !s->active || s->committed != end(s->stage) || s->published != s->committed)
        return fail(s, NPU_COLD_INODE_ORDER);
    s->completed = s->reserved;
    s->active = 0;
    return context(s, p, epoch, c) ? NPU_COLD_INODE_OK : fail(s, NPU_COLD_INODE_STALE);
}

int npu_cold_inode_live(const struct npu_cold_inode_state *s, const struct npu_cold_inode_plan *p,
    uint32_t epoch, const struct npu_cold_inode_context *c)
{
    return context(s, p, epoch, c) && !s->active && s->stage == 1 && s->completed == 3 &&
           s->committed == NPU_COLD_INODE_STORES && s->published == s->committed;
}
