#include "cold-txdone.h"

_Static_assert(sizeof(struct npu_cold_txdone_plan) == 136, "TXDONE plan changed");
_Static_assert(sizeof(struct npu_cold_txdone_state) == 13512, "TXDONE owner changed");

#define HEAP 0x3e800000u
#define HEAP_END 0x3e878000u

static uint32_t load(const uint32_t *word)
{
    return __atomic_load_n(word, __ATOMIC_ACQUIRE);
}

void npu_cold_txdone_fault(struct npu_cold_txdone_state *s)
{
    if (s)
        __atomic_store_n(&s->fault, 1, __ATOMIC_RELEASE);
}

static uint32_t fail(struct npu_cold_txdone_state *s, uint32_t status)
{
    npu_cold_txdone_fault(s);
    return status;
}

static int overlap(uint32_t a, uint32_t bytes, uint32_t b, uint32_t size)
{
    return (uint64_t)a < (uint64_t)b + size && (uint64_t)b < (uint64_t)a + bytes;
}

int npu_cold_txdone_plan_valid(const struct npu_cold_txdone_plan *p)
{
    const uint32_t bytes[] = {32768, 1024, 4096, 16384};
    uint32_t bases[4], i, j;

    if (!p || !npu_cold_rx_event_plan_valid(&p->prior))
        return 0;
    bases[0] = p->packet_pool;
    bases[1] = p->ids_pool;
    bases[2] = p->temporary;
    bases[3] = p->skb_queue;
    for (i = 0; i < 4; i++) {
        if ((bases[i] & 31) || bases[i] < HEAP || bases[i] >= HEAP_END ||
            bytes[i] > HEAP_END - bases[i] ||
            overlap(bases[i], bytes[i], p->prior.prior.arena, NPU_COLD_DESCRIPTOR_ARENA_BYTES))
            return 0;
        for (j = 0; j < i; j++)
            if (overlap(bases[i], bytes[i], bases[j], bytes[j]))
                return 0;
    }
    return 1;
}

void npu_cold_txdone_plan_copy(struct npu_cold_txdone_plan *to,
                             const struct npu_cold_txdone_plan *from)
{
    npu_cold_rx_event_plan_copy(&to->prior, &from->prior);
    to->packet_pool = from->packet_pool;
    to->ids_pool = from->ids_pool;
    to->temporary = from->temporary;
    to->skb_queue = from->skb_queue;
}

int npu_cold_txdone_plan_equal(const struct npu_cold_txdone_plan *a,
                              const struct npu_cold_txdone_plan *b)
{
    return a && b && npu_cold_rx_event_plan_equal(&a->prior, &b->prior) &&
           a->packet_pool == b->packet_pool && a->ids_pool == b->ids_pool &&
           a->temporary == b->temporary && a->skb_queue == b->skb_queue;
}

static int context(const struct npu_cold_txdone_state *s,
                   const struct npu_cold_txdone_plan *p, uint32_t epoch)
{
    return s && p && load(&s->magic) == NPU_COLD_TXDONE_MAGIC && epoch == 1 &&
           s->epoch == epoch && !load(&s->fault) && s->active <= 1 &&
           s->reserved == s->committed && s->committed <= NPU_COLD_TXDONE_STORES &&
           s->published <= s->committed && s->committed - s->published <= 1 &&
           s->claims_reserved <= NPU_COLD_TXDONE_IDS &&
           s->claims_published <= s->claims_committed &&
           s->claims_committed <= s->claims_reserved &&
           s->claims_reserved - s->claims_published <= 1 && s->skb_reserved <= 1 &&
           s->next_free <= NPU_COLD_TXDONE_CAPACITY &&
           npu_cold_txdone_plan_valid(p) && npu_cold_txdone_plan_equal(&s->plan, p);
}

static uint32_t population(uint32_t bits)
{
    bits -= (bits >> 1) & 0x55555555u;
    bits = (bits & 0x33333333u) + ((bits >> 2) & 0x33333333u);
    bits = (bits + (bits >> 4)) & 0x0f0f0f0fu;
    return (bits * 0x01010101u) >> 24;
}

static int packet_header(const struct npu_cold_packet_state *pkt,
                         const struct npu_cold_txdone_plan *p, uint32_t count)
{
    const struct npu_bootstrap_range *region = &p->prior.prior.boot.region[NPU_BOOT_PKT];

    return pkt && load(&pkt->magic) == NPU_COLD_PACKET_MAGIC && pkt->epoch == 1 &&
           !load(&pkt->fault) && pkt->count == count && pkt->head == count &&
           pkt->packet_base == region->base && pkt->packet_bytes == region->bytes;
}

static int packets_live(const struct npu_cold_txdone_state *s,
                         const struct npu_cold_packet_state *pkt)
{
    volatile uint32_t expected[NPU_COLD_PACKET_WORDS];
    uint32_t i, id;

    if (!packet_header(pkt, &s->plan, NPU_COLD_TXDONE_PREFIX + s->claims_committed))
        return 0;
    for (i = 0; i < NPU_COLD_PACKET_WORDS; i++)
        expected[i] = s->prefix[i];
    for (i = 0; i < s->claims_committed; i++) {
        uint32_t bit;

        id = s->ids[i];
        if (id >= NPU_COLD_PACKET_IDS)
            return 0;
        bit = 1u << (id & 31);
        if (expected[id >> 5] & bit)
            return 0;
        expected[id >> 5] |= bit;
    }
    for (i = 0; i < NPU_COLD_PACKET_WORDS; i++)
        if (pkt->claimed[i] != expected[i])
            return 0;
    return 1;
}

uint32_t npu_cold_txdone_begin(struct npu_cold_txdone_state *s,
    const struct npu_cold_txdone_plan *p, uint32_t epoch,
    const struct npu_cold_rx_event_state *rx, uint32_t rx_readback,
    const struct npu_cold_packet_state *pkt)
{
    const volatile uint32_t *words = (const volatile void *)s;
    uint32_t i, count = 0;

    if (!s || !p || !rx || !pkt)
        return fail(s, NPU_COLD_TXDONE_ARGUMENT);
    if (epoch != 1 || !npu_cold_txdone_plan_valid(p) ||
        !npu_cold_rx_event_live(rx, &p->prior, epoch, rx_readback) ||
        !packet_header(pkt, p, NPU_COLD_TXDONE_PREFIX))
        return fail(s, NPU_COLD_TXDONE_PLAN);
    for (i = 0; i < sizeof(*s) / 4; i++)
        if (words[i])
            return fail(s, NPU_COLD_TXDONE_REINITIALIZE);
    for (i = 0; i < NPU_COLD_PACKET_WORDS; i++)
        count += population(pkt->claimed[i]);
    if (count != NPU_COLD_TXDONE_PREFIX)
        return fail(s, NPU_COLD_TXDONE_CORRUPT);
    npu_cold_txdone_plan_copy(&s->plan, p);
    for (i = 0; i < NPU_COLD_PACKET_WORDS; i++)
        s->prefix[i] = pkt->claimed[i];
    s->epoch = epoch;
    s->active = 1;
    __atomic_store_n(&s->magic, NPU_COLD_TXDONE_MAGIC, __ATOMIC_RELEASE);
    return NPU_COLD_TXDONE_OK;
}

uint32_t npu_cold_txdone_claim_reserve(struct npu_cold_txdone_state *s,
    const struct npu_cold_txdone_plan *p, uint32_t epoch, const struct npu_cold_packet_state *pkt)
{
    if (!context(s, p, epoch))
        return fail(s, NPU_COLD_TXDONE_STALE);
    if (!s->active || s->skb_reserved || s->committed != s->published ||
        s->claims_reserved != s->claims_published || s->claims_committed != s->claims_published ||
        s->claims_published >= NPU_COLD_TXDONE_IDS ||
        s->published != 2 + s->claims_published * 6 || !packets_live(s, pkt))
        return fail(s, NPU_COLD_TXDONE_ORDER);
    s->claims_reserved++;
    return NPU_COLD_TXDONE_OK;
}

uint32_t npu_cold_txdone_claim_publish(struct npu_cold_txdone_state *s,
    const struct npu_cold_txdone_plan *p, uint32_t epoch, const struct npu_cold_packet_state *pkt,
    const struct npu_cold_packet_queue_result *result)
{
    const struct npu_bootstrap_range *region;
    uint32_t index;

    if (!context(s, p, epoch) || !result)
        return fail(s, NPU_COLD_TXDONE_STALE);
    index = s->claims_published;
    if (!s->active || s->skb_reserved || s->claims_reserved != index + 1 ||
        s->claims_committed != index || result->packet.committed > 1 || result->published > 1)
        return fail(s, NPU_COLD_TXDONE_ORDER);
    region = &p->prior.prior.boot.region[NPU_BOOT_PKT];
    if (result->packet.committed) {
        if (result->packet.id >= NPU_COLD_PACKET_IDS)
            return fail(s, NPU_COLD_TXDONE_CORRUPT);
        s->ids[index] = result->packet.id;
        s->claims_committed++;
        if (result->published)
            s->claims_published++;
    }
    if (!result->packet.committed || !result->published ||
        result->packet.status != NPU_COLD_PACKET_OK ||
        result->packet.address != region->base + result->packet.id * NPU_COLD_PACKET_BYTES ||
        result->packet.next_head != NPU_COLD_TXDONE_PREFIX + s->claims_committed ||
        !packets_live(s, pkt))
        return fail(s, NPU_COLD_TXDONE_PUBLISH);
    return NPU_COLD_TXDONE_OK;
}

uint32_t npu_cold_txdone_skb_begin(struct npu_cold_txdone_state *s,
    const struct npu_cold_txdone_plan *p, uint32_t epoch,
    const struct npu_cold_rx_event_state *rx, uint32_t rx_readback,
    const struct npu_cold_packet_state *pkt, const volatile uint32_t *occupied)
{
    uint32_t i;

    if (!context(s, p, epoch) || !rx || !occupied)
        return fail(s, NPU_COLD_TXDONE_STALE);
    if (!s->active || s->skb_reserved || s->committed != NPU_COLD_TXDONE_DESCRIPTOR_STORES ||
        s->published != s->committed || s->claims_reserved != NPU_COLD_TXDONE_IDS ||
        s->claims_committed != NPU_COLD_TXDONE_IDS || s->claims_published != NPU_COLD_TXDONE_IDS ||
        !packets_live(s, pkt) || !npu_cold_rx_event_live(rx, &p->prior, epoch, rx_readback))
        return fail(s, NPU_COLD_TXDONE_ORDER);
    s->skb_reserved = 1;
    for (i = 0; i < NPU_COLD_TXDONE_OCCUPIED; i++) {
        uint32_t id = occupied[i], bit;

        if (id >= NPU_COLD_TXDONE_CAPACITY)
            return fail(s, NPU_COLD_TXDONE_CORRUPT);
        bit = 1u << (id & 31);
        if (s->occupied_bitmap[id >> 5] & bit)
            return fail(s, NPU_COLD_TXDONE_CORRUPT);
        s->occupied[i] = id;
        s->occupied_bitmap[id >> 5] |= bit;
    }
    return NPU_COLD_TXDONE_OK;
}

uint32_t npu_cold_txdone_recipe(const struct npu_cold_txdone_state *s,
                               struct npu_cold_txdone_store *out)
{
    uint32_t position, index, field, id;

    if (!s || !out || s->published >= NPU_COLD_TXDONE_STORES)
        return NPU_COLD_TXDONE_ARGUMENT;
    position = s->published;
    if (position < 2) {
        if (s->claims_reserved || s->claims_committed || s->claims_published || s->skb_reserved)
            return NPU_COLD_TXDONE_ORDER;
        out->address = position ? 0x3e902cf4u : 0x3e902a7cu;
        out->bytes = position ? 4 : 2;
        out->value = position ? s->plan.ids_pool : NPU_COLD_TXDONE_IDS;
        return NPU_COLD_TXDONE_OK;
    }
    if (position < NPU_COLD_TXDONE_DESCRIPTOR_STORES) {
        static const uint32_t offsets[] = {4, 0, 8, 12, 4};

        index = (position - 2) / 6;
        field = (position - 2) % 6;
        if (s->skb_reserved || s->claims_published != index + 1 || s->claims_committed != index + 1 ||
            s->claims_reserved != index + 1 || s->ids[index] >= NPU_COLD_PACKET_IDS)
            return NPU_COLD_TXDONE_ORDER;
        id = s->ids[index];
        out->address = field == 5 ? s->plan.ids_pool + index * 2 :
                       npu_cold_rx_event_value(s->plan.prior.ring) + index * 16 + offsets[field];
        out->bytes = field == 5 ? 2 : 4;
        out->value = field == 5 ? id : field == 4 ? 0x07000100u : 0;
        if (field == 1)
            out->value = ((s->plan.prior.prior.boot.region[NPU_BOOT_PKT].base +
                           id * NPU_COLD_PACKET_BYTES) & 0x3fffffffu) + 0x80000080u;
        return NPU_COLD_TXDONE_OK;
    }
    if (s->skb_reserved != 1 || s->claims_reserved != NPU_COLD_TXDONE_IDS ||
        s->claims_committed != NPU_COLD_TXDONE_IDS || s->claims_published != NPU_COLD_TXDONE_IDS)
        return NPU_COLD_TXDONE_ORDER;
    position -= NPU_COLD_TXDONE_DESCRIPTOR_STORES;
    out->bytes = 2;
    if (position < NPU_COLD_TXDONE_OCCUPIED) {
        out->address = s->plan.temporary + position * 2;
        out->value = 65535;
        return NPU_COLD_TXDONE_OK;
    }
    position -= NPU_COLD_TXDONE_OCCUPIED;
    if (position < NPU_COLD_TXDONE_OCCUPIED) {
        out->address = s->plan.temporary + position * 2;
        out->value = s->occupied[position];
        return out->value < NPU_COLD_TXDONE_CAPACITY ? NPU_COLD_TXDONE_OK : NPU_COLD_TXDONE_CORRUPT;
    }
    position -= NPU_COLD_TXDONE_OCCUPIED;
    if (position < NPU_COLD_TXDONE_CAPACITY) {
        out->address = npu_cold_rx_event_value(s->plan.prior.prior.boot.region[NPU_BOOT_TXCHECK].base) + position * 2;
        out->value = 0;
        return NPU_COLD_TXDONE_OK;
    }
    position -= NPU_COLD_TXDONE_CAPACITY;
    if (position < NPU_COLD_TXDONE_OCCUPIED) {
        id = s->occupied[position];
        if (id >= NPU_COLD_TXDONE_CAPACITY)
            return NPU_COLD_TXDONE_CORRUPT;
        out->address = npu_cold_rx_event_value(s->plan.prior.prior.boot.region[NPU_BOOT_TXCHECK].base) + id * 2;
        out->value = 3;
        return NPU_COLD_TXDONE_OK;
    }
    position -= NPU_COLD_TXDONE_OCCUPIED;
    if (position < NPU_COLD_TXDONE_CAPACITY) {
        id = position < NPU_COLD_TXDONE_OCCUPIED ? s->occupied[position] : s->next_free;
        if (position >= NPU_COLD_TXDONE_OCCUPIED)
            while (id < NPU_COLD_TXDONE_CAPACITY &&
                   (s->occupied_bitmap[id >> 5] & (1u << (id & 31))))
                id++;
        if (id >= NPU_COLD_TXDONE_CAPACITY)
            return NPU_COLD_TXDONE_CORRUPT;
        out->address = s->plan.skb_queue + position * 2;
        out->value = id;
        return NPU_COLD_TXDONE_OK;
    }
    position -= NPU_COLD_TXDONE_CAPACITY;
    switch (position) {
    case 0: out->address = 0x3e901bb4u; out->value = NPU_COLD_TXDONE_OCCUPIED; break;
    case 1: out->address = 0x3e901b94u; out->value = 0; break;
    case 2: out->address = 0x3e903974u; out->bytes = 4; out->value = 0; break;
    case 3: out->address = 0x3e9046fau; out->bytes = 1; out->value = 1; break;
    default: return NPU_COLD_TXDONE_ORDER;
    }
    return NPU_COLD_TXDONE_OK;
}

uint32_t npu_cold_txdone_reserve(struct npu_cold_txdone_state *s,
    const struct npu_cold_txdone_plan *p, uint32_t epoch,
    uint32_t address, uint32_t bytes, uint32_t value, uint32_t before)
{
    struct npu_cold_txdone_store store;

    if (!context(s, p, epoch))
        return fail(s, NPU_COLD_TXDONE_STALE);
    if (!s->active || s->committed != s->published ||
        npu_cold_txdone_recipe(s, &store) || address != store.address ||
        bytes != store.bytes || value != store.value)
        return fail(s, NPU_COLD_TXDONE_ORDER);
    s->before = before;
    s->pending_address = address;
    s->pending_bytes = bytes;
    s->pending_value = value;
    s->reserved = ++s->committed;
    return NPU_COLD_TXDONE_OK;
}

uint32_t npu_cold_txdone_publish(struct npu_cold_txdone_state *s,
    const struct npu_cold_txdone_plan *p, uint32_t epoch,
    uint32_t address, uint32_t bytes, uint32_t readback)
{
    struct npu_cold_txdone_store store;
    uint32_t free_begin = NPU_COLD_TXDONE_DESCRIPTOR_STORES + NPU_COLD_TXDONE_OCCUPIED * 4u +
                          NPU_COLD_TXDONE_CAPACITY;
    uint32_t free_end = NPU_COLD_TXDONE_DESCRIPTOR_STORES + NPU_COLD_TXDONE_OCCUPIED * 3u +
                        NPU_COLD_TXDONE_CAPACITY * 2u;

    if (!context(s, p, epoch))
        return fail(s, NPU_COLD_TXDONE_STALE);
    if (!s->active || s->committed != s->published + 1 ||
        address != s->pending_address || bytes != s->pending_bytes ||
        npu_cold_txdone_recipe(s, &store) || address != store.address ||
        bytes != store.bytes || store.value != s->pending_value)
        return fail(s, NPU_COLD_TXDONE_ORDER);
    if (readback != store.value)
        return fail(s, NPU_COLD_TXDONE_PUBLISH);
    if (s->published >= free_begin && s->published < free_end)
        s->next_free = store.value + 1;
    s->published++;
    return NPU_COLD_TXDONE_OK;
}

static int complete(const struct npu_cold_txdone_state *s, const struct npu_cold_txdone_plan *p,
                    uint32_t epoch, const struct npu_cold_rx_event_state *rx, uint32_t rx_readback,
                    const struct npu_cold_packet_state *pkt, uint32_t ready)
{
    volatile uint32_t bitmap[NPU_COLD_TXDONE_BITMAP_WORDS];
    uint32_t i;

    if (!context(s, p, epoch) || ready != 1 || s->reserved != NPU_COLD_TXDONE_STORES ||
        s->committed != NPU_COLD_TXDONE_STORES || s->published != NPU_COLD_TXDONE_STORES ||
        s->claims_reserved != NPU_COLD_TXDONE_IDS || s->claims_committed != NPU_COLD_TXDONE_IDS ||
        s->claims_published != NPU_COLD_TXDONE_IDS || s->skb_reserved != 1 ||
        !packets_live(s, pkt) || !npu_cold_rx_event_live(rx, &p->prior, epoch, rx_readback))
        return 0;
    for (i = 0; i < NPU_COLD_TXDONE_BITMAP_WORDS; i++)
        bitmap[i] = 0;
    for (i = 0; i < NPU_COLD_TXDONE_OCCUPIED; i++) {
        uint32_t id = s->occupied[i], bit;

        if (id >= NPU_COLD_TXDONE_CAPACITY)
            return 0;
        bit = 1u << (id & 31);
        if (bitmap[id >> 5] & bit)
            return 0;
        bitmap[id >> 5] |= bit;
    }
    for (i = 0; i < NPU_COLD_TXDONE_BITMAP_WORDS; i++)
        if (bitmap[i] != s->occupied_bitmap[i])
            return 0;
    for (i = s->next_free; i < NPU_COLD_TXDONE_CAPACITY; i++)
        if (!(bitmap[i >> 5] & (1u << (i & 31))))
            return 0;
    return 1;
}

uint32_t npu_cold_txdone_finish(struct npu_cold_txdone_state *s,
    const struct npu_cold_txdone_plan *p, uint32_t epoch,
    const struct npu_cold_rx_event_state *rx, uint32_t rx_readback,
    const struct npu_cold_packet_state *pkt, uint32_t ready)
{
    if (!s || s->active != 1 || !complete(s, p, epoch, rx, rx_readback, pkt, ready))
        return fail(s, NPU_COLD_TXDONE_CORRUPT);
    s->active = 0;
    return NPU_COLD_TXDONE_OK;
}

int npu_cold_txdone_live(const struct npu_cold_txdone_state *s,
    const struct npu_cold_txdone_plan *p, uint32_t epoch,
    const struct npu_cold_rx_event_state *rx, uint32_t rx_readback,
    const struct npu_cold_packet_state *pkt, uint32_t ready)
{
    return s && !s->active && complete(s, p, epoch, rx, rx_readback, pkt, ready);
}
