/* Unpromoted binding for hart7's bridge allocation call only. Core0 callers
 * require mailbox-safe failure handling before they can use this binding. */
#include "allocator.h"
#include "barrier.h"
#include <stddef.h>

_Static_assert(sizeof(void *) == 4, "RV32 binding");
_Static_assert(offsetof(struct npu_allocator_state, count) == 8, "native count");
_Static_assert(offsetof(struct npu_allocator_state, used) == 20, "native cursor");
_Static_assert(offsetof(struct npu_allocator_state, entries) == 24, "native entries");

extern struct npu_barrier npu_emulation_barrier_state;

typedef uint32_t (*native_hart_id)(void);
typedef int (*native_lock)(uint32_t *lock_id);

static const struct npu_allocator_layout layout = {
    .base = 0x3e800000u,
    .bytes = 0x78000u,
    .tables = {
        (const struct npu_allocator_definition *)(uintptr_t)0x8401b224u,
        (const struct npu_allocator_definition *)(uintptr_t)0x8401cfc8u,
    },
    .lengths = {6, 18},
};

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

__attribute__((noreturn, noinline)) static void failure_hold(void)
{
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    npu_barrier_fail(&npu_emulation_barrier_state);
    for (;;) {
        __asm__ volatile (".global npu_emulation_allocator_fault_park\n"
                          "npu_emulation_allocator_fault_park:\n nop" ::: "memory");
    }
}

uint32_t npu_emulation_bridge_allocate(uint32_t type)
{
    struct npu_allocator_state *state = (void *)(uintptr_t)0x3e901bccu;
    const struct npu_allocator_lock lock = {state, acquire, release};
    struct npu_allocator_result result;
    uint32_t status;

    __asm__ volatile ("csrrci %0, mstatus, 8" : "=r"(status) :: "memory");
    if (((native_hart_id)(uintptr_t)0x84004212u)() != 7 || type != 0x81 ||
        __atomic_load_n(&npu_emulation_barrier_state.fault, __ATOMIC_ACQUIRE))
        failure_hold();
    result = npu_allocator_allocate(state, &layout, &lock, type, 0);
    if (result.status != NPU_ALLOCATOR_OK ||
        __atomic_load_n(&npu_emulation_barrier_state.fault, __ATOMIC_ACQUIRE))
        failure_hold();
    __asm__ volatile ("csrw mstatus, %0" :: "r"(status) : "memory");
    return result.address;
}
