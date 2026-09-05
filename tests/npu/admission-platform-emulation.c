/* Test-only RV32 platform binding. These addresses and the retirement callbacks
 * are not a production memory or device-drain contract. */
#include "admission.h"

#define BARRIER ((struct npu_barrier *)0x3e920000u)
#define ADMISSION ((struct npu_admission *)0x3e920100u)
#define MASKED ((uint32_t *)0x3e920140u)
#define MBOX 0x1ec0c000u
#define CALLBACKS ((const uint32_t *)0x3e900d2cu)

typedef uint32_t (*native_call)(uint32_t, uint32_t);
typedef uint32_t (*native_hart_id)(void);
typedef void (*native_irq_source)(uint32_t);
extern void npu_original_irq_trampoline(uint32_t source);

static uint32_t read32(uint32_t address)
{
    return *(volatile uint32_t *)(uintptr_t)address;
}

static void write32(uint32_t address, uint32_t value)
{
    *(volatile uint32_t *)(uintptr_t)address = value;
}

static void fence(void)
{
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
}

void npu_emulation_admission_init(void)
{
    uint32_t i;

    /* Cold, independently contained initialization only. */
    for (i = 0; i < NPU_ADMISSION_IRQ_WORDS; i++)
        MASKED[i] = 0;
    npu_admission_init(ADMISSION);
}

void npu_emulation_irq_dispatch(uint32_t source)
{
    uint32_t hart = ((native_hart_id)0x84004212u)();
    enum npu_irq_admission action;
    uint32_t word, mask;

    if (hart) {
        npu_original_irq_trampoline(source);
        return;
    }
    action = npu_admission_irq(ADMISSION, BARRIER, source);
    if (action == NPU_IRQ_NATIVE || action == NPU_IRQ_CONTROL) {
        npu_original_irq_trampoline(source);
        if (action == NPU_IRQ_NATIVE)
            npu_admission_leave(ADMISSION, BARRIER);
        return;
    }
    if (action == NPU_IRQ_INVALID)
        return;
    word = (source + 1) / 32 * 4;
    mask = 1u << ((source + 1) % 32);
    if (read32(0x0c002000u + word) & mask)
        MASKED[source / 32] |= 1u << (source % 32);
    ((native_irq_source)0x8400326au)(source);
    fence();
    if ((read32(0x0c002000u + word) & mask) || !(read32(0x0c003000u + word) & mask))
        npu_admission_fail(ADMISSION, BARRIER);
    /* Completing the PLIC claim does not consume the pending device event. */
    write32(0x0c200004u, source + 1);
}

void npu_emulation_mailbox(uint32_t source)
{
    uint32_t flags, length, address, function, result = 0;
    struct npu_control_packet *packet;

    if (source != 8 || ((native_hart_id)0x84004212u)())
        return;
    write32(MBOX, 1);
    if (read32(MBOX) & 1) {
        npu_admission_fail(ADMISSION, BARRIER);
        return;
    }
    flags = read32(MBOX + 0x3c);
    length = read32(MBOX + 0x34);
    address = read32(MBOX + 0x30);
    function = flags >> 11 & 15;
    /* The strict candidate supports synchronous dynamic requests only. Reject
     * static registration before it can index the overlapping callback array. */
    if (function >= 8 || (flags & ~0x3801u) || !(flags & 1) ||
        !address || (address & 3) || length < 8 || length > 256)
        goto done;
    packet = (struct npu_control_packet *)(uintptr_t)((address & 0x3fffffffu) | 0x40000000u);
    if (!function && npu_admission_control(ADMISSION, BARRIER, packet, length)) {
        result = 1;
    } else if (CALLBACKS[function] && npu_admission_begin_legacy(ADMISSION, BARRIER)) {
        /* Individual legacy command payload contracts are not reimplemented
         * here. This is an admission adapter, not full legacy parser validation. */
        result = ((native_call)(uintptr_t)CALLBACKS[function])(address, length) & 7;
        npu_admission_leave(ADMISSION, BARRIER);
    }
done:
    fence();
    write32(MBOX + 0x3c, (flags & 0x7801u) | (result << 2) | 2);
}

uint32_t npu_emulation_open(void)
{
    uint32_t source;

    if (!npu_admission_open(ADMISSION, BARRIER))
        return 0;
    for (source = 0; source < NPU_ADMISSION_IRQS; source++) {
        uint32_t mask = 1u << (source % 32);
        uint32_t word = (source + 1) / 32 * 4;
        uint32_t irq_mask = 1u << ((source + 1) % 32);

        if (!(MASKED[source / 32] & mask))
            continue;
        ((native_irq_source)0x84003200u)(source);
        fence();
        if (!(read32(0x0c002000u + word) & irq_mask) || (read32(0x0c003000u + word) & irq_mask)) {
            npu_admission_fail(ADMISSION, BARRIER);
            return 0;
        }
        MASKED[source / 32] &= ~mask;
    }
    return 1;
}

__attribute__((noreturn)) void npu_emulation_idle(void)
{
    for (;;) {
        uint32_t status;

        __asm__ volatile ("csrrci %0, mstatus, 8" : "=r"(status) :: "memory");
        npu_admission_idle(ADMISSION, BARRIER);
        __asm__ volatile ("csrw mstatus, %0" :: "r"(status) : "memory");
        __asm__ volatile (".global npu_emulation_idle_irq_window\n"
                          "npu_emulation_idle_irq_window:\n nop" ::: "memory");
    }
}
