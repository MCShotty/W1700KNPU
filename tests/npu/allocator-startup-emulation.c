/* Unpromoted cold-start binding. Active callback failure handling and physical
 * containment are separate contracts, not supplied by the coordinator idle. */
#include "allocator.h"
#include "admission.h"
#include "bootstrap.h"

extern struct npu_barrier npu_emulation_barrier_state;
extern struct npu_admission npu_emulation_admission_state;
extern struct npu_bootstrap npu_emulation_bootstrap_state;
extern void npu_emulation_mailbox(uint32_t source);
extern void npu_emulation_idle(void) __attribute__((noreturn));

#define BARRIER (&npu_emulation_barrier_state)
#define ADMISSION (&npu_emulation_admission_state)
#define BOOTSTRAP (&npu_emulation_bootstrap_state)

typedef uint32_t (*native_hart_id)(void);
typedef int (*native_lock)(uint32_t *lock_id);

#ifdef NPU_EMULATION_COMMAND_RING
__attribute__((section(".command_ring")))
uint32_t npu_emulation_command_ring[0x8010 / sizeof(uint32_t)] = {0xfe};

static const struct npu_allocator_entry placements[] = {
    {0x19, 0, NPU_EMULATION_COMMAND_RING},
};
#endif

static const struct npu_allocator_layout layout = {
    .base = 0x3e800000u,
    .bytes = 0x78000u,
    .tables = {
        (const struct npu_allocator_definition *)(uintptr_t)0x8401b224u,
        (const struct npu_allocator_definition *)(uintptr_t)0x8401cfc8u,
    },
    .lengths = {6, 18},
#ifdef NPU_EMULATION_COMMAND_RING
    .placements = placements,
    .placement_count = sizeof(placements) / sizeof(placements[0]),
#endif
};

static uint32_t load(const uint32_t *word)
{
    return __atomic_load_n(word, __ATOMIC_ACQUIRE);
}

static uint32_t expected_type(uint32_t hart, uint32_t caller)
{
    if (hart == 7)
        return caller == 0x8400148au ? 0x81u : UINT32_MAX;
    if (hart)
        return UINT32_MAX;
    switch (caller) {
    case 0x84005a34u: return 0x89u;
    case 0x84004ecau: return 0x8au;
    case 0x84004eeeu: return 0x12u;
    case 0x84004f2cu: return 0x1du;
    case 0x8400b932u: return 1u;
    case 0x8400a376u: return 0x0bu;
    case 0x8400bab8u: return 0x19u;
    default: return UINT32_MAX;
    }
}

static int acquire(void *context)
{
    struct npu_allocator_state *state = context;

    if (state->lock_id != 18)
        return -1;
    return ((native_lock)(uintptr_t)0x840064b4u)(&state->lock_id);
}

static void release(void *context)
{
    struct npu_allocator_state *state = context;

    ((native_lock)(uintptr_t)0x8400651cu)(&state->lock_id);
}

static int control_available(uint32_t hart, uint32_t status)
{
    uint32_t mie;

    __asm__ volatile ("csrr %0, mie" : "=r"(mie));
    return !hart && (status & 8) && (mie & 0x800) && !ADMISSION->active &&
           *(const volatile uint32_t *)(uintptr_t)0x3e901870u ==
               (uint32_t)(uintptr_t)npu_emulation_mailbox &&
           (*(const volatile uint32_t *)(uintptr_t)0x0c002000u & (1u << 9));
}

__attribute__((noreturn, noinline)) static void fail(uint32_t hart, uint32_t status,
                                                    int service)
{
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    if (!hart) {
        npu_admission_fail(ADMISSION, BARRIER);
        if (service) {
            __asm__ volatile ("csrw mstatus, %0" :: "r"(status) : "memory");
            npu_emulation_idle();
        }
    } else {
        npu_barrier_fail(BARRIER);
    }
    for (;;) {
        __asm__ volatile (".global npu_emulation_allocator_startup_hold\n"
                          "npu_emulation_allocator_startup_hold:\n nop" ::: "memory");
    }
}

uint32_t npu_emulation_startup_allocate(uint32_t type, uint32_t caller)
{
    struct npu_allocator_state *state = (void *)(uintptr_t)0x3e901bccu;
    const struct npu_allocator_lock lock = {state, acquire, release};
    struct npu_allocator_result result;
    uint32_t status, hart;
    int service;

    __asm__ volatile ("csrrci %0, mstatus, 8" : "=r"(status) :: "memory");
    hart = ((native_hart_id)(uintptr_t)0x84004212u)();
    service = control_available(hart, status);
    if (type >= NPU_ALLOCATOR_TYPES || expected_type(hart, caller) != type ||
        load(&BARRIER->fault) || load(&BARRIER->request) != 1 ||
        load(&BARRIER->prepared) || load(&BARRIER->released) || load(&BARRIER->armed) ||
        ADMISSION->closed != 1 || ADMISSION->active || ADMISSION->fault ||
        BOOTSTRAP->magic != NPU_BOOTSTRAP_MAGIC || BOOTSTRAP->failed || BOOTSTRAP->inflight ||
        load(&BARRIER->parked[hart]) || (!hart && !service))
        fail(hart, status, service);
    result = npu_allocator_allocate(state, &layout, &lock, type, type < 0x81);
    if (result.status != NPU_ALLOCATOR_OK || load(&BARRIER->fault))
        fail(hart, status, service);
    __asm__ volatile ("csrw mstatus, %0" :: "r"(status) : "memory");
    return result.address;
}
