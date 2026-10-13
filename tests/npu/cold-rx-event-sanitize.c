#include <assert.h>
#include <string.h>
#include "cold-rx-event.h"

int main(void)
{
    struct npu_cold_rx_event_plan plan = {.prior = {
        .arena = 0x3e810000, .endpoint_base = 0x20000000, .endpoint_bytes = 0x100000,
        .host = {0x96000000, 0x96100000, 0x96200000, 0x96300000, 0x96400000, 0x96500000},
        .mailbox = {0x83000000, 0x83100000, 0x83200000, 0x83300000,
                    0x83400000, 0x83500000, 0x83600000, 0x83700000},
        .boot.region = {{0x84000000, 0xa00000}, {0x90c00000, 0xe000},
                        {0x8a000000, 0x2c00000}, {0x8cc00000, 0x4000000},
                        {0x90c0e000, 0x200000}, {0x83000000, 256}}
    }};
    struct npu_cold_rx_event_state state;
    for (unsigned alias = 0; alias < 3; alias++) {
        plan.ring = 0x17000000 + alias * 0x40000000;
        uint32_t expected = npu_cold_rx_event_value(plan.ring);
        memset(&state, 0, sizeof(state));
        assert(!npu_cold_rx_event_begin(&state, &plan, 1, 0xdeadbeef));
        assert(npu_cold_rx_event_reserve(&state, &plan, 1, 0xdead0000, 4, expected, 0xdeadbeef));
        assert(state.fault && !state.committed && !state.published);
        memset(&state, 0, sizeof(state));
        assert(!npu_cold_rx_event_begin(&state, &plan, 1, 0xdeadbeef));
        assert(!npu_cold_rx_event_reserve(&state, &plan, 1, NPU_COLD_RX_EVENT_METADATA, 4, expected, 0xdeadbeef));
        assert(state.reserved == 1 && state.committed == 1 && !state.published);
        assert(npu_cold_rx_event_publish(&state, &plan, 1, NPU_COLD_RX_EVENT_METADATA, 4, expected ^ 1));
        assert(state.active && state.fault && state.committed == 1 && !state.published);
        memset(&state, 0, sizeof(state));
        assert(!npu_cold_rx_event_begin(&state, &plan, 1, 0xdeadbeef));
        assert(!npu_cold_rx_event_reserve(&state, &plan, 1, NPU_COLD_RX_EVENT_METADATA, 4, expected, 0xdeadbeef));
        assert(!npu_cold_rx_event_publish(&state, &plan, 1, NPU_COLD_RX_EVENT_METADATA, 4, expected));
        assert(!npu_cold_rx_event_finish(&state, &plan, 1, expected));
        assert(npu_cold_rx_event_live(&state, &plan, 1, expected));
        assert(npu_cold_rx_event_begin(&state, &plan, 1, 0));
        assert(state.fault && state.committed == 1 && state.published == 1);
    }
    assert(npu_cold_rx_event_begin(NULL, &plan, 1, 0));
    return 0;
}
