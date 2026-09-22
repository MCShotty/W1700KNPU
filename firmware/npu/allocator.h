#ifndef W1700K_NPU_ALLOCATOR_H
#define W1700K_NPU_ALLOCATOR_H

#include <stdint.h>

#define NPU_ALLOCATOR_ENTRIES 100u
#define NPU_ALLOCATOR_TABLES 2u
#define NPU_ALLOCATOR_TYPES 256u

struct npu_allocator_definition {
    uint16_t type;
    uint8_t alignment_tag;
    uint8_t reserved;
    uint32_t bytes;
};

struct npu_allocator_entry {
    uint16_t type;
    uint16_t reserved;
    uint32_t address;
};

/* Native layout at 0x3e901bcc. Unused native words remain untouched. */
struct npu_allocator_state {
    uint32_t lock_id;
    uint32_t native_reserved0;
    uint32_t count;
    uint32_t native_reserved1;
    uint32_t attempts;
    uint32_t used;
    struct npu_allocator_entry entries[NPU_ALLOCATOR_ENTRIES];
};

struct npu_allocator_layout {
    uint32_t base;
    uint32_t bytes;
    const struct npu_allocator_definition *tables[NPU_ALLOCATOR_TABLES];
    uint32_t lengths[NPU_ALLOCATOR_TABLES];
    const struct npu_allocator_entry *placements;
    uint32_t placement_count;
};

/* Layout/tables are immutable. Every metadata user must honor the same lock.
 * Optional placements reserve a definition's full extent outside the heap;
 * their records count normally but do not advance the heap cursor. The caller
 * supplies backing, initialization and one non-aliasing address namespace.
 * Acquire returns zero only with ownership; release is called only then.
 * Platform grant, release and cache-coherency semantics remain caller contracts. */
struct npu_allocator_lock {
    void *context;
    int (*acquire)(void *context);
    void (*release)(void *context);
};

enum npu_allocator_status {
    NPU_ALLOCATOR_OK,
    NPU_ALLOCATOR_ARGUMENT,
    NPU_ALLOCATOR_LAYOUT,
    NPU_ALLOCATOR_UNKNOWN_TYPE,
    NPU_ALLOCATOR_LOCK_DENIED,
    NPU_ALLOCATOR_CORRUPT,
    NPU_ALLOCATOR_CAPACITY,
};

struct npu_allocator_result {
    uint32_t status;
    uint32_t address;
};

/* Rejects do not change allocation metadata. Cached lookup does not allocate.
 * Failure retention and mailbox-safe error handling belong to the caller. */
struct npu_allocator_result npu_allocator_allocate(
    struct npu_allocator_state *state, const struct npu_allocator_layout *layout,
    const struct npu_allocator_lock *lock, uint32_t type, uint32_t table);

#endif
