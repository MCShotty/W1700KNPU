#include "cold-descriptor.h"

_Static_assert(sizeof(struct npu_cold_descriptor_state) == 6188, "descriptor owner changed");

static uint32_t load(const uint32_t *p)
{
    return __atomic_load_n(p, __ATOMIC_ACQUIRE);
}

void npu_cold_descriptor_fault(struct npu_cold_descriptor_state *s)
{
    if (s)
        __atomic_store_n(&s->fault, 1, __ATOMIC_RELEASE);
}

static uint32_t fail(struct npu_cold_descriptor_state *s, uint32_t status)
{
    npu_cold_descriptor_fault(s);
    return status;
}

static uint32_t lower(uint32_t step)
{
    return step < 7 ? 0 : 512;
}

static uint32_t upper(uint32_t step)
{
    return step < 6 ? 0 : step == 6 ? 512 : 1536;
}

static uint32_t valid(struct npu_cold_descriptor_state *s, uint32_t arena,
                      uint32_t epoch, uint32_t active)
{
    uint32_t completed, reserved, bound;

    if (!s)
        return NPU_COLD_DESCRIPTOR_ARGUMENT;
    if (load(&s->fault))
        return NPU_COLD_DESCRIPTOR_FAULT;
    if (s->next > NPU_COLD_DESCRIPTOR_STEPS || (active && s->next == NPU_COLD_DESCRIPTOR_STEPS))
        return fail(s, NPU_COLD_DESCRIPTOR_CORRUPT);
    completed = s->next < 7 ? 0 : s->next == 7 ? 1 : 3;
    reserved = active && s->next >= 6 ? (s->next == 6 ? 1 : 3) : completed;
    bound = active ? upper(s->next) : s->next < 7 ? 0 : s->next == 7 ? 512 : 1536;
    if (!npu_cold_descriptor_arena_valid(arena) || s->magic != NPU_COLD_DESCRIPTOR_MAGIC ||
        s->epoch != 1 || s->arena != arena || s->active != active ||
        s->completed != (1u << s->next) - 1 || s->reserved_tx != reserved ||
        s->completed_tx != completed || s->committed > bound || s->published > s->committed ||
        s->committed - s->published > 1 ||
        (active && s->committed < lower(s->next)) ||
        (!active && (s->committed != bound || s->published != bound)))
        return fail(s, NPU_COLD_DESCRIPTOR_CORRUPT);
    return epoch == s->epoch ? NPU_COLD_DESCRIPTOR_OK : NPU_COLD_DESCRIPTOR_STALE;
}

uint32_t npu_cold_descriptor_begin(struct npu_cold_descriptor_state *s, uint32_t arena,
    uint32_t epoch, uint32_t selector, const volatile uint32_t *descriptors)
{
    uint32_t step = npu_cold_descriptor_step(selector), i, status;

    if (!s)
        return NPU_COLD_DESCRIPTOR_ARGUMENT;
    if (!s->magic) {
        const unsigned char *bytes = (const unsigned char *)s;

        for (i = 0; i < sizeof(*s); i++)
            if (bytes[i])
                return NPU_COLD_DESCRIPTOR_REINITIALIZE;
        if (epoch != 1 || step || descriptors || !npu_cold_descriptor_arena_valid(arena))
            return fail(s, NPU_COLD_DESCRIPTOR_PLAN);
        s->epoch = 1;
        s->arena = arena;
        __atomic_store_n(&s->magic, NPU_COLD_DESCRIPTOR_MAGIC, __ATOMIC_RELEASE);
    }
    status = valid(s, arena, epoch, 0);
    if (status)
        return status;
    if (step != s->next || step == NPU_COLD_DESCRIPTOR_STEPS ||
        (step < 6 ? !!descriptors : !descriptors || ((uintptr_t)descriptors & 3)))
        return fail(s, NPU_COLD_DESCRIPTOR_ORDER);
    s->active = 1;
    if (step >= 6) {
        s->reserved_tx |= 1u << (step - 6);
        for (i = lower(step); i < upper(step); i++)
            s->preimages[i] = descriptors[(i - lower(step)) * 4 + 1];
    }
    return load(&s->fault) ? NPU_COLD_DESCRIPTOR_FAULT : NPU_COLD_DESCRIPTOR_OK;
}

static uint32_t address(const struct npu_cold_descriptor_state *s, uint32_t index)
{
    return s->arena + npu_cold_descriptor_offset(s->next) + 4 +
           (index - lower(s->next)) * 16;
}

uint32_t npu_cold_descriptor_reserve(struct npu_cold_descriptor_state *s, uint32_t arena,
    uint32_t epoch, uint32_t destination, uint32_t value, uint32_t before)
{
    uint32_t status = valid(s, arena, epoch, 1);

    if (status)
        return status;
    if (s->next < 6 || s->committed != s->published || s->committed == upper(s->next) ||
        destination != address(s, s->committed) || value != NPU_COLD_DESCRIPTOR_STATUS ||
        before != s->preimages[s->committed])
        return fail(s, NPU_COLD_DESCRIPTOR_ORDER);
    __atomic_store_n(&s->committed, s->committed + 1, __ATOMIC_RELEASE);
    return load(&s->fault) ? NPU_COLD_DESCRIPTOR_FAULT : NPU_COLD_DESCRIPTOR_OK;
}

uint32_t npu_cold_descriptor_publish(struct npu_cold_descriptor_state *s, uint32_t arena,
    uint32_t epoch, uint32_t destination, uint32_t readback)
{
    uint32_t status = valid(s, arena, epoch, 1);

    if (status)
        return status;
    if (s->next < 6 || s->committed != s->published + 1 || s->published == upper(s->next) ||
        destination != address(s, s->published) || readback != NPU_COLD_DESCRIPTOR_STATUS)
        return fail(s, NPU_COLD_DESCRIPTOR_PUBLISH);
    __atomic_store_n(&s->published, s->published + 1, __ATOMIC_RELEASE);
    return load(&s->fault) ? NPU_COLD_DESCRIPTOR_FAULT : NPU_COLD_DESCRIPTOR_OK;
}

uint32_t npu_cold_descriptor_finish(struct npu_cold_descriptor_state *s, uint32_t arena,
    uint32_t epoch, uint32_t reply, const volatile uint32_t *descriptors)
{
    uint32_t status = valid(s, arena, epoch, 1), i;

    if (status)
        return status;
    if (npu_cold_descriptor_reply_arena(s->next, reply, arena) != arena ||
        s->committed != upper(s->next) || s->published != s->committed ||
        (s->next < 6 ? !!descriptors : !descriptors || ((uintptr_t)descriptors & 3)))
        return fail(s, NPU_COLD_DESCRIPTOR_PUBLISH);
    if (s->next >= 6) {
        for (i = lower(s->next); i < upper(s->next); i++)
            if (descriptors[(i - lower(s->next)) * 4 + 1] != NPU_COLD_DESCRIPTOR_STATUS)
                return fail(s, NPU_COLD_DESCRIPTOR_PUBLISH);
        s->completed_tx |= 1u << (s->next - 6);
    }
    s->completed |= 1u << s->next;
    s->next++;
    s->active = 0;
    return load(&s->fault) ? NPU_COLD_DESCRIPTOR_FAULT : NPU_COLD_DESCRIPTOR_OK;
}
