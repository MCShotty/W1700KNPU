#include "cold-rx-event.h"

_Static_assert(sizeof(struct npu_cold_rx_event_plan) == 120, "RX-event plan changed");
_Static_assert(sizeof(struct npu_cold_rx_event_state) == 152, "RX-event owner changed");

static uint32_t load(const uint32_t *word)
{
    return __atomic_load_n(word, __ATOMIC_ACQUIRE);
}

void npu_cold_rx_event_fault(struct npu_cold_rx_event_state *s)
{
    if (s)
        __atomic_store_n(&s->fault, 1, __ATOMIC_RELEASE);
}

static uint32_t fail(struct npu_cold_rx_event_state *s, uint32_t status)
{
    npu_cold_rx_event_fault(s);
    return status;
}

static int overlap(uint32_t left, uint32_t bytes, uint32_t right, uint32_t size)
{
    uint64_t a = left & 0x3fffffffu, b = right & 0x3fffffffu;

    return a < b + size && b < a + bytes;
}

int npu_cold_rx_event_dma_valid(const struct npu_cold_txbuf_plan *p, uint32_t enrolled,
                              uint32_t ring)
{
    uint32_t i, mailboxes;

    if (!npu_cold_txbuf_dma_valid(p, enrolled) || !ring || ring >= 0xc0000000u ||
        (ring & (NPU_COLD_RX_EVENT_STRIDE - 1)) ||
        NPU_COLD_RX_EVENT_BYTES > 0xc0000000u - ring ||
        NPU_COLD_RX_EVENT_BYTES > 0x40000000u - (ring & 0x3fffffffu) ||
        overlap(ring, NPU_COLD_RX_EVENT_BYTES, p->endpoint_base, p->endpoint_bytes))
        return 0;
    /* External DMA aliases are compared conservatively. This does not establish
     * physical SRAM/L2 equivalence or independent DMA visibility.
     */
    for (i = 0; i < NPU_BOOT_REGIONS; i++)
        if (overlap(ring, NPU_COLD_RX_EVENT_BYTES, p->boot.region[i].base,
                    p->boot.region[i].bytes))
            return 0;
    mailboxes = enrolled < NPU_COLD_TXBUF_MAILBOXES ? enrolled : NPU_COLD_TXBUF_MAILBOXES;
    for (i = 0; i < mailboxes; i++)
        if (overlap(ring, NPU_COLD_RX_EVENT_BYTES, p->mailbox[i], 256))
            return 0;
    for (i = 0; i < enrolled - mailboxes; i++)
        if (overlap(ring, NPU_COLD_RX_EVENT_BYTES, p->host[i], npu_cold_txbuf_bytes(i)))
            return 0;
    return 1;
}

int npu_cold_rx_event_plan_valid(const struct npu_cold_rx_event_plan *p)
{
    return p && npu_cold_txbuf_plan_valid(&p->prior) &&
           npu_cold_rx_event_dma_valid(&p->prior, NPU_COLD_TXBUF_RECORDS, p->ring);
}

void npu_cold_rx_event_plan_copy(struct npu_cold_rx_event_plan *to,
                                 const struct npu_cold_rx_event_plan *from)
{
    npu_cold_txbuf_plan_copy(&to->prior, &from->prior);
    to->ring = from->ring;
}

int npu_cold_rx_event_plan_equal(const struct npu_cold_rx_event_plan *left,
                                const struct npu_cold_rx_event_plan *right)
{
    return left && right && left->ring == right->ring &&
           npu_cold_txbuf_plan_equal(&left->prior, &right->prior);
}

uint32_t npu_cold_rx_event_value(uint32_t ring)
{
    return (ring & 0x3fffffffu) | 0x40000000u;
}

static int context(const struct npu_cold_rx_event_state *s,
                   const struct npu_cold_rx_event_plan *p, uint32_t epoch)
{
    return s && p && load(&s->magic) == NPU_COLD_RX_EVENT_MAGIC && epoch == 1 &&
           s->epoch == epoch && !load(&s->fault) && s->active <= 1 &&
           s->reserved <= 1 && s->committed <= s->reserved && s->published <= s->committed &&
           npu_cold_rx_event_plan_valid(p) && npu_cold_rx_event_plan_equal(&s->plan, p);
}

uint32_t npu_cold_rx_event_begin(struct npu_cold_rx_event_state *s,
    const struct npu_cold_rx_event_plan *p, uint32_t epoch, uint32_t before)
{
    const volatile uint32_t *words = (const volatile void *)s;
    uint32_t i;

    if (!s || !p)
        return fail(s, NPU_COLD_RX_EVENT_ARGUMENT);
    if (epoch != 1 || !npu_cold_rx_event_plan_valid(p))
        return fail(s, NPU_COLD_RX_EVENT_PLAN);
    for (i = 0; i < sizeof(*s) / 4; i++)
        if (words[i])
            return fail(s, NPU_COLD_RX_EVENT_REINITIALIZE);
    npu_cold_rx_event_plan_copy(&s->plan, p);
    s->epoch = epoch;
    s->before = before;
    s->active = 1;
    __atomic_store_n(&s->magic, NPU_COLD_RX_EVENT_MAGIC, __ATOMIC_RELEASE);
    return NPU_COLD_RX_EVENT_OK;
}

uint32_t npu_cold_rx_event_reserve(struct npu_cold_rx_event_state *s,
    const struct npu_cold_rx_event_plan *p, uint32_t epoch, uint32_t address,
    uint32_t bytes, uint32_t value, uint32_t before)
{
    if (!context(s, p, epoch))
        return fail(s, NPU_COLD_RX_EVENT_STALE);
    if (s->active != 1 || s->reserved || s->committed || s->published ||
        address != NPU_COLD_RX_EVENT_METADATA || bytes != 4 || before != s->before ||
        value != npu_cold_rx_event_value(p->ring))
        return fail(s, NPU_COLD_RX_EVENT_ORDER);
    /* Retain the possible effect before the caller issues its native store. */
    s->reserved = s->committed = 1;
    return NPU_COLD_RX_EVENT_OK;
}

uint32_t npu_cold_rx_event_publish(struct npu_cold_rx_event_state *s,
    const struct npu_cold_rx_event_plan *p, uint32_t epoch, uint32_t address,
    uint32_t bytes, uint32_t readback)
{
    if (!context(s, p, epoch))
        return fail(s, NPU_COLD_RX_EVENT_STALE);
    if (s->active != 1 || s->reserved != 1 || s->committed != 1 || s->published ||
        address != NPU_COLD_RX_EVENT_METADATA || bytes != 4)
        return fail(s, NPU_COLD_RX_EVENT_ORDER);
    if (readback != npu_cold_rx_event_value(p->ring))
        return fail(s, NPU_COLD_RX_EVENT_PUBLISH);
    s->published = 1;
    return NPU_COLD_RX_EVENT_OK;
}

uint32_t npu_cold_rx_event_finish(struct npu_cold_rx_event_state *s,
    const struct npu_cold_rx_event_plan *p, uint32_t epoch, uint32_t readback)
{
    if (!context(s, p, epoch))
        return fail(s, NPU_COLD_RX_EVENT_STALE);
    if (s->active != 1 || s->reserved != 1 || s->committed != 1 || s->published != 1 ||
        readback != npu_cold_rx_event_value(p->ring))
        return fail(s, NPU_COLD_RX_EVENT_CORRUPT);
    s->active = 0;
    return NPU_COLD_RX_EVENT_OK;
}

int npu_cold_rx_event_live(const struct npu_cold_rx_event_state *s,
    const struct npu_cold_rx_event_plan *p, uint32_t epoch, uint32_t readback)
{
    return context(s, p, epoch) && !s->active && s->reserved == 1 &&
           s->committed == 1 && s->published == 1 &&
           readback == npu_cold_rx_event_value(p->ring);
}
