/* Original PCIe0/2/15 effects; physical DMA/cache/drain authority stays external. */
#include "cold-setup.h"

extern struct npu_cold_setup npu_emulation_cold_setup_state;
extern struct npu_admission npu_emulation_admission_state;
extern struct npu_barrier npu_emulation_barrier_state;
extern struct npu_cold_rx_pcie_state npu_emulation_rx_pcie_state;
extern struct npu_cold_tx_state npu_emulation_tx_state;
extern struct npu_cold_txdone_state npu_emulation_desc10_state;
extern struct npu_cold_rx_event_state npu_emulation_rx_event_state;
extern struct npu_cold_packet_state npu_emulation_packet_state;
extern int npu_emulation_rx_pcie_prior_live_tail(const struct npu_cold_rx_pcie_plan *);
extern int npu_emulation_rx_pcie_prior_live_inode(const struct npu_cold_rx_pcie_plan *);
extern int npu_emulation_desc10_read(void *, uint32_t, uint32_t, uint32_t *);
extern uint32_t npu_emulation_rx_pcie_callback(struct npu_bootstrap_packet *);

struct npu_cold_pcie_tail_state npu_emulation_pcie_tail_state;
uint32_t npu_emulation_pcie_tail_running;
static struct npu_cold_pcie_tail_plan plan;
static uint32_t held_setup[sizeof(struct npu_cold_setup) / 4];
static uint32_t neighbors[NPU_COLD_PCIE_TAIL_STORES][2], neighbors_captured, lock_owned, phase;
static const uint32_t lock_id = 18;

#define SETUP (&npu_emulation_cold_setup_state)
#define OWNER (&npu_emulation_pcie_tail_state)
#define PCIE (&npu_emulation_rx_pcie_state)
#define TX (&npu_emulation_tx_state)
#define DONE (&npu_emulation_desc10_state)

static uint32_t word(uint32_t address)
{
    return *(const volatile uint32_t *)(uintptr_t)address;
}

static void copy(void *destination, const void *source, uint32_t bytes)
{
    volatile unsigned char *to = destination;
    const volatile unsigned char *from = source;

    for (uint32_t i = 0; i < bytes; i++) to[i] = from[i];
}

static uint32_t fail(void)
{
    npu_cold_pcie_tail_fault(OWNER);
    npu_admission_fail(&npu_emulation_admission_state, &npu_emulation_barrier_state);
    return 0;
}

static int tail_read_for(void *opaque, uint32_t address, uint32_t bytes, uint32_t *value,
                         uint32_t inode)
{
    static const uint32_t metadata[] = {0x3e90395c, 0x3e902a80, 0x3e904630, 0x3e902a9c, 0x3e902a90};
    struct npu_cold_pcie_tail_store store;
    uint32_t i, status;

    __asm__ volatile ("csrr %0, mstatus" : "=r"(status));
    if (status & 8 || inode > 1 || opaque != OWNER || !value ||
        (inode ? npu_emulation_pcie_tail_running || lock_owned || phase != 2 ||
         neighbors_captured != 1 || !npu_cold_inode_inflight(SETUP) :
         npu_emulation_pcie_tail_running != 1) ||
        !npu_cold_pcie_tail_plan_valid(&plan))
        return 0;
    if (address == 0x3e902a7cu && bytes == 2)
        return npu_emulation_desc10_read(DONE, address, bytes, value);
    if (bytes != 4 || (address & 3))
        return 0;
    for (i = 0; i < sizeof(metadata) / 4; i++)
        if (address == metadata[i]) {
            *value = word(address);
            return 1;
        }
    for (i = 0; i < NPU_COLD_PCIE_TAIL_STORES; i++)
        if (!npu_cold_pcie_tail_recipe(&plan, i, &store) && address == store.address) {
            *value = word(address);
            return 1;
        }
    return 0;
}

static int tail_read(void *opaque, uint32_t address, uint32_t bytes, uint32_t *value)
{
    return tail_read_for(opaque, address, bytes, value, 0);
}

int npu_emulation_pcie_tail_read_inode(void *opaque, uint32_t address, uint32_t bytes,
                                      uint32_t *value)
{
    return tail_read_for(opaque, address, bytes, value, 1);
}

static struct npu_cold_pcie_tail_context prior(void)
{
    const struct npu_cold_pcie_tail_context c = {
        .pcie = PCIE, .tx = TX,
        .prior = {.done = DONE, .rx = &npu_emulation_rx_event_state,
            .packets = &npu_emulation_packet_state, .read = npu_emulation_desc10_read,
            .opaque = DONE, .rx_readback = word(NPU_COLD_RX_EVENT_METADATA),
            .ready = *(const volatile uint8_t *)(uintptr_t)0x3e9046fau},
        .read = tail_read, .opaque = OWNER, .pcie_readback = word(NPU_COLD_RX_PCIE_METADATA)
    };

    return c;
}

static int context(void)
{
    const volatile uint32_t *current = (const volatile void *)SETUP;
    uint32_t i, status;

    __asm__ volatile ("csrr %0, mstatus" : "=r"(status));
    if (status & 8 || npu_emulation_pcie_tail_running != 1 ||
        phase >= NPU_COLD_PCIE_TAIL_STAGES || !npu_cold_pcie_tail_inflight(SETUP) ||
        SETUP->pcie_tail_steps != phase ||
        SETUP->command.value != npu_cold_pcie_tail_value(&plan, phase) ||
        SETUP->tx2_register != plan.tx.host2 || SETUP->prior_tx2_register != plan.tx.host2 ||
        word(0x3e900178u) != 0x8400fdc4u ||
        !npu_emulation_rx_pcie_prior_live_tail(&plan.prior))
        return 0;
    for (i = 0; i < sizeof(held_setup) / 4; i++)
        if (current[i] != held_setup[i])
            return 0;
    return 1;
}

static int neighbor_span(uint32_t address)
{
    uint32_t offset = address - plan.tx.endpoint_base;

    if (address == 0x3e902cf0u || address == 0x3e903904u)
        return 1;
    return address >= plan.tx.endpoint_base && offset >= 4 &&
           plan.tx.endpoint_bytes >= 12 && offset <= plan.tx.endpoint_bytes - 8;
}

static int capture_neighbors(void)
{
    struct npu_cold_pcie_tail_store store;

    if (neighbors_captured || OWNER->magic || phase)
        return 0;
    for (uint32_t i = 0; i < NPU_COLD_PCIE_TAIL_STORES; i++) {
        if (npu_cold_pcie_tail_recipe(&plan, i, &store) || !neighbor_span(store.address))
            return 0;
        neighbors[i][0] = word(store.address - 4);
        neighbors[i][1] = word(store.address + 4);
    }
    neighbors_captured = 1;
    return 1;
}

static int neighbors_live(void)
{
    struct npu_cold_pcie_tail_store store;

    if (neighbors_captured != 1)
        return 0;
    for (uint32_t i = 0; i < NPU_COLD_PCIE_TAIL_STORES; i++)
        if (npu_cold_pcie_tail_recipe(&plan, i, &store) || !neighbor_span(store.address) ||
            word(store.address - 4) != neighbors[i][0] || word(store.address + 4) != neighbors[i][1])
            return 0;
    return 1;
}

static int owned(void)
{
    return lock_owned && context() && neighbors_live();
}

int npu_emulation_pcie_tail_prior_live_inode(const struct npu_cold_pcie_tail_plan *candidate)
{
    const struct npu_cold_setup *held = (const void *)held_setup;
    const volatile uint32_t *current = (const volatile void *)SETUP;
    const volatile unsigned char *wanted = (const volatile void *)candidate;
    const volatile unsigned char *saved = (const volatile void *)&plan;
    struct npu_cold_pcie_tail_context c;
    uint32_t i, status;

    __asm__ volatile ("csrr %0, mstatus" : "=r"(status));
    if (!candidate || status & 8 || npu_emulation_pcie_tail_running || lock_owned || phase != 2 ||
        SETUP->sequence <= held->sequence || !npu_cold_inode_inflight(SETUP) ||
        held->command.header != 0x1f || held->command.api || held->command.value ||
        held->pcie_tail_steps != 2 || held->prior_pcie_tail_steps != 2 ||
        held->inode_steps || held->prior_inode_steps ||
        word(0x3e900178u) != 0x8400fdc4u || !neighbors_live() ||
        !npu_emulation_rx_pcie_prior_live_inode(&candidate->prior))
        return 0;
    for (i = 0; i < sizeof(plan); i++)
        if (wanted[i] != saved[i])
            return 0;
    for (i = 0; i < sizeof(held_setup) / 4; i++) {
        if (i == __builtin_offsetof(struct npu_cold_setup, sequence) / 4 ||
            (i >= __builtin_offsetof(struct npu_cold_setup, command) / 4 &&
             i < (__builtin_offsetof(struct npu_cold_setup, command) + sizeof(SETUP->command)) / 4) ||
            i == __builtin_offsetof(struct npu_cold_setup, pcie_tail_steps) / 4 ||
            i == __builtin_offsetof(struct npu_cold_setup, prior_pcie_tail_steps) / 4 ||
            i == __builtin_offsetof(struct npu_cold_setup, inode_steps) / 4 ||
            i == __builtin_offsetof(struct npu_cold_setup, prior_inode_steps) / 4)
            continue;
        if (current[i] != held_setup[i])
            return 0;
    }
    c = prior();
    c.read = npu_emulation_pcie_tail_read_inode;
    return npu_cold_pcie_tail_live(OWNER, candidate, 1, &c) &&
           npu_cold_inode_inflight(SETUP) && neighbors_live();
}

uint32_t npu_emulation_pcie_tail_reserve(uint32_t address, uint32_t value, uint32_t bytes)
{
    struct npu_cold_pcie_tail_store store;
    struct npu_cold_pcie_tail_context c = prior();

    if (!owned() || npu_cold_pcie_tail_recipe(&plan, OWNER->committed, &store) ||
        address != store.address || bytes != store.bytes || value != store.value ||
        npu_cold_pcie_tail_reserve(OWNER, &plan, 1, &c, address, bytes, value, word(address)) || !owned())
        return fail();
    return 1;
}

uint32_t npu_emulation_pcie_tail_publish(uint32_t address, uint32_t bytes)
{
    struct npu_cold_pcie_tail_store store;
    struct npu_cold_pcie_tail_context c = prior();

    if (!owned() || npu_cold_pcie_tail_recipe(&plan, OWNER->published, &store) ||
        address != store.address || bytes != store.bytes ||
        npu_cold_pcie_tail_publish(OWNER, &plan, 1, &c, address, bytes, word(address)) || !owned())
        return fail();
    return 1;
}

uint32_t npu_emulation_pcie_tail_callback(struct npu_bootstrap_packet *packet)
{
    struct npu_bootstrap_packet snapshot;
    struct npu_cold_pcie_tail_context c;
    const volatile uint32_t *current = (const volatile void *)SETUP;
    uint32_t i, status, result = 0, acquired = 0, entered = 0;

    if (npu_cold_pcie_tail_command_step(packet) == NPU_COLD_PCIE_TAIL_STAGES)
        return npu_emulation_rx_pcie_callback(packet);
    __asm__ volatile ("csrrci %0, mstatus, 8" : "=r"(status) :: "memory");
    snapshot = *packet;
    if (npu_emulation_pcie_tail_running || lock_owned)
        goto fault;
    npu_emulation_pcie_tail_running = entered = 1;
    phase = npu_cold_pcie_tail_command_step(&snapshot);
    if (!OWNER->magic) {
        if (phase || neighbors_captured)
            goto fault;
        copy(&plan.prior, &PCIE->plan, sizeof(plan.prior));
        copy(&plan.tx, &TX->plan, sizeof(plan.tx));
    }
    for (i = 0; i < sizeof(held_setup) / 4; i++)
        held_setup[i] = current[i];
    if (snapshot.header != SETUP->command.header || snapshot.api != SETUP->command.api ||
        snapshot.value != SETUP->command.value || !context())
        goto fault;
    if (((int (*)(const uint32_t *))(uintptr_t)0x840064b4u)(&lock_id))
        goto fault;
    lock_owned = acquired = 1;
    if ((!OWNER->magic && !capture_neighbors()) || !owned())
        goto fault;
    c = prior();
    if (npu_cold_pcie_tail_begin(OWNER, &plan, 1, &c, snapshot.header & 15, snapshot.value) || !owned())
        goto fault;
    /* Call the linked predecessor, not the original address now detoured here. */
    result = npu_emulation_rx_pcie_callback(&snapshot);
    c = prior();
    if (result != 1 || !owned() || npu_cold_pcie_tail_finish(OWNER, &plan, 1, &c) ||
        !npu_cold_pcie_tail_stage_live(OWNER, &plan, 1, &c, phase))
        goto fault;
    goto done;
fault:
    result = fail();
done:
    if (acquired) {
        __asm__ volatile ("fence iorw, iorw" ::: "memory");
        ((void (*)(const uint32_t *))(uintptr_t)0x8400651cu)(&lock_id);
        lock_owned = 0;
        c = prior();
        if (!context() || !neighbors_live() || !npu_cold_pcie_tail_stage_live(OWNER, &plan, 1, &c, phase))
            result = fail();
    }
    if (entered)
        npu_emulation_pcie_tail_running = 0;
    __asm__ volatile ("csrw mstatus, %0" :: "r"(status) : "memory");
    return result;
}
