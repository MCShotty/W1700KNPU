/* Guarded original RX statistics/initializer composition; no physical proof. */
#include "allocator.h"
#include "bootstrap.h"

extern uint32_t npu_emulation_callback_guarded;
extern uint32_t npu_emulation_callback_lifetime(void);
extern struct npu_barrier npu_emulation_barrier_state;
extern struct npu_admission npu_emulation_admission_state;
extern uint32_t npu_emulation_page_callback(const struct npu_bootstrap_packet *);
extern uint32_t npu_original_rx_dispatch(uint32_t count, uint32_t selector);

static uint32_t word(uint32_t address)
{
    return *(const volatile uint32_t *)(uintptr_t)address;
}

static void fail(void)
{
    npu_admission_fail(&npu_emulation_admission_state, &npu_emulation_barrier_state);
}

uint32_t npu_emulation_rx_stats_valid(uint32_t address, uint32_t type)
{
    const struct npu_allocator_state *state = (const void *)(uintptr_t)0x3e901bccu;
    uint32_t i;

    if (!npu_emulation_callback_lifetime() || (type != 9 && type != 10) ||
        !address || (address & 31) || address < 0x3e800000u ||
        address > 0x3e878000u - 1000 || state->count > NPU_ALLOCATOR_ENTRIES)
        goto fault;
    for (i = 0; i < state->count; i++)
        if (state->entries[i].type == type && !state->entries[i].reserved &&
            state->entries[i].address == address)
            return 1;
fault:
    fail();
    return 0;
}

uint32_t npu_emulation_rx_dispatch_live(uint32_t selector)
{
    uint32_t type = selector ? 9 : 10;

    return npu_emulation_rx_stats_valid(word(selector ? 0x3e901f18u : 0x3e901f04u), type);
}

uint32_t npu_emulation_rx_stats_callback(const struct npu_bootstrap_packet *packet)
{
    struct npu_bootstrap_packet snapshot;
    uint32_t selector = packet->header & 15, status, result = 0, ready;

    if (selector != 0 && selector != 2)
        return npu_emulation_page_callback(packet);
    __asm__ volatile ("csrrci %0, mstatus, 8" : "=r"(status) :: "memory");
    snapshot = *packet;
    ready = selector ? 0x3e904588u : 0x3e902a84u;
    if (snapshot.header != (0x10u | selector) || snapshot.api != 1 || !snapshot.value ||
        snapshot.value > (selector ? 1024u : 1536u) || npu_emulation_callback_guarded ||
        !npu_emulation_callback_lifetime() || word(ready)) {
        fail();
        goto done;
    }
    npu_emulation_callback_guarded = 1;
    result = !npu_original_rx_dispatch(snapshot.value, selector);
    if (!result || !npu_emulation_rx_dispatch_live(selector) || word(ready) != 1) {
        fail();
        *(volatile uint32_t *)(uintptr_t)ready = 0;
        result = 0;
    }
    npu_emulation_callback_guarded = 0;
done:
    __asm__ volatile ("csrw mstatus, %0" :: "r"(status) : "memory");
    return result;
}
