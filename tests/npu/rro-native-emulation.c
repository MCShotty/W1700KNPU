/* Freestanding RV32 fixture; backing, exclusion and MCU success remain models. */
#include "rro-native-fixture.h"

struct npu_rro_lifetime rro_emulation_state;
struct npu_rro_plan rro_emulation_plan;
uint32_t rro_emulation_reads, rro_emulation_writes;
static uint32_t table, base, extent_bytes, reset_mode;
static uint32_t failure_kind, failure_index = UINT32_MAX;

static int mapped(uint32_t address, uint32_t bytes, int write)
{
    uint32_t status;
    __asm__ volatile ("csrr %0,mstatus" : "=r"(status));
    if ((status & 8) || (bytes != 1 && bytes != 4) || (address & (bytes - 1)))
        return 0;
    return (address == table && bytes == 4 && (!write || !reset_mode)) ||
           (address >= base && bytes <= extent_bytes && address - base <= extent_bytes - bytes);
}

static int read_memory(void *opaque, uint32_t address, uint32_t bytes, uint32_t *value)
{
    uint32_t index = rro_emulation_reads++;
    if (opaque != &rro_emulation_state || !mapped(address, bytes, 0) ||
        (failure_kind == 1 && index == failure_index))
        return 0;
    *value = bytes == 1 ? *(const volatile uint8_t *)(uintptr_t)address :
                         *(const volatile uint32_t *)(uintptr_t)address;
    if (failure_kind == 4 && index == failure_index)
        *value ^= 1;
    return 1;
}

static int write_memory(void *opaque, uint32_t address, uint32_t bytes, uint32_t value)
{
    uint32_t index = rro_emulation_writes++;
    if (opaque != &rro_emulation_state || !mapped(address, bytes, 1) ||
        (failure_kind == 2 && index == failure_index))
        return 0;
    if (bytes == 1)
        *(volatile uint8_t *)(uintptr_t)address = value;
    else
        *(volatile uint32_t *)(uintptr_t)address = value;
    return !(failure_kind == 3 && index == failure_index);
}

static const struct npu_rro_native_context context = {read_memory, write_memory, &rro_emulation_state};

static uint32_t enter(void)
{
    uint32_t status;
    __asm__ volatile ("csrrci %0,mstatus,8" : "=r"(status) :: "memory");
    return status;
}

static void leave(uint32_t status)
{
    __asm__ volatile ("csrw mstatus,%0" :: "r"(status) : "memory");
}

uint32_t rro_emulation_fault(uint32_t kind, uint32_t index)
{
    failure_kind = kind;
    failure_index = index;
    return 0;
}

uint32_t rro_emulation_init(uint32_t profile)
{
    rro_test_zero(&rro_emulation_state, sizeof(rro_emulation_state));
    rro_test_plan(&rro_emulation_plan, profile);
    failure_kind = rro_emulation_reads = rro_emulation_writes = 0;
    failure_index = UINT32_MAX;
    return npu_rro_open(&rro_emulation_state, &rro_emulation_plan);
}

uint32_t rro_emulation_enroll(uint32_t ordinal)
{
    struct npu_rro_extent item;
    uint32_t result = rro_test_extent(rro_emulation_plan.profile, ordinal, &item);
    return result ? result : npu_rro_enroll(&rro_emulation_state, &rro_emulation_plan, &item);
}

static void view(uint32_t ordinal, uint32_t session, int reset)
{
    uint32_t slot = ordinal == 128 ? npu_rro_extent_count(rro_emulation_plan.profile) - 1 :
                    ordinal + (rro_emulation_plan.profile == NPU_RRO_V3 ? 2 : 0);
    base = (rro_emulation_state.extents[slot].dma_lo & 0x3fffffff) | 0x40000000;
    extent_bytes = ordinal == 128 ? NPU_RRO_SESSION_BYTES : NPU_RRO_BLOCK_BYTES;
    table = ordinal == 128 ? NPU_RRO_NATIVE_SESSION_TABLE : NPU_RRO_NATIVE_BLOCK_TABLE + ordinal * 4;
    reset_mode = reset;
    if (reset) {
        base += session == 1024 ? 0 : session % 8 * NPU_RRO_SESSION_BYTES;
        extent_bytes = NPU_RRO_SESSION_BYTES;
    }
    rro_emulation_reads = rro_emulation_writes = 0;
}

uint32_t rro_emulation_publish(uint32_t ordinal)
{
    if (ordinal >= NPU_RRO_PUBLICATIONS)
        return NPU_RRO_ARGUMENT;
    uint32_t status = enter();
    view(ordinal, 0, 0);
    uint32_t result = npu_rro_native_publish(&rro_emulation_state, &rro_emulation_plan, ordinal, &context);
    leave(status);
    return result;
}

uint32_t rro_emulation_hardware(void)
{
    return npu_rro_hardware_begin(&rro_emulation_state, &rro_emulation_plan);
}

uint32_t rro_emulation_reset(uint32_t session, uint32_t generation)
{
    uint32_t ticket;
    uint32_t result = npu_rro_reset_queue(&rro_emulation_state, &rro_emulation_plan, session, generation, &ticket);
    if (result)
        return result;
    uint32_t status = enter();
    view(session == 1024 ? 128 : session / 8, session, 1);
    result = npu_rro_native_reset(&rro_emulation_state, &rro_emulation_plan, session, generation, ticket, &context);
    leave(status);
    return result;
}

uint32_t rro_emulation_mcu(uint32_t session, uint32_t generation)
{
    if (session >= NPU_RRO_SESSIONS)
        return NPU_RRO_ARGUMENT;
    uint32_t ticket = rro_emulation_state.resets[session].ticket;
    uint32_t result = npu_rro_reset_mcu_begin(&rro_emulation_state, &rro_emulation_plan, session, generation, ticket);
    return result ? result : npu_rro_reset_mcu_complete(&rro_emulation_state, &rro_emulation_plan, session, generation, ticket, 0);
}
