/* Original GET binding; physical ownership, cache visibility and drains stay external. */
#include "allocator.h"
#include "cold-setup.h"
#include "cold-descriptor.h"
#include "cold-tx.h"
#include "cold-indication.h"
#include "cold-packet.h"
#include "cold-page.h"

extern struct npu_bootstrap npu_emulation_bootstrap_state;
extern struct npu_admission npu_emulation_admission_state;
extern struct npu_barrier npu_emulation_barrier_state;
extern struct npu_cold_setup npu_emulation_cold_setup_state;
extern struct npu_cold_tx_state npu_emulation_tx_state;
extern struct npu_cold_indication_state npu_emulation_indication_state;
extern struct npu_cold_packet_state npu_emulation_packet_state;
extern struct npu_cold_page_state npu_emulation_page_state;
extern int npu_emulation_cold_arena_live(void);
extern uint32_t npu_original_descriptor_callback(struct npu_bootstrap_packet *);

struct npu_cold_descriptor_state npu_emulation_descriptor_state;
static uint32_t native_arena, allocation_count, allocation_used, record_index, lock_owned;
static uint32_t identity[5], getter_step, slots[8];
static const uint32_t lock_id = 18;

#define SETUP (&npu_emulation_cold_setup_state)
#define OWNER (&npu_emulation_descriptor_state)
#define TX (&npu_emulation_tx_state)
#define IND (&npu_emulation_indication_state)
#define PKT (&npu_emulation_packet_state)
#define BA (&npu_emulation_page_state)
#define METADATA ((const struct npu_allocator_state *)(uintptr_t)0x3e901bccu)

static uint32_t word(uint32_t address)
{
    return *(const volatile uint32_t *)(uintptr_t)address;
}

static uint32_t slot(uint32_t step)
{
    static const uint32_t addresses[] = {0x3e902ab0, 0x3e902ce0, 0x3e902a94, 0x3e902aa4,
                                        0x3e904638, 0x3e902aa0, 0x3e9021ec, 0x3e90459c};

    return addresses[step];
}

static uint32_t fail(void)
{
    npu_cold_descriptor_fault(OWNER);
    npu_admission_fail(&npu_emulation_admission_state, &npu_emulation_barrier_state);
    return 0;
}

static int prior_context(uint32_t packets)
{
    static const uint32_t profile[] = {1536, 1024, 256, 512, 1024};
    static const uint32_t types[] = {1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 65535};
    static const uint32_t offsets[] = {0, 0x22020, 0x6020, 0x26040, 0x1f020,
                                      0x18020, 0x19020, 0x1b020, 0x8020, 0x2a040, 0};
    uint32_t i;

    if (!npu_emulation_cold_arena_live() || SETUP->failed || SETUP->inflight != 1 ||
        SETUP->completed != NPU_COLD_COMPLETED_MASK || SETUP->prior_completed != NPU_COLD_COMPLETED_MASK ||
        SETUP->descriptor_arena != SETUP->prior_descriptor_arena ||
        SETUP->endpoint_base != SETUP->prior_base || SETUP->endpoint_bytes != SETUP->prior_bytes ||
        *(const volatile uint8_t *)(uintptr_t)0x3e90390eu != 2 ||
        METADATA->lock_id != 18 || METADATA->count > NPU_ALLOCATOR_ENTRIES ||
        TX->magic != NPU_COLD_TX_MAGIC || TX->epoch != 1 || TX->fault || TX->active ||
        TX->reserved != 7 || TX->completed != 7 || TX->committed != 11 || TX->published != 11 ||
        TX->stage != 2 || TX->plan.arena != word(0x3e9030fcu) ||
        TX->plan.arena_bytes != NPU_COLD_DESCRIPTOR_ARENA_BYTES ||
        TX->plan.endpoint_base != SETUP->endpoint_base || TX->plan.endpoint_bytes != SETUP->endpoint_bytes ||
        TX->plan.host0 != SETUP->endpoint_base + NPU_COLD_TX_REG0 ||
        SETUP->tx2_register != TX->plan.host2 || SETUP->prior_tx2_register != TX->plan.host2 ||
        (TX->plan.host2 != SETUP->endpoint_base + NPU_COLD_TX_REG2 &&
         TX->plan.host2 != SETUP->endpoint_base + NPU_COLD_TX_REG2 + NPU_COLD_TX_HIF2) ||
        TX->plan.host2 - SETUP->endpoint_base > SETUP->endpoint_bytes - 12 ||
        *(const volatile uint16_t *)(uintptr_t)0x3e903978u ||
        *(const volatile uint16_t *)(uintptr_t)0x3e9021f4u ||
        IND->magic != NPU_COLD_INDICATION_MAGIC || IND->epoch != 1 || IND->fault || IND->active ||
        IND->committed != 1536 || IND->published != 1536 || IND->count != 1536 ||
        IND->base != word(0x3e9030fcu) + 0x1f020u ||
        PKT->magic != NPU_COLD_PACKET_MAGIC || PKT->epoch != 1 || PKT->fault ||
        PKT->count != packets || PKT->head != packets ||
        PKT->packet_base != npu_emulation_bootstrap_state.plan.region[NPU_BOOT_PKT].base ||
        PKT->packet_bytes != npu_emulation_bootstrap_state.plan.region[NPU_BOOT_PKT].bytes ||
        BA->magic != NPU_COLD_PAGE_MAGIC || BA->epoch != 1 || BA->fault || BA->count != 1792 || BA->head != 1792 ||
        BA->packet_base != npu_emulation_bootstrap_state.plan.region[NPU_BOOT_BA].base ||
        BA->packet_bytes != npu_emulation_bootstrap_state.plan.region[NPU_BOOT_BA].bytes ||
        word(0x8401cfc8u) != 1 || word(0x8401cfccu) != NPU_COLD_DESCRIPTOR_ARENA_BYTES)
        return 0;
    for (i = 0; i < 5; i++)
        if (SETUP->counts[i] != profile[i] || SETUP->prior_counts[i] != profile[i])
            return 0;
    for (i = 0; i < 11; i++)
        if (word(0x8401cf18u + i * 8) != types[i] || word(0x8401cf1cu + i * 8) != offsets[i])
            return 0;
    return 1;
}

static int context(void)
{
    return getter_step < 8 && SETUP->descriptor_gets == getter_step &&
           SETUP->prior_descriptor_gets == getter_step &&
           SETUP->command.header == (0x30u | npu_cold_descriptor_selector(getter_step)) &&
           SETUP->command.api == 4 && !SETUP->command.value && prior_context(2560);
}

static int arena_pinned(void)
{
    const struct npu_allocator_entry *entry;
    uint32_t i;

    if (!npu_cold_descriptor_arena_valid(native_arena) ||
        word(0x3e9030fcu) != native_arena ||
        METADATA->count != allocation_count || METADATA->used != allocation_used ||
        record_index >= METADATA->count)
        return 0;
    entry = &METADATA->entries[record_index];
    if (entry->type != 1 || entry->reserved || entry->address != native_arena)
        return 0;
    for (i = 0; i < 8; i++)
        if (slots[i] != native_arena + npu_cold_descriptor_offset(i) || word(slot(i)) != slots[i])
            return 0;
    return word(0x3e904700u) == TX->plan.host0 && word(0x3e9046fcu) == TX->plan.host2 &&
           word(0x3e900bc0u) == 8192 &&
           word(0x1fc08030u) == (native_arena & 0x1fffffffu) &&
           word(0x1fc08034u) == ((native_arena + 0x22020u) & 0x1fffffffu) &&
           word(0x1fc48030u) == ((native_arena + 0x22020u) & 0x1fffffffu) &&
           word(0x1fc48034u) == ((native_arena + 0x4a040u) & 0x1fffffffu);
}

static int pinned(void)
{
    return context() && arena_pinned() &&
           (getter_step ? SETUP->descriptor_arena == native_arena : !SETUP->descriptor_arena) &&
           SETUP->sequence == identity[0] && SETUP->boot_lo == identity[1] &&
           SETUP->boot_hi == identity[2] && SETUP->nonce_lo == identity[3] && SETUP->nonce_hi == identity[4];
}

static int prior_live_packets(uint32_t gets, uint32_t packets, uint32_t successor)
{
    uint32_t count = gets == 7 ? 512 : 1536, tx = gets == 7 ? 1 : 3;

    return successor <= 3 && (gets == 7 || gets == 8) && packets >= 2560 && packets <= 3072 &&
           (successor == 3 ? gets == 8 && packets == 3072 && npu_cold_inode_inflight(SETUP) :
            successor == 2 ? gets == 8 && packets == 3072 && npu_cold_pcie_tail_inflight(SETUP) :
            successor == 1 ? gets == 8 && packets == 3072 &&
            npu_cold_rx_pcie_command(&SETUP->command) &&
            SETUP->command.value == SETUP->endpoint_base + NPU_COLD_RX_PCIE_REGISTER &&
            SETUP->rx_event_steps == 2 && SETUP->prior_rx_event_steps == 2 :
            packets == 2560 || (gets == 8 && SETUP->command.header == 0x1a &&
            SETUP->command.api == 1 && SETUP->command.value == 512 &&
            SETUP->rx_event_steps == 1 && SETUP->prior_rx_event_steps == 1)) &&
           prior_context(packets) && arena_pinned() &&
           SETUP->descriptor_gets == gets && SETUP->prior_descriptor_gets == gets &&
           SETUP->descriptor_arena == native_arena &&
           SETUP->boot_lo == identity[1] && SETUP->boot_hi == identity[2] &&
           SETUP->nonce_lo == identity[3] && SETUP->nonce_hi == identity[4] &&
           OWNER->magic == NPU_COLD_DESCRIPTOR_MAGIC && OWNER->epoch == 1 && !OWNER->fault &&
           !OWNER->active && OWNER->next == gets && OWNER->completed == (1u << gets) - 1 &&
           OWNER->arena == native_arena && OWNER->reserved_tx == tx && OWNER->completed_tx == tx &&
           OWNER->committed == count && OWNER->published == count;
}

int npu_emulation_descriptor_prior_live_packets(uint32_t gets, uint32_t packets)
{
    return prior_live_packets(gets, packets, 0);
}

/* The completed-DESC10 caller has verified its retained owner and supplies
 * the owner-derived count. This entry does not grant dispatch/store authority.
 */
int npu_emulation_descriptor_prior_live_done(uint32_t packets)
{
    return prior_live_packets(8, packets, 1);
}

int npu_emulation_descriptor_prior_live_tail(uint32_t packets)
{
    return prior_live_packets(8, packets, 2);
}

int npu_emulation_descriptor_prior_live_inode(uint32_t packets)
{
    return prior_live_packets(8, packets, 3);
}

int npu_emulation_descriptor_prior_live(uint32_t gets)
{
    return npu_emulation_descriptor_prior_live_packets(gets, 2560);
}

static int owned(void)
{
    return lock_owned && pinned();
}

static int field(uint32_t address, uint32_t index)
{
    uint32_t first = getter_step == 6 ? 0 : 512, limit = getter_step == 6 ? 512 : 1536;

    return getter_step >= 6 && getter_step < 8 && OWNER->next == getter_step &&
           index >= first && index < limit && address == slots[getter_step] + 4 + (index - first) * 16;
}

uint32_t npu_emulation_descriptor_reserve(uint32_t address, uint32_t value)
{
    if (!owned() || !field(address, OWNER->committed) ||
        npu_cold_descriptor_reserve(OWNER, native_arena, 1, address, value, word(address)) || !owned())
        return fail();
    return 1;
}

uint32_t npu_emulation_descriptor_publish(uint32_t address)
{
    if (!owned() || !field(address, OWNER->published) ||
        npu_cold_descriptor_publish(OWNER, native_arena, 1, address, word(address)) || !owned())
        return fail();
    return 1;
}

uint32_t npu_emulation_descriptor_callback(struct npu_bootstrap_packet *packet)
{
    struct npu_bootstrap_packet snapshot;
    const volatile uint32_t *descriptors;
    uint32_t status, i, matches = 0, result = 0, acquired = 0;

    __asm__ volatile ("csrrci %0, mstatus, 8" : "=r"(status) :: "memory");
    snapshot = *packet;
    getter_step = npu_cold_descriptor_command_step(&snapshot);
    if (lock_owned || !context())
        goto fault;
    if (((int (*)(const uint32_t *))(uintptr_t)0x840064b4u)(&lock_id))
        goto fault;
    lock_owned = 1;
    acquired = 1;
    if (!getter_step) {
        native_arena = word(0x3e9030fcu);
        allocation_count = METADATA->count;
        allocation_used = METADATA->used;
        for (i = 0; i < METADATA->count; i++) {
            const struct npu_allocator_entry *entry = &METADATA->entries[i];

            if (entry->type == 1 && !entry->reserved && entry->address == native_arena) {
                record_index = i;
                matches++;
            }
        }
        if (matches != 1)
            goto fault;
        for (i = 0; i < 8; i++)
            slots[i] = word(slot(i));
    }
    identity[0] = SETUP->sequence;
    identity[1] = SETUP->boot_lo;
    identity[2] = SETUP->boot_hi;
    identity[3] = SETUP->nonce_lo;
    identity[4] = SETUP->nonce_hi;
    if (!owned())
        goto fault;
    descriptors = getter_step >= 6 ? (const volatile void *)(uintptr_t)slots[getter_step] : 0;
    if (npu_cold_descriptor_begin(OWNER, native_arena, 1, snapshot.header & 15, descriptors) || !owned())
        goto fault;
    result = npu_original_descriptor_callback(&snapshot);
    if (result != 1 || !owned() ||
        npu_cold_descriptor_finish(OWNER, native_arena, 1, snapshot.value, descriptors))
        goto fault;
    goto done;
fault:
    result = fail();
done:
    if (acquired) {
        __asm__ volatile ("fence iorw, iorw" ::: "memory");
        ((void (*)(const uint32_t *))(uintptr_t)0x8400651cu)(&lock_id);
        lock_owned = 0;
        if (!pinned())
            result = fail();
    }
    if (result == 1)
        packet->value = snapshot.value;
    __asm__ volatile ("csrw mstatus, %0" :: "r"(status) : "memory");
    return result;
}
