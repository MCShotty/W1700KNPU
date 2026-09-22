#include "allocator.h"
#include <stddef.h>

_Static_assert(sizeof(struct npu_allocator_definition) == 8, "native definition stride");
_Static_assert(sizeof(struct npu_allocator_entry) == 8, "native cache stride");
_Static_assert(offsetof(struct npu_allocator_state, entries) == 24, "native cache offset");
_Static_assert(sizeof(struct npu_allocator_state) == 824, "native state size");

struct npu_allocator_state npu_allocator_test_state;
struct npu_allocator_state npu_allocator_test_after_lock;
struct npu_allocator_state npu_allocator_test_at_unlock;
struct npu_allocator_definition npu_allocator_test_definitions[2][128];
struct npu_allocator_layout npu_allocator_test_layout;
struct npu_allocator_entry npu_allocator_test_placements[NPU_ALLOCATOR_ENTRIES];
uint32_t npu_allocator_test_deny;
uint32_t npu_allocator_test_replace;
uint32_t npu_allocator_test_acquires;
uint32_t npu_allocator_test_releases;
uint32_t npu_allocator_test_owned;
uint32_t npu_allocator_test_error;

static void copy_state(volatile struct npu_allocator_state *to,
                       const struct npu_allocator_state *from)
{
    volatile unsigned char *destination = (volatile unsigned char *)to;
    const unsigned char *source = (const unsigned char *)from;
    unsigned int i;

    for (i = 0; i < sizeof(*to); i++)
        destination[i] = source[i];
}

static int acquire(void *context)
{
    (void)context;
    npu_allocator_test_acquires++;
    if (npu_allocator_test_deny)
        return -1;
    if (npu_allocator_test_owned)
        npu_allocator_test_error++;
    npu_allocator_test_owned = 1;
    if (npu_allocator_test_replace)
        copy_state(&npu_allocator_test_state, &npu_allocator_test_after_lock);
    return 0;
}

static void release(void *context)
{
    (void)context;
    if (!npu_allocator_test_owned)
        npu_allocator_test_error++;
    copy_state(&npu_allocator_test_at_unlock, &npu_allocator_test_state);
    npu_allocator_test_owned = 0;
    npu_allocator_test_releases++;
}

void npu_allocator_test_setup(uint32_t base, uint32_t bytes,
                               uint32_t high_count, uint32_t low_count)
{
    npu_allocator_test_layout.base = base;
    npu_allocator_test_layout.bytes = bytes;
    npu_allocator_test_layout.tables[0] = npu_allocator_test_definitions[0];
    npu_allocator_test_layout.tables[1] = npu_allocator_test_definitions[1];
    npu_allocator_test_layout.lengths[0] = high_count;
    npu_allocator_test_layout.lengths[1] = low_count;
    npu_allocator_test_layout.placements = 0;
    npu_allocator_test_layout.placement_count = 0;
    npu_allocator_test_acquires = npu_allocator_test_releases = 0;
    npu_allocator_test_owned = npu_allocator_test_error = 0;
}

void npu_allocator_test_place(uint32_t count, uint32_t missing)
{
    npu_allocator_test_layout.placements = missing ? 0 : npu_allocator_test_placements;
    npu_allocator_test_layout.placement_count = count;
}

struct npu_allocator_result npu_allocator_test_allocate(uint32_t type, uint32_t table)
{
    const struct npu_allocator_lock lock = {0, acquire, release};

    return npu_allocator_allocate(&npu_allocator_test_state, &npu_allocator_test_layout,
                                  &lock, type, table);
}
