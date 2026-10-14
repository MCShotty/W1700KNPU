#include "cold-rx-pcie.h"

_Static_assert(sizeof(struct npu_cold_rx_pcie_plan) == 136, "RX PCIe plan changed");
_Static_assert(sizeof(struct npu_cold_rx_pcie_state) == 168, "RX PCIe owner changed");

static uint32_t load(const uint32_t *word)
{
    return __atomic_load_n(word, __ATOMIC_ACQUIRE);
}

void npu_cold_rx_pcie_fault(struct npu_cold_rx_pcie_state *s)
{
    if (s)
        __atomic_store_n(&s->fault, 1, __ATOMIC_RELEASE);
}

static uint32_t fail(struct npu_cold_rx_pcie_state *s, uint32_t status)
{
    npu_cold_rx_pcie_fault(s);
    return status;
}

int npu_cold_rx_pcie_plan_valid(const struct npu_cold_rx_pcie_plan *p)
{
    const struct npu_cold_txbuf_plan *bar;

    if (!p || !npu_cold_txdone_plan_valid(&p->prior))
        return 0;
    bar = &p->prior.prior.prior;
    return bar->endpoint_bytes >= NPU_COLD_RX_PCIE_REGISTER_BYTES &&
           NPU_COLD_RX_PCIE_REGISTER <= bar->endpoint_bytes - NPU_COLD_RX_PCIE_REGISTER_BYTES;
}

uint32_t npu_cold_rx_pcie_value(const struct npu_cold_rx_pcie_plan *p)
{
    return npu_cold_rx_pcie_plan_valid(p) ?
           p->prior.prior.prior.endpoint_base + NPU_COLD_RX_PCIE_REGISTER : 0;
}

static int prior_live(const struct npu_cold_rx_pcie_plan *p, uint32_t epoch,
                      const struct npu_cold_rx_pcie_context *c)
{
    return c && npu_cold_rx_pcie_plan_valid(p) &&
           npu_cold_txdone_memory_live(c->done, &p->prior, epoch, c->rx,
               c->rx_readback, c->packets, c->ready, c->read, c->opaque);
}

static int context(const struct npu_cold_rx_pcie_state *s,
    const struct npu_cold_rx_pcie_plan *p, uint32_t epoch,
    const struct npu_cold_rx_pcie_context *c)
{
    return s && p && epoch == 1 && s->epoch == epoch &&
           load(&s->magic) == NPU_COLD_RX_PCIE_MAGIC && !load(&s->fault) &&
           s->active <= 1 && s->reserved <= 1 && s->committed <= s->reserved &&
           s->published <= s->committed &&
           npu_cold_txdone_plan_equal(&s->plan.prior, &p->prior) && prior_live(p, epoch, c);
}

uint32_t npu_cold_rx_pcie_begin(struct npu_cold_rx_pcie_state *s,
    const struct npu_cold_rx_pcie_plan *p, uint32_t epoch,
    const struct npu_cold_rx_pcie_context *c, uint32_t before)
{
    const volatile uint32_t *words = (const volatile void *)s;
    uint32_t i;

    if (!s || !p || !c)
        return fail(s, NPU_COLD_RX_PCIE_ARGUMENT);
    if (epoch != 1 || !prior_live(p, epoch, c))
        return fail(s, NPU_COLD_RX_PCIE_PLAN);
    for (i = 0; i < sizeof(*s) / 4; i++)
        if (words[i])
            return fail(s, NPU_COLD_RX_PCIE_REINITIALIZE);
    npu_cold_txdone_plan_copy(&s->plan.prior, &p->prior);
    s->epoch = epoch;
    s->before = before;
    s->active = 1;
    __atomic_store_n(&s->magic, NPU_COLD_RX_PCIE_MAGIC, __ATOMIC_RELEASE);
    return NPU_COLD_RX_PCIE_OK;
}

uint32_t npu_cold_rx_pcie_reserve(struct npu_cold_rx_pcie_state *s,
    const struct npu_cold_rx_pcie_plan *p, uint32_t epoch,
    const struct npu_cold_rx_pcie_context *c, uint32_t address,
    uint32_t bytes, uint32_t value, uint32_t before)
{
    if (!context(s, p, epoch, c))
        return fail(s, NPU_COLD_RX_PCIE_STALE);
    if (s->active != 1 || s->reserved || s->committed || s->published ||
        address != NPU_COLD_RX_PCIE_METADATA || bytes != 4 || before != s->before ||
        value != npu_cold_rx_pcie_value(p))
        return fail(s, NPU_COLD_RX_PCIE_ORDER);
    s->reserved = s->committed = 1;
    return NPU_COLD_RX_PCIE_OK;
}

uint32_t npu_cold_rx_pcie_publish(struct npu_cold_rx_pcie_state *s,
    const struct npu_cold_rx_pcie_plan *p, uint32_t epoch,
    const struct npu_cold_rx_pcie_context *c, uint32_t address,
    uint32_t bytes, uint32_t readback)
{
    if (!context(s, p, epoch, c))
        return fail(s, NPU_COLD_RX_PCIE_STALE);
    if (s->active != 1 || s->reserved != 1 || s->committed != 1 || s->published ||
        address != NPU_COLD_RX_PCIE_METADATA || bytes != 4)
        return fail(s, NPU_COLD_RX_PCIE_ORDER);
    if (readback != npu_cold_rx_pcie_value(p))
        return fail(s, NPU_COLD_RX_PCIE_PUBLISH);
    s->published = 1;
    return NPU_COLD_RX_PCIE_OK;
}

uint32_t npu_cold_rx_pcie_finish(struct npu_cold_rx_pcie_state *s,
    const struct npu_cold_rx_pcie_plan *p, uint32_t epoch,
    const struct npu_cold_rx_pcie_context *c, uint32_t readback)
{
    if (!context(s, p, epoch, c))
        return fail(s, NPU_COLD_RX_PCIE_STALE);
    if (s->active != 1 || s->reserved != 1 || s->committed != 1 || s->published != 1 ||
        readback != npu_cold_rx_pcie_value(p))
        return fail(s, NPU_COLD_RX_PCIE_ORDER);
    s->active = 0;
    return NPU_COLD_RX_PCIE_OK;
}

int npu_cold_rx_pcie_live(const struct npu_cold_rx_pcie_state *s,
    const struct npu_cold_rx_pcie_plan *p, uint32_t epoch,
    const struct npu_cold_rx_pcie_context *c, uint32_t readback)
{
    return context(s, p, epoch, c) && !s->active && s->reserved == 1 &&
           s->committed == 1 && s->published == 1 && readback == npu_cold_rx_pcie_value(p);
}
