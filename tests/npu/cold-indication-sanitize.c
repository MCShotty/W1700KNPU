#include "cold-indication.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static struct npu_cold_indication_state state;
static const struct npu_cold_indication_plan plan = {0x3e800000, NPU_COLD_INDICATION_BYTES};
static uint32_t words[NPU_COLD_INDICATION_COUNT * 2];
static unsigned cases;

static void fresh(void)
{
    memset(&state, 0, sizeof(state));
    memset(words, 0, sizeof(words));
    cases++;
}

static void begin(void)
{
    fresh();
    assert(!npu_cold_indication_begin(&state, &plan, 1, words));
}

static void entry(unsigned index)
{
    uint32_t address = plan.base + index * 8;
    assert(!npu_cold_indication_reserve(&state, &plan, 1, address, NPU_COLD_INDICATION_STATUS, words));
    assert(state.committed == index + 1 && state.published == index);
    assert(!npu_cold_indication_pending(&state, &plan, 1, address, NPU_COLD_INDICATION_STATUS, words));
    words[index * 2 + 1] = NPU_COLD_INDICATION_STATUS;
    assert(!npu_cold_indication_publish(&state, &plan, 1, address, words));
    assert(state.committed == state.published && state.published == index + 1);
}

int main(void)
{
    begin();
    for (unsigned i = 0; i < NPU_COLD_INDICATION_COUNT; i++) entry(i);
    assert(!npu_cold_indication_finish(&state, &plan, 1, words) && !state.active);
    assert(npu_cold_indication_begin(&state, &plan, 1, words) == NPU_COLD_INDICATION_REINITIALIZE);
    for (unsigned field = 0; field < NPU_COLD_INDICATION_COUNT * 2; field++) {
        fresh(); words[field] = 1;
        assert(npu_cold_indication_begin(&state, &plan, 1, words) == NPU_COLD_INDICATION_FRESHNESS);
        assert(state.fault && !state.committed && !state.published && !state.active);
    }
    for (unsigned field = 0; field < 8; field++) {
        fresh(); ((uint32_t *)&state)[field] = 1;
        struct npu_cold_indication_state before = state;
        assert(npu_cold_indication_begin(&state, &plan, 1, words) == NPU_COLD_INDICATION_REINITIALIZE);
        assert(!memcmp(&state, &before, sizeof(state)));
    }
    const struct npu_cold_indication_plan bad[] = {
        {0, 12288}, {0x3e800001, 12288}, {0x3e877000, 12288},
        {0x3e800000, 0}, {0x3e800000, 12287}, {0x3e800000, 12289}
    };
    for (unsigned i = 0; i < sizeof(bad) / sizeof(bad[0]); i++) {
        fresh();
        assert(npu_cold_indication_begin(&state, &bad[i], 1, (const void *)(uintptr_t)1) == NPU_COLD_INDICATION_PLAN);
        assert(state.fault);
    }
    for (unsigned mode = 0; mode < 9; mode++) {
        begin();
        assert(!npu_cold_indication_reserve(&state, &plan, 1, plan.base, NPU_COLD_INDICATION_STATUS, words));
        uint32_t status;
        if (mode == 0) status = npu_cold_indication_reserve(&state, &plan, 1, plan.base + 8, NPU_COLD_INDICATION_STATUS, words);
        else if (mode == 1) status = npu_cold_indication_publish(&state, &plan, 1, plan.base, words);
        else if (mode == 2) status = npu_cold_indication_pending(&state, &plan, 1, plan.base, NPU_COLD_INDICATION_STATUS | 1, words);
        else if (mode == 3) status = npu_cold_indication_finish(&state, &plan, 1, words);
        else if (mode == 4) {
            npu_cold_indication_fault(&state);
            status = npu_cold_indication_pending(&state, &plan, 1, plan.base, NPU_COLD_INDICATION_STATUS, words);
        } else if (mode == 5) {
            state.count--;
            status = npu_cold_indication_pending(&state, &plan, 1, plan.base, NPU_COLD_INDICATION_STATUS, words);
        } else if (mode == 6) {
            words[0] = 1;
            status = npu_cold_indication_pending(&state, &plan, 1, plan.base, NPU_COLD_INDICATION_STATUS, words);
        } else if (mode == 7) {
            words[1] = NPU_COLD_INDICATION_STATUS;
            status = npu_cold_indication_publish(&state, &plan, 1, plan.base + 4, words);
        } else {
            words[1] = NPU_COLD_INDICATION_STATUS;
            npu_cold_indication_fault(&state);
            status = npu_cold_indication_publish(&state, &plan, 1, plan.base, words);
        }
        assert(status && state.fault && state.active == 1 && state.committed == 1 && !state.published);
    }
    begin();
    assert(npu_cold_indication_reserve(&state, &plan, 1, plan.base, 0, words) == NPU_COLD_INDICATION_ORDER);
    begin(); entry(0);
    for (unsigned i = 0; i < NPU_COLD_INDICATION_COUNT; i++) words[i * 2 + 1] = NPU_COLD_INDICATION_STATUS;
    assert(npu_cold_indication_finish(&state, &plan, 1, words) == NPU_COLD_INDICATION_ORDER);
    begin();
    for (unsigned i = 0; i < NPU_COLD_INDICATION_COUNT; i++) entry(i);
    words[0] = 1;
    assert(npu_cold_indication_finish(&state, &plan, 1, words) == NPU_COLD_INDICATION_PUBLISH);
    assert(state.active == 1 && state.committed == 1536 && state.published == 1536);
    fresh();
    assert(npu_cold_indication_begin(NULL, &plan, 1, words) == NPU_COLD_INDICATION_ARGUMENT);
    assert(npu_cold_indication_begin(&state, NULL, 1, words) == NPU_COLD_INDICATION_PLAN);
    npu_cold_indication_fault(NULL);
    printf("{\"passed\":true,\"cases\":%u,\"fresh_word_controls\":3072}\n", cases);
    return 0;
}
