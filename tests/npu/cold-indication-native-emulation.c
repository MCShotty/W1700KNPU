/* Guarded native indication initialization; physical contracts remain external. */
#include "allocator.h"
#include "cold-indication.h"
#include "cold-setup.h"

extern struct npu_bootstrap npu_emulation_bootstrap_state;
extern struct npu_admission npu_emulation_admission_state;
extern struct npu_barrier npu_emulation_barrier_state;
extern struct npu_cold_setup npu_emulation_cold_setup_state;
extern uint32_t npu_original_page_dispatch(uint32_t count, uint32_t selector);
extern int npu_emulation_cold_arena_live(void);

struct npu_cold_indication_state npu_emulation_indication_state;
struct npu_cold_indication_plan npu_emulation_indication_plan;
static uint32_t arena, record_index, allocation_count, allocation_used;
static uint32_t identity[5];
static uint32_t lock_owned;
static const uint32_t lock_id = 18;

#define SETUP (&npu_emulation_cold_setup_state)
#define OWNER (&npu_emulation_indication_state)
#define PLAN (&npu_emulation_indication_plan)
#define METADATA ((const struct npu_allocator_state *)(uintptr_t)0x3e901bccu)

static uint32_t word(uint32_t address)
{
    return *(const volatile uint32_t *)(uintptr_t)address;
}

static uint32_t fail(void)
{
    npu_cold_indication_fault(OWNER);
    npu_admission_fail(&npu_emulation_admission_state, &npu_emulation_barrier_state);
    return 0;
}

static int context(void)
{
    static const uint32_t limits[NPU_COLD_COUNTS] = {1536, 1024, 256, 512, 1024};
    uint32_t i;

    if (!npu_emulation_cold_arena_live() || SETUP->failed || SETUP->inflight != 1 ||
        SETUP->completed != 4095 || SETUP->command.header != 0x18 ||
        SETUP->command.api != 1 || SETUP->command.value != NPU_COLD_INDICATION_COUNT ||
        SETUP->endpoint_base != SETUP->prior_base || SETUP->endpoint_bytes != SETUP->prior_bytes ||
        word(0x3e902a9cu) != SETUP->endpoint_base + NPU_COLD_IND_REG ||
        word(0x8401cf38u) != 6 || word(0x8401cf3cu) != 0x1f020 ||
        word(0x8401cfc8u) != 1 || word(0x8401cfccu) != 303168 ||
        METADATA->lock_id != 18 || METADATA->count > NPU_ALLOCATOR_ENTRIES)
        return 0;
    for (i = 0; i < NPU_COLD_COUNTS; i++)
        if (SETUP->counts[i] != limits[i] || SETUP->prior_counts[i] != limits[i])
            return 0;
    return 1;
}

static int owned(void)
{
    const struct npu_allocator_entry *entry;

    if (!lock_owned || !context() || word(0x3e9030fcu) != arena || PLAN->base != arena + 0x1f020u ||
        PLAN->bytes != NPU_COLD_INDICATION_BYTES || record_index >= METADATA->count ||
        METADATA->count != allocation_count || METADATA->used != allocation_used ||
        SETUP->sequence != identity[0] || SETUP->boot_lo != identity[1] ||
        SETUP->boot_hi != identity[2] || SETUP->nonce_lo != identity[3] || SETUP->nonce_hi != identity[4])
        return 0;
    entry = &METADATA->entries[record_index];
    return entry->type == 1 && !entry->reserved && entry->address == arena;
}

static const volatile uint32_t *words(void)
{
    return (const volatile uint32_t *)(uintptr_t)PLAN->base;
}

uint32_t npu_emulation_indication_reserve(uint32_t address)
{
    if (!owned() || word(0x3e902aa0u) != PLAN->base ||
        npu_cold_indication_reserve(OWNER, PLAN, 1, address,
            NPU_COLD_INDICATION_STATUS, words()) != NPU_COLD_INDICATION_OK)
        return fail();
    return 1;
}

uint32_t npu_emulation_indication_pending(uint32_t address, uint32_t value)
{
    if (!owned() || word(0x3e902aa0u) != PLAN->base ||
        npu_cold_indication_pending(OWNER, PLAN, 1, address, value, words()) != NPU_COLD_INDICATION_OK)
        return fail();
    return 1;
}

uint32_t npu_emulation_indication_publish(uint32_t address)
{
    if (!owned() || word(0x3e902aa0u) != PLAN->base ||
        npu_cold_indication_publish(OWNER, PLAN, 1, address, words()) != NPU_COLD_INDICATION_OK)
        return fail();
    return 1;
}

uint32_t npu_emulation_indication_callback(const struct npu_bootstrap_packet *packet)
{
    struct npu_bootstrap_packet snapshot;
    uint32_t status, result = 0, matches = 0, i;

    __asm__ volatile ("csrrci %0, mstatus, 8" : "=r"(status) :: "memory");
    snapshot = *packet;
    if (snapshot.header != 0x18 || snapshot.api != 1 ||
        snapshot.value != NPU_COLD_INDICATION_COUNT || lock_owned || !context() ||
        word(0x3e902aa0u) || word(0x3e901fd4u) ||
        *(const volatile uint8_t *)(uintptr_t)0x3e904590u)
        goto fault;
    if (((int (*)(const uint32_t *))(uintptr_t)0x840064b4u)(&lock_id))
        goto fault;
    lock_owned = 1;
    arena = word(0x3e9030fcu);
    allocation_count = METADATA->count;
    allocation_used = METADATA->used;
    for (i = 0; i < METADATA->count; i++) {
        const struct npu_allocator_entry *entry = &METADATA->entries[i];

        if (entry->type == 1 && !entry->reserved && entry->address == arena) {
            record_index = i;
            matches++;
        }
    }
    if (matches != 1)
        goto fault;
    PLAN->base = arena + 0x1f020u;
    PLAN->bytes = NPU_COLD_INDICATION_BYTES;
    identity[0] = SETUP->sequence;
    identity[1] = SETUP->boot_lo;
    identity[2] = SETUP->boot_hi;
    identity[3] = SETUP->nonce_lo;
    identity[4] = SETUP->nonce_hi;
    if (!owned() || npu_cold_indication_begin(OWNER, PLAN, 1, words()) != NPU_COLD_INDICATION_OK)
        goto fault;
    result = !npu_original_page_dispatch(snapshot.value, 8);
    if (!result || !owned() || word(0x3e902aa0u) != PLAN->base ||
        word(0x3e901fd4u) || *(const volatile uint8_t *)(uintptr_t)0x3e904590u ||
        npu_cold_indication_finish(OWNER, PLAN, 1, words()) != NPU_COLD_INDICATION_OK)
        goto fault;
    goto done;
fault:
    result = fail();
done:
    if (lock_owned) {
        __asm__ volatile ("fence iorw, iorw" ::: "memory");
        ((void (*)(const uint32_t *))(uintptr_t)0x8400651cu)(&lock_id);
        lock_owned = 0;
        if (!context() || word(0x3e9030fcu) != arena ||
            METADATA->count != allocation_count || METADATA->used != allocation_used)
            result = fail();
    }
    __asm__ volatile ("csrw mstatus, %0" :: "r"(status) : "memory");
    return result;
}
