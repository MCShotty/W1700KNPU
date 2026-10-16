/* Bound original selector10 pointer store; no physical DMA/drain authority. */
#include "cold-setup.h"

extern struct npu_cold_setup npu_emulation_cold_setup_state;
extern struct npu_admission npu_emulation_admission_state;
extern struct npu_barrier npu_emulation_barrier_state;
extern struct npu_cold_txdone_state npu_emulation_desc10_state;
extern struct npu_cold_rx_event_state npu_emulation_rx_event_state;
extern struct npu_cold_packet_state npu_emulation_packet_state;
extern int npu_emulation_desc10_prior_live(const struct npu_cold_txdone_plan *);
extern int npu_emulation_desc10_prior_live_tail(const struct npu_cold_txdone_plan *);
extern int npu_emulation_desc10_prior_live_inode(const struct npu_cold_txdone_plan *);
extern int npu_emulation_desc10_read(void *, uint32_t, uint32_t, uint32_t *);
extern uint32_t npu_original_rx_pcie_callback(struct npu_bootstrap_packet *);

struct npu_cold_rx_pcie_state npu_emulation_rx_pcie_state;
uint32_t npu_emulation_rx_pcie_running;
static struct npu_cold_rx_pcie_plan plan;
static uint32_t held_setup[sizeof(struct npu_cold_setup) / 4], neighbors[2], lock_owned;
static const uint32_t lock_id = 18;

#define SETUP (&npu_emulation_cold_setup_state)
#define OWNER (&npu_emulation_rx_pcie_state)
#define DONE (&npu_emulation_desc10_state)

static uint32_t word(uint32_t address)
{
    return *(const volatile uint32_t *)(uintptr_t)address;
}

static uint32_t fail(void)
{
    npu_cold_rx_pcie_fault(OWNER);
    npu_admission_fail(&npu_emulation_admission_state, &npu_emulation_barrier_state);
    return 0;
}

static struct npu_cold_rx_pcie_context prior(void)
{
    const struct npu_cold_rx_pcie_context c = {
        .done = DONE, .rx = &npu_emulation_rx_event_state,
        .packets = &npu_emulation_packet_state, .read = npu_emulation_desc10_read,
        .opaque = DONE, .rx_readback = word(NPU_COLD_RX_EVENT_METADATA),
        .ready = *(const volatile uint8_t *)(uintptr_t)0x3e9046fau
    };

    return c;
}

static int context(void)
{
    const volatile uint32_t *current = (const volatile void *)SETUP;
    uint32_t i, status;

    __asm__ volatile ("csrr %0, mstatus" : "=r"(status));
    if (status & 8 || npu_emulation_rx_pcie_running != 1 ||
        !npu_cold_rx_pcie_command(&SETUP->command) ||
        SETUP->command.value != npu_cold_rx_pcie_value(&plan) ||
        word(0x3e900178u) != 0x8400fdc4u ||
        !npu_emulation_desc10_prior_live(&plan.prior))
        return 0;
    for (i = 0; i < sizeof(held_setup) / 4; i++)
        if (current[i] != held_setup[i])
            return 0;
    return 1;
}

static int neighbors_live(void)
{
    return word(NPU_COLD_RX_PCIE_METADATA - 4) == neighbors[0] &&
           word(NPU_COLD_RX_PCIE_METADATA + 4) == neighbors[1];
}

static int completed_prior_live(const struct npu_cold_rx_pcie_plan *candidate, uint32_t inode)
{
    const struct npu_cold_setup *held = (const void *)held_setup;
    const volatile uint32_t *current = (const volatile void *)SETUP;
    struct npu_cold_rx_pcie_context c;
    uint32_t i, status;

    __asm__ volatile ("csrr %0, mstatus" : "=r"(status));
    if (!candidate || inode > 1 || status & 8 || lock_owned || npu_emulation_rx_pcie_running ||
        SETUP->sequence <= held->sequence ||
        (inode ? !npu_cold_inode_inflight(SETUP) : !npu_cold_pcie_tail_inflight(SETUP)) ||
        !npu_cold_rx_pcie_command(&held->command) ||
        held->command.value != npu_cold_rx_pcie_value(&plan) ||
        held->rx_event_steps != 2 || held->prior_rx_event_steps != 2 ||
        held->pcie_tail_steps || held->prior_pcie_tail_steps ||
        held->inode_steps || held->prior_inode_steps ||
        word(0x3e900178u) != 0x8400fdc4u || !neighbors_live() ||
        !npu_cold_txdone_plan_equal(&candidate->prior, &plan.prior) ||
        !(inode ? npu_emulation_desc10_prior_live_inode(&plan.prior) :
                  npu_emulation_desc10_prior_live_tail(&plan.prior)))
        return 0;
    for (i = 0; i < sizeof(held_setup) / 4; i++) {
        if (i == __builtin_offsetof(struct npu_cold_setup, sequence) / 4 ||
            (i >= __builtin_offsetof(struct npu_cold_setup, command) / 4 &&
             i < (__builtin_offsetof(struct npu_cold_setup, command) + sizeof(SETUP->command)) / 4) ||
            i == __builtin_offsetof(struct npu_cold_setup, rx_event_steps) / 4 ||
            i == __builtin_offsetof(struct npu_cold_setup, prior_rx_event_steps) / 4 ||
            i == __builtin_offsetof(struct npu_cold_setup, pcie_tail_steps) / 4 ||
            i == __builtin_offsetof(struct npu_cold_setup, prior_pcie_tail_steps) / 4)
            continue;
        if (inode && (i == __builtin_offsetof(struct npu_cold_setup, inode_steps) / 4 ||
                      i == __builtin_offsetof(struct npu_cold_setup, prior_inode_steps) / 4))
            continue;
        if (current[i] != held_setup[i])
            return 0;
    }
    c = prior();
    return npu_cold_rx_pcie_live(OWNER, &plan, 1, &c, word(NPU_COLD_RX_PCIE_METADATA)) &&
           (inode ? npu_cold_inode_inflight(SETUP) : npu_cold_pcie_tail_inflight(SETUP)) && neighbors_live();
}

int npu_emulation_rx_pcie_prior_live_tail(const struct npu_cold_rx_pcie_plan *candidate)
{
    return completed_prior_live(candidate, 0);
}

int npu_emulation_rx_pcie_prior_live_inode(const struct npu_cold_rx_pcie_plan *candidate)
{
    return completed_prior_live(candidate, 1);
}

static int owned(void)
{
    return lock_owned && context() && neighbors_live();
}

uint32_t npu_emulation_rx_pcie_reserve(uint32_t address, uint32_t value, uint32_t bytes)
{
    struct npu_cold_rx_pcie_context c = prior();

    if (!owned() || address != NPU_COLD_RX_PCIE_METADATA || bytes != 4 ||
        value != npu_cold_rx_pcie_value(&plan) ||
        npu_cold_rx_pcie_reserve(OWNER, &plan, 1, &c, address, bytes, value, word(address)) ||
        !owned())
        return fail();
    return 1;
}

uint32_t npu_emulation_rx_pcie_publish(uint32_t address, uint32_t bytes)
{
    struct npu_cold_rx_pcie_context c = prior();

    if (!owned() || address != NPU_COLD_RX_PCIE_METADATA || bytes != 4 ||
        npu_cold_rx_pcie_publish(OWNER, &plan, 1, &c, address, bytes, word(address)) || !owned())
        return fail();
    return 1;
}

uint32_t npu_emulation_rx_pcie_callback(struct npu_bootstrap_packet *packet)
{
    struct npu_bootstrap_packet snapshot;
    struct npu_cold_rx_pcie_context c;
    const volatile uint32_t *current = (const volatile void *)SETUP;
    uint32_t i, status, result = 0, acquired = 0, entered = 0;

    if ((packet->header & 15) != 10)
        return npu_original_rx_pcie_callback(packet);
    __asm__ volatile ("csrrci %0, mstatus, 8" : "=r"(status) :: "memory");
    snapshot = *packet;
    if (npu_emulation_rx_pcie_running || lock_owned || !npu_cold_rx_pcie_command(&snapshot))
        goto fault;
    npu_emulation_rx_pcie_running = entered = 1;
    npu_cold_txdone_plan_copy(&plan.prior, &DONE->plan);
    for (i = 0; i < sizeof(held_setup) / 4; i++)
        held_setup[i] = current[i];
    if (snapshot.value != npu_cold_rx_pcie_value(&plan) || !context())
        goto fault;
    if (((int (*)(const uint32_t *))(uintptr_t)0x840064b4u)(&lock_id))
        goto fault;
    lock_owned = acquired = 1;
    neighbors[0] = word(NPU_COLD_RX_PCIE_METADATA - 4);
    neighbors[1] = word(NPU_COLD_RX_PCIE_METADATA + 4);
    c = prior();
    if (!owned() || npu_cold_rx_pcie_begin(OWNER, &plan, 1, &c, word(NPU_COLD_RX_PCIE_METADATA)) || !owned())
        goto fault;
    result = npu_original_rx_pcie_callback(&snapshot);
    c = prior();
    if (result != 1 || !owned() ||
        npu_cold_rx_pcie_finish(OWNER, &plan, 1, &c, word(NPU_COLD_RX_PCIE_METADATA)) ||
        !npu_cold_rx_pcie_live(OWNER, &plan, 1, &c, word(NPU_COLD_RX_PCIE_METADATA)))
        goto fault;
    goto done;
fault:
    result = fail();
done:
    if (acquired) {
        __asm__ volatile ("fence iorw, iorw" ::: "memory");
        ((void (*)(const uint32_t *))(uintptr_t)0x8400651cu)(&lock_id);
        lock_owned = 0;
        if (!context() || !neighbors_live())
            result = fail();
    }
    if (entered)
        npu_emulation_rx_pcie_running = 0;
    __asm__ volatile ("csrw mstatus, %0" :: "r"(status) : "memory");
    return result;
}
