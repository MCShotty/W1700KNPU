/* Portable logical memory fixture, not original RV32 stores or hardware backing. */
#include "cold-txdone.h"

struct npu_cold_txdone_state npu_test_txdone_state;
struct npu_cold_txdone_plan npu_test_txdone_plan;
struct npu_cold_rx_event_state npu_test_txdone_rx;
struct npu_cold_packet_state npu_test_txdone_packet;
struct npu_cold_packet_queue_result npu_test_txdone_last;
uint32_t npu_test_txdone_occupied[NPU_COLD_TXDONE_OCCUPIED];
uint16_t npu_test_txdone_pool[NPU_COLD_PACKET_IDS], npu_test_txdone_head, npu_test_txdone_tail;
uint8_t npu_test_txdone_ring[8192], npu_test_txdone_ids[1024], npu_test_txdone_temp[4096];
uint8_t npu_test_txdone_check[16384], npu_test_txdone_queue[16384];
uint32_t npu_test_txdone_count, npu_test_txdone_pointer, npu_test_txdone_skb_head;
uint32_t npu_test_txdone_skb_tail, npu_test_txdone_counter, npu_test_txdone_ready;
uint32_t npu_test_txdone_events[NPU_COLD_TXDONE_STORES * 3], npu_test_txdone_event_count;

#define STATE (&npu_test_txdone_state)
#define PLAN (&npu_test_txdone_plan)
#define RX (&npu_test_txdone_rx)
#define PKT (&npu_test_txdone_packet)

static void zero(void *memory, uint32_t bytes)
{
    volatile uint8_t *data = memory;

    for (uint32_t i = 0; i < bytes; i++)
        data[i] = 0;
}

static void fill(uint8_t *data, uint32_t bytes)
{
    for (uint32_t i = 0; i < bytes; i++)
        data[i] = 0xa5;
}

static struct npu_cold_packet_queue queue(void)
{
    const struct npu_cold_packet_queue result = {
        &npu_test_txdone_head, &npu_test_txdone_tail, npu_test_txdone_pool, NPU_COLD_PACKET_IDS
    };

    return result;
}

uint32_t npu_test_txdone_fresh(uint32_t alias)
{
    static const struct npu_cold_txdone_plan plan = {.prior = {.prior = {
        .arena = 0x3e810000, .endpoint_base = 0x20000000, .endpoint_bytes = 0x100000,
        .host = {0x96000000, 0x96100000, 0x96200000, 0x96300000, 0x96400000, 0x96500000},
        .mailbox = {0x83000000, 0x83100000, 0x83200000, 0x83300000,
                    0x83400000, 0x83500000, 0x83600000, 0x83700000},
        .boot.region = {{0x84000000, 0xa00000}, {0x90c00000, 0xe000},
                        {0x8a000000, 0x2c00000}, {0x8cc00000, 0x4000000},
                        {0x90c0e000, 0x200000}, {0x83000000, 256}}
    }, .ring = 0x17000000}, .packet_pool = 0x3e800020, .ids_pool = NPU_COLD_TXDONE_IDS_POOL,
       .temporary = 0x3e871000, .skb_queue = 0x3e872000};
    struct npu_cold_packet_plan packets = {0x8a000000, 0x2c00000};
    struct npu_cold_packet_queue q;
    uint32_t i, expected;

    if (alias > 2)
        return 1;
    zero(STATE, sizeof(*STATE));
    zero(RX, sizeof(*RX));
    zero(PKT, sizeof(*PKT));
    zero(&npu_test_txdone_last, sizeof(npu_test_txdone_last));
    zero(npu_test_txdone_events, sizeof(npu_test_txdone_events));
    npu_test_txdone_event_count = 0;
    npu_cold_txdone_plan_copy(PLAN, &plan);
    PLAN->prior.ring += alias * 0x40000000u;
    expected = npu_cold_rx_event_value(PLAN->prior.ring);
    if (npu_cold_rx_event_begin(RX, &PLAN->prior, 1, 0xdeadbeef) ||
        npu_cold_rx_event_reserve(RX, &PLAN->prior, 1, NPU_COLD_RX_EVENT_METADATA, 4, expected, 0xdeadbeef) ||
        npu_cold_rx_event_publish(RX, &PLAN->prior, 1, NPU_COLD_RX_EVENT_METADATA, 4, expected) ||
        npu_cold_rx_event_finish(RX, &PLAN->prior, 1, expected) ||
        npu_cold_packet_init(PKT, &packets, 1))
        return 2;
    npu_test_txdone_head = 0;
    npu_test_txdone_tail = NPU_COLD_TXDONE_PREFIX + NPU_COLD_TXDONE_IDS + 1;
    for (i = 0; i < NPU_COLD_PACKET_IDS; i++)
        npu_test_txdone_pool[i] = i;
    for (i = 0; i < NPU_COLD_TXDONE_IDS; i++)
        npu_test_txdone_pool[NPU_COLD_TXDONE_PREFIX + i] = 8000 + (i * 13) % NPU_COLD_TXDONE_IDS;
    q = queue();
    for (i = 0; i < NPU_COLD_TXDONE_PREFIX; i++) {
        struct npu_cold_packet_queue_result taken = npu_cold_packet_queue_take(PKT, &packets, 1, &q);

        if (taken.packet.status || !taken.packet.committed || !taken.published)
            return 3;
    }
    for (i = 0; i < NPU_COLD_TXDONE_OCCUPIED; i++)
        npu_test_txdone_occupied[i] = (i * 17 + 7) % NPU_COLD_TXDONE_CAPACITY;
    fill(npu_test_txdone_ring, sizeof(npu_test_txdone_ring));
    fill(npu_test_txdone_ids, sizeof(npu_test_txdone_ids));
    fill(npu_test_txdone_temp, sizeof(npu_test_txdone_temp));
    fill(npu_test_txdone_check, sizeof(npu_test_txdone_check));
    fill(npu_test_txdone_queue, sizeof(npu_test_txdone_queue));
    npu_test_txdone_count = npu_test_txdone_pointer = npu_test_txdone_skb_head = 0xa5a5a5a5;
    npu_test_txdone_skb_tail = npu_test_txdone_counter = npu_test_txdone_ready = 0xa5a5a5a5;
    return 0;
}

static uint8_t *span(uint32_t address, uint32_t bytes)
{
    const uint32_t bases[] = {npu_cold_rx_event_value(PLAN->prior.ring), PLAN->ids_pool,
        PLAN->temporary, npu_cold_rx_event_value(PLAN->prior.prior.boot.region[NPU_BOOT_TXCHECK].base),
        PLAN->skb_queue, 0x3e902a7c, 0x3e902cf4, 0x3e901bb4, 0x3e901b94, 0x3e903974, 0x3e9046fa};
    const uint32_t sizes[] = {8192, 1024, 4096, 16384, 16384, 4, 4, 4, 4, 4, 4};
    uint8_t *const arrays[] = {npu_test_txdone_ring, npu_test_txdone_ids, npu_test_txdone_temp,
        npu_test_txdone_check, npu_test_txdone_queue, (void *)&npu_test_txdone_count,
        (void *)&npu_test_txdone_pointer, (void *)&npu_test_txdone_skb_head,
        (void *)&npu_test_txdone_skb_tail, (void *)&npu_test_txdone_counter,
        (void *)&npu_test_txdone_ready};

    for (uint32_t i = 0; i < sizeof(bases) / 4; i++)
        if (address >= bases[i] && address - bases[i] < sizes[i] &&
            bytes <= sizes[i] - (address - bases[i]))
            return arrays[i] + address - bases[i];
    return 0;
}

static uint32_t read(const uint8_t *data, uint32_t bytes)
{
    uint32_t result = 0;

    for (uint32_t i = 0; i < bytes; i++)
        result |= (uint32_t)data[i] << (i * 8);
    return result;
}

int npu_test_txdone_read(void *opaque, uint32_t address, uint32_t bytes, uint32_t *value)
{
    const uint8_t *data = span(address, bytes);

    (void)opaque;
    if (!data || !value || (bytes != 1 && bytes != 2 && bytes != 4))
        return 0;
    *value = read(data, bytes);
    return 1;
}

uint32_t npu_test_txdone_begin(void)
{
    return npu_cold_txdone_begin(STATE, PLAN, 1, RX, npu_cold_rx_event_value(PLAN->prior.ring), PKT);
}

uint32_t npu_test_txdone_take(void)
{
    struct npu_cold_packet_plan packets = {PKT->packet_base, PKT->packet_bytes};
    struct npu_cold_packet_queue q = queue();
    uint32_t status = npu_cold_txdone_claim_reserve(STATE, PLAN, 1, PKT);

    if (status)
        return status;
    npu_test_txdone_last = npu_cold_packet_queue_take(PKT, &packets, 1, &q);
    return npu_cold_txdone_claim_publish(STATE, PLAN, 1, PKT, &npu_test_txdone_last);
}

uint32_t npu_test_txdone_skb_begin(void)
{
    return npu_cold_txdone_skb_begin(STATE, PLAN, 1, RX,
        npu_cold_rx_event_value(PLAN->prior.ring), PKT, npu_test_txdone_occupied);
}

uint32_t npu_test_txdone_take_late(uint32_t published)
{
    struct npu_cold_packet_plan packets = {PKT->packet_base, PKT->packet_bytes};
    struct npu_cold_packet_queue q = queue();
    uint32_t status = npu_cold_txdone_claim_reserve(STATE, PLAN, 1, PKT);

    if (status)
        return status;
    if (published) {
        npu_test_txdone_last = npu_cold_packet_queue_take(PKT, &packets, 1, &q);
        npu_cold_packet_fault(PKT);
    } else {
        npu_test_txdone_last.packet = npu_cold_packet_take(PKT, &packets, 1,
            npu_test_txdone_head, npu_test_txdone_tail, npu_test_txdone_pool[npu_test_txdone_head]);
        npu_test_txdone_last.published = 0;
    }
    return npu_cold_txdone_claim_publish(STATE, PLAN, 1, PKT, &npu_test_txdone_last);
}

/* Fault 1 stops after reservation, fault 2 changes readback after the real
 * logical write, and fault 3 latches a fault after publication. */
uint32_t npu_test_txdone_run(uint32_t count, uint32_t fault)
{
    for (uint32_t i = 0; i < count; i++) {
        struct npu_cold_txdone_store store;
        uint8_t *target;
        uint32_t status;

        if (STATE->published < NPU_COLD_TXDONE_DESCRIPTOR_STORES && STATE->published >= 2 &&
            (STATE->published - 2) % 6 == 0 &&
            STATE->claims_published == (STATE->published - 2) / 6) {
            status = npu_test_txdone_take();
            if (status)
                return status;
        }
        if (STATE->published == NPU_COLD_TXDONE_DESCRIPTOR_STORES && !STATE->skb_reserved) {
            status = npu_test_txdone_skb_begin();
            if (status)
                return status;
        }
        status = npu_cold_txdone_recipe(STATE, &store);
        if (status)
            return status;
        target = span(store.address, store.bytes);
        if (!target)
            return 100;
        status = npu_cold_txdone_reserve(STATE, PLAN, 1, store.address, store.bytes,
                                       store.value, read(target, store.bytes));
        if (status)
            return status;
        if (fault == 1) {
            npu_cold_txdone_fault(STATE);
            return NPU_COLD_TXDONE_STALE;
        }
        for (uint32_t byte = 0; byte < store.bytes; byte++)
            target[byte] = store.value >> (byte * 8);
        npu_test_txdone_events[npu_test_txdone_event_count * 3] = store.address;
        npu_test_txdone_events[npu_test_txdone_event_count * 3 + 1] = store.bytes;
        npu_test_txdone_events[npu_test_txdone_event_count * 3 + 2] = store.value;
        npu_test_txdone_event_count++;
        status = npu_cold_txdone_publish(STATE, PLAN, 1, store.address, store.bytes,
                                       read(target, store.bytes) ^ (fault == 2));
        if (status)
            return status;
        if (fault == 3) {
            npu_cold_txdone_fault(STATE);
            return NPU_COLD_TXDONE_STALE;
        }
    }
    return 0;
}

uint32_t npu_test_txdone_finish(void)
{
    return npu_cold_txdone_finish(STATE, PLAN, 1, RX, npu_cold_rx_event_value(PLAN->prior.ring),
                                PKT, npu_test_txdone_ready & 255);
}

uint32_t npu_test_txdone_live(void)
{
    return npu_cold_txdone_live(STATE, PLAN, 1, RX, npu_cold_rx_event_value(PLAN->prior.ring),
                              PKT, npu_test_txdone_ready & 255);
}

#ifdef NPU_TXDONE_SANITIZER
#include <assert.h>

int main(void)
{
    for (uint32_t alias = 0; alias < 3; alias++) {
        assert(!npu_test_txdone_fresh(alias));
        assert(!npu_test_txdone_begin());
        assert(!npu_test_txdone_run(NPU_COLD_TXDONE_STORES, 0));
        assert(!npu_test_txdone_finish());
        assert(npu_test_txdone_live());
        assert(npu_test_txdone_event_count == NPU_COLD_TXDONE_STORES);
        assert(npu_test_txdone_begin());
        assert(STATE->fault && STATE->committed == NPU_COLD_TXDONE_STORES);
    }
    for (uint32_t fault = 1; fault <= 3; fault++) {
        assert(!npu_test_txdone_fresh(0));
        assert(!npu_test_txdone_begin());
        assert(!npu_test_txdone_run(2, 0));
        assert(npu_test_txdone_run(1, fault));
        assert(STATE->fault && STATE->active && STATE->committed == 3);
        assert(STATE->published == (fault == 3 ? 3u : 2u));
        assert(STATE->claims_committed == 1);
        assert(!npu_test_txdone_live());
    }
    return 0;
}
#endif
