/* Raw CODE binding. The caller owns the pinned request, retained DMA backing
 * and coordinator exclusion; these accesses do not witness a physical drain. */
#include "bootstrap-v2.h"
#include "rro-session.h"
#include "rro-wire-native-abi.h"

extern struct npu_bootstrap npu_emulation_bootstrap_state;
extern struct npu_control_v2_session npu_emulation_control_v2_state;
extern struct npu_admission npu_emulation_admission_state;
extern struct npu_barrier npu_emulation_barrier_state;
extern struct npu_cold_setup npu_emulation_cold_setup_state;

struct npu_rro_session npu_emulation_rro_session_state;
static uint32_t last_extent = NPU_RRO_MAX_EXTENTS;

_Static_assert(sizeof(struct npu_rro_session) == NPU_RRO_NATIVE_SESSION_BYTES,
               "RRO session storage changed");
_Static_assert(NPU_RRO_NATIVE_BLOCK_TABLE + NPU_RRO_BLOCKS * 4u <= 0x3e90458cu,
               "RRO native tables overlap");
_Static_assert(NPU_RRO_NATIVE_SESSION_TABLE + 4u <= 0x3e904754u,
               "RRO table overlaps bootstrap SRAM");

static uint32_t load(const uint32_t *word)
{
    return __atomic_load_n(word, __ATOMIC_ACQUIRE);
}

static int irq_excluded(void)
{
    uint32_t status;

    __asm__ volatile ("csrr %0, mstatus" : "=r"(status) :: "memory");
    return !(status & 8u);
}

static int active_owner(void *opaque)
{
    const struct npu_rro_session *s = &npu_emulation_rro_session_state;
    const struct npu_admission *a = &npu_emulation_admission_state;
    const struct npu_barrier *b = &npu_emulation_barrier_state;
    const struct npu_control_v2_session *v2 = &npu_emulation_control_v2_state;
    const struct npu_bootstrap *boot = &npu_emulation_bootstrap_state;

    if (opaque != s || !irq_excluded() || s->magic != NPU_RRO_SESSION_MAGIC ||
        s->error || s->inflight != 1 || s->owner.magic != NPU_RRO_MAGIC ||
        load(&s->owner.error) || s->owner.cpu_joined ||
        (s->owner.phase != NPU_RRO_BUILDING && s->owner.phase != NPU_RRO_LIVE) ||
        s->owner.allocated > NPU_RRO_MAX_EXTENTS ||
        a->closed != 1 || a->active != 1 || a->fault ||
        a->nonce_lo != v2->nonce_lo || a->nonce_hi != v2->nonce_hi ||
        !(v2->nonce_lo || v2->nonce_hi) || !s->sequence ||
        v2->last_sequence != s->sequence ||
        s->plan.identity.boot_lo != v2->boot_lo ||
        s->plan.identity.boot_hi != v2->boot_hi ||
        s->plan.identity.nonce_lo != v2->nonce_lo ||
        s->plan.identity.nonce_hi != v2->nonce_hi ||
        boot->magic != NPU_BOOTSTRAP_MAGIC || boot->failed || boot->inflight ||
        boot->step != NPU_BOOTSTRAP_STEPS || boot->retained_mask != 0x1eu ||
        load(&b->request) != 1 || load(&b->fault) || load(&b->prepared) ||
        load(&b->released) || load(&b->armed))
        return 0;
    for (uint32_t i = 0; i < NPU_BARRIER_WORKERS; i++)
        if (load(&b->parked[i]) != 1 || load(&b->ready[i]))
            return 0;
    for (uint32_t i = 0; i < NPU_BARRIER_DOMAINS; i++)
        if (load(&b->drained[i]))
            return 0;
    for (uint32_t i = 0; i < NPU_ADMISSION_IRQ_WORDS; i++)
        if (a->deferred[i])
            return 0;
    return 1;
}

static int in_extent(const struct npu_rro_lifetime *owner, uint32_t slot,
                     uint32_t address, uint32_t bytes, uint32_t *offset,
                     uint32_t *role)
{
    const struct npu_rro_extent *item;
    uint32_t base;

    if (slot >= owner->allocated)
        return 0;
    item = &owner->extents[slot];
    if ((item->role != NPU_RRO_ELEMENT || item->bytes != NPU_RRO_BLOCK_BYTES) &&
        (item->role != NPU_RRO_SESSION || item->bytes != NPU_RRO_SESSION_BYTES))
        return 0;
    if (!item->dma_lo || item->dma_hi || (item->dma_lo & 3u))
        return 0;
    base = (item->dma_lo & 0x3fffffffu) | 0x40000000u;
    if (item->bytes > UINT32_MAX - base || address < base ||
        bytes > item->bytes || address - base > item->bytes - bytes)
        return 0;
    *offset = address - base;
    *role = item->role;
    return 1;
}

static int access_allowed(void *opaque, uint32_t address, uint32_t bytes,
                          int write, uint32_t value)
{
    const struct npu_rro_lifetime *owner = &npu_emulation_rro_session_state.owner;
    uint32_t offset, role, slot;

    if (!active_owner(opaque) || (bytes != 1 && bytes != 4) ||
        (address & (bytes - 1u)))
        return 0;
    if (bytes == 4 && address >= NPU_RRO_NATIVE_BLOCK_TABLE &&
        address - NPU_RRO_NATIVE_BLOCK_TABLE < NPU_RRO_BLOCKS * 4u) {
        slot = (address - NPU_RRO_NATIVE_BLOCK_TABLE) / 4u +
               (owner->plan.profile == NPU_RRO_V3 ? 2u : 0u);
        return slot < owner->allocated && owner->extents[slot].role == NPU_RRO_ELEMENT &&
               (!write || (owner->phase == NPU_RRO_BUILDING &&
                           value == ((owner->extents[slot].dma_lo & 0x3fffffffu) | 0x40000000u)));
    }
    if (bytes == 4 && address == NPU_RRO_NATIVE_SESSION_TABLE) {
        slot = npu_rro_extent_count(owner->plan.profile);
        return slot && slot <= owner->allocated &&
               owner->extents[slot - 1u].role == NPU_RRO_SESSION &&
               (!write || (owner->phase == NPU_RRO_BUILDING &&
                           value == ((owner->extents[slot - 1u].dma_lo & 0x3fffffffu) |
                                     0x40000000u)));
    }
    if (!in_extent(owner, last_extent, address, bytes, &offset, &role)) {
        for (uint32_t i = 0; i < owner->allocated; i++)
            if (in_extent(owner, i, address, bytes, &offset, &role)) {
                last_extent = i;
                break;
            }
        if (last_extent >= owner->allocated ||
            !in_extent(owner, last_extent, address, bytes, &offset, &role))
            return 0;
    }
    if (bytes == 1)
        return (offset & 7u) == 7u && (!write || value == 0xffu);
    return role == NPU_RRO_ELEMENT &&
           (!write || (owner->phase == NPU_RRO_BUILDING && !value));
}

static int read_memory(void *opaque, uint32_t address, uint32_t bytes, uint32_t *value)
{
    if (!value || !access_allowed(opaque, address, bytes, 0, 0))
        return 0;
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    *value = bytes == 1 ? *(const volatile uint8_t *)(uintptr_t)address :
                          *(const volatile uint32_t *)(uintptr_t)address;
    return active_owner(opaque);
}

static int write_memory(void *opaque, uint32_t address, uint32_t bytes, uint32_t value)
{
    if (!access_allowed(opaque, address, bytes, 1, value))
        return 0;
    if (bytes == 1)
        *(volatile uint8_t *)(uintptr_t)address = (uint8_t)value;
    else
        *(volatile uint32_t *)(uintptr_t)address = value;
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    return active_owner(opaque);
}

static const struct npu_rro_native_context native_context = {
    read_memory, write_memory, &npu_emulation_rro_session_state
};

int npu_emulation_rro_mailbox(void *packet, uint32_t bytes)
{
    const struct npu_bootstrap *boot = &npu_emulation_bootstrap_state;
    const struct npu_bootstrap_range *request = &boot->plan.region[NPU_BOOT_REQUEST];
    uintptr_t alias = (request->base & 0x3fffffffu) | 0x40000000u;

    if (bytes != NPU_RRO_WIRE_SIZE || (uintptr_t)packet != alias ||
        !irq_excluded() || !npu_bootstrap_v2_transport(boot, request->base, bytes, 1))
        return 0;
    return npu_rro_session_dispatch(&npu_emulation_rro_session_state,
        &npu_emulation_control_v2_state, &npu_emulation_admission_state,
        &npu_emulation_barrier_state, boot, &npu_emulation_cold_setup_state,
        packet, bytes, &native_context);
}

int npu_emulation_rro_cold_ready(void)
{
    const struct npu_admission *a = &npu_emulation_admission_state;
    const struct npu_barrier *b = &npu_emulation_barrier_state;

    return irq_excluded() && a->closed == 1 && !a->active && !a->fault &&
           load(&b->request) == 1 && !load(&b->fault) &&
           !npu_emulation_bootstrap_state.failed &&
           npu_rro_session_cold_ready(&npu_emulation_rro_session_state);
}
