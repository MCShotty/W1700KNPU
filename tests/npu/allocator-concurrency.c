#include "allocator.h"
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static struct npu_allocator_state state;
static struct npu_allocator_definition high[127], low[128];
static struct npu_allocator_layout layout = {
    .base = 0x3e800000, .bytes = 0x78000,
    .tables = {high, low}, .lengths = {127, 128},
};
static pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
static _Atomic uint32_t addresses[101];
static struct npu_allocator_entry placements[50];
static int placement_mode;

static int acquire(void *context)
{
    return pthread_mutex_lock(context);
}

static void release(void *context)
{
    assert(pthread_mutex_unlock(context) == 0);
}

static int deny(void *context)
{
    (void)context;
    return -1;
}

static const struct npu_allocator_lock lock = {&mutex, acquire, release};

static void *worker(void *argument)
{
    uint32_t id = (uint32_t)(uintptr_t)argument;
    uint32_t i;

    for (i = 0; i < 4000; i++) {
        uint32_t type = (i*29 + id*17) % 100 + 1;
        uint32_t expected = 0;
        struct npu_allocator_result result = npu_allocator_allocate(&state, &layout, &lock, type, 1);

        assert(result.status == NPU_ALLOCATOR_OK);
        if (placement_mode && (type & 1))
            assert(result.address == 0x84060000+(type/2)*32);
        else
            assert(result.address >= layout.base &&
                   result.address+32 <= layout.base+(placement_mode ? 1600 : 3200));
        if (!atomic_compare_exchange_strong(&addresses[type], &expected, result.address))
            assert(expected == result.address);
    }
    return 0;
}

int main(int argc, char **argv)
{
    pthread_t threads[8];
    struct npu_allocator_state before;
    struct npu_allocator_result result;
    struct npu_allocator_lock denied = {&mutex, deny, release};
    uint32_t i, cursor = 0;

    assert(argc == 1 || (argc == 2 && !strcmp(argv[1], "--placements")));
    placement_mode = argc == 2;
    state.lock_id = 18;
    state.native_reserved0 = 0x12345678;
    state.native_reserved1 = 0x87654321;
    for (i = 0; i < 128; i++)
        low[i] = (struct npu_allocator_definition){i+1, 0, 0, 32};
    for (i = 0; i < 127; i++)
        high[i] = (struct npu_allocator_definition){i+129, 0, 0, 32};
    if (placement_mode) {
        for (i = 0; i < 50; i++)
            placements[i] = (struct npu_allocator_entry){i*2+1, 0, 0x84060000+i*32};
        layout.placements = placements;
        layout.placement_count = 50;
    }
    for (i = 0; i < 8; i++)
        assert(pthread_create(&threads[i], 0, worker, (void *)(uintptr_t)i) == 0);
    for (i = 0; i < 8; i++)
        assert(pthread_join(threads[i], 0) == 0);
    assert(state.count == 100 && state.used == (placement_mode ? 1600u : 3200u) && state.attempts == 100);
    assert(state.native_reserved0 == 0x12345678 && state.native_reserved1 == 0x87654321);
    for (i = 0; i < 100; i++) {
        const struct npu_allocator_entry *entry = &state.entries[i];

        assert(entry->type >= 1 && entry->type <= 100 && !entry->reserved);
        if (placement_mode && (entry->type & 1)) {
            assert(entry->address == 0x84060000+(entry->type/2)*32);
        } else {
            assert(entry->address == layout.base+cursor);
            cursor += 32;
        }
        assert(atomic_load(&addresses[entry->type]) == entry->address);
    }
    before = state;
    result = npu_allocator_allocate(&state, &layout, &lock, 101, 1);
    assert(result.status == NPU_ALLOCATOR_CAPACITY && !result.address);
    assert(memcmp(&state, &before, sizeof(state)) == 0);
    layout.bytes = state.used;
    result = npu_allocator_allocate(&state, &layout, &lock, 100, 1);
    assert(result.status == NPU_ALLOCATOR_OK && result.address == atomic_load(&addresses[100]));
    assert(memcmp(&state, &before, sizeof(state)) == 0);
    result = npu_allocator_allocate(&state, &layout, &denied, 1, 1);
    assert(result.status == NPU_ALLOCATOR_LOCK_DENIED && !result.address);
    assert(memcmp(&state, &before, sizeof(state)) == 0);
    printf("{\"threads\":8,\"concurrent_calls\":32000,\"unique_allocations\":100,"
           "\"used_bytes\":%u,\"placements\":%u,\"post_checks\":3,\"passed\":true}\n",
           state.used, layout.placement_count);
    return 0;
}
