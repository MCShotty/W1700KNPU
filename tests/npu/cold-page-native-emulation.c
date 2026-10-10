/* Native instruction composition, not a production loader/storage contract. */
#include "cold-page.h"
#include "bootstrap.h"

extern struct npu_barrier npu_emulation_barrier_state;
extern struct npu_admission npu_emulation_admission_state;
extern struct npu_bootstrap npu_emulation_bootstrap_state;
extern uint32_t npu_emulation_txdone_callback(const struct npu_bootstrap_packet *);
extern uint32_t npu_original_page_dispatch(uint32_t count, uint32_t selector);
extern uint32_t npu_emulation_indication_callback(const struct npu_bootstrap_packet *);

struct npu_cold_page_state npu_emulation_page_state;
struct npu_cold_page_plan npu_emulation_page_plan;
struct npu_cold_page_queue_result npu_emulation_page_last;
static uint32_t busy;
static uint32_t arena_snapshot;

#define BARRIER (&npu_emulation_barrier_state)
#define ADMISSION (&npu_emulation_admission_state)
#define BOOT (&npu_emulation_bootstrap_state)
#define HEAD 0x3e903950u
#define TAIL 0x3e901f40u
#define POOL 0x3e8a9c70u

static uint32_t word(uint32_t address)
{
    return *(const volatile uint32_t *)(uintptr_t)address;
}

static uint32_t load(const uint32_t *address)
{
    return __atomic_load_n(address, __ATOMIC_ACQUIRE);
}

int npu_emulation_cold_arena_live(void)
{
    uint32_t i, stats = word(0x3e901f08u), arena = word(0x3e9030fcu);

    if (((uint32_t (*)(void))(uintptr_t)0x84004212u)() ||
        load(&BARRIER->request) != 1 || load(&BARRIER->fault) ||
        load(&BARRIER->prepared) || load(&BARRIER->released) || load(&BARRIER->armed) ||
        load(&ADMISSION->closed) != 1 || load(&ADMISSION->fault) ||
        load(&ADMISSION->active) != 1 || BOOT->magic != NPU_BOOTSTRAP_MAGIC ||
        BOOT->failed || BOOT->step != NPU_BOOTSTRAP_STEPS || BOOT->inflight ||
        BOOT->retained_mask != 0x1e ||
        (arena & 31) || arena < 0x3e800000u || arena > 0x3e878000u - 303168u ||
        (arena_snapshot && arena_snapshot != arena) ||
        (stats && ((stats & 3) || stats < 0x3e800000u || stats > 0x3e878000u - 0x4c)) ||
        word(0x3e904634u) != POOL ||
        word(0x3e902ce4u) != BOOT->plan.region[NPU_BOOT_BA].base)
        return 0;
    for (i = 0; i < NPU_BARRIER_WORKERS; i++)
        if (load(&BARRIER->parked[i]) != 1 || load(&BARRIER->ready[i]))
            return 0;
    for (i = 0; i < NPU_BARRIER_DOMAINS; i++)
        if (load(&BARRIER->drained[i]))
            return 0;
    for (i = 0; i < NPU_ADMISSION_IRQ_WORDS; i++)
        if (load(&ADMISSION->deferred[i]))
            return 0;
    return 1;
}

static int live(void)
{
    return npu_emulation_cold_arena_live();
}

static void statistic(uint32_t offset)
{
    uint32_t stats = word(0x3e901f08u);

    if (stats && !(stats & 3) && stats >= 0x3e800000u && stats <= 0x3e878000u - 0x4c) {
        volatile uint32_t *value = (volatile uint32_t *)(uintptr_t)(stats + offset);

        *value = *value + 1;
    }
}

static void fail(void)
{
    npu_cold_page_fault(&npu_emulation_page_state);
    npu_admission_fail(ADMISSION, BARRIER);
}

uint32_t npu_emulation_page_init(void)
{
    const struct npu_bootstrap_range *ba = &BOOT->plan.region[NPU_BOOT_BA];
    struct npu_cold_page_plan plan = {ba->base, ba->bytes};
    uint32_t status;

    if (!live() || *(const volatile uint16_t *)(uintptr_t)HEAD ||
        *(const volatile uint16_t *)(uintptr_t)TAIL)
        return NPU_COLD_PAGE_CORRUPT;
    status = npu_cold_page_init(&npu_emulation_page_state, &plan, 1);
    if (status == NPU_COLD_PAGE_OK || status == NPU_COLD_PAGE_FAULT) {
        npu_emulation_page_plan = plan;
        arena_snapshot = word(0x3e9030fcu);
    }
    return status;
}

uint32_t npu_emulation_page_get(void)
{
    const struct npu_cold_page_queue queue = {
        (volatile uint16_t *)(uintptr_t)HEAD,
        (const volatile uint16_t *)(uintptr_t)TAIL,
        (const volatile uint16_t *)(uintptr_t)POOL,
        NPU_COLD_PAGE_IDS
    };

    if (!busy || !live() || npu_emulation_page_plan.packet_base != BOOT->plan.region[NPU_BOOT_BA].base ||
        npu_emulation_page_plan.packet_bytes != BOOT->plan.region[NPU_BOOT_BA].bytes) {
        fail();
        return UINT32_MAX;
    }
    npu_emulation_page_last = npu_cold_page_queue_take(
        &npu_emulation_page_state, &npu_emulation_page_plan, 1, &queue);
    if (npu_emulation_page_last.page.status != NPU_COLD_PAGE_OK ||
        !npu_emulation_page_last.published || !live()) {
        statistic(0x44);
        fail();
        return UINT32_MAX;
    }
    statistic(0x48);
    return npu_emulation_page_last.page.id;
}

uint32_t npu_emulation_page_ready(void)
{
    if (!busy || !live() || load(&npu_emulation_page_state.fault)) {
        fail();
        return 0;
    }
    return 1;
}

uint32_t npu_emulation_page_callback(const struct npu_bootstrap_packet *packet)
{
    uint32_t selector = packet->header & 15, status, result = 0, ready;
    struct npu_bootstrap_packet snapshot;
    static const uint32_t limits[3] = {256, 512, 1024};
    static const uint32_t flags[3] = {0x3e901f44u, 0x3e903954u, 0x3e902ce8u};

    if (selector == 8)
        return npu_emulation_indication_callback(packet);
    if (selector < 5 || selector > 7)
        return npu_emulation_txdone_callback(packet);
    __asm__ volatile ("csrrci %0, mstatus, 8" : "=r"(status) :: "memory");
    snapshot = *packet;
    ready = flags[selector - 5];
    if (selector == 5 && snapshot.header == 0x15 && snapshot.api == 1 &&
        snapshot.value && snapshot.value <= limits[0] &&
        !load(&npu_emulation_page_state.magic) &&
        npu_emulation_page_init() != NPU_COLD_PAGE_OK) {
        fail();
        goto done;
    }
    if (snapshot.header != (0x10u | selector) || snapshot.api != 1 ||
        !snapshot.value || snapshot.value > limits[selector - 5] || busy ||
        !live() || word(ready) || load(&npu_emulation_page_state.fault) ||
        load(&npu_emulation_page_state.magic) != NPU_COLD_PAGE_MAGIC) {
        fail();
        goto done;
    }
    busy = 1;
    result = !npu_original_page_dispatch(snapshot.value, selector);
    if (!result || !live() || load(&npu_emulation_page_state.fault) || word(ready) != 1) {
        fail();
        *(volatile uint32_t *)(uintptr_t)ready = 0;
        result = 0;
    }
    busy = 0;
done:
    __asm__ volatile ("csrw mstatus, %0" :: "r"(status) : "memory");
    return result;
}
