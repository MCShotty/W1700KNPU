#include "rro-native.h"

struct access {
    struct npu_rro_lifetime *owner;
    const struct npu_rro_native_context *context;
    npu_rro_native_read_fn read;
    npu_rro_native_write_fn write;
    void *opaque;
};

static int owned(const struct access *a)
{
    return !__atomic_load_n(&a->owner->error, __ATOMIC_ACQUIRE) &&
           (a->owner->phase == NPU_RRO_BUILDING || a->owner->phase == NPU_RRO_LIVE) &&
           !a->owner->cpu_joined && a->context->read == a->read &&
           a->context->write == a->write && a->context->opaque == a->opaque;
}

static int read_equal(const struct access *a, uint32_t address, uint32_t bytes, uint32_t expected)
{
    uint32_t value;

    return owned(a) && a->read(a->opaque, address, bytes, &value) && owned(a) && value == expected;
}

static int store(const struct access *a, uint32_t address, uint32_t bytes, uint32_t value)
{
    return owned(a) && a->write(a->opaque, address, bytes, value) && owned(a);
}

static uint32_t alias(uint32_t physical)
{
    return (physical & 0x3fffffffu) | 0x40000000u;
}

static int signatures(const struct access *a, uint32_t base, uint32_t bytes)
{
    for (uint32_t offset = 7; offset < bytes; offset += 8)
        if (!store(a, base + offset, 1, 0xff))
            return 0;
    for (uint32_t offset = 7; offset < bytes; offset += 8)
        if (!read_equal(a, base + offset, 1, 0xff))
            return 0;
    return 1;
}

static uint32_t block_slot(uint32_t profile, uint32_t block)
{
    struct npu_rro_extent geometry;

    for (uint32_t slot = 0; slot < npu_rro_extent_count(profile); slot++)
        if (!npu_rro_extent_geometry(profile, slot, &geometry) &&
            geometry.role == NPU_RRO_ELEMENT && geometry.index == block)
            return slot;
    return NPU_RRO_MAX_EXTENTS;
}

static int context_valid(const struct npu_rro_native_context *c)
{
    return c && c->read && c->write && c->opaque;
}

uint32_t npu_rro_native_publish(struct npu_rro_lifetime *s, const struct npu_rro_plan *p,
    uint32_t ordinal, const struct npu_rro_native_context *c)
{
    struct npu_rro_command command;
    uint32_t ticket, status, base, table, bytes;
    int okay;

    if (!context_valid(c))
        return NPU_RRO_ARGUMENT;
    status = npu_rro_publish_begin(s, p, ordinal, &ticket, &command);
    if (status)
        return status;
    const struct access a = {s, c, c->read, c->write, c->opaque};
    base = alias(command.words[1]);
    table = command.selector ? NPU_RRO_NATIVE_SESSION_TABLE :
            NPU_RRO_NATIVE_BLOCK_TABLE + command.words[0] * 4;
    bytes = command.selector ? NPU_RRO_SESSION_BYTES : NPU_RRO_BLOCK_BYTES;
    /* The journal latches possible exposure before even the table store. */
    okay = store(&a, table, 4, base) && read_equal(&a, table, 4, base);
    if (okay && !command.selector) {
        for (uint32_t offset = 0; offset < bytes; offset += 4)
            if (!store(&a, base + offset, 4, 0)) {
                okay = 0;
                break;
            }
    }
    if (okay)
        okay = signatures(&a, base, bytes);
    if (okay && !command.selector) {
        for (uint32_t offset = 0; offset < bytes; offset += 8)
            if (!read_equal(&a, base + offset, 4, 0) ||
                !read_equal(&a, base + offset + 4, 4, 0xff000000u)) {
                okay = 0;
                break;
            }
    }
    okay = okay && read_equal(&a, table, 4, base);
    return npu_rro_publish_complete(s, p, ordinal, ticket, okay ? 0 : -1);
}

uint32_t npu_rro_native_reset(struct npu_rro_lifetime *s, const struct npu_rro_plan *p,
    uint32_t session, uint32_t generation, uint32_t ticket, const struct npu_rro_native_context *c)
{
    struct npu_rro_command command;
    uint32_t status, slot, table, base, start;
    int okay;

    if (!context_valid(c))
        return NPU_RRO_ARGUMENT;
    status = npu_rro_reset_npu_begin(s, p, session, generation, ticket, &command);
    if (status)
        return status;
    const struct access a = {s, c, c->read, c->write, c->opaque};
    if (session == NPU_RRO_SESSIONS - 1) {
        slot = npu_rro_extent_count(p->profile) - 1;
        table = NPU_RRO_NATIVE_SESSION_TABLE;
        start = 0;
    } else {
        slot = block_slot(p->profile, session / 8);
        table = NPU_RRO_NATIVE_BLOCK_TABLE + (session / 8) * 4;
        start = (session % 8) * NPU_RRO_SESSION_BYTES;
    }
    if (slot >= s->allocated) {
        npu_rro_fault(s, NPU_RRO_CORRUPT);
        return NPU_RRO_CORRUPT;
    }
    base = alias(s->extents[slot].dma_lo);
    okay = read_equal(&a, table, 4, base) &&
           signatures(&a, base + start, NPU_RRO_SESSION_BYTES) && read_equal(&a, table, 4, base);
    return npu_rro_reset_npu_complete(s, p, session, generation, ticket, okay ? 0 : -1);
}
