#include "cold-page.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const struct npu_cold_page_plan plan = {0x90c0e000, 0x200000};

static void fresh(struct npu_cold_page_state *s)
{
    memset(s, 0, sizeof(*s));
    assert(npu_cold_page_init(s, &plan, 1) == NPU_COLD_PAGE_OK);
}

int main(void)
{
    struct npu_cold_page_state *s = malloc(sizeof(*s)), before;
    struct npu_cold_page_result result;
    assert(s);
    fresh(s);
    before = *s;
    assert(npu_cold_page_init(s, &plan, 2) == NPU_COLD_PAGE_REINITIALIZE);
    assert(!memcmp(s, &before, sizeof(*s)));
    for (unsigned i = 0; i < 1792; i++) {
        unsigned id = (i * 17) & 8191;
        result = npu_cold_page_take(s, &plan, 1, i, 0, id);
        assert(result.status == NPU_COLD_PAGE_OK && result.committed == 1);
        assert(result.id == id && result.address == plan.packet_base + id * 128);
        assert(result.next_head == i + 1 && s->head == i + 1 && s->count == i + 1);
        assert(s->claimed[id >> 5] & (1u << (id & 31)));
    }
    before = *s;
    npu_cold_page_fault(s);
    assert(s->fault == 1 && s->count == before.count && s->head == before.head);
    assert(!memcmp(s->claimed, before.claimed, sizeof(s->claimed)));
    result = npu_cold_page_take(s, &plan, 1, s->head, 0, 7000);
    assert(result.status == NPU_COLD_PAGE_FAULT && !result.committed);
    assert(s->count == before.count && s->head == before.head);
    assert(!memcmp(s->claimed, before.claimed, sizeof(s->claimed)));

    for (unsigned scenario = 0; scenario < 13; scenario++) {
        fresh(s);
        result = npu_cold_page_take(s, &plan, 1, 0, 0, 11);
        assert(result.status == NPU_COLD_PAGE_OK);
        unsigned epoch = 1, head = 1, tail = 0, id = 12;
        unsigned expected = NPU_COLD_PAGE_CORRUPT;
        struct npu_cold_page_plan supplied = plan;
        switch (scenario) {
        case 0: epoch = 2; expected = NPU_COLD_PAGE_STALE; break;
        case 1: head = 2; break;
        case 2: tail = 8192; break;
        case 3: tail = 2; expected = NPU_COLD_PAGE_EMPTY; break;
        case 4: id = 8192; expected = NPU_COLD_PAGE_ID; break;
        case 5: id = UINT32_MAX; expected = NPU_COLD_PAGE_ID; break;
        case 6: id = 11; expected = NPU_COLD_PAGE_DUPLICATE; break;
        case 7: s->count = 0; break;
        case 8: s->claimed[0] = 0; break;
        case 9: supplied.packet_base += 128; break;
        case 10: s->epoch = 0; break;
        case 12: s->head = head = 17; break;
        case 11: s->fault = 1; expected = NPU_COLD_PAGE_FAULT; break;
        }
        before = *s;
        result = npu_cold_page_take(s, &supplied, epoch, head, tail, id);
        assert(result.status == expected && !result.committed);
        assert(result.id == UINT32_MAX && !result.address && result.next_head == UINT32_MAX);
        assert(s->head == before.head && s->count == before.count);
        assert(!memcmp(s->claimed, before.claimed, sizeof(s->claimed)));
        assert(s->fault == (expected == NPU_COLD_PAGE_STALE ? 0u : 1u));
    }
    memset(s, 0, sizeof(*s));
    s->claimed[1] = 1;
    before = *s;
    assert(npu_cold_page_init(s, &plan, 1) == NPU_COLD_PAGE_REINITIALIZE);
    assert(!memcmp(s, &before, sizeof(*s)));
    struct npu_cold_page_plan crossing = {0xbff00000, 0x100080};
    memset(s, 0, sizeof(*s));
    assert(npu_cold_page_init(s, &crossing, 1) == NPU_COLD_PAGE_PLAN && s->fault == 1);
    assert(npu_cold_page_init(s, &plan, 1) == NPU_COLD_PAGE_REINITIALIZE);
    assert(npu_cold_page_init(NULL, &plan, 1) == NPU_COLD_PAGE_ARGUMENT);
    assert(npu_cold_page_init(s, NULL, 1) == NPU_COLD_PAGE_ARGUMENT);
    result = npu_cold_page_take(NULL, &plan, 1, 0, 0, 0);
    assert(result.status == NPU_COLD_PAGE_ARGUMENT && !result.committed);
    npu_cold_page_fault(NULL);
    uint16_t *ids = calloc(NPU_COLD_PAGE_IDS, sizeof(*ids));
    uint16_t head = 0, tail = 0;
    struct npu_cold_page_queue queue = {&head, &tail, ids, NPU_COLD_PAGE_IDS};
    struct npu_cold_page_queue_result queued;
    assert(ids);
    for (unsigned i = 0; i < NPU_COLD_PAGE_IDS; i++)
        ids[i] = i;
    fresh(s);
    for (unsigned i = 0; i < 17; i++) {
        queued = npu_cold_page_queue_take(s, &plan, 1, &queue);
        assert(queued.page.status == NPU_COLD_PAGE_OK && queued.published);
        assert(queued.page.id == i && head == i + 1 && s->count == i + 1);
    }
    before = *s;
    queue.ids = (const volatile uint16_t *)(uintptr_t)1;
    queued = npu_cold_page_queue_take(s, &plan, 2, &queue);
    assert(queued.page.status == NPU_COLD_PAGE_STALE && !queued.published);
    assert(!memcmp(s, &before, sizeof(*s)));
    queue.ids = ids;
    for (unsigned scenario = 0; scenario < 7; scenario++) {
        fresh(s);
        head = tail = 0;
        ids[0] = 0;
        queue.capacity = NPU_COLD_PAGE_IDS;
        unsigned expected = NPU_COLD_PAGE_CORRUPT;
        switch (scenario) {
        case 0: tail = 1; expected = NPU_COLD_PAGE_EMPTY; break;
        case 1: head = NPU_COLD_PAGE_IDS; break;
        case 2: tail = NPU_COLD_PAGE_IDS; break;
        case 3: ids[0] = NPU_COLD_PAGE_IDS; expected = NPU_COLD_PAGE_ID; break;
        case 4: queue.capacity--; break;
        case 5: queue.ids = NULL; break;
        case 6:
            queued = npu_cold_page_queue_take(s, &plan, 1, &queue);
            assert(queued.published);
            ids[1] = 0;
            expected = NPU_COLD_PAGE_DUPLICATE;
            break;
        }
        before = *s;
        uint16_t saved_head = head;
        queued = npu_cold_page_queue_take(s, &plan, 1, &queue);
        assert(queued.page.status == expected && !queued.page.committed && !queued.published);
        assert(head == saved_head && s->count == before.count && s->fault == 1);
        assert(!memcmp(s->claimed, before.claimed, sizeof(s->claimed)));
        queue.ids = ids;
    }
    queued = npu_cold_page_queue_take(NULL, &plan, 1, &queue);
    assert(queued.page.status == NPU_COLD_PAGE_ARGUMENT && !queued.published);
    queued = npu_cold_page_queue_take(s, NULL, 1, &queue);
    assert(queued.page.status == NPU_COLD_PAGE_ARGUMENT && !queued.published);
    queued = npu_cold_page_queue_take(s, &plan, 1, NULL);
    assert(queued.page.status == NPU_COLD_PAGE_ARGUMENT && !queued.published);
    free(ids);
    free(s);
    puts("PASS cold-page sanitizer ownership/argument/lifetime cases");
    return 0;
}
