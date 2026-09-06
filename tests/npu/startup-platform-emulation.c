/* Cold-start adapter only: production loader containment/cache proof is absent. */
#include "startup.h"
#include <stddef.h>

_Static_assert(offsetof(struct npu_startup, fault) == 16, "precheck fault offset");
_Static_assert(offsetof(struct npu_startup, arrived) == 20, "precheck entry offset");
_Static_assert(offsetof(struct npu_startup, reserved) == 52, "precheck reserved offset");
_Static_assert(offsetof(struct npu_barrier, fault) == 16, "precheck barrier offset");
_Static_assert(NPU_STARTUP_FRESH == 0 && NPU_STARTUP_FAILED == 3, "precheck phases");

extern struct npu_startup npu_emulation_startup_state;
extern struct npu_barrier npu_emulation_barrier_state;
extern struct npu_admission npu_emulation_admission_state;
extern uint32_t npu_emulation_masked_state[NPU_ADMISSION_IRQ_WORDS];
extern void npu_emulation_admission_init(void);

void npu_emulation_cold_start(uint32_t hart)
{
    struct npu_startup *startup = &npu_emulation_startup_state;
    struct npu_barrier *barrier = &npu_emulation_barrier_state;
    enum npu_startup_action action;
    /* Core 0 sets this marker during cold boot, before late workers arrive. */
    uint32_t warm = !hart && *(volatile uint32_t *)0x1ec0c140u == UINT32_MAX;

    action = npu_startup_arrive(startup, hart, warm);
    if (action == NPU_STARTUP_INITIALIZE) {
        npu_barrier_init(barrier);
        npu_emulation_admission_init();
        if (!npu_startup_publish(startup, barrier, &npu_emulation_admission_state,
                                 npu_emulation_masked_state, hart))
            action = NPU_STARTUP_FAULT;
    }
    for (;;) {
        if (action == NPU_STARTUP_FAULT) {
            npu_barrier_fail(barrier);
            for (;;) {
                __asm__ volatile (".global npu_emulation_startup_fault\n"
                                  "npu_emulation_startup_fault:\n nop" ::: "memory");
            }
        }
        action = npu_startup_poll(startup, hart);
        if (action == NPU_STARTUP_CONTINUE)
            return;
        if (action == NPU_STARTUP_FAULT)
            continue;
        __asm__ volatile (".global npu_emulation_startup_wait\n"
                          "npu_emulation_startup_wait:\n nop" ::: "memory");
    }
}
