#include "cold-tx.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static struct npu_cold_tx_state state;
static struct npu_cold_tx_plan plan;
static unsigned cases;

static void fresh(void)
{
    memset(&state, 0, sizeof(state));
    plan = (struct npu_cold_tx_plan){.arena = 0x3e800000,
        .arena_bytes = 303168, .endpoint_base = 0x20000000, .endpoint_bytes = 0x100000,
        .host0 = 0x200d4420, .register_before = {11, 22, 33, 44}, .token_before = 16384};
    cases++;
}

static void event(unsigned stage, unsigned offset, uint32_t *address, uint32_t *value,
                  uint32_t *bytes, uint32_t *before)
{
    *bytes = 4;
    *before = 0;
    if (stage == 2) {
        *address = 0x3e900bc0; *value = 8192; *before = plan.token_before;
    } else if (!offset) {
        *address = stage ? 0x3e9046fc : 0x3e904700;
        *value = stage ? plan.host2 : plan.host0;
    } else if (offset <= 2) {
        *address = offset == 1 ? 0x3e903978 : 0x3e9021f4;
        *bytes = 2; *value = 0;
    } else {
        *address = (stage ? 0x1fc48030 : 0x1fc08030) + 4 * (offset - 3);
        unsigned delta[2][2] = {{0, 0x22020}, {0x22020, 0x4a040}};
        *value = (plan.arena + delta[stage][offset - 3]) & 0x1fffffff;
        *before = plan.register_before[stage * 2 + offset - 3];
    }
}

static void entries(unsigned stage, uint32_t *readback)
{
    for (unsigned i = 0; i < (stage == 2 ? 1u : 5u); i++) {
        uint32_t address, value, bytes, before;
        event(stage, i, &address, &value, &bytes, &before);
        assert(!npu_cold_tx_reserve(&state, &plan, 1, address, value, bytes, before));
        assert(state.committed == state.published + 1);
        assert(!npu_cold_tx_publish(&state, &plan, 1, address, bytes, value));
        readback[i] = value;
    }
}

int main(void)
{
    fresh();
    for (unsigned stage = 0; stage < 3; stage++) {
        uint32_t readback[5];
        if (stage == 1) plan.host2 = 0x200d8450;
        assert(!npu_cold_tx_begin(&state, &plan, 1, stage));
        entries(stage, readback);
        assert(!npu_cold_tx_finish(&state, &plan, 1, readback));
    }
    assert(state.reserved == 7 && state.completed == 7 && state.committed == 11 && state.published == 11);
    assert(npu_cold_tx_begin(&state, &plan, 1, 0) && state.completed == 7 && state.committed == 11);
    for (unsigned field = 0; field < 20; field++) {
        fresh(); ((uint32_t *)&state)[field] = 1;
        struct npu_cold_tx_state previous = state;
        assert(npu_cold_tx_begin(&state, &plan, 1, 0));
        if (field) assert(!memcmp(&state, &previous, sizeof(state)));
    }
    for (unsigned mode = 0; mode < 7; mode++) {
        fresh();
        assert(!npu_cold_tx_begin(&state, &plan, 1, 0));
        assert(!npu_cold_tx_reserve(&state, &plan, 1, 0x3e904700, plan.host0, 4, 0));
        uint32_t status;
        if (mode == 0) status = npu_cold_tx_reserve(&state, &plan, 1, 0x3e903978, 0, 2, 0);
        else if (mode == 1) status = npu_cold_tx_publish(&state, &plan, 1, 0x3e904700, 4, 0);
        else if (mode == 2) { plan.register_before[3]++; status = npu_cold_tx_publish(&state, &plan, 1, 0x3e904700, 4, plan.host0); }
        else if (mode == 3) { npu_cold_tx_fault(&state); status = npu_cold_tx_publish(&state, &plan, 1, 0x3e904700, 4, plan.host0); }
        else if (mode == 4) status = npu_cold_tx_publish(&state, &plan, 1, 0x3e904704, 4, plan.host0);
        else if (mode == 5) status = npu_cold_tx_publish(&state, &plan, 1, 0x3e904700, 2, plan.host0);
        else status = npu_cold_tx_finish(&state, &plan, 1, (const uint32_t[]){plan.host0, 0, 0, 0, 0});
        assert(status && state.fault && state.active && state.reserved == 1 && !state.completed);
        assert(state.committed == 1 && !state.published);
    }
    fresh(); assert(!npu_cold_tx_begin(&state, &plan, 1, 0));
    assert(npu_cold_tx_reserve(&state, &plan, 1, 0x3e904700, plan.host0, 4, 1) && !state.committed);
    fresh(); assert(!npu_cold_tx_begin(&state, &plan, 1, 0));
    uint32_t readback[5]; entries(0, readback); readback[0]++;
    assert(npu_cold_tx_finish(&state, &plan, 1, readback) && state.committed == 5 && !state.completed);
    fresh(); assert(!npu_cold_tx_begin(&state, &plan, 1, 0)); entries(0, readback);
    assert(!npu_cold_tx_finish(&state, &plan, 1, readback)); plan.host2 = 0x200d4454;
    assert(npu_cold_tx_begin(&state, &plan, 1, 1) && state.reserved == 1 && state.committed == 5);
    fresh(); assert(npu_cold_tx_begin(NULL, &plan, 1, 0) == NPU_COLD_TX_ARGUMENT);
    assert(npu_cold_tx_begin(&state, NULL, 1, 0) == NPU_COLD_TX_PLAN);
    printf("{\"passed\":true,\"cases\":%u}\n", cases);
}
