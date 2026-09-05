/* Unpromoted binding for the pinned firmware's legacy void copy helper. */
#include "barrier.h"
#include "gdma.h"

extern struct npu_barrier npu_emulation_barrier_state;

#ifndef NPU_GDMA_POLL_LIMIT
#define NPU_GDMA_POLL_LIMIT 65536u
#endif

void npu_emulation_gdma_copy(uint32_t channel, uint32_t source,
                              uint32_t destination, uint32_t length)
{
    struct npu_barrier *barrier = &npu_emulation_barrier_state;
    uint32_t status, hart;
    enum npu_gdma_result result = NPU_GDMA_INVALID;

    __asm__ volatile ("csrrci %0, mstatus, 8" : "=r"(status) :: "memory");
    hart = ((uint32_t (*)(void))0x84004212u)();
    if (!__atomic_load_n(&barrier->fault, __ATOMIC_ACQUIRE))
        result = npu_gdma_copy(hart, channel, source, destination, length, NPU_GDMA_POLL_LIMIT);
    if (result != NPU_GDMA_OK || __atomic_load_n(&barrier->fault, __ATOMIC_ACQUIRE)) {
        npu_barrier_fail(barrier);
        /* No ACK, refresh, return or timeout-based release from this context. */
        for (;;) {
            __asm__ volatile (".global npu_emulation_gdma_fault_park\n"
                              "npu_emulation_gdma_fault_park:\n nop" ::: "memory");
        }
    }
    __asm__ volatile ("csrw mstatus, %0" :: "r"(status) : "memory");
}
