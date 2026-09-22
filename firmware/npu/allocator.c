#include "allocator.h"

static void ownership_fence(void)
{
#ifdef __riscv
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
#else
    __atomic_thread_fence(__ATOMIC_SEQ_CST);
#endif
}

static int in_table(uint32_t type, uint32_t table)
{
    return type < NPU_ALLOCATOR_TYPES && (table == 1 ? type < 0x81 : type >= 0x81);
}

static const struct npu_allocator_definition *definition(
    const struct npu_allocator_layout *layout, uint32_t type, uint32_t table)
{
    uint32_t i;

    for (i = 0; i < layout->lengths[table]; i++)
        if (layout->tables[table][i].type == type)
            return &layout->tables[table][i];
    return 0;
}

static uint32_t alignment_for(const struct npu_allocator_definition *d)
{
    return d->alignment_tag ? 16 : 32;
}

static int valid_placements(const struct npu_allocator_layout *layout)
{
    uint32_t i, j;

    if (layout->placement_count > NPU_ALLOCATOR_ENTRIES ||
        (layout->placement_count && !layout->placements))
        return 0;
    for (i = 0; i < layout->placement_count; i++) {
        const struct npu_allocator_entry *p = &layout->placements[i];
        const struct npu_allocator_definition *d;
        uint32_t alignment, end;

        if (p->type >= NPU_ALLOCATOR_TYPES || p->reserved || !p->address)
            return 0;
        d = definition(layout, p->type, p->type < 0x81);
        if (!d || d->bytes > UINT32_MAX - p->address)
            return 0;
        alignment = alignment_for(d);
        end = p->address + d->bytes;
        if ((p->address & (alignment - 1)) ||
            (p->address < layout->base + layout->bytes && end > layout->base))
            return 0;
        for (j = 0; j < i; j++) {
            const struct npu_allocator_entry *other = &layout->placements[j];
            const struct npu_allocator_definition *other_d =
                definition(layout, other->type, other->type < 0x81);

            if (p->type == other->type ||
                (p->address < other->address + other_d->bytes && end > other->address))
                return 0;
        }
    }
    return 1;
}

static int valid_layout(const struct npu_allocator_layout *layout)
{
    uint32_t seen[8] = {0};
    uint32_t table, i, total = 0;

    if (!layout->base || (layout->base & 31) || !layout->bytes ||
        layout->bytes > UINT32_MAX - layout->base)
        return 0;
    for (table = 0; table < NPU_ALLOCATOR_TABLES; table++) {
        uint32_t count = layout->lengths[table];

        if (count > 128 || (count && !layout->tables[table]))
            return 0;
        total += count;
        for (i = 0; i < count; i++) {
            const struct npu_allocator_definition *d = &layout->tables[table][i];
            uint32_t bit;

            if (!in_table(d->type, table) || d->alignment_tag > 1 ||
                d->reserved || !d->bytes)
                return 0;
            bit = 1u << (d->type & 31);
            if (seen[d->type >> 5] & bit)
                return 0;
            seen[d->type >> 5] |= bit;
        }
    }
    return total != 0 && valid_placements(layout);
}

static int extent(const struct npu_allocator_layout *layout, uint32_t used,
                  const struct npu_allocator_definition *d,
                  uint32_t *address, uint32_t *end)
{
    uint32_t alignment = alignment_for(d);
    uint32_t padding = (0u - used) & (alignment - 1);
    uint32_t i;

    for (i = 0; i < layout->placement_count; i++) {
        if (layout->placements[i].type == d->type) {
            *address = layout->placements[i].address;
            *end = used;
            return 1;
        }
    }
    if (used > layout->bytes || padding > layout->bytes - used ||
        d->bytes > layout->bytes - used - padding)
        return 0;
    *address = layout->base + used + padding;
    *end = used + padding + d->bytes;
    return 1;
}

static int valid_state(const struct npu_allocator_state *state,
                       const struct npu_allocator_layout *layout,
                       uint32_t requested_type, uint32_t *cached)
{
    uint32_t seen[8] = {0};
    uint32_t i, cursor = 0;

    if (state->count > NPU_ALLOCATOR_ENTRIES || state->used > layout->bytes)
        return 0;
    *cached = 0;
    for (i = 0; i < state->count; i++) {
        const struct npu_allocator_entry *entry = &state->entries[i];
        const struct npu_allocator_definition *d;
        uint32_t address, end, bit;

        if (entry->type >= NPU_ALLOCATOR_TYPES || entry->reserved)
            return 0;
        bit = 1u << (entry->type & 31);
        if (seen[entry->type >> 5] & bit)
            return 0;
        seen[entry->type >> 5] |= bit;
        d = definition(layout, entry->type, entry->type < 0x81);
        if (!d || !extent(layout, cursor, d, &address, &end) || entry->address != address)
            return 0;
        cursor = end;
        if (entry->type == requested_type)
            *cached = address;
    }
    return cursor == state->used;
}

struct npu_allocator_result npu_allocator_allocate(
    struct npu_allocator_state *state, const struct npu_allocator_layout *layout,
    const struct npu_allocator_lock *lock, uint32_t type, uint32_t table)
{
    struct npu_allocator_result result = {NPU_ALLOCATOR_ARGUMENT, 0};
    const struct npu_allocator_definition *d;
    uint32_t cached, address, end, count;

    if (!state || !layout || !lock || !lock->acquire || !lock->release ||
        table >= NPU_ALLOCATOR_TABLES || !in_table(type, table))
        return result;
    result.status = NPU_ALLOCATOR_LAYOUT;
    if (!valid_layout(layout))
        return result;
    result.status = NPU_ALLOCATOR_UNKNOWN_TYPE;
    d = definition(layout, type, table);
    if (!d)
        return result;
    result.status = NPU_ALLOCATOR_LOCK_DENIED;
    if (lock->acquire(lock->context))
        return result;
    ownership_fence();
    result.status = NPU_ALLOCATOR_CORRUPT;
    if (!valid_state(state, layout, type, &cached))
        goto unlock;
    if (cached) {
        result.status = NPU_ALLOCATOR_OK;
        result.address = cached;
        goto unlock;
    }
    result.status = NPU_ALLOCATOR_CAPACITY;
    count = state->count;
    if (count == NPU_ALLOCATOR_ENTRIES || !extent(layout, state->used, d, &address, &end))
        goto unlock;
    state->entries[count].type = (uint16_t)type;
    state->entries[count].reserved = 0;
    state->entries[count].address = address;
    state->used = end;
    state->attempts++;
    state->count = count + 1;
    result.status = NPU_ALLOCATOR_OK;
    result.address = address;
unlock:
    ownership_fence();
    lock->release(lock->context);
    return result;
}
