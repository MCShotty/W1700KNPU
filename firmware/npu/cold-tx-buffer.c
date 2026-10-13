#include "cold-tx-buffer.h"

_Static_assert(sizeof(struct npu_cold_txbuf_plan) == 116, "TX buffer plan changed");
_Static_assert(sizeof(struct npu_cold_txbuf_state) == 213200, "TX buffer owner changed");

static uint32_t load(const uint32_t *p)
{
    return __atomic_load_n(p, __ATOMIC_ACQUIRE);
}

void npu_cold_txbuf_fault(struct npu_cold_txbuf_state *s)
{
    if (s)
        __atomic_store_n(&s->fault, 1, __ATOMIC_RELEASE);
}

static uint32_t fail(struct npu_cold_txbuf_state *s, uint32_t status)
{
    npu_cold_txbuf_fault(s);
    return status;
}

uint32_t npu_cold_txbuf_selector(uint32_t step)
{
    static const uint32_t values[] = {0, 5, 10, 2, 7, 12};

    return step < NPU_COLD_TXBUF_STEPS ? values[step] : UINT32_MAX;
}

uint32_t npu_cold_txbuf_bytes(uint32_t step)
{
    return step < NPU_COLD_TXBUF_STEPS ? step < 2 ? 0x20000u : 0x40000u : 0;
}

static uint32_t metadata_count(uint32_t step)
{
    return step == 2 || step == 5 ? 4 : 1;
}

uint32_t npu_cold_txbuf_count(uint32_t step)
{
    static const uint32_t counts[] = {1, 16385, 2052, 1, 32769, 2052};

    return step < NPU_COLD_TXBUF_STEPS ? counts[step] : 0;
}

static uint32_t lower(uint32_t step)
{
    uint32_t i, result = 0;

    for (i = 0; i < step && i < NPU_COLD_TXBUF_STEPS; i++)
        result += npu_cold_txbuf_count(i);
    return result;
}

static int range(uint32_t base, uint32_t bytes, uint32_t alignment)
{
    return base && base < 0xc0000000u && !(base & (alignment - 1)) && bytes &&
           bytes <= 0xc0000000u - base && bytes <= 0x40000000u - (base & 0x3fffffffu);
}

static int overlap(uint32_t a, uint32_t an, uint32_t b, uint32_t bn)
{
    uint64_t left = a & 0x3fffffffu, right = b & 0x3fffffffu;

    return left < right + bn && right < left + an;
}

static int protected(const struct npu_cold_txbuf_plan *p, uint32_t base, uint32_t bytes)
{
    uint32_t i;

    /* Normalize external DMA aliases only. Native SRAM/L2 destinations are
     * validated separately; equal low bits do not prove physical aliasing.
     */
    if (overlap(base, bytes, p->endpoint_base, p->endpoint_bytes))
        return 1;
    for (i = 0; i < NPU_BOOT_REGIONS; i++)
        if (overlap(base, bytes, p->boot.region[i].base, p->boot.region[i].bytes))
            return 1;
    return 0;
}

int npu_cold_txbuf_dma_valid(const struct npu_cold_txbuf_plan *p, uint32_t enrolled)
{
    uint32_t i, j, mailboxes, hosts;

    if (!p || enrolled > NPU_COLD_TXBUF_RECORDS ||
        !range(p->endpoint_base, p->endpoint_bytes, 4096) ||
        p->endpoint_bytes < 0xd45ccu || (p->endpoint_bytes & 4095u))
        return 0;
    for (i = 0; i < NPU_BOOT_REGIONS; i++) {
        const struct npu_bootstrap_range *r = &p->boot.region[i];

        if (r->base < 0x80000000u || !range(r->base, r->bytes, 4) ||
            overlap(r->base, r->bytes, p->endpoint_base, p->endpoint_bytes))
            return 0;
        for (j = 0; j < i; j++)
            if (overlap(r->base, r->bytes, p->boot.region[j].base, p->boot.region[j].bytes))
                return 0;
    }
    if (p->boot.region[NPU_BOOT_BINARY].bytes < 0x240000u ||
        p->boot.region[NPU_BOOT_TXCHECK].bytes < 0xe000u ||
        p->boot.region[NPU_BOOT_REQUEST].bytes != 256)
        return 0;
    mailboxes = enrolled < NPU_COLD_TXBUF_MAILBOXES ? enrolled : NPU_COLD_TXBUF_MAILBOXES;
    hosts = enrolled - mailboxes;
    if (mailboxes && p->mailbox[0] != p->boot.region[NPU_BOOT_REQUEST].base)
        return 0;
    for (i = 0; i < NPU_COLD_TXBUF_MAILBOXES; i++) {
        if (i >= mailboxes) {
            if (p->mailbox[i])
                return 0;
            continue;
        }
        if (!range(p->mailbox[i], 256, 4))
            return 0;
        /* The first mailbox is exactly the bootstrap request region. */
        if (i && protected(p, p->mailbox[i], 256))
            return 0;
        for (j = 0; j < i; j++)
            if (overlap(p->mailbox[i], 256, p->mailbox[j], 256))
                return 0;
    }
    for (i = 0; i < NPU_COLD_TXBUF_STEPS; i++) {
        uint32_t bytes = npu_cold_txbuf_bytes(i);

        if (i >= hosts) {
            if (p->host[i])
                return 0;
            continue;
        }
        if (!range(p->host[i], bytes, 256) || protected(p, p->host[i], bytes))
            return 0;
        for (j = 0; j < NPU_COLD_TXBUF_MAILBOXES; j++)
            if (overlap(p->host[i], bytes, p->mailbox[j], 256))
                return 0;
        for (j = 0; j < i; j++)
            if (overlap(p->host[i], bytes, p->host[j], npu_cold_txbuf_bytes(j)))
                return 0;
    }
    return 1;
}

int npu_cold_txbuf_plan_valid(const struct npu_cold_txbuf_plan *p)
{
    return p && npu_cold_descriptor_arena_valid(p->arena) &&
           npu_cold_txbuf_dma_valid(p, NPU_COLD_TXBUF_RECORDS);
}

uint32_t npu_cold_txbuf_recipe(const struct npu_cold_txbuf_plan *p, uint32_t step,
    uint32_t index, struct npu_cold_txbuf_store *out)
{
    static const uint32_t slots[] = {0x3e902cf8, 0x3e901f38, 0x3e903960,
                                     0x3e902ab4, 0x3e902abc, 0x3e902a88};
    static const uint32_t counters[2][3] = {
        {0x3e90462c, 0x3e90395a, 0x3e902acc},
        {0x3e902a8c, 0x3e90390c, 0x3e9021e8}
    };
    uint32_t meta, band = step >= 3, internal, base, item;

    if (!p || !out || step >= NPU_COLD_TXBUF_STEPS || index >= npu_cold_txbuf_count(step))
        return NPU_COLD_TXBUF_ARGUMENT;
    meta = metadata_count(step);
    internal = step == 1 || step == 4;
    base = internal ? p->arena + (band ? 0x2a040u : 0x8020u) :
                     band ? 0x3e8a4020u : 0x3e8a2000u;
    out->bytes = 4;
    if (!index) {
        out->address = slots[step];
        out->value = internal ? base : (p->host[step] & 0x3fffffffu) | 0x40000000u;
    } else if (index < meta) {
        out->address = counters[band][index - 1];
        out->bytes = index < 3 ? 2 : 4;
        out->value = index < 3 ? 0 : base;
    } else {
        item = index - meta;
        out->address = base + item * 4;
        if (internal)
            out->value = item % 32 == 0 ? 0x100000u : item % 32 == 31 ? 0x10000u : 0;
        else {
            out->bytes = item % 4 == 3 ? 1 : 4;
            out->value = item % 4 ? 0 :
                         ((p->host[step] + item / 4 * 256) & 0x3fffffffu) | 0x80000000u;
        }
    }
    return NPU_COLD_TXBUF_OK;
}

void npu_cold_txbuf_plan_copy(struct npu_cold_txbuf_plan *destination,
                            const struct npu_cold_txbuf_plan *source)
{
    volatile unsigned char *to = (volatile void *)destination;
    const volatile unsigned char *from = (const volatile void *)source;
    uint32_t i;

    for (i = 0; i < sizeof(*destination); i++)
        to[i] = from[i];
}

int npu_cold_txbuf_plan_equal(const struct npu_cold_txbuf_plan *left,
                             const struct npu_cold_txbuf_plan *right)
{
    const unsigned char *a = (const void *)left, *b = (const void *)right;
    uint32_t i;

    for (i = 0; i < sizeof(*left); i++)
        if (a[i] != b[i])
            return 0;
    return 1;
}

static uint32_t valid(struct npu_cold_txbuf_state *s, const struct npu_cold_txbuf_plan *p,
                      uint32_t epoch, uint32_t active)
{
    uint32_t from, until, done, reserved;

    if (!s || !p)
        return NPU_COLD_TXBUF_ARGUMENT;
    if (load(&s->fault))
        return NPU_COLD_TXBUF_FAULT;
    if (s->next > NPU_COLD_TXBUF_STEPS || (active && s->next == NPU_COLD_TXBUF_STEPS))
        return fail(s, NPU_COLD_TXBUF_CORRUPT);
    from = lower(s->next);
    until = from + (active ? npu_cold_txbuf_count(s->next) : 0);
    done = (1u << s->next) - 1;
    reserved = active ? (1u << (s->next + 1)) - 1 : done;
    if (s->magic != NPU_COLD_TXBUF_MAGIC || s->epoch != 1 || s->active != active ||
        !npu_cold_txbuf_plan_equal(&s->plan, p) || s->completed != done || s->reserved != reserved ||
        s->from != from || s->until != until || s->committed < from ||
        s->committed > until || s->published > s->committed ||
        s->committed - s->published > 1 || (!active && s->published != until))
        return fail(s, NPU_COLD_TXBUF_CORRUPT);
    return epoch == s->epoch ? NPU_COLD_TXBUF_OK : NPU_COLD_TXBUF_STALE;
}

uint32_t npu_cold_txbuf_begin(struct npu_cold_txbuf_state *s,
    const struct npu_cold_txbuf_plan *p, uint32_t epoch, uint32_t selector,
    uint32_t host, const volatile uint32_t *metadata, const volatile uint32_t *records)
{
    uint32_t i, meta, status;

    if (!s || !p)
        return NPU_COLD_TXBUF_ARGUMENT;
    if (!s->magic) {
        const unsigned char *bytes = (const void *)s;

        for (i = 0; i < sizeof(*s); i++)
            if (bytes[i])
                return NPU_COLD_TXBUF_REINITIALIZE;
        if (epoch != 1 || selector || !npu_cold_txbuf_plan_valid(p))
            return fail(s, NPU_COLD_TXBUF_PLAN);
        npu_cold_txbuf_plan_copy(&s->plan, p);
        s->epoch = 1;
        __atomic_store_n(&s->magic, NPU_COLD_TXBUF_MAGIC, __ATOMIC_RELEASE);
    }
    status = valid(s, p, epoch, 0);
    if (status)
        return status;
    if (s->next == NPU_COLD_TXBUF_STEPS || selector != npu_cold_txbuf_selector(s->next) ||
        host != p->host[s->next] || !metadata || ((uintptr_t)metadata & 3) ||
        (s->next == 0 || s->next == 3 ? !!records : !records || ((uintptr_t)records & 3)))
        return fail(s, NPU_COLD_TXBUF_ORDER);
    s->active = 1;
    s->reserved |= 1u << s->next;
    s->until = s->from + npu_cold_txbuf_count(s->next);
    meta = metadata_count(s->next);
    for (i = 0; i < meta; i++) {
        if ((s->next == 2 || s->next == 5) && (i == 1 || i == 2) && metadata[i] > 65535)
            return fail(s, NPU_COLD_TXBUF_PLAN);
        s->preimages[s->from + i] = metadata[i];
    }
    for (i = meta; i < npu_cold_txbuf_count(s->next); i++)
        s->preimages[s->from + i] = records[i - meta];
    return load(&s->fault) ? NPU_COLD_TXBUF_FAULT : NPU_COLD_TXBUF_OK;
}

uint32_t npu_cold_txbuf_reserve(struct npu_cold_txbuf_state *s,
    const struct npu_cold_txbuf_plan *p, uint32_t epoch, uint32_t address,
    uint32_t bytes, uint32_t value, uint32_t before)
{
    struct npu_cold_txbuf_store store;
    uint32_t status = valid(s, p, epoch, 1);

    if (status)
        return status;
    if (s->committed != s->published || s->committed == s->until ||
        npu_cold_txbuf_recipe(p, s->next, s->committed - s->from, &store) ||
        address != store.address || bytes != store.bytes || value != store.value ||
        before != s->preimages[s->committed])
        return fail(s, NPU_COLD_TXBUF_ORDER);
    __atomic_store_n(&s->committed, s->committed + 1, __ATOMIC_RELEASE);
    return load(&s->fault) ? NPU_COLD_TXBUF_FAULT : NPU_COLD_TXBUF_OK;
}

static uint32_t expected(const struct npu_cold_txbuf_state *s, uint32_t index,
                          const struct npu_cold_txbuf_store *store)
{
    return store->bytes == 1 ? (s->preimages[index] & 0xffffff00u) | store->value : store->value;
}

uint32_t npu_cold_txbuf_publish(struct npu_cold_txbuf_state *s,
    const struct npu_cold_txbuf_plan *p, uint32_t epoch, uint32_t address,
    uint32_t bytes, uint32_t readback)
{
    struct npu_cold_txbuf_store store;
    uint32_t status = valid(s, p, epoch, 1);

    if (status)
        return status;
    if (s->committed != s->published + 1 || s->published == s->until ||
        npu_cold_txbuf_recipe(p, s->next, s->published - s->from, &store) ||
        address != store.address || bytes != store.bytes || readback != expected(s, s->published, &store))
        return fail(s, NPU_COLD_TXBUF_PUBLISH);
    __atomic_store_n(&s->published, s->published + 1, __ATOMIC_RELEASE);
    return load(&s->fault) ? NPU_COLD_TXBUF_FAULT : NPU_COLD_TXBUF_OK;
}

uint32_t npu_cold_txbuf_finish(struct npu_cold_txbuf_state *s,
    const struct npu_cold_txbuf_plan *p, uint32_t epoch,
    const volatile uint32_t *metadata, const volatile uint32_t *records)
{
    struct npu_cold_txbuf_store store;
    uint32_t status = valid(s, p, epoch, 1), i, meta;

    if (status)
        return status;
    if (s->committed != s->until || s->published != s->until ||
        !metadata || ((uintptr_t)metadata & 3) ||
        (s->next == 0 || s->next == 3 ? !!records : !records || ((uintptr_t)records & 3)))
        return fail(s, NPU_COLD_TXBUF_PUBLISH);
    meta = metadata_count(s->next);
    for (i = 0; i < npu_cold_txbuf_count(s->next); i++) {
        uint32_t readback = i < meta ? metadata[i] : records[i - meta];

        if (npu_cold_txbuf_recipe(p, s->next, i, &store) ||
            readback != expected(s, s->from + i, &store))
            return fail(s, NPU_COLD_TXBUF_PUBLISH);
    }
    s->completed |= 1u << s->next;
    s->next++;
    s->from = s->until;
    s->active = 0;
    return load(&s->fault) ? NPU_COLD_TXBUF_FAULT : NPU_COLD_TXBUF_OK;
}
