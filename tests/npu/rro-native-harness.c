#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "rro-native-fixture.h"
#include "rro-source-geometry.h"

_Static_assert(MT7996_RRO_ADDR_ELEM_LEN == NPU_RRO_BLOCKS, "full element geometry");
_Static_assert(MT7996_RRO_WINDOW_MAX_SIZE * 8 == NPU_RRO_BLOCK_BYTES, "full block bytes");
_Static_assert(MT7996_RRO_WINDOW_MAX_LEN * 8 == NPU_RRO_SESSION_BYTES, "full session bytes");
_Static_assert(MT7996_RRO_MAX_SESSION + 1 == NPU_RRO_SESSIONS, "all reset IDs");

static struct npu_rro_lifetime state, prefix[129], live, before;
static struct npu_rro_plan plan;
static unsigned char sram[RRO_TEST_SRAM_BYTES], saved_sram[RRO_TEST_SRAM_BYTES];
static unsigned char prefix_sram[129][RRO_TEST_SRAM_BYTES];
static unsigned char dma[RRO_TEST_ALIAS_BYTES], saved_dma[RRO_TEST_ALIAS_BYTES];
static unsigned char expected[NPU_RRO_BLOCK_BYTES];
static unsigned char expected_sram[RRO_TEST_SRAM_BYTES];
static struct {
    uint32_t ordinal, slot, session, reads, writes, fail_read, fail_write;
    int reset, after_write, wrong_read;
} bus;
static FILE *frames, *states;
static unsigned cases, publication_failures, reset_failures, state_records, frame_count;

static uint32_t alias(uint32_t physical) { return (physical & 0x3fffffff) | 0x40000000; }

static unsigned char *mapping(uint32_t address, uint32_t bytes)
{
    assert(bytes);
    if (bytes <= RRO_TEST_SRAM_BYTES && address >= RRO_TEST_SRAM && address - RRO_TEST_SRAM <= RRO_TEST_SRAM_BYTES - bytes)
        return sram + (address - RRO_TEST_SRAM);
    assert(bytes <= RRO_TEST_ALIAS_BYTES && address >= RRO_TEST_ALIAS && address - RRO_TEST_ALIAS <= RRO_TEST_ALIAS_BYTES - bytes);
    return dma + (address - RRO_TEST_ALIAS);
}

static void possible(void)
{
    if (bus.reset)
        assert(state.resets[bus.session].phase == NPU_RRO_RESET_NPU_POSSIBLE &&
               "native reset exposure precedes memory access");
    else
        assert(state.publication[bus.ordinal].ticket && (state.exposure[bus.slot] & NPU_RRO_NPU_POSSIBLE) &&
               "native publication exposure precedes memory access");
}

static int read_memory(void *opaque, uint32_t address, uint32_t bytes, uint32_t *value)
{
    assert(opaque == &bus); possible();
    assert((bytes == 1 || bytes == 4) && !(address & (bytes - 1)));
    unsigned index = bus.reads++;
    if (index == bus.fail_read && !bus.wrong_read) return 0;
    *value = 0;
    memcpy(value, mapping(address, bytes), bytes);
    if (index == bus.fail_read) *value ^= 1;
    return 1;
}

static int write_memory(void *opaque, uint32_t address, uint32_t bytes, uint32_t value)
{
    assert(opaque == &bus); possible();
    assert((bytes == 1 || bytes == 4) && !(address & (bytes - 1)));
    uint32_t base = alias(state.extents[bus.slot].dma_lo);
    uint32_t count = state.extents[bus.slot].bytes;
    uint32_t table = bus.ordinal == 128 ? NPU_RRO_NATIVE_SESSION_TABLE : NPU_RRO_NATIVE_BLOCK_TABLE + bus.ordinal * 4;
    if (bus.reset) {
        base += bus.session == 1024 ? 0 : (bus.session % 8) * NPU_RRO_SESSION_BYTES;
        count = NPU_RRO_SESSION_BYTES;
    }
    assert(((!bus.reset && address == table && bytes == 4) ||
            (address >= base && bytes <= count && address - base <= count - bytes)) &&
           "native write stays inside exact RRO lease");
    unsigned index = bus.writes++;
    if (index == bus.fail_write && !bus.after_write) return 0;
    memcpy(mapping(address, bytes), &value, bytes);
    return index != bus.fail_write;
}

static const struct npu_rro_native_context context = {read_memory, write_memory, &bus};

static uint32_t slot_for(uint32_t ordinal)
{
    if (ordinal == 128) return npu_rro_extent_count(plan.profile) - 1;
    return ordinal + (plan.profile == NPU_RRO_V3 ? 2 : 0);
}

static void bus_begin(uint32_t ordinal, int reset, uint32_t session)
{
    memset(&bus, 0, sizeof(bus));
    bus.ordinal = ordinal; bus.slot = slot_for(ordinal); bus.reset = reset; bus.session = session;
    bus.fail_read = bus.fail_write = UINT32_MAX;
}

static void record(uint32_t kind, uint32_t ordinal)
{
    if (!states) return;
    uint32_t header[4] = {kind, plan.profile, ordinal, sizeof(state)};
    assert(fwrite(header, sizeof(header), 1, states) == 1 && fwrite(&state, sizeof(state), 1, states) == 1);
    state_records++;
}

static void frame(uint32_t selector, uint32_t argument, uint32_t physical)
{
    if (plan.profile || !frames) return;
    uint32_t words[6] = {0x10 | selector, 24, argument, physical, 0, 0};
    assert(fwrite(words, sizeof(words), 1, frames) == 1); frame_count++;
}

static void exact_region(uint32_t ordinal, uint32_t written)
{
    uint32_t size = ordinal == 128 ? NPU_RRO_SESSION_BYTES : NPU_RRO_BLOCK_BYTES;
    uint32_t base = alias(state.extents[slot_for(ordinal)].dma_lo);
    uint32_t table = ordinal == 128 ? NPU_RRO_NATIVE_SESSION_TABLE : NPU_RRO_NATIVE_BLOCK_TABLE + ordinal * 4;
    memset(expected, 0xa5, size);
    memcpy(expected_sram, prefix_sram[ordinal], sizeof(sram));
    if (written) {
        uint32_t pointer;
        memcpy(&pointer, mapping(table, 4), 4);
        assert(pointer == base);
        memcpy(expected_sram + (table - RRO_TEST_SRAM), &base, 4);
        written--;
    }
    if (ordinal != 128) {
        uint32_t clear = written < size / 4 ? written : size / 4;
        memset(expected, 0, clear * 4); written -= clear;
    }
    for (uint32_t i = 0; i < written; i++) expected[i * 8 + 7] = 0xff;
    assert(!memcmp(mapping(base, size), expected, size) && "failed native publication retains exact possible prefix");
    assert(!memcmp(sram, expected_sram, sizeof(sram)));
    assert(!memcmp(dma, saved_dma, base - RRO_TEST_ALIAS));
    uint32_t tail = base - RRO_TEST_ALIAS + size;
    assert(!memcmp(dma + tail, saved_dma + tail, sizeof(dma) - tail));
}

static void publication_errors(uint32_t ordinal)
{
    uint32_t writes = ordinal == 128 ? 1025 : 24577;
    uint32_t reads = ordinal == 128 ? 1026 : 24578;
    const uint32_t write_points[] = {0, 1, writes / 2, writes - 2, writes - 1};
    const uint32_t read_points[] = {0, 1, reads / 2, reads - 2, reads - 1};
    uint32_t base = alias(prefix[ordinal].extents[slot_for(ordinal)].dma_lo);
    uint32_t size = ordinal == 128 ? NPU_RRO_SESSION_BYTES : NPU_RRO_BLOCK_BYTES;
    for (uint32_t mode = 0; mode < 4; mode++) {
        for (uint32_t point = 0; point < 5; point++) {
            state = prefix[ordinal]; memcpy(sram, prefix_sram[ordinal], sizeof(sram));
            memset(mapping(base, size), 0xa5, size); bus_begin(ordinal, 0, 0);
            if (mode < 2) { bus.fail_write = write_points[point]; bus.after_write = mode; }
            else { bus.fail_read = read_points[point]; bus.wrong_read = mode == 3; }
            assert(npu_rro_native_publish(&state, &plan, ordinal, &context) == NPU_RRO_HELD &&
                   "failed native memory access or readback must not confirm publication");
            assert(state.error && state.confirmed == ordinal && state.publication[ordinal].ticket &&
                   state.publication[ordinal].error && state.exposure[bus.slot] == 3);
            uint32_t written = mode < 2 ? write_points[point] + mode : point ? writes : 1;
            exact_region(ordinal, written);
            uint32_t io = bus.reads + bus.writes;
            assert(npu_rro_native_publish(&state, &plan, ordinal, &context) == NPU_RRO_HELD);
            assert(bus.reads + bus.writes == io && state.allocated == prefix[ordinal].allocated);
            publication_failures++; cases++;
        }
    }
    memcpy(mapping(base, size), saved_dma + (base - RRO_TEST_ALIAS), size);
}

static void profile(uint32_t mode)
{
    rro_test_zero(&state, sizeof(state)); rro_test_plan(&plan, mode);
    memset(sram, 0xa5, sizeof(sram)); memset(dma, 0xa5, sizeof(dma));
    assert(!npu_rro_open(&state, &plan)); record(0, 0);
    for (uint32_t i = 0; i < npu_rro_extent_count(mode); i++) {
        struct npu_rro_extent item;
        assert(!rro_test_extent(mode, i, &item) && !npu_rro_enroll(&state, &plan, &item));
        record(1, i);
        if (item.role != NPU_RRO_ELEMENT && item.role != NPU_RRO_SESSION) continue;
        uint32_t ordinal = item.role == NPU_RRO_SESSION ? 128 : item.index;
        prefix[ordinal] = state; memcpy(prefix_sram[ordinal], sram, sizeof(sram));
        bus_begin(ordinal, 0, 0);
        assert(!npu_rro_native_publish(&state, &plan, ordinal, &context) &&
               "native publication must complete its verified stock projection");
        uint32_t base = alias(item.dma_lo);
        for (uint32_t j = 0; j < item.bytes; j++)
            assert(mapping(base, item.bytes)[j] == (j % 8 == 7 ? 0xff : ordinal == 128 ? 0xa5 : 0) &&
                   "native publication has exact stock byte projection");
        assert(state.confirmed == ordinal + 1 && state.exposure[i] == 7);
        frame(ordinal == 128, ordinal == 128 ? 0 : ordinal, item.dma_lo); record(2, ordinal); cases++;
    }
    live = state; memcpy(saved_dma, dma, sizeof(dma)); memcpy(saved_sram, sram, sizeof(sram));
    for (uint32_t ordinal = 0; ordinal < 129; ordinal++) publication_errors(ordinal);
    state = live; memcpy(sram, saved_sram, sizeof(sram)); memcpy(dma, saved_dma, sizeof(dma));
    assert(!npu_rro_hardware_begin(&state, &plan)); record(3, 0); live = state;
    for (uint32_t generation = 1; generation <= 2; generation++) {
        for (uint32_t id = 0; id < NPU_RRO_SESSIONS; id++) {
            uint32_t ordinal = id == 1024 ? 128 : id / 8;
            uint32_t slot = slot_for(ordinal), base = alias(state.extents[slot].dma_lo);
            uint32_t start = base + (id == 1024 ? 0 : id % 8 * NPU_RRO_SESSION_BYTES);
            uint32_t ticket;
            memset(mapping(start, 8192), 0x35, 8192); memcpy(saved_dma, dma, sizeof(dma));
            assert(!npu_rro_reset_queue(&state, &plan, id, generation, &ticket)); bus_begin(ordinal, 1, id);
            assert(!npu_rro_native_reset(&state, &plan, id, generation, ticket, &context) &&
                   "native reset must match its exact table and session");
            for (uint32_t j = 0; j < 8192; j++)
                assert(mapping(start, 8192)[j] == (j % 8 == 7 ? 0xff : 0x35) && "reset affects exact session only");
            assert(!memcmp(dma, saved_dma, start - RRO_TEST_ALIAS));
            uint32_t tail = start - RRO_TEST_ALIAS + 8192;
            assert(!memcmp(dma + tail, saved_dma + tail, sizeof(dma) - tail) && !memcmp(sram, saved_sram, sizeof(sram)));
            assert(state.resets[id].phase == NPU_RRO_RESET_NPU_CONFIRMED && state.resets[id].generation == generation);
            if (generation == 1) {
                record(4, id);
                if (id == 0 || id == 7 || id == 8 || id == 1023 || id == 1024) frame(3, id, 0);
            }
            /* Only metadata MCU success is modeled; no firmware exchange occurs. */
            assert(!npu_rro_reset_mcu_begin(&state, &plan, id, generation, ticket));
            assert(!npu_rro_reset_mcu_complete(&state, &plan, id, generation, ticket, 0));
            if (generation == 1) record(5, id);
            assert(state.resets[id].generation == generation + 1); cases++;
        }
    }
    const uint32_t ids[] = {0, 7, 8, 1023, 1024};
    for (uint32_t i = 0; i < 5; i++) {
        uint32_t id = ids[i], ordinal = id == 1024 ? 128 : id / 8, slot = slot_for(ordinal);
        uint32_t start = alias(live.extents[slot].dma_lo) + (id == 1024 ? 0 : id % 8 * 8192);
        for (uint32_t mode = 0; mode < 3; mode++) {
            for (uint32_t point = 0; point < 3; point++) {
                state = live; uint32_t ticket;
                memset(mapping(start, 8192), 0x35, 8192);
                assert(!npu_rro_reset_queue(&state, &plan, id, 1, &ticket)); bus_begin(ordinal, 1, id);
                if (mode < 2) { bus.fail_write = point == 0 ? 0 : point == 1 ? 512 : 1023; bus.after_write = mode; }
                else bus.fail_read = point == 0 ? 0 : point == 1 ? 513 : 1025;
                assert(npu_rro_native_reset(&state, &plan, id, 1, ticket, &context) == NPU_RRO_HELD);
                assert(state.resets[id].phase == NPU_RRO_RESET_NPU_POSSIBLE && state.resets[id].npu_error && state.error);
                uint32_t written = mode < 2 ? bus.fail_write + mode : point ? 1024 : 0;
                for (uint32_t j = 0; j < 8192; j++)
                    assert(mapping(start, 8192)[j] == ((j % 8 == 7 && j / 8 < written) ? 0xff : 0x35));
                before = state;
                assert(npu_rro_reset_mcu_begin(&state, &plan, id, 1, ticket) != NPU_RRO_OK);
                assert(!memcmp(&before, &state, sizeof(state))); reset_failures++; cases++;
            }
        }
    }
}

int main(int argc, char **argv)
{
    assert(argc == 3 && __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__);
    frames = fopen(argv[1], "wbx"); states = fopen(argv[2], "wbx"); assert(frames && states);
    for (uint32_t mode = 0; mode < 3; mode++) profile(mode);
    assert(!fclose(frames) && !fclose(states) && frame_count == 134);
    printf("{\"passed\":true,\"cases\":%u,\"publication_failures\":%u,\"reset_failures\":%u,"
           "\"state_records\":%u,\"state_bytes\":%zu,\"frames\":%u,\"hardware\":false}\n",
           cases, publication_failures, reset_failures, state_records, sizeof(state), frame_count);
    return 0;
}
