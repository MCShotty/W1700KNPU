/* Original TX instruction binding; hardware grants/coherency remain external. */
#include "allocator.h"
#include "cold-indication.h"
#include "cold-setup.h"
#include "cold-tx.h"

extern struct npu_bootstrap npu_emulation_bootstrap_state;
extern struct npu_admission npu_emulation_admission_state;
extern struct npu_barrier npu_emulation_barrier_state;
extern struct npu_cold_setup npu_emulation_cold_setup_state;
extern struct npu_cold_indication_state npu_emulation_indication_state;
extern int npu_emulation_cold_arena_live(void);
extern uint32_t npu_original_tx_callback(const struct npu_bootstrap_packet *);
extern uint32_t npu_original_token_callback(const struct npu_bootstrap_packet *);

struct npu_cold_tx_state npu_emulation_tx_state;
struct npu_cold_tx_plan npu_emulation_tx_plan;
static uint32_t record_index, allocation_count, allocation_used, stage, lock_owned;
static uint32_t identity[5];
static const uint32_t lock_id = 18;

#define SETUP (&npu_emulation_cold_setup_state)
#define OWNER (&npu_emulation_tx_state)
#define PLAN (&npu_emulation_tx_plan)
#define IND (&npu_emulation_indication_state)
#define METADATA ((const struct npu_allocator_state *)(uintptr_t)0x3e901bccu)

static uint32_t read(uint32_t address, uint32_t bytes)
{
    if (bytes == 2)
        return *(const volatile uint16_t *)(uintptr_t)address;
    return *(const volatile uint32_t *)(uintptr_t)address;
}

static uint32_t fail(void)
{
    npu_cold_tx_fault(OWNER);
    npu_admission_fail(&npu_emulation_admission_state, &npu_emulation_barrier_state);
    return 0;
}

static int context(void)
{
    static const uint32_t prefixes[] = {16383, 32767, 65535};
    static const uint32_t limits[] = {1536, 1024, 256, 512, 1024};
    uint32_t i;

    if (stage > 2 || !npu_emulation_cold_arena_live() || SETUP->failed || SETUP->inflight != 1 ||
        SETUP->completed != prefixes[stage] || SETUP->prior_completed != prefixes[stage] ||
        SETUP->command.api != (stage == 2 ? 33u : 19u) ||
        SETUP->command.header != (stage == 1 ? 0x12u : 0x10u) ||
        SETUP->endpoint_base != SETUP->prior_base || SETUP->endpoint_bytes != SETUP->prior_bytes ||
        *(const volatile uint8_t *)(uintptr_t)0x3e90390eu != 2 ||
        read(0x8401cf18u, 4) != 1 || read(0x8401cf1cu, 4) ||
        read(0x8401cf20u, 4) != 2 || read(0x8401cf24u, 4) != 0x22020 ||
        read(0x8401cfc8u, 4) != 1 || read(0x8401cfccu, 4) != NPU_COLD_TX_ARENA_BYTES ||
        IND->magic != NPU_COLD_INDICATION_MAGIC || IND->epoch != 1 || IND->fault || IND->active ||
        IND->committed != 1536 || IND->published != 1536 || IND->count != 1536 ||
        IND->base != read(0x3e9030fcu, 4) + 0x1f020u ||
        read(0x3e902aa0u, 4) != IND->base ||
        METADATA->lock_id != 18 || METADATA->count > NPU_ALLOCATOR_ENTRIES)
        return 0;
    for (i = 0; i < NPU_COLD_COUNTS; i++)
        if (SETUP->counts[i] != limits[i] || SETUP->prior_counts[i] != limits[i])
            return 0;
    return 1;
}

static int pinned(void)
{
    const struct npu_allocator_entry *entry;
    uint32_t value = stage == 2 ? 8192 : stage ? PLAN->host2 : PLAN->host0;

    if (!context() || PLAN->arena != read(0x3e9030fcu, 4) ||
        PLAN->arena_bytes != NPU_COLD_TX_ARENA_BYTES ||
        PLAN->endpoint_base != SETUP->endpoint_base || PLAN->endpoint_bytes != SETUP->endpoint_bytes ||
        SETUP->command.value != value || METADATA->count != allocation_count ||
        METADATA->used != allocation_used || record_index >= METADATA->count ||
        SETUP->sequence != identity[0] || SETUP->boot_lo != identity[1] || SETUP->boot_hi != identity[2] ||
        SETUP->nonce_lo != identity[3] || SETUP->nonce_hi != identity[4])
        return 0;
    entry = &METADATA->entries[record_index];
    return entry->type == 1 && !entry->reserved && entry->address == PLAN->arena;
}

static int owned(void)
{
    return lock_owned && pinned();
}

static int allowed(uint32_t address, uint32_t bytes)
{
    if (bytes == 2)
        return address == 0x3e903978u || address == 0x3e9021f4u;
    return bytes == 4 && (address == 0x3e904700u || address == 0x3e9046fcu ||
        address == 0x3e900bc0u || address == 0x1fc08030u || address == 0x1fc08034u ||
        address == 0x1fc48030u || address == 0x1fc48034u);
}

uint32_t npu_emulation_tx_reserve(uint32_t address, uint32_t value, uint32_t bytes)
{
    if (!owned() || !allowed(address, bytes) ||
        npu_cold_tx_reserve(OWNER, PLAN, 1, address, value, bytes, read(address, bytes)) || !owned())
        return fail();
    return 1;
}

uint32_t npu_emulation_tx_publish(uint32_t address, uint32_t bytes)
{
    if (!owned() || !allowed(address, bytes) ||
        npu_cold_tx_publish(OWNER, PLAN, 1, address, bytes, read(address, bytes)) || !owned())
        return fail();
    return 1;
}

static int previous(void)
{
    uint32_t base = PLAN->arena;

    if (OWNER->completed & 1)
        if (read(0x3e904700u, 4) != PLAN->host0 ||
            read(0x1fc08030u, 4) != (base & 0x1fffffffu) ||
            read(0x1fc08034u, 4) != ((base + 0x22020u) & 0x1fffffffu))
            return 0;
    if (OWNER->completed & 2)
        if (read(0x3e9046fcu, 4) != PLAN->host2 ||
            read(0x1fc48030u, 4) != ((base + 0x22020u) & 0x1fffffffu) ||
            read(0x1fc48034u, 4) != ((base + 0x4a040u) & 0x1fffffffu))
            return 0;
    return !read(0x3e903978u, 2) && !read(0x3e9021f4u, 2);
}

static uint32_t callback(const struct npu_bootstrap_packet *packet, uint32_t selected)
{
    struct npu_bootstrap_packet snapshot;
    static const uint32_t registers[] = {0x1fc08030, 0x1fc08034, 0x1fc48030, 0x1fc48034};
    uint32_t status, result = 0, matches = 0, i, values[5], acquired = 0;

    __asm__ volatile ("csrrci %0, mstatus, 8" : "=r"(status) :: "memory");
    snapshot = *packet;
    stage = selected;
    if (lock_owned || !context() || snapshot.header != SETUP->command.header ||
        snapshot.api != SETUP->command.api || snapshot.value != SETUP->command.value ||
        (stage < 2 && read(stage ? 0x3e9046fcu : 0x3e904700u, 4)))
        goto fault;
    if (((int (*)(const uint32_t *))(uintptr_t)0x840064b4u)(&lock_id))
        goto fault;
    lock_owned = 1;
    acquired = 1;
    allocation_count = METADATA->count;
    allocation_used = METADATA->used;
    for (i = 0; i < METADATA->count; i++) {
        const struct npu_allocator_entry *entry = &METADATA->entries[i];

        if (entry->type == 1 && !entry->reserved && entry->address == read(0x3e9030fcu, 4)) {
            record_index = i;
            matches++;
        }
    }
    if (matches != 1)
        goto fault;
    if (!stage) {
        PLAN->arena = read(0x3e9030fcu, 4);
        PLAN->arena_bytes = NPU_COLD_TX_ARENA_BYTES;
        PLAN->endpoint_base = SETUP->endpoint_base;
        PLAN->endpoint_bytes = SETUP->endpoint_bytes;
        PLAN->host0 = snapshot.value;
        PLAN->host2 = 0;
        for (i = 0; i < 4; i++)
            PLAN->register_before[i] = read(registers[i], 4);
        PLAN->token_before = read(0x3e900bc0u, 4);
    } else if (stage == 1) {
        PLAN->host2 = snapshot.value;
    }
    identity[0] = SETUP->sequence;
    identity[1] = SETUP->boot_lo;
    identity[2] = SETUP->boot_hi;
    identity[3] = SETUP->nonce_lo;
    identity[4] = SETUP->nonce_hi;
    if (!owned() || !previous() || read(0x3e900bc0u, 4) != PLAN->token_before ||
        npu_cold_tx_begin(OWNER, PLAN, 1, stage))
        goto fault;
    result = stage == 2 ? npu_original_token_callback(&snapshot) : npu_original_tx_callback(&snapshot);
    if (stage == 2) {
        values[0] = read(0x3e900bc0u, 4);
    } else {
        values[0] = read(stage ? 0x3e9046fcu : 0x3e904700u, 4);
        values[1] = read(0x3e903978u, 2);
        values[2] = read(0x3e9021f4u, 2);
        values[3] = read(registers[stage * 2], 4);
        values[4] = read(registers[stage * 2 + 1], 4);
    }
    if (result != 1 || !owned() || npu_cold_tx_finish(OWNER, PLAN, 1, values) || !previous())
        goto fault;
    goto done;
fault:
    result = fail();
done:
    if (acquired) {
        __asm__ volatile ("fence iorw, iorw" ::: "memory");
        ((void (*)(const uint32_t *))(uintptr_t)0x8400651cu)(&lock_id);
        lock_owned = 0;
        if (!pinned() || !previous())
            result = fail();
    }
    __asm__ volatile ("csrw mstatus, %0" :: "r"(status) : "memory");
    return result;
}

uint32_t npu_emulation_tx_callback(const struct npu_bootstrap_packet *packet)
{
    if (packet->header == 0x13 && packet->api == 19)
        return npu_original_tx_callback(packet);
    if (packet->api != 19 || (packet->header != 0x10 && packet->header != 0x12))
        return fail();
    return callback(packet, packet->header == 0x12);
}

uint32_t npu_emulation_token_callback(const struct npu_bootstrap_packet *packet)
{
    if (packet->header != 0x10 || packet->api != 33 || packet->value != 8192)
        return fail();
    return callback(packet, 2);
}
