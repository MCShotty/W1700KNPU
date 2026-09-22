/* Selected cold TXDONE callback only. Physical ring backing and DMA/cache
 * containment remain platform contracts; this does not open strict admission. */
#include "bootstrap.h"

extern struct npu_barrier npu_emulation_barrier_state;
extern struct npu_admission npu_emulation_admission_state;
extern struct npu_bootstrap npu_emulation_bootstrap_state;
extern uint32_t npu_original_desc_callback(const struct npu_bootstrap_packet *packet);

#define BARRIER (&npu_emulation_barrier_state)
#define ADMISSION (&npu_emulation_admission_state)
#define BOOTSTRAP (&npu_emulation_bootstrap_state)
#define HEAP 0x3e800000u
#define HEAP_END 0x3e878000u
#define TX_BASE 0x3e891000u

static uint32_t read32(uint32_t address)
{
    return *(const volatile uint32_t *)(uintptr_t)address;
}

static uint32_t read16(uint32_t address)
{
    return *(const volatile uint16_t *)(uintptr_t)address;
}

static uint32_t load(const uint32_t *word)
{
    return __atomic_load_n(word, __ATOMIC_ACQUIRE);
}

static int heap_span(uint32_t address, uint32_t bytes)
{
    return !(address & 31) && address >= HEAP && address < HEAP_END && bytes <= HEAP_END-address;
}

static uint32_t hart(void)
{
    return ((uint32_t (*)(void))(uintptr_t)0x84004212u)();
}

void npu_emulation_txdone_fail(void)
{
    __asm__ volatile ("csrci mstatus, 8\n fence iorw, iorw" ::: "memory");
    if (!hart())
        npu_admission_fail(ADMISSION, BARRIER);
    else
        npu_barrier_fail(BARRIER);
}

/* Called with native bufid lock 28 owned, before any queue/statistics mutation. */
int npu_emulation_txdone_bufid_valid(void)
{
    uint32_t head = read16(0x3e901ba4u), tail = read16(0x3e901b80u);
    uint32_t pool = read32(0x3e901b88u), id, packet_bytes;

    if (head >= 16384 || tail >= 16384 || !heap_span(pool, 32768))
        return 0;
    if (((head+1) & 16383) == tail)
        return 1;
    id = read16(pool+head*2);
    packet_bytes = BOOTSTRAP->plan.region[NPU_BOOT_PKT].bytes;
    return id < 16384 && packet_bytes >= 2048 && id <= (packet_bytes-2048)/2048;
}

/* Both SKB locks are owned here. The TX descriptor snapshot must be immutable
 * under the independently contained cold-call contract. */
int npu_emulation_txdone_skb_valid(void)
{
    volatile uint32_t seen[896];
    uint32_t capacity = read32(0x3e900bc0u), band, index;
    uint32_t packet = read32(0x3e902ab8u);
    const struct npu_bootstrap_range *tx = &BOOTSTRAP->plan.region[NPU_BOOT_TXPKT];
    const struct npu_bootstrap_range *state = &BOOTSTRAP->plan.region[NPU_BOOT_TXCHECK];

    for (index = 0; index < 896; index++)
        seen[index] = 0;
    if (capacity < 2048 || capacity > 0x7000 || capacity > state->bytes/2 ||
        !heap_span(read32(0x3e901bc0u), 4096) ||
        !heap_span(read32(0x3e901b84u), capacity*2) ||
        read32(0x3e90469cu) != ((state->base & 0x3fffffffu) | 0x40000000u) ||
        packet != tx->base || (packet & 2047) || tx->bytes < 2048)
        return 0;
    for (band = 0; band < 2; band++) {
        uint32_t descriptors = read32(0x3e901f28u+band*4);

        if (descriptors != TX_BASE+band*32768)
            return 0;
        for (index = 0; index < 1024; index++) {
            uint32_t address = read32(descriptors+index*32+8);
            uint32_t offset = address-packet, id = offset/2048;
            uint32_t bit;

            if ((offset & 2047) || id >= capacity || offset > tx->bytes-2048)
                return 0;
            bit = 1u << (id & 31);
            if (seen[id >> 5] & bit)
                return 0;
            seen[id >> 5] |= bit;
        }
    }
    return 1;
}

static int cold_request(const struct npu_bootstrap_packet *packet)
{
    uint32_t i, descriptor = read32(0x3e903964u);

    if (hart() || packet->header != 0x1a || packet->api != 1 ||
        !packet->value || packet->value > 512 ||
        load(&BARRIER->request) != 1 || load(&BARRIER->fault) ||
        load(&BARRIER->prepared) || load(&BARRIER->released) || load(&BARRIER->armed) ||
        ADMISSION->closed != 1 || ADMISSION->fault || ADMISSION->active > 1 ||
        BOOTSTRAP->magic != NPU_BOOTSTRAP_MAGIC || BOOTSTRAP->failed ||
        BOOTSTRAP->step != NPU_BOOTSTRAP_STEPS ||
        *(const volatile uint8_t *)(uintptr_t)0x3e9046fau ||
        read32(0x3e901b9cu) != 28 || read32(0x3e901bb8u) != 19 || read32(0x3e901bc4u) != 20 ||
        read32(0x3e90396cu) != BOOTSTRAP->plan.region[NPU_BOOT_PKT].base ||
        (descriptor & 15) || descriptor < 0x40000000u || descriptor > 0x80000000u-8192)
        return 0;
    for (i = 0; i < NPU_BARRIER_WORKERS; i++)
        if (load(&BARRIER->parked[i]) != 1)
            return 0;
    for (i = 0; i < NPU_BOOT_REGIONS; i++) {
        const struct npu_bootstrap_range *r = &BOOTSTRAP->plan.region[i];
        uint32_t base = (r->base & 0x3fffffffu) | 0x40000000u;

        if (descriptor < base+r->bytes && base < descriptor+8192)
            return 0;
    }
    return 1;
}

uint32_t npu_emulation_txdone_callback(const struct npu_bootstrap_packet *packet)
{
    struct npu_bootstrap_packet snapshot;
    uint32_t header = packet->header;
    uint32_t status, result = 0;

    if ((header & 15) != 10)
        return npu_original_desc_callback(packet);
    __asm__ volatile ("csrrci %0, mstatus, 8" : "=r"(status) :: "memory");
    snapshot.header = header;
    snapshot.api = packet->api;
    snapshot.value = packet->value;
    if (!cold_request(&snapshot))
        goto done;
    result = npu_original_desc_callback(&snapshot);
    if (load(&BARRIER->fault) || *(const volatile uint8_t *)(uintptr_t)0x3e9046fau != 1) {
        npu_emulation_txdone_fail();
        result = 0;
    }
done:
    __asm__ volatile ("csrw mstatus, %0" :: "r"(status) : "memory");
    return result;
}
