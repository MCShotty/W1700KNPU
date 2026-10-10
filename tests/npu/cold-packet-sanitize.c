#include "cold-packet.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const struct npu_cold_packet_plan plan = {0x8a000000u, 0x2c00000u};

static void fresh(struct npu_cold_packet_state *s)
{
    memset(s, 0, sizeof(*s));
    assert(npu_cold_packet_init(s, &plan, 1) == NPU_COLD_PACKET_OK);
}

int main(void)
{
    struct npu_cold_packet_state *s = calloc(1, sizeof(*s)), before;
    uint16_t *ids = calloc(NPU_COLD_PACKET_IDS, sizeof(*ids)), head = 0, tail = 0;
    struct npu_cold_packet_queue queue = {&head, &tail, ids, NPU_COLD_PACKET_IDS};
    struct npu_cold_packet_queue_result result;

    assert(s && ids);
    for (unsigned i = 0; i < NPU_COLD_PACKET_IDS; i++)
        ids[i] = i;
    fresh(s);
    for (unsigned i = 0; i < 2560; i++) {
        result = npu_cold_packet_queue_take(s, &plan, 1, &queue);
        assert(result.packet.status == NPU_COLD_PACKET_OK && result.packet.committed && result.published);
        assert(result.packet.id == i && result.packet.address == plan.packet_base + i * 2048);
        assert(head == i + 1 && s->head == head && s->count == head);
    }
    before = *s;
    assert(npu_cold_packet_init(s, &plan, 2) == NPU_COLD_PACKET_REINITIALIZE);
    assert(!memcmp(s, &before, sizeof(*s)));
    npu_cold_packet_fault(s);
    result = npu_cold_packet_queue_take(s, &plan, 1, &queue);
    assert(result.packet.status == NPU_COLD_PACKET_FAULT && !result.packet.committed && !result.published);
    assert(s->count == before.count && !memcmp(s->claimed, before.claimed, sizeof(s->claimed)));
    for (unsigned scenario = 0; scenario < 9; scenario++) {
        fresh(s);
        head = tail = 0;
        ids[0] = 0;
        queue.capacity = NPU_COLD_PACKET_IDS;
        unsigned expected = NPU_COLD_PACKET_CORRUPT;
        switch (scenario) {
        case 0: tail = 1; expected = NPU_COLD_PACKET_EMPTY; break;
        case 1: head = NPU_COLD_PACKET_IDS; break;
        case 2: tail = NPU_COLD_PACKET_IDS; break;
        case 3: ids[0] = NPU_COLD_PACKET_IDS; expected = NPU_COLD_PACKET_ID; break;
        case 4: ids[0] = UINT16_MAX; expected = NPU_COLD_PACKET_ID; break;
        case 5: queue.capacity--; break;
        case 6: s->head = head = 17; break;
        case 7: s->count = 1; break;
        case 8: s->claimed[0] = 1; break;
        }
        before = *s;
        uint16_t saved = head;
        result = npu_cold_packet_queue_take(s, &plan, 1, &queue);
        assert(result.packet.status == expected && !result.packet.committed && !result.published);
        assert(head == saved && s->count == before.count && s->fault == 1);
        assert(!memcmp(s->claimed, before.claimed, sizeof(s->claimed)));
    }
    fresh(s);
    head = tail = 0;
    ids[0] = 0;
    queue.capacity = NPU_COLD_PACKET_IDS;
    result = npu_cold_packet_queue_take(s, &plan, 1, &queue);
    assert(result.packet.status == NPU_COLD_PACKET_OK);
    ids[1] = 0;
    result = npu_cold_packet_queue_take(s, &plan, 1, &queue);
    assert(result.packet.status == NPU_COLD_PACKET_DUPLICATE && head == 1 && s->count == 1);
    before = *s;
    result = npu_cold_packet_queue_take(s, &plan, 2, &queue);
    assert(result.packet.status == NPU_COLD_PACKET_FAULT);
    assert(!memcmp(s, &before, sizeof(*s)));
    free(ids);
    free(s);
    puts("PASS cold-packet sanitizer retained claims and queue publication");
    return 0;
}
