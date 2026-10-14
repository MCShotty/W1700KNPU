#include "cold-pcie-tail.h"

_Static_assert(sizeof(struct npu_cold_pcie_tail_plan) == 180, "PCIe tail plan changed");
_Static_assert(sizeof(struct npu_cold_pcie_tail_state) == 256, "PCIe tail owner changed");

static uint32_t load(const uint32_t *p)
{
    return __atomic_load_n(p, __ATOMIC_ACQUIRE);
}

void npu_cold_pcie_tail_fault(struct npu_cold_pcie_tail_state *s)
{
    if (s)
        __atomic_store_n(&s->fault, 1, __ATOMIC_RELEASE);
}

static uint32_t fail(struct npu_cold_pcie_tail_state *s, uint32_t status)
{
    npu_cold_pcie_tail_fault(s);
    return status;
}

static uint32_t start(uint32_t stage)
{
    return stage * 2;
}

static uint32_t end(uint32_t stage)
{
    return stage == 2 ? NPU_COLD_PCIE_TAIL_STORES : start(stage) + 2;
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

int npu_cold_pcie_tail_plan_valid(const struct npu_cold_pcie_tail_plan *p)
{
    const struct npu_cold_txbuf_plan *bar;
    uint32_t offset;

    if (!p || !npu_cold_rx_pcie_plan_valid(&p->prior))
        return 0;
    bar = &p->prior.prior.prior.prior;
    if (p->tx.arena != bar->arena || p->tx.arena_bytes != NPU_COLD_TX_ARENA_BYTES ||
        p->tx.endpoint_base != bar->endpoint_base || p->tx.endpoint_bytes != bar->endpoint_bytes ||
        p->tx.host0 != bar->endpoint_base + 0xd4420u || !p->tx.host2)
        return 0;
    offset = p->tx.host2 - bar->endpoint_base;
    if (offset != 0xd4450u && offset != 0xd8450u)
        return 0;
    return bar->endpoint_bytes >= offset + 0x110u + 12u &&
           bar->endpoint_bytes >= 0xd4580u + 12u;
}

uint32_t npu_cold_pcie_tail_selector(uint32_t stage)
{
    static const uint32_t selectors[] = {0, 2, 15};

    return stage < NPU_COLD_PCIE_TAIL_STAGES ? selectors[stage] : UINT32_MAX;
}

uint32_t npu_cold_pcie_tail_value(const struct npu_cold_pcie_tail_plan *p, uint32_t stage)
{
    if (!npu_cold_pcie_tail_plan_valid(p) || stage >= NPU_COLD_PCIE_TAIL_STAGES)
        return 0;
    return stage == 0 ? p->tx.host0 + 0x160u : stage == 1 ? p->tx.host2 + 0x110u : 0;
}

uint32_t npu_cold_pcie_tail_recipe(const struct npu_cold_pcie_tail_plan *p,
                                  uint32_t index, struct npu_cold_pcie_tail_store *out)
{
    static const uint32_t offsets[] = {0xd45a0, 0xd45b0, 0xd45c0, 0xa040, 0xd4590};
    static const uint32_t counts[] = {255, 511, 1023, 1535, 511};
    struct npu_cold_pcie_tail_store value = {0, 4, 0};

    if (!out || !npu_cold_pcie_tail_plan_valid(p) || index >= NPU_COLD_PCIE_TAIL_STORES)
        return NPU_COLD_PCIE_TAIL_ARGUMENT;
    if (index < 4) {
        uint32_t stage = index / 2;
        uint32_t pointer = npu_cold_pcie_tail_value(p, stage);

        value.address = index & 1 ? pointer + 8 : stage ? 0x3e903904u : 0x3e902cf0u;
        value.value = index & 1 ? stage ? 1023 : 1535 : pointer;
    } else {
        value.address = p->tx.endpoint_base + offsets[index - 4] + 8;
        value.value = counts[index - 4];
    }
    *out = value;
    return NPU_COLD_PCIE_TAIL_OK;
}

static int read_equal(const struct npu_cold_pcie_tail_context *c,
                      uint32_t address, uint32_t bytes, uint32_t expected)
{
    uint32_t value;

    return c->read(c->opaque, address, bytes, &value) && value == expected;
}

static int prior_live(const struct npu_cold_pcie_tail_plan *p, uint32_t epoch,
                      const struct npu_cold_pcie_tail_context *c)
{
    static const uint32_t metadata[] = {0x3e90395c, 0x3e902a80, 0x3e904630, 0x3e902a9c, 0x3e902a90};
    static const uint32_t offsets[] = {0xd45a0, 0xd45b0, 0xd45c0, 0xa040, 0xd4590};
    struct npu_cold_tx_state held_tx;
    struct npu_cold_rx_pcie_state held_pcie;
    struct npu_cold_pcie_tail_plan held_plan;
    const struct npu_cold_tx_state *tx = &held_tx;

    if (!c || !c->tx || !c->pcie || !c->read || !c->opaque || epoch != 1 ||
        !npu_cold_pcie_tail_plan_valid(p))
        return 0;
    copy(&held_tx, c->tx, sizeof(held_tx));
    copy(&held_pcie, c->pcie, sizeof(held_pcie));
    copy(&held_plan, p, sizeof(held_plan));
    if (load(&tx->magic) != NPU_COLD_TX_MAGIC || tx->epoch != epoch || load(&tx->fault) ||
        tx->active || tx->stage != 2 || tx->reserved != 7 || tx->completed != 7 ||
        tx->committed != NPU_COLD_TX_WRITES || tx->published != NPU_COLD_TX_WRITES ||
        !equal(&tx->plan, &p->tx, sizeof(p->tx)) ||
        !npu_cold_rx_pcie_live(c->pcie, &p->prior, epoch, &c->prior, c->pcie_readback))
        return 0;
    for (uint32_t i = 0; i < 5; i++)
        if (!read_equal(c, metadata[i], 4, p->tx.endpoint_base + offsets[i]))
            return 0;
    return read_equal(c, 0x3e902a7c, 2, NPU_COLD_TXDONE_IDS) &&
           equal(c->tx, &held_tx, sizeof(held_tx)) &&
           equal(c->pcie, &held_pcie, sizeof(held_pcie)) &&
           equal(p, &held_plan, sizeof(held_plan));
}

static int prefix_live(const struct npu_cold_pcie_tail_state *s,
                       const struct npu_cold_pcie_tail_plan *p,
                       const struct npu_cold_pcie_tail_context *c)
{
    struct npu_cold_pcie_tail_store store;

    for (uint32_t i = 0; i < s->published; i++)
        if (npu_cold_pcie_tail_recipe(p, i, &store) ||
            !read_equal(c, store.address, store.bytes, store.value))
            return 0;
    return 1;
}

static int state_valid(const struct npu_cold_pcie_tail_state *s,
    const struct npu_cold_pcie_tail_plan *p, uint32_t epoch)
{
    if (!s || !p || s->stage >= NPU_COLD_PCIE_TAIL_STAGES ||
        load(&s->magic) != NPU_COLD_PCIE_TAIL_MAGIC || s->epoch != epoch || load(&s->fault) ||
        s->active > 1 || s->reserved != (1u << (s->stage + 1)) - 1 ||
        s->completed != (s->active ? (1u << s->stage) - 1 : s->reserved) ||
        s->captured != (1u << end(s->stage)) - 1 ||
        s->committed < start(s->stage) || s->committed > end(s->stage) ||
        s->published < start(s->stage) || s->published > s->committed ||
        s->committed - s->published > 1 ||
        (!s->active && (s->committed != end(s->stage) || s->published != s->committed)) ||
        !equal(&s->plan, p, sizeof(*p)))
        return 0;
    for (uint32_t i = end(s->stage); i < NPU_COLD_PCIE_TAIL_STORES; i++)
        if (s->before[i])
            return 0;
    return 1;
}

static int context(const struct npu_cold_pcie_tail_state *s,
    const struct npu_cold_pcie_tail_plan *p, uint32_t epoch,
    const struct npu_cold_pcie_tail_context *c)
{
    struct npu_cold_pcie_tail_state held;
    struct npu_cold_tx_state tx;
    struct npu_cold_rx_pcie_state pcie;

    if (!state_valid(s, p, epoch) || !c || !c->tx || !c->pcie)
        return 0;
    copy(&held, s, sizeof(held));
    copy(&tx, c->tx, sizeof(tx));
    copy(&pcie, c->pcie, sizeof(pcie));
    return prior_live(p, epoch, c) && prefix_live(&held, p, c) &&
           equal(s, &held, sizeof(held)) && equal(c->tx, &tx, sizeof(tx)) &&
           equal(c->pcie, &pcie, sizeof(pcie)) && state_valid(s, p, epoch);
}

uint32_t npu_cold_pcie_tail_begin(struct npu_cold_pcie_tail_state *s,
    const struct npu_cold_pcie_tail_plan *p, uint32_t epoch,
    const struct npu_cold_pcie_tail_context *c, uint32_t selector, uint32_t value)
{
    uint32_t stage = 0;
    struct npu_cold_pcie_tail_store store;

    while (stage < NPU_COLD_PCIE_TAIL_STAGES && npu_cold_pcie_tail_selector(stage) != selector)
        stage++;
    if (!s || !p || !c)
        return fail(s, NPU_COLD_PCIE_TAIL_ARGUMENT);
    if (stage == NPU_COLD_PCIE_TAIL_STAGES || !prior_live(p, epoch, c) ||
        value != npu_cold_pcie_tail_value(p, stage))
        return fail(s, NPU_COLD_PCIE_TAIL_PLAN);
    if (!s->magic) {
        const volatile unsigned char *bytes = (const volatile void *)s;

        for (uint32_t i = 0; i < sizeof(*s); i++)
            if (bytes[i])
                return fail(s, NPU_COLD_PCIE_TAIL_REINITIALIZE);
        if (stage)
            return fail(s, NPU_COLD_PCIE_TAIL_ORDER);
        copy(&s->plan, p, sizeof(*p));
        s->epoch = epoch;
        __atomic_store_n(&s->magic, NPU_COLD_PCIE_TAIL_MAGIC, __ATOMIC_RELEASE);
    } else if (!context(s, p, epoch, c) || s->active || stage != s->stage + 1) {
        return fail(s, NPU_COLD_PCIE_TAIL_ORDER);
    }
    s->stage = stage;
    s->active = 1;
    s->reserved |= 1u << stage;
    for (uint32_t i = start(stage); i < end(stage); i++) {
        if (npu_cold_pcie_tail_recipe(p, i, &store) ||
            !c->read(c->opaque, store.address, store.bytes, &s->before[i]))
            return fail(s, NPU_COLD_PCIE_TAIL_READ);
        s->captured |= 1u << i;
    }
    return context(s, p, epoch, c) ? NPU_COLD_PCIE_TAIL_OK : fail(s, NPU_COLD_PCIE_TAIL_STALE);
}

uint32_t npu_cold_pcie_tail_reserve(struct npu_cold_pcie_tail_state *s,
    const struct npu_cold_pcie_tail_plan *p, uint32_t epoch,
    const struct npu_cold_pcie_tail_context *c, uint32_t address, uint32_t bytes,
    uint32_t value, uint32_t before)
{
    struct npu_cold_pcie_tail_store store;

    if (!context(s, p, epoch, c))
        return fail(s, NPU_COLD_PCIE_TAIL_STALE);
    if (!s->active || s->committed != s->published || s->committed == end(s->stage) ||
        npu_cold_pcie_tail_recipe(p, s->committed, &store) ||
        address != store.address || bytes != store.bytes || value != store.value ||
        before != s->before[s->committed] || !read_equal(c, address, bytes, before))
        return fail(s, NPU_COLD_PCIE_TAIL_ORDER);
    __atomic_store_n(&s->committed, s->committed + 1, __ATOMIC_RELEASE);
    return context(s, p, epoch, c) ? NPU_COLD_PCIE_TAIL_OK : fail(s, NPU_COLD_PCIE_TAIL_STALE);
}

uint32_t npu_cold_pcie_tail_publish(struct npu_cold_pcie_tail_state *s,
    const struct npu_cold_pcie_tail_plan *p, uint32_t epoch,
    const struct npu_cold_pcie_tail_context *c, uint32_t address, uint32_t bytes, uint32_t readback)
{
    struct npu_cold_pcie_tail_store store;

    if (!context(s, p, epoch, c))
        return fail(s, NPU_COLD_PCIE_TAIL_STALE);
    if (!s->active || s->committed != s->published + 1 ||
        npu_cold_pcie_tail_recipe(p, s->published, &store) ||
        address != store.address || bytes != store.bytes || readback != store.value ||
        !read_equal(c, address, bytes, readback))
        return fail(s, NPU_COLD_PCIE_TAIL_PUBLISH);
    __atomic_store_n(&s->published, s->published + 1, __ATOMIC_RELEASE);
    return context(s, p, epoch, c) ? NPU_COLD_PCIE_TAIL_OK : fail(s, NPU_COLD_PCIE_TAIL_STALE);
}

uint32_t npu_cold_pcie_tail_finish(struct npu_cold_pcie_tail_state *s,
    const struct npu_cold_pcie_tail_plan *p, uint32_t epoch,
    const struct npu_cold_pcie_tail_context *c)
{
    if (!context(s, p, epoch, c) || !s->active ||
        s->committed != end(s->stage) || s->published != s->committed)
        return fail(s, NPU_COLD_PCIE_TAIL_ORDER);
    s->completed = s->reserved;
    s->active = 0;
    return context(s, p, epoch, c) ? NPU_COLD_PCIE_TAIL_OK : fail(s, NPU_COLD_PCIE_TAIL_STALE);
}

int npu_cold_pcie_tail_live(const struct npu_cold_pcie_tail_state *s,
    const struct npu_cold_pcie_tail_plan *p, uint32_t epoch,
    const struct npu_cold_pcie_tail_context *c)
{
    return context(s, p, epoch, c) && !s->active && s->stage == 2 &&
           s->completed == 7 && s->committed == NPU_COLD_PCIE_TAIL_STORES &&
           s->published == NPU_COLD_PCIE_TAIL_STORES;
}
