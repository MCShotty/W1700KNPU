/* Original DESC10 binding; physical exclusion, DMA visibility and drains stay external. */
#include "allocator.h"
#include "cold-setup.h"
#include "cold-txdone.h"

extern struct npu_cold_setup npu_emulation_cold_setup_state;
extern struct npu_admission npu_emulation_admission_state;
extern struct npu_barrier npu_emulation_barrier_state;
extern struct npu_cold_packet_state npu_emulation_packet_state;
extern struct npu_cold_packet_plan npu_emulation_packet_plan;
extern struct npu_cold_packet_queue_result npu_emulation_packet_last;
extern struct npu_cold_rx_event_state npu_emulation_rx_event_state;
extern uint32_t npu_emulation_callback_guarded;
extern uint32_t npu_emulation_packet_callback(const struct npu_bootstrap_packet *);
extern uint32_t npu_emulation_packet_take(uint32_t acquired);
extern uint32_t npu_emulation_packet_live(void);
extern int npu_emulation_txdone_skb_valid(void);
extern int npu_emulation_rx_event_prior_live(uint32_t packets, uint32_t full);
extern int npu_emulation_rx_event_prior_live_done(uint32_t packets);

struct npu_cold_txdone_state npu_emulation_desc10_state;
uint32_t npu_emulation_desc10_running;
static struct npu_cold_txdone_plan plan;
static uint32_t held_setup[sizeof(struct npu_cold_setup) / 4];
static uint32_t metadata[sizeof(struct npu_allocator_state) / 4];
static uint32_t occupied[NPU_COLD_TXDONE_OCCUPIED];

#define OWNER (&npu_emulation_desc10_state)
#define SETUP (&npu_emulation_cold_setup_state)
#define PKT (&npu_emulation_packet_state)
#define RX (&npu_emulation_rx_event_state)

static uint32_t word(uint32_t address)
{
    return *(const volatile uint32_t *)(uintptr_t)address;
}

static uint32_t read(uint32_t address, uint32_t bytes)
{
    if (bytes == 1)
        return *(const volatile uint8_t *)(uintptr_t)address;
    if (bytes == 2)
        return *(const volatile uint16_t *)(uintptr_t)address;
    return word(address);
}

static uint32_t fail(void)
{
    npu_cold_txdone_fault(OWNER);
    npu_admission_fail(&npu_emulation_admission_state, &npu_emulation_barrier_state);
    return 0;
}

static int typed_pool(const volatile struct npu_allocator_state *state,
                      uint32_t type, uint32_t pool, uint32_t bytes)
{
    uint32_t i, found = 0;

    if (!state || !bytes || bytes > 0x78000u || (pool & 31) ||
        pool < 0x3e800000u || pool - 0x3e800000u > 0x78000u - bytes ||
        state->count > NPU_ALLOCATOR_ENTRIES)
        return 0;
    for (i = 0; i < state->count; i++) {
        const volatile struct npu_allocator_entry *entry = &state->entries[i];

        if (entry->type != type && entry->address != pool)
            continue;
        if (found || entry->type != type || entry->reserved || entry->address != pool)
            return 0;
        found = 1;
    }
    return found;
}

static int allocations_live(void)
{
    const volatile uint32_t *current = (const volatile void *)(uintptr_t)0x3e901bccu;
    const volatile struct npu_allocator_state *allocator = (const volatile void *)current;
    uint32_t i;

    if (word(0x3e90017cu) != 0x8400fe34u ||
        word(0x8401cfa8u) != 0x107 || word(0x8401cfacu) != NPU_COLD_TXDONE_IDS_POOL ||
        word(0x8401cfb0u) != 0x108 || word(0x8401cfb4u) != NPU_COLD_TXDONE_IDS_POOL + 2048 ||
        word(0x3e901b88u) != plan.packet_pool || word(0x3e901bc0u) != plan.temporary ||
        word(0x3e901b84u) != plan.skb_queue || word(0x3e900bc0u) != NPU_COLD_TXDONE_CAPACITY ||
        word(0x3e901b9cu) != 28 || word(0x3e901bb8u) != 19 || word(0x3e901bc4u) != 20 ||
        word(0x8401b224u) != 0x8a || word(0x8401b228u) != 32768 ||
        word(0x8401d028u) != 0x12 || word(0x8401d02cu) != 57344 ||
        word(0x8401d048u) != 0x1d || word(0x8401d04cu) != 4096 ||
        !typed_pool(allocator, 0x8a, plan.packet_pool, 32768) ||
        !typed_pool(allocator, 0x12, plan.skb_queue, 57344) ||
        !typed_pool(allocator, 0x1d, plan.temporary, 4096) ||
        !npu_cold_txdone_plan_valid(&plan))
        return 0;
    for (i = 0; i < sizeof(metadata) / 4; i++)
        if (current[i] != metadata[i])
            return 0;
    return 1;
}

static int packet_plan_live(void)
{
    const volatile struct npu_cold_packet_plan *current = &npu_emulation_packet_plan;

    return current->packet_base == plan.prior.prior.boot.region[NPU_BOOT_PKT].base &&
           current->packet_bytes == plan.prior.prior.boot.region[NPU_BOOT_PKT].bytes;
}

static int context(uint32_t full)
{
    const volatile uint32_t *setup = (const volatile void *)SETUP;
    uint32_t i, status, packets = NPU_COLD_TXDONE_PREFIX + OWNER->claims_committed;

    __asm__ volatile ("csrr %0, mstatus" : "=r"(status));
    if (status & 8 || !npu_emulation_desc10_running ||
        SETUP->failed || SETUP->inflight != 1 ||
        SETUP->command.header != 0x1a || SETUP->command.api != 1 || SETUP->command.value != 512 ||
        SETUP->rx_event_steps != 1 || SETUP->prior_rx_event_steps != 1 ||
        !packet_plan_live() || !allocations_live() ||
        !npu_emulation_rx_event_prior_live(packets, full))
        return 0;
    for (i = 0; i < sizeof(held_setup) / 4; i++)
        if (setup[i] != held_setup[i])
            return 0;
    return (!OWNER->magic || npu_cold_txdone_packets_live(OWNER, &plan, 1, PKT)) &&
           packet_plan_live();
}

int npu_emulation_desc10_read(void *opaque, uint32_t address, uint32_t bytes, uint32_t *value)
{
    const uint32_t bases[] = {npu_cold_rx_event_value(plan.prior.ring), plan.ids_pool,
        plan.temporary, npu_cold_rx_event_value(plan.prior.prior.boot.region[NPU_BOOT_TXCHECK].base),
        plan.skb_queue, 0x3e902a7c, 0x3e902cf4, 0x3e901bb4, 0x3e901b94, 0x3e903974, 0x3e9046fa};
    const uint32_t sizes[] = {8192, 1024, 4096, 16384, 16384, 2, 4, 2, 2, 4, 1};
    uint32_t i;

    if (opaque != OWNER || !value || (bytes != 1 && bytes != 2 && bytes != 4) ||
        (address & (bytes - 1)) || !npu_cold_txdone_plan_valid(&plan))
        return 0;
    for (i = 0; i < sizeof(bases) / 4; i++) {
        if (address >= bases[i] && address - bases[i] < sizes[i] &&
            bytes <= sizes[i] - (address - bases[i])) {
            *value = read(address, bytes);
            return 1;
        }
    }
    return 0;
}

int npu_emulation_desc10_prior_live(const struct npu_cold_txdone_plan *candidate)
{
    const struct npu_cold_setup *prior = (const void *)held_setup;
    const volatile uint32_t *setup = (const volatile void *)SETUP;
    uint32_t i, status, packets = NPU_COLD_TXDONE_PREFIX + OWNER->claims_committed;

    __asm__ volatile ("csrr %0, mstatus" : "=r"(status));
    if (status & 8 || npu_emulation_desc10_running || npu_emulation_callback_guarded ||
        SETUP->failed || SETUP->inflight != 1 || SETUP->sequence <= prior->sequence ||
        !npu_cold_rx_pcie_command(&SETUP->command) ||
        SETUP->command.value != plan.prior.prior.endpoint_base + NPU_COLD_RX_PCIE_REGISTER ||
        SETUP->rx_event_steps != 2 || SETUP->prior_rx_event_steps != 2 ||
        prior->command.header != 0x1a || prior->command.api != 1 || prior->command.value != 512 ||
        prior->rx_event_steps != 1 || prior->prior_rx_event_steps != 1 ||
        !npu_cold_txdone_plan_equal(candidate, &plan) || !packet_plan_live() ||
        !allocations_live() ||
        !npu_cold_txdone_live(OWNER, &plan, 1, RX, word(NPU_COLD_RX_EVENT_METADATA),
                                PKT, read(0x3e9046fa, 1)))
        return 0;
    for (i = 0; i < sizeof(held_setup) / 4; i++) {
        if (i == __builtin_offsetof(struct npu_cold_setup, sequence) / 4 ||
            (i >= __builtin_offsetof(struct npu_cold_setup, command) / 4 &&
             i < (__builtin_offsetof(struct npu_cold_setup, command) + sizeof(SETUP->command)) / 4) ||
            i == __builtin_offsetof(struct npu_cold_setup, rx_event_steps) / 4 ||
            i == __builtin_offsetof(struct npu_cold_setup, prior_rx_event_steps) / 4)
            continue;
        if (setup[i] != held_setup[i])
            return 0;
    }
    return npu_emulation_rx_event_prior_live_done(packets) &&
           npu_cold_txdone_memory_live(OWNER, &plan, 1, RX,
               word(NPU_COLD_RX_EVENT_METADATA), PKT, read(0x3e9046fa, 1),
               npu_emulation_desc10_read, OWNER) && packet_plan_live();
}

uint32_t npu_emulation_desc10_take(uint32_t acquired)
{
    const volatile uint32_t *last;
    uint32_t *clear = (void *)&npu_emulation_packet_last;
    uint32_t id, i, published;

    if (acquired)
        return fail(), UINT32_MAX;
    if (!npu_emulation_callback_guarded || !context(0) ||
        npu_cold_txdone_claim_reserve(OWNER, &plan, 1, PKT)) {
        static const uint32_t lock = 28;

        ((void (*)(const uint32_t *))(uintptr_t)0x8400651cu)(&lock);
        return fail(), UINT32_MAX;
    }
    /* Clear only the per-call result, never the shared ownership bitmap. */
    for (i = 0; i < sizeof(npu_emulation_packet_last) / 4; i++)
        clear[i] = 0;
    id = npu_emulation_packet_take(0);
    last = (const volatile void *)&npu_emulation_packet_last;
    published = npu_cold_txdone_claim_publish(OWNER, &plan, 1, PKT,
                                            (const void *)last);
    if (published || id == UINT32_MAX || !context(0))
        return fail(), UINT32_MAX;
    return id;
}

uint32_t npu_emulation_desc10_skb_prepare(uint32_t acquired)
{
    uint32_t band, index;

    if (acquired || !npu_emulation_callback_guarded || !context(1) ||
        !npu_emulation_txdone_skb_valid())
        return fail();
    for (band = 0; band < 2; band++) {
        uint32_t descriptors = word(0x3e901f28u + band * 4);
        uint32_t base = plan.prior.prior.boot.region[NPU_BOOT_TXPKT].base;

        for (index = 0; index < 1024; index++)
            occupied[band * 1024 + index] = (word(descriptors + index * 32 + 8) - base) / 2048;
    }
    if (npu_cold_txdone_skb_begin(OWNER, &plan, 1, RX,
        word(NPU_COLD_RX_EVENT_METADATA), PKT, occupied) || !context(0))
        return fail();
    return 1;
}

uint32_t npu_emulation_desc10_reserve(uint32_t address, uint32_t value, uint32_t bytes)
{
    struct npu_cold_txdone_store store;
    uint32_t full = address == 0x3e903974u || address == 0x3e9046fau;

    if (!npu_emulation_callback_guarded || !context(full) ||
        npu_cold_txdone_recipe(OWNER, &store) || address != store.address ||
        bytes != store.bytes)
        return fail();
    /* Native byte/halfword stores discard the register's upper bits. */
    if (bytes < 4)
        value &= bytes == 1 ? 0xffu : 0xffffu;
    if (value != store.value ||
        npu_cold_txdone_reserve(OWNER, &plan, 1, address, bytes, value, read(address, bytes)) ||
        !context(0))
        return fail();
    return 1;
}

uint32_t npu_emulation_desc10_publish(uint32_t address, uint32_t bytes)
{
    if (!npu_emulation_callback_guarded || !context(0) ||
        address != OWNER->pending_address || bytes != OWNER->pending_bytes ||
        npu_cold_txdone_publish(OWNER, &plan, 1, address, bytes, read(address, bytes)) ||
        !context(0))
        return fail();
    return 1;
}

uint32_t npu_emulation_desc10_ready(void)
{
    if (!npu_emulation_callback_guarded || !context(1) ||
        OWNER->committed != NPU_COLD_TXDONE_STORES - 2 ||
        OWNER->published != NPU_COLD_TXDONE_STORES - 2 ||
        OWNER->claims_published != 512 || OWNER->skb_reserved != 1)
        return fail();
    return 1;
}

uint32_t npu_emulation_desc10_callback(const struct npu_bootstrap_packet *packet)
{
    struct npu_bootstrap_packet snapshot;
    const volatile uint32_t *setup = (const volatile void *)SETUP;
    const volatile uint32_t *current = (const volatile void *)(uintptr_t)0x3e901bccu;
    uint32_t i, status, result = 0, entered = 0;

    if ((packet->header & 15) != 10)
        return npu_emulation_packet_callback(packet);
    __asm__ volatile ("csrrci %0, mstatus, 8" : "=r"(status) :: "memory");
    snapshot = *packet;
    if (npu_emulation_desc10_running || npu_emulation_callback_guarded ||
        snapshot.header != 0x1a || snapshot.api != 1 || snapshot.value != 512 ||
        read(0x3e9046fau, 1) || PKT->count != NPU_COLD_TXDONE_PREFIX)
        goto fault;
    npu_emulation_desc10_running = entered = 1;
    npu_cold_rx_event_plan_copy(&plan.prior, &RX->plan);
    plan.packet_pool = word(0x3e901b88u);
    plan.ids_pool = NPU_COLD_TXDONE_IDS_POOL;
    plan.temporary = word(0x3e901bc0u);
    plan.skb_queue = word(0x3e901b84u);
    for (i = 0; i < sizeof(held_setup) / 4; i++)
        held_setup[i] = setup[i];
    for (i = 0; i < sizeof(metadata) / 4; i++)
        metadata[i] = current[i];
    if (!context(1) || !npu_emulation_packet_live() ||
        npu_cold_txdone_begin(OWNER, &plan, 1, RX, word(NPU_COLD_RX_EVENT_METADATA), PKT))
        goto fault;
    result = npu_emulation_packet_callback(&snapshot);
    if (result != 1 || !context(1) ||
        npu_cold_txdone_finish(OWNER, &plan, 1, RX, word(NPU_COLD_RX_EVENT_METADATA),
                               PKT, read(0x3e9046fau, 1)))
        goto fault;
    goto done;
fault:
    result = fail();
done:
    if (entered)
        npu_emulation_desc10_running = 0;
    __asm__ volatile ("csrw mstatus, %0" :: "r"(status) : "memory");
    return result;
}
