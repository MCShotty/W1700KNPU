/* Original selector0/API22 store; physical DMA visibility remains external. */
#include "cold-setup.h"

extern struct npu_cold_setup npu_emulation_cold_setup_state;
extern struct npu_admission npu_emulation_admission_state;
extern struct npu_barrier npu_emulation_barrier_state;
extern int npu_emulation_txbuf_prior_live(void);
extern int npu_emulation_txbuf_prior_live_packets(uint32_t packets, uint32_t full);
extern int npu_emulation_txbuf_prior_live_done(uint32_t packets);
extern uint32_t npu_original_rx_event_callback(struct npu_bootstrap_packet *);

struct npu_cold_rx_event_state npu_emulation_rx_event_state;
static struct npu_cold_rx_event_plan plan;
static uint32_t held_setup[sizeof(struct npu_cold_setup) / 4], neighbors[2], lock_owned;
static const uint32_t lock_id = 18;

#define SETUP (&npu_emulation_cold_setup_state)
#define OWNER (&npu_emulation_rx_event_state)

static uint32_t word(uint32_t address)
{
    return *(const volatile uint32_t *)(uintptr_t)address;
}

static uint32_t fail(void)
{
    npu_cold_rx_event_fault(OWNER);
    npu_admission_fail(&npu_emulation_admission_state, &npu_emulation_barrier_state);
    return 0;
}

static int context(void)
{
    const volatile uint32_t *current = (const volatile void *)SETUP;
    uint32_t i, status;

    __asm__ volatile ("csrr %0, mstatus" : "=r"(status));
    if (status & 8 || !npu_emulation_txbuf_prior_live() ||
        !npu_cold_rx_event_plan_valid(&plan) ||
        SETUP->rx_event != plan.ring || SETUP->prior_rx_event != plan.ring ||
        SETUP->pending_rx_event != plan.ring || SETUP->rx_event_steps || SETUP->prior_rx_event_steps ||
        SETUP->command.header != 0x10 || SETUP->command.api != 22 ||
        SETUP->command.value != plan.ring || word(0x3e9001d0u) != 0x8400fbb4u)
        return 0;
    for (i = 0; i < sizeof(held_setup) / 4; i++)
        if (current[i] != held_setup[i])
            return 0;
    return 1;
}

static int neighbors_live(void)
{
    return word(NPU_COLD_RX_EVENT_METADATA - 4) == neighbors[0] &&
           word(NPU_COLD_RX_EVENT_METADATA + 4) == neighbors[1];
}

static int prior_live(uint32_t packets, uint32_t full, uint32_t completed)
{
    const struct npu_cold_setup *prior = (const void *)held_setup;
    const volatile uint32_t *current = (const volatile void *)SETUP;
    uint32_t i, status;

    __asm__ volatile ("csrr %0, mstatus" : "=r"(status));
    if (status & 8 || lock_owned || SETUP->sequence <= prior->sequence ||
        (completed ? !npu_cold_rx_pcie_command(&SETUP->command) ||
         SETUP->command.value != SETUP->endpoint_base + NPU_COLD_RX_PCIE_REGISTER ||
         SETUP->rx_event_steps != 2 || SETUP->prior_rx_event_steps != 2 :
         SETUP->command.header != 0x1a || SETUP->command.api != 1 || SETUP->command.value != 512 ||
         SETUP->rx_event_steps != 1 || SETUP->prior_rx_event_steps != 1) ||
        prior->rx_event_steps || prior->prior_rx_event_steps ||
        prior->command.header != 0x10 || prior->command.api != 22 || prior->command.value != plan.ring ||
        !(completed ? npu_emulation_txbuf_prior_live_done(packets) :
          npu_emulation_txbuf_prior_live_packets(packets, full)) || !neighbors_live() ||
        word(0x3e9001d0u) != 0x8400fbb4u ||
        !npu_cold_rx_event_live(OWNER, &plan, 1, word(NPU_COLD_RX_EVENT_METADATA)))
        return 0;
    for (i = 0; i < sizeof(held_setup) / 4; i++) {
        if (i == __builtin_offsetof(struct npu_cold_setup, sequence) / 4 ||
            (i >= __builtin_offsetof(struct npu_cold_setup, command) / 4 &&
             i < (__builtin_offsetof(struct npu_cold_setup, command) + sizeof(SETUP->command)) / 4) ||
            i == __builtin_offsetof(struct npu_cold_setup, rx_event_steps) / 4 ||
            i == __builtin_offsetof(struct npu_cold_setup, prior_rx_event_steps) / 4)
            continue;
        if (current[i] != held_setup[i])
            return 0;
    }
    return 1;
}

int npu_emulation_rx_event_prior_live(uint32_t packets, uint32_t full)
{
    return prior_live(packets, full, 0);
}

int npu_emulation_rx_event_prior_live_done(uint32_t packets)
{
    return prior_live(packets, 1, 1);
}

static int owned(void)
{
    return lock_owned && context() && neighbors_live();
}

uint32_t npu_emulation_rx_event_reserve(uint32_t address, uint32_t data, uint32_t width)
{
    if (!owned() || address != NPU_COLD_RX_EVENT_METADATA || width != 4 ||
        data != npu_cold_rx_event_value(plan.ring) ||
        npu_cold_rx_event_reserve(OWNER, &plan, 1, address, width, data, word(address)) || !owned())
        return fail();
    return 1;
}

uint32_t npu_emulation_rx_event_publish(uint32_t address, uint32_t width)
{
    if (!owned() || address != NPU_COLD_RX_EVENT_METADATA || width != 4 ||
        npu_cold_rx_event_publish(OWNER, &plan, 1, address, width, word(address)) || !owned())
        return fail();
    return 1;
}

uint32_t npu_emulation_rx_event_callback(struct npu_bootstrap_packet *packet)
{
    struct npu_bootstrap_packet snapshot;
    const volatile uint32_t *current = (const volatile void *)SETUP;
    uint32_t status, i, result = 0, acquired = 0;

    __asm__ volatile ("csrrci %0, mstatus, 8" : "=r"(status) :: "memory");
    if (lock_owned)
        goto fault;
    snapshot = *packet;
    npu_cold_txbuf_plan_copy(&plan.prior, &SETUP->txbuf);
    plan.prior.arena = SETUP->descriptor_arena;
    plan.ring = SETUP->rx_event;
    for (i = 0; i < sizeof(held_setup) / 4; i++)
        held_setup[i] = current[i];
    if (!npu_cold_rx_event_command(&snapshot) || snapshot.value != plan.ring || !context())
        goto fault;
    if (((int (*)(const uint32_t *))(uintptr_t)0x840064b4u)(&lock_id))
        goto fault;
    lock_owned = acquired = 1;
    neighbors[0] = word(NPU_COLD_RX_EVENT_METADATA - 4);
    neighbors[1] = word(NPU_COLD_RX_EVENT_METADATA + 4);
    if (!owned() || npu_cold_rx_event_begin(OWNER, &plan, 1, word(NPU_COLD_RX_EVENT_METADATA)) || !owned())
        goto fault;
    result = npu_original_rx_event_callback(&snapshot);
    if (result != 1 || !owned() ||
        npu_cold_rx_event_finish(OWNER, &plan, 1, word(NPU_COLD_RX_EVENT_METADATA)) ||
        !npu_cold_rx_event_live(OWNER, &plan, 1, word(NPU_COLD_RX_EVENT_METADATA)))
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
    __asm__ volatile ("csrw mstatus, %0" :: "r"(status) : "memory");
    return result;
}
