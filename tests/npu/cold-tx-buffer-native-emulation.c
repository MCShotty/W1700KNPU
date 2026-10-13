/* Original API21 stores under retained software ownership, not physical drains. */
#include "cold-setup.h"

extern struct npu_bootstrap npu_emulation_bootstrap_state;
extern struct npu_admission npu_emulation_admission_state;
extern struct npu_barrier npu_emulation_barrier_state;
extern struct npu_cold_setup npu_emulation_cold_setup_state;
extern int npu_emulation_descriptor_prior_live(uint32_t gets);
extern uint32_t npu_original_txbuf_callback(struct npu_bootstrap_packet *);

struct npu_cold_txbuf_state npu_emulation_txbuf_state;
static struct npu_cold_txbuf_plan plan;
static uint32_t held_setup[sizeof(struct npu_cold_setup) / 4];
static uint32_t phase, lock_owned, metadata[4], neighbors[4];
static const uint32_t lock_id = 18;

#define SETUP (&npu_emulation_cold_setup_state)
#define BOOT (&npu_emulation_bootstrap_state)
#define OWNER (&npu_emulation_txbuf_state)

static uint32_t word(uint32_t address)
{
    return *(const volatile uint32_t *)(uintptr_t)address;
}

static uint32_t value(uint32_t address, uint32_t width)
{
    return width == 2 ? *(const volatile uint16_t *)(uintptr_t)address : word(address);
}

static uint32_t fail(void)
{
    npu_cold_txbuf_fault(OWNER);
    npu_admission_fail(&npu_emulation_admission_state, &npu_emulation_barrier_state);
    return 0;
}

static uint32_t meta_count(uint32_t step)
{
    return step == 2 || step == 5 ? 4 : 1;
}

static uint32_t record_base(uint32_t step)
{
    return step == 0 || step == 3 ? 0 : step == 1 ? plan.arena + 0x8020u :
           step == 4 ? plan.arena + 0x2a040u : step == 2 ? 0x3e8a2000u : 0x3e8a4020u;
}

static uint32_t counter(uint32_t band, uint32_t index)
{
    static const uint32_t addresses[2][2] = {{0x3e90462c, 0x3e90395a}, {0x3e902a8c, 0x3e90390c}};

    return addresses[band][index];
}

static int neighbor_live(uint32_t band, uint32_t index, uint32_t after)
{
    uint32_t address = counter(band, index), expected = neighbors[band * 2 + index];

    if (after)
        expected &= address & 2 ? 0xffffu : 0xffff0000u;
    return word(address & ~3u) == expected;
}

static int context(void)
{
    uint32_t i, status;
    const volatile uint32_t *current = (const volatile void *)SETUP;

    __asm__ volatile ("csrr %0, mstatus" : "=r"(status));
    if (phase >= NPU_COLD_TXBUF_STEPS || status & 8 ||
        !npu_emulation_descriptor_prior_live(phase < 3 ? 7 : 8) ||
        SETUP->txbuf_enrolled != NPU_COLD_TXBUF_RECORDS ||
        SETUP->txbuf_steps != phase || SETUP->prior_txbuf_steps != phase ||
        SETUP->command.api != 21 ||
        SETUP->command.header != (0x10u | npu_cold_txbuf_selector(phase)) ||
        SETUP->command.value != plan.host[phase] ||
        word(0x3e9001ccu) != 0x8400fbcau ||
        word(0x8401cf70u) != 0x100 || word(0x8401cf74u) != 0x3e8a2000u ||
        word(0x8401cf78u) != 0x101 || word(0x8401cf7cu) != 0x3e8a4020u ||
        word(0x3e902ab8u) != plan.boot.region[NPU_BOOT_TXPKT].base ||
        word(0x3e9030fcu) != plan.arena)
        return 0;
    for (i = 0; i < sizeof(held_setup) / 4; i++)
        if (current[i] != held_setup[i])
            return 0;
    for (i = 0; i < NPU_BOOT_REGIONS; i++)
        if (BOOT->plan.region[i].base != plan.boot.region[i].base ||
            BOOT->plan.region[i].bytes != plan.boot.region[i].bytes)
            return 0;
    return 1;
}

static int owned(void)
{
    return lock_owned && context();
}

static int descriptor_spans(void)
{
    uint32_t i;

    for (i = 0; i < 512; i++)
        if (word(plan.arena + 0x6024u + i * 16) != NPU_COLD_DESCRIPTOR_STATUS)
            return 0;
    if (phase >= 3)
        for (i = 0; i < 1024; i++)
            if (word(plan.arena + 0x26044u + i * 16) != NPU_COLD_DESCRIPTOR_STATUS)
                return 0;
    return 1;
}

static int completed_spans(uint32_t completed)
{
    struct npu_cold_txbuf_store store;
    uint32_t step, index, position = 0, expected;

    for (step = 0; step < completed; step++) {
        for (index = 0; index < npu_cold_txbuf_count(step); index++, position++) {
            if (npu_cold_txbuf_recipe(&plan, step, index, &store))
                return 0;
            expected = store.bytes == 1 ? (OWNER->preimages[position] & 0xffffff00u) | store.value : store.value;
            if (value(store.address, store.bytes) != expected)
                return 0;
        }
        if ((step == 2 || step == 5) &&
            (!neighbor_live(step / 3, 0, 1) || !neighbor_live(step / 3, 1, 1)))
            return 0;
    }
    return 1;
}

int npu_emulation_txbuf_prior_live(void)
{
    struct npu_cold_txbuf_plan current;
    uint32_t i, status;

    __asm__ volatile ("csrr %0, mstatus" : "=r"(status));
    npu_cold_txbuf_plan_copy(&current, &SETUP->txbuf);
    current.arena = SETUP->descriptor_arena;
    if (status & 8 || lock_owned || phase != NPU_COLD_TXBUF_STEPS - 1 ||
        !npu_emulation_descriptor_prior_live(8) ||
        SETUP->txbuf_enrolled != NPU_COLD_TXBUF_RECORDS ||
        SETUP->txbuf_steps != NPU_COLD_TXBUF_STEPS ||
        SETUP->prior_txbuf_steps != NPU_COLD_TXBUF_STEPS ||
        !npu_cold_txbuf_plan_valid(&current) ||
        !npu_cold_txbuf_plan_equal(&current, &plan) ||
        !npu_cold_txbuf_plan_equal(&OWNER->plan, &plan) ||
        OWNER->magic != NPU_COLD_TXBUF_MAGIC || OWNER->epoch != 1 ||
        OWNER->fault || OWNER->active || OWNER->next != NPU_COLD_TXBUF_STEPS ||
        OWNER->completed != 63 || OWNER->reserved != 63 ||
        OWNER->committed != NPU_COLD_TXBUF_STORES || OWNER->published != NPU_COLD_TXBUF_STORES ||
        OWNER->from != NPU_COLD_TXBUF_STORES || OWNER->until != NPU_COLD_TXBUF_STORES ||
        word(0x3e9001ccu) != 0x8400fbcau ||
        word(0x8401cf70u) != 0x100 || word(0x8401cf74u) != 0x3e8a2000u ||
        word(0x8401cf78u) != 0x101 || word(0x8401cf7cu) != 0x3e8a4020u ||
        word(0x3e902ab8u) != plan.boot.region[NPU_BOOT_TXPKT].base ||
        word(0x3e9030fcu) != plan.arena)
        return 0;
    for (i = 0; i < NPU_BOOT_REGIONS; i++)
        if (BOOT->plan.region[i].base != plan.boot.region[i].base ||
            BOOT->plan.region[i].bytes != plan.boot.region[i].bytes)
            return 0;
    return descriptor_spans() && completed_spans(NPU_COLD_TXBUF_STEPS);
}

static int read_metadata(void)
{
    struct npu_cold_txbuf_store store;
    uint32_t i;

    for (i = 0; i < meta_count(phase); i++) {
        if (npu_cold_txbuf_recipe(&plan, phase, i, &store))
            return 0;
        metadata[i] = value(store.address, store.bytes);
    }
    return 1;
}

uint32_t npu_emulation_txbuf_reserve(uint32_t address, uint32_t data, uint32_t width)
{
    struct npu_cold_txbuf_store store;
    uint32_t band = phase / 3, i;

    if (!owned() || OWNER->next != phase || OWNER->committed < OWNER->from ||
        npu_cold_txbuf_recipe(&plan, phase, OWNER->committed - OWNER->from, &store) ||
        address != store.address || width != store.bytes || data != store.value)
        return fail();
    if (width == 2) {
        for (i = 0; i < 2; i++)
            if (address == counter(band, i))
                break;
        if (i == 2 || !neighbor_live(band, i, 0))
            return fail();
    }
    if (npu_cold_txbuf_reserve(OWNER, &plan, 1, address, width, data, value(address, width)) || !owned())
        return fail();
    return 1;
}

uint32_t npu_emulation_txbuf_publish(uint32_t address, uint32_t width)
{
    struct npu_cold_txbuf_store store;
    uint32_t band = phase / 3, i;

    if (!owned() || OWNER->next != phase || OWNER->published < OWNER->from ||
        npu_cold_txbuf_recipe(&plan, phase, OWNER->published - OWNER->from, &store) ||
        address != store.address || width != store.bytes ||
        npu_cold_txbuf_publish(OWNER, &plan, 1, address, width, value(address, width)))
        return fail();
    if (width == 2) {
        for (i = 0; i < 2; i++)
            if (address == counter(band, i))
                break;
        if (i == 2 || !neighbor_live(band, i, 1))
            return fail();
    }
    return owned() ? 1 : fail();
}

uint32_t npu_emulation_txbuf_callback(struct npu_bootstrap_packet *packet)
{
    struct npu_bootstrap_packet snapshot;
    const volatile uint32_t *current = (const volatile void *)SETUP;
    const volatile uint32_t *records;
    uint32_t status, i, result = 0, acquired = 0;

    __asm__ volatile ("csrrci %0, mstatus, 8" : "=r"(status) :: "memory");
    if (lock_owned)
        goto fault;
    snapshot = *packet;
    phase = npu_cold_txbuf_command_step(&snapshot);
    if (phase >= NPU_COLD_TXBUF_STEPS)
        goto fault;
    npu_cold_txbuf_plan_copy(&plan, &SETUP->txbuf);
    plan.arena = SETUP->descriptor_arena;
    for (i = 0; i < sizeof(held_setup) / 4; i++)
        held_setup[i] = current[i];
    if (snapshot.header != SETUP->command.header || snapshot.api != SETUP->command.api ||
        snapshot.value != SETUP->command.value || !npu_cold_txbuf_plan_valid(&plan) || !context())
        goto fault;
    if (((int (*)(const uint32_t *))(uintptr_t)0x840064b4u)(&lock_id))
        goto fault;
    lock_owned = acquired = 1;
    if (!owned() || !descriptor_spans() || (phase && !completed_spans(phase)))
        goto fault;
    if (phase == 2 || phase == 5)
        for (i = 0; i < 2; i++)
            neighbors[phase / 3 * 2 + i] = word(counter(phase / 3, i) & ~3u);
    if (!read_metadata())
        goto fault;
    records = (const volatile void *)(uintptr_t)record_base(phase);
    if (npu_cold_txbuf_begin(OWNER, &plan, 1, snapshot.header & 15, snapshot.value, metadata, records) || !owned())
        goto fault;
    result = npu_original_txbuf_callback(&snapshot);
    if (result != 1 || !owned() || !read_metadata() ||
        npu_cold_txbuf_finish(OWNER, &plan, 1, metadata, records) ||
        !completed_spans(phase + 1) || !descriptor_spans())
        goto fault;
    goto done;
fault:
    result = fail();
done:
    if (acquired) {
        __asm__ volatile ("fence iorw, iorw" ::: "memory");
        ((void (*)(const uint32_t *))(uintptr_t)0x8400651cu)(&lock_id);
        lock_owned = 0;
        if (!context())
            result = fail();
    }
    __asm__ volatile ("csrw mstatus, %0" :: "r"(status) : "memory");
    return result;
}
