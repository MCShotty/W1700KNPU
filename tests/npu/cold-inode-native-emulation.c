/* Guard original API24 constructors; physical exclusion/drains remain external. */
#include "cold-setup.h"
#include "cold-inode.h"

extern struct npu_cold_setup npu_emulation_cold_setup_state;
extern struct npu_admission npu_emulation_admission_state;
extern struct npu_barrier npu_emulation_barrier_state;
extern struct npu_cold_pcie_tail_state npu_emulation_pcie_tail_state;
extern struct npu_cold_rx_pcie_state npu_emulation_rx_pcie_state;
extern struct npu_cold_tx_state npu_emulation_tx_state;
extern struct npu_cold_txdone_state npu_emulation_desc10_state;
extern struct npu_cold_rx_event_state npu_emulation_rx_event_state;
extern struct npu_cold_packet_state npu_emulation_packet_state;
extern int npu_emulation_pcie_tail_prior_live_inode(const struct npu_cold_pcie_tail_plan *);
extern int npu_emulation_pcie_tail_read_inode(void *, uint32_t, uint32_t, uint32_t *);
extern int npu_emulation_desc10_read(void *, uint32_t, uint32_t, uint32_t *);
extern uint32_t npu_original_inode_callback(struct npu_bootstrap_packet *);

struct npu_cold_inode_state npu_emulation_inode_state;
uint32_t npu_emulation_inode_running;
static struct npu_cold_inode_plan plan;
static uint32_t held_setup[sizeof(struct npu_cold_setup) / 4];
static uint32_t phase, lock_owned, neighbors_captured, icv_neighbors[2];
static uint8_t flag_neighbors[36];
static const uint32_t lock_id = 18;

#define SETUP (&npu_emulation_cold_setup_state)
#define OWNER (&npu_emulation_inode_state)
#define TAIL (&npu_emulation_pcie_tail_state)
#define DONE (&npu_emulation_desc10_state)
#define FLAGS 0x3e9046dcu

struct inode_frame {
    struct npu_bootstrap_packet command;
    uint32_t padding[3];
};
_Static_assert(sizeof(struct inode_frame) == 24, "original API24 frame span changed");

static uint32_t word(uint32_t address)
{
    return *(const volatile uint32_t *)(uintptr_t)address;
}

static uint32_t value(uint32_t address, uint32_t bytes)
{
    return bytes == 1 ? *(const volatile uint8_t *)(uintptr_t)address : word(address);
}

static void copy(void *destination, const void *source, uint32_t bytes)
{
    volatile uint8_t *to = destination;
    const volatile uint8_t *from = source;

    for (uint32_t i = 0; i < bytes; i++) to[i] = from[i];
}

static uint32_t fail(void)
{
    npu_cold_inode_fault(OWNER);
    npu_admission_fail(&npu_emulation_admission_state, &npu_emulation_barrier_state);
    return 0;
}

static int inode_read(void *opaque, uint32_t address, uint32_t bytes, uint32_t *result)
{
    uint32_t status;

    __asm__ volatile ("csrr %0, mstatus" : "=r"(status));
    if (status & 8 || opaque != OWNER || !result || npu_emulation_inode_running != 1 ||
        (bytes != 1 && bytes != 4) || (address & (bytes - 1)) ||
        plan.icv != NPU_COLD_INODE_ICV || plan.icv_bytes != NPU_COLD_INODE_ICV_BYTES)
        return 0;
    if (bytes == 4 && (address == 0x8401cfb8u || address == 0x8401cfbcu || address == 0x3e902ac0u)) {
        *result = word(address);
        return 1;
    }
    /* The core pins the complete validated plan around each read. This view
     * authorizes only fixed spans, never addresses from a mutable plan.
     */
    if ((address >= NPU_COLD_INODE_ICV && address - NPU_COLD_INODE_ICV < NPU_COLD_INODE_ICV_BYTES &&
         bytes <= NPU_COLD_INODE_ICV_BYTES - (address - NPU_COLD_INODE_ICV)) ||
        (address >= FLAGS && address - FLAGS < sizeof(flag_neighbors) &&
         bytes <= sizeof(flag_neighbors) - (address - FLAGS))) {
        *result = value(address, bytes);
        return 1;
    }
    return 0;
}

static struct npu_cold_inode_context prior(void)
{
    const struct npu_cold_inode_context c = {
        .pcie = TAIL,
        .prior = {.pcie = &npu_emulation_rx_pcie_state, .tx = &npu_emulation_tx_state,
            .prior = {.done = DONE, .rx = &npu_emulation_rx_event_state,
                .packets = &npu_emulation_packet_state, .read = npu_emulation_desc10_read,
                .opaque = DONE, .rx_readback = word(NPU_COLD_RX_EVENT_METADATA),
                .ready = *(const volatile uint8_t *)(uintptr_t)0x3e9046fau},
            .read = npu_emulation_pcie_tail_read_inode, .opaque = TAIL,
            .pcie_readback = word(NPU_COLD_RX_PCIE_METADATA)},
        .read = inode_read, .opaque = OWNER
    };

    return c;
}

static int context(void)
{
    const volatile uint32_t *current = (const volatile void *)SETUP;
    uint32_t status;

    __asm__ volatile ("csrr %0, mstatus" : "=r"(status));
    if (status & 8 || npu_emulation_inode_running != 1 || phase >= 2 ||
        !npu_cold_inode_inflight(SETUP) || SETUP->inode_steps != phase ||
        SETUP->command.header != (0x10u | npu_cold_inode_selector(phase)) ||
        SETUP->tx2_register != plan.prior.tx.host2 ||
        word(0x3e9001d8u) != 0x8400fc2cu ||
        word(0x8401cfb8u) != 0x109 || word(0x8401cfbcu) != NPU_COLD_INODE_ICV ||
        word(0x3e902ac0u) != NPU_COLD_INODE_ICV ||
        !npu_emulation_pcie_tail_prior_live_inode(&plan.prior))
        return 0;
    for (uint32_t i = 0; i < sizeof(held_setup) / 4; i++)
        if (current[i] != held_setup[i])
            return 0;
    return 1;
}

static int flag_effect(uint32_t address)
{
    return address == 0x3e9046e0u || address == 0x3e9046e1u ||
           (address >= 0x3e9046ecu && address < 0x3e9046f4u) ||
           address == 0x3e9046f5u || address == 0x3e9046f7u ||
           address == 0x3e9046f8u || address == 0x3e9046f9u;
}

static int capture_neighbors(void)
{
    if (neighbors_captured || OWNER->magic || phase || !npu_cold_inode_plan_valid(&plan))
        return 0;
    icv_neighbors[0] = word(plan.icv - 4);
    icv_neighbors[1] = word(plan.icv + plan.icv_bytes);
    for (uint32_t i = 0; i < sizeof(flag_neighbors); i++)
        flag_neighbors[i] = *(const volatile uint8_t *)(uintptr_t)(FLAGS + i);
    neighbors_captured = 1;
    return 1;
}

static int neighbors_live(void)
{
    if (neighbors_captured != 1 || word(plan.icv - 4) != icv_neighbors[0] ||
        word(plan.icv + plan.icv_bytes) != icv_neighbors[1])
        return 0;
    for (uint32_t i = 0; i < sizeof(flag_neighbors); i++)
        if (!flag_effect(FLAGS + i) &&
            *(const volatile uint8_t *)(uintptr_t)(FLAGS + i) != flag_neighbors[i])
            return 0;
    return 1;
}

static int owned(void)
{
    return lock_owned && context() && neighbors_live();
}

uint32_t npu_emulation_inode_reserve(uint32_t address, uint32_t expected, uint32_t bytes)
{
    struct npu_cold_inode_store store;
    struct npu_cold_inode_context c = prior();

    if (!owned() || npu_cold_inode_recipe(&plan, OWNER->committed, &store) ||
        address != store.address || bytes != store.bytes || expected != store.value ||
        npu_cold_inode_reserve(OWNER, &plan, 1, &c, address, bytes, expected, value(address, bytes)) || !owned())
        return fail();
    return 1;
}

uint32_t npu_emulation_inode_publish(uint32_t address, uint32_t bytes)
{
    struct npu_cold_inode_store store;
    struct npu_cold_inode_context c = prior();

    if (!owned() || npu_cold_inode_recipe(&plan, OWNER->published, &store) ||
        address != store.address || bytes != store.bytes ||
        npu_cold_inode_publish(OWNER, &plan, 1, &c, address, bytes, value(address, bytes)) || !owned())
        return fail();
    return 1;
}

uint32_t npu_emulation_inode_callback(struct npu_bootstrap_packet *packet)
{
    struct inode_frame frame;
    struct npu_cold_inode_context c;
    const volatile uint32_t *current = (const volatile void *)SETUP;
    uint32_t status, result = 0, acquired = 0, entered = 0;

    __asm__ volatile ("csrrci %0, mstatus, 8" : "=r"(status) :: "memory");
    frame.command = *packet;
    for (uint32_t i = 0; i < 3; i++) frame.padding[i] = 0;
    if (npu_emulation_inode_running || lock_owned)
        goto fault;
    npu_emulation_inode_running = entered = 1;
    phase = npu_cold_inode_command_step(&frame.command);
    if (phase >= 2)
        goto fault;
    if (!OWNER->magic) {
        if (phase || neighbors_captured)
            goto fault;
        copy(&plan.prior, &TAIL->plan, sizeof(plan.prior));
        plan.icv = NPU_COLD_INODE_ICV;
        plan.icv_bytes = NPU_COLD_INODE_ICV_BYTES;
    }
    for (uint32_t i = 0; i < sizeof(held_setup) / 4; i++) held_setup[i] = current[i];
    if (frame.command.header != SETUP->command.header || frame.command.api != SETUP->command.api ||
        frame.command.value != SETUP->command.value || !context())
        goto fault;
    /* Added checked-lane exclusion uses the stock lock primitive,not a stock constructor lock. */
    if (((int (*)(const uint32_t *))(uintptr_t)0x840064b4u)(&lock_id))
        goto fault;
    lock_owned = acquired = 1;
    if ((!OWNER->magic && !capture_neighbors()) || !owned())
        goto fault;
    c = prior();
    if (npu_cold_inode_begin(OWNER, &plan, 1, &c, frame.command.header & 15, frame.command.value) || !owned())
        goto fault;
    result = npu_original_inode_callback(&frame.command);
    c = prior();
    if (result != 1 || !owned() || frame.command.header != SETUP->command.header ||
        frame.command.api != SETUP->command.api || frame.command.value != SETUP->command.value ||
        frame.padding[0] || frame.padding[1] || frame.padding[2] ||
        npu_cold_inode_finish(OWNER, &plan, 1, &c) ||
        !npu_cold_inode_stage_live(OWNER, &plan, 1, &c, phase))
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
        if (!context() || !neighbors_live() || !npu_cold_inode_stage_live(OWNER, &plan, 1, &c, phase))
            result = fail();
    }
    if (entered) npu_emulation_inode_running = 0;
    __asm__ volatile ("csrw mstatus, %0" :: "r"(status) : "memory");
    return result;
}
