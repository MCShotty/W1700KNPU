/* Logical test data; prior owners are built through their portable APIs. */
#include "cold-inode.h"

extern struct npu_cold_pcie_tail_state npu_test_tail_state;
extern struct npu_cold_pcie_tail_plan npu_test_tail_plan;
extern uint32_t npu_test_txdone_ready;
extern struct npu_cold_tx_state npu_test_tail_tx;
extern struct npu_cold_rx_pcie_state npu_test_pcie_state;
extern struct npu_cold_txdone_state npu_test_txdone_state;
extern struct npu_cold_rx_event_state npu_test_txdone_rx;
extern uint32_t npu_test_tail_live(void);
extern struct npu_cold_pcie_tail_context npu_test_tail_context(void);

static void clear(void *target, uint32_t bytes)
{
    volatile unsigned char *p = target;

    for (uint32_t i = 0; i < bytes; i++) p[i] = 0;
}

static void copy(void *target, const void *source, uint32_t bytes)
{
    volatile unsigned char *to = target;
    const volatile unsigned char *from = source;

    for (uint32_t i = 0; i < bytes; i++) to[i] = from[i];
}

struct npu_cold_inode_state npu_test_inode_state;
struct npu_cold_inode_plan npu_test_inode_plan;
uint32_t npu_test_inode_window[2048], npu_test_inode_metadata[3];
uint8_t npu_test_inode_flags[36];
uint32_t npu_test_inode_events[NPU_COLD_INODE_STORES * 3], npu_test_inode_effects;
uint32_t npu_test_inode_reads, npu_test_inode_read_failure;
uint32_t npu_test_inode_mutation, npu_test_inode_mutated;
static uint32_t inode_cookie = 0x31434e49;

static int inode_read(void *opaque, uint32_t address, uint32_t bytes, uint32_t *value)
{
    const volatile uint8_t *source;

    if (opaque != &inode_cookie || !value || address == npu_test_inode_read_failure ||
        (bytes != 1 && bytes != 4) || (address & (bytes - 1))) return 0;
    npu_test_inode_reads++;
    if (address == 0x8401cfb8 && bytes == 4) {
        *value = npu_test_inode_metadata[0];
        if (npu_test_inode_mutation && !npu_test_inode_mutated) {
            if (npu_test_inode_mutation == 1) npu_test_inode_state.fault = 1;
            if (npu_test_inode_mutation == 2) npu_test_inode_state.published++;
            if (npu_test_inode_mutation == 3) npu_test_tail_state.fault = 1;
            if (npu_test_inode_mutation == 4) npu_test_tail_state.before[0] ^= 1;
            if (npu_test_inode_mutation == 5) npu_test_tail_tx.fault = 1;
            if (npu_test_inode_mutation == 6) npu_test_pcie_state.fault = 1;
            if (npu_test_inode_mutation == 7) npu_test_txdone_state.fault = 1;
            if (npu_test_inode_mutation == 8) npu_test_txdone_rx.fault = 1;
            npu_test_inode_mutated = 1;
        }
        return 1;
    }
    if (address == 0x8401cfbc && bytes == 4) { *value = npu_test_inode_metadata[1]; return 1; }
    if (address == 0x3e902ac0 && bytes == 4) { *value = npu_test_inode_metadata[2]; return 1; }
    if (address >= NPU_COLD_INODE_ICV && address - NPU_COLD_INODE_ICV < NPU_COLD_INODE_ICV_BYTES &&
        bytes == 4 && bytes <= NPU_COLD_INODE_ICV_BYTES - (address - NPU_COLD_INODE_ICV))
        source = (const volatile uint8_t *)npu_test_inode_window + (address - 0x3e8bc000u);
    else if (address >= 0x3e9046e0u && address - 0x3e9046e0u < sizeof(npu_test_inode_flags) &&
             bytes <= sizeof(npu_test_inode_flags) - (address - 0x3e9046e0u))
        source = npu_test_inode_flags + (address - 0x3e9046e0u);
    else return 0;
    *value = 0;
    for (uint32_t i = 0; i < bytes; i++) *value |= (uint32_t)source[i] << (i * 8);
    return 1;
}

static struct npu_cold_inode_context inode_context(void)
{
    struct npu_cold_inode_context c = {.pcie = &npu_test_tail_state,
        .prior = npu_test_tail_context(), .read = inode_read, .opaque = &inode_cookie};
    npu_test_inode_reads = npu_test_inode_mutated = 0;
    return c;
}

uint32_t npu_test_inode_prepare(uint32_t hif2)
{
    if (hif2 > 1 || npu_test_tail_plan.tx.host2 != 0x200d4450u + hif2 * 0x4000u ||
        !npu_test_tail_live()) return 1;
    copy(&npu_test_inode_plan.prior, &npu_test_tail_plan, sizeof(npu_test_tail_plan));
    npu_test_inode_plan.icv = NPU_COLD_INODE_ICV;
    npu_test_inode_plan.icv_bytes = NPU_COLD_INODE_ICV_BYTES;
    clear(&npu_test_inode_state, sizeof(npu_test_inode_state));
    clear(npu_test_inode_events, sizeof(npu_test_inode_events));
    for (uint32_t i = 0; i < 2048; i++) npu_test_inode_window[i] = 0x96969696;
    for (uint32_t i = 0; i < sizeof(npu_test_inode_flags); i++) npu_test_inode_flags[i] = 0xa5;
    npu_test_inode_flags[0x1a] = npu_test_txdone_ready & 255;
    npu_test_inode_metadata[0] = 0x109;
    npu_test_inode_metadata[1] = npu_test_inode_metadata[2] = NPU_COLD_INODE_ICV;
    npu_test_inode_effects = npu_test_inode_reads = npu_test_inode_read_failure = 0;
    npu_test_inode_mutation = npu_test_inode_mutated = 0;
    return 0;
}

uint32_t npu_test_inode_begin(uint32_t selector, uint32_t value, uint32_t epoch)
{
    struct npu_cold_inode_context c = inode_context();
    return npu_cold_inode_begin(&npu_test_inode_state, &npu_test_inode_plan, epoch, &c, selector, value);
}

uint32_t npu_test_inode_effect(uint32_t index)
{
    struct npu_cold_inode_store store;
    volatile uint8_t *target;

    if (npu_cold_inode_recipe(&npu_test_inode_plan, index, &store) ||
        npu_test_inode_effects >= NPU_COLD_INODE_STORES) return 1;
    if (store.address >= NPU_COLD_INODE_ICV && store.address - NPU_COLD_INODE_ICV < NPU_COLD_INODE_ICV_BYTES)
        target = (volatile uint8_t *)npu_test_inode_window + (store.address - 0x3e8bc000u);
    else target = npu_test_inode_flags + (store.address - 0x3e9046e0u);
    for (uint32_t i = 0; i < store.bytes; i++) target[i] = store.value >> (i * 8);
    npu_test_inode_events[npu_test_inode_effects * 3] = store.address;
    npu_test_inode_events[npu_test_inode_effects * 3 + 1] = store.bytes;
    npu_test_inode_events[npu_test_inode_effects * 3 + 2] = store.value;
    npu_test_inode_effects++;
    return 0;
}

uint32_t npu_test_inode_reserve(uint32_t address, uint32_t bytes, uint32_t value, uint32_t before)
{
    struct npu_cold_inode_context c = inode_context();
    return npu_cold_inode_reserve(&npu_test_inode_state, &npu_test_inode_plan, 1, &c, address, bytes, value, before);
}

uint32_t npu_test_inode_publish(uint32_t address, uint32_t bytes, uint32_t value)
{
    struct npu_cold_inode_context c = inode_context();
    return npu_cold_inode_publish(&npu_test_inode_state, &npu_test_inode_plan, 1, &c, address, bytes, value);
}

uint32_t npu_test_inode_run(uint32_t count, uint32_t stop)
{
    struct npu_cold_inode_context c = inode_context();
    struct npu_cold_inode_store store;
    uint32_t before;

    if (!count || count > 16 || stop > 2) return 1;
    for (uint32_t i = 0; i < count; i++) {
        uint32_t index = npu_test_inode_state.committed;
        if (npu_cold_inode_recipe(&npu_test_inode_plan, index, &store) ||
            !inode_read(&inode_cookie, store.address, store.bytes, &before) ||
            npu_cold_inode_reserve(&npu_test_inode_state, &npu_test_inode_plan, 1, &c,
                store.address, store.bytes, store.value, before)) return 2;
        if (stop == 1) return 3;
        if (npu_test_inode_effect(index)) return 4;
        if (stop == 2) return 5;
        if (npu_cold_inode_publish(&npu_test_inode_state, &npu_test_inode_plan, 1, &c,
                store.address, store.bytes, store.value)) return 6;
    }
    return 0;
}

uint32_t npu_test_inode_finish(void)
{
    struct npu_cold_inode_context c = inode_context();
    return npu_cold_inode_finish(&npu_test_inode_state, &npu_test_inode_plan, 1, &c);
}

uint32_t npu_test_inode_live(void)
{
    struct npu_cold_inode_context c = inode_context();
    return npu_cold_inode_live(&npu_test_inode_state, &npu_test_inode_plan, 1, &c);
}

uint32_t npu_test_inode_stage_live(uint32_t stage)
{
    struct npu_cold_inode_context c = inode_context();
    return npu_cold_inode_stage_live(&npu_test_inode_state, &npu_test_inode_plan, 1, &c, stage);
}
