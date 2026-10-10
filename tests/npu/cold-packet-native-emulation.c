/* Selected locked cold packet users; backing/grant/drain are platform contracts. */
#include "cold-packet.h"
#include "bootstrap.h"
#include "allocator.h"

extern uint32_t npu_emulation_callback_guarded;
extern uint32_t npu_emulation_callback_lifetime(void);
extern uint32_t npu_emulation_rx_dispatch_live(uint32_t selector);
extern uint32_t npu_emulation_rx_stats_callback(const struct npu_bootstrap_packet *);
extern uint32_t npu_previous_txdone_callback(const struct npu_bootstrap_packet *);
extern struct npu_bootstrap npu_emulation_bootstrap_state;
extern struct npu_admission npu_emulation_admission_state;
extern struct npu_barrier npu_emulation_barrier_state;

struct npu_cold_packet_state npu_emulation_packet_state;
struct npu_cold_packet_plan npu_emulation_packet_plan;
struct npu_cold_packet_queue_result npu_emulation_packet_last;
const uint32_t npu_emulation_packet_lock_id = 28;
static uint32_t pool_snapshot;

#define BOOT (&npu_emulation_bootstrap_state)
#define LOCK 0x3e901b9cu
#define HEAD 0x3e901ba4u
#define TAIL 0x3e901b80u
#define POOL 0x3e800000u

static uint32_t word(uint32_t address)
{
    return *(const volatile uint32_t *)(uintptr_t)address;
}

static uint32_t load(const uint32_t *address)
{
    return __atomic_load_n(address, __ATOMIC_ACQUIRE);
}

static void fail(void)
{
    __asm__ volatile ("csrci mstatus, 8\n fence iorw, iorw" ::: "memory");
    npu_cold_packet_fault(&npu_emulation_packet_state);
    npu_admission_fail(&npu_emulation_admission_state, &npu_emulation_barrier_state);
}

static int valid_pool(uint32_t pool)
{
    const struct npu_allocator_state *state = (const void *)(uintptr_t)0x3e901bccu;
    uint32_t i;

    if ((pool & 31) || pool < POOL || pool > POOL + 0x78000u - 32768 ||
        state->count > NPU_ALLOCATOR_ENTRIES)
        return 0;
    for (i = 0; i < state->count; i++)
        if (state->entries[i].type == 0x8a && !state->entries[i].reserved &&
            state->entries[i].address == pool)
            return 1;
    return 0;
}

static int context(void)
{
    uint32_t status, stats = word(0x3e901f08u), pool = word(0x3e901b88u);

    __asm__ volatile ("csrr %0, mstatus" : "=r"(status));
    return !(status & 8) && npu_emulation_callback_lifetime() && word(LOCK) == 28 &&
           valid_pool(pool) && (!pool_snapshot || pool == pool_snapshot) &&
           word(0x3e90396cu) == BOOT->plan.region[NPU_BOOT_PKT].base &&
           (!stats || (!(stats & 3) && stats >= POOL && stats <= POOL + 0x78000u - 112));
}

uint32_t npu_emulation_packet_begin(void)
{
    if (!npu_emulation_callback_guarded || !context() ||
        load(&npu_emulation_packet_state.magic) != NPU_COLD_PACKET_MAGIC ||
        load(&npu_emulation_packet_state.fault)) {
        fail();
        return 0;
    }
    return 1;
}

uint32_t npu_emulation_packet_init(void)
{
    const struct npu_bootstrap_range *pkt = &BOOT->plan.region[NPU_BOOT_PKT];
    const struct npu_cold_packet_plan plan = {pkt->base, pkt->bytes};
    uint32_t status;

    if (!context() || *(const volatile uint16_t *)(uintptr_t)HEAD ||
        *(const volatile uint16_t *)(uintptr_t)TAIL)
        return NPU_COLD_PACKET_CORRUPT;
    status = npu_cold_packet_init(&npu_emulation_packet_state, &plan, 1);
    if (status == NPU_COLD_PACKET_OK || status == NPU_COLD_PACKET_FAULT) {
        npu_emulation_packet_plan = plan;
        pool_snapshot = word(0x3e901b88u);
    }
    return status;
}

static void statistic(uint32_t offset)
{
    uint32_t stats = word(0x3e901f08u);

    if (stats && !(stats & 3) && stats >= POOL && stats <= POOL + 0x78000u - 112) {
        volatile uint32_t *value = (volatile uint32_t *)(uintptr_t)(stats + offset);

        *value = *value + 1;
    }
}

uint32_t npu_emulation_packet_take(uint32_t acquired)
{
    const struct npu_cold_packet_queue queue = {
        (volatile uint16_t *)(uintptr_t)HEAD,
        (const volatile uint16_t *)(uintptr_t)TAIL,
        (const volatile uint16_t *)(uintptr_t)pool_snapshot,
        NPU_COLD_PACKET_IDS
    };
    uint32_t id = UINT32_MAX;

    if (acquired) {
        fail();
        return UINT32_MAX;
    }
    if (!npu_emulation_callback_guarded || !context() ||
        npu_emulation_packet_plan.packet_base != BOOT->plan.region[NPU_BOOT_PKT].base ||
        npu_emulation_packet_plan.packet_bytes != BOOT->plan.region[NPU_BOOT_PKT].bytes)
        goto done;
    npu_emulation_packet_last = npu_cold_packet_queue_take(
        &npu_emulation_packet_state, &npu_emulation_packet_plan, 1, &queue);
    if (npu_emulation_packet_last.published) {
        volatile uint32_t *attempts = (volatile uint32_t *)(uintptr_t)0x3e901b90u;

        *attempts = *attempts + 1;
        statistic(0x1c);
    }
    if (npu_emulation_packet_last.packet.status == NPU_COLD_PACKET_OK &&
        npu_emulation_packet_last.published && context())
        id = npu_emulation_packet_last.packet.id;
    else
        statistic(0x20);
done:
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    ((void (*)(const uint32_t *))(uintptr_t)0x8400651cu)(&npu_emulation_packet_lock_id);
    if (id == UINT32_MAX || load(&npu_emulation_packet_state.fault) || !context()) {
        fail();
        return UINT32_MAX;
    }
    return id;
}

uint32_t npu_emulation_packet_live(void)
{
    const struct npu_cold_packet_state *state = &npu_emulation_packet_state;
    uint32_t i, population = 0;

    if (!context() || load(&npu_emulation_packet_state.magic) != NPU_COLD_PACKET_MAGIC ||
        load(&npu_emulation_packet_state.fault) || npu_emulation_packet_state.epoch != 1 ||
        npu_emulation_packet_state.head != *(const volatile uint16_t *)(uintptr_t)HEAD ||
        state->count > NPU_COLD_PACKET_IDS ||
        state->head != (state->count & (NPU_COLD_PACKET_IDS - 1)) ||
        state->packet_base != npu_emulation_packet_plan.packet_base ||
        state->packet_bytes != npu_emulation_packet_plan.packet_bytes ||
        state->packet_base != BOOT->plan.region[NPU_BOOT_PKT].base ||
        state->packet_bytes != BOOT->plan.region[NPU_BOOT_PKT].bytes)
        goto fault;
    for (i = 0; i < NPU_COLD_PACKET_WORDS; i++) {
        uint32_t bits = state->claimed[i];

        bits -= (bits >> 1) & 0x55555555u;
        bits = (bits & 0x33333333u) + ((bits >> 2) & 0x33333333u);
        bits = (bits + (bits >> 4)) & 0x0f0f0f0fu;
        population += (bits * 0x01010101u) >> 24;
    }
    if (population != state->count)
        goto fault;
    return 1;
fault:
    fail();
    return 0;
}

uint32_t npu_emulation_packet_ready(uint32_t selector)
{
    if (!npu_emulation_packet_live() || !npu_emulation_rx_dispatch_live(selector)) {
        fail();
        return 0;
    }
    return 1;
}

uint32_t npu_emulation_packet_txdone_ready(void)
{
    if (!npu_emulation_callback_guarded || !npu_emulation_packet_live()) {
        fail();
        return 0;
    }
    return 1;
}

uint32_t npu_emulation_packet_callback(const struct npu_bootstrap_packet *packet)
{
    struct npu_bootstrap_packet snapshot;
    volatile uint8_t *ready = (volatile uint8_t *)(uintptr_t)0x3e9046fau;
    uint32_t status, result = 0;

    if ((packet->header & 15) != 10)
        return npu_emulation_rx_stats_callback(packet);
    __asm__ volatile ("csrrci %0, mstatus, 8" : "=r"(status) :: "memory");
    snapshot = *packet;
    if (snapshot.header != 0x1a || snapshot.api != 1 || !snapshot.value ||
        snapshot.value > 512 || npu_emulation_callback_guarded || *ready ||
        !npu_emulation_packet_live()) {
        fail();
        goto done;
    }
    npu_emulation_callback_guarded = 1;
    result = npu_previous_txdone_callback(&snapshot);
    if (!result || !npu_emulation_packet_live() || *ready != 1) {
        fail();
        *ready = 0;
        result = 0;
    }
    npu_emulation_callback_guarded = 0;
done:
    __asm__ volatile ("csrw mstatus, %0" :: "r"(status) : "memory");
    return result;
}
