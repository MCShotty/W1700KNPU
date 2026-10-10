/* Two fixed geometries share the same retained-claim implementation. */
#ifdef NPU_COLD_PACKET_BUILD
#include "cold-packet.h"
#define npu_cold_page_state npu_cold_packet_state
#define npu_cold_page_plan npu_cold_packet_plan
#define npu_cold_page_result npu_cold_packet_result
#define npu_cold_page_queue npu_cold_packet_queue
#define npu_cold_page_queue_result npu_cold_packet_queue_result
#define npu_cold_page_init npu_cold_packet_init
#define npu_cold_page_take npu_cold_packet_take
#define npu_cold_page_queue_take npu_cold_packet_queue_take
#define npu_cold_page_fault npu_cold_packet_fault
#define NPU_COLD_PAGE_MAGIC NPU_COLD_PACKET_MAGIC
#define NPU_COLD_PAGE_IDS NPU_COLD_PACKET_IDS
#define NPU_COLD_PAGE_BYTES NPU_COLD_PACKET_BYTES
#define NPU_COLD_PAGE_WORDS NPU_COLD_PACKET_WORDS
#define NPU_COLD_PAGE_OK NPU_COLD_PACKET_OK
#define NPU_COLD_PAGE_ARGUMENT NPU_COLD_PACKET_ARGUMENT
#define NPU_COLD_PAGE_PLAN NPU_COLD_PACKET_PLAN
#define NPU_COLD_PAGE_REINITIALIZE NPU_COLD_PACKET_REINITIALIZE
#define NPU_COLD_PAGE_FAULT NPU_COLD_PACKET_FAULT
#define NPU_COLD_PAGE_STALE NPU_COLD_PACKET_STALE
#define NPU_COLD_PAGE_CORRUPT NPU_COLD_PACKET_CORRUPT
#define NPU_COLD_PAGE_EMPTY NPU_COLD_PACKET_EMPTY
#define NPU_COLD_PAGE_ID NPU_COLD_PACKET_ID
#define NPU_COLD_PAGE_DUPLICATE NPU_COLD_PACKET_DUPLICATE
#define page packet
#define COLD_STATE_BYTES 2076
#else
#include "cold-page.h"
#define COLD_STATE_BYTES 1052
#endif

_Static_assert(sizeof(struct npu_cold_page_state) == COLD_STATE_BYTES, "cold pool state changed");
_Static_assert(sizeof(struct npu_cold_page_plan) == 8, "cold page plan changed");
_Static_assert(sizeof(struct npu_cold_page_result) == 20, "cold page result changed");

static uint32_t faulted(const struct npu_cold_page_state *s)
{
    return __atomic_load_n(&s->fault, __ATOMIC_ACQUIRE);
}

void npu_cold_page_fault(struct npu_cold_page_state *s)
{
    if (s)
        __atomic_store_n(&s->fault, 1, __ATOMIC_RELEASE);
}

static int plan_valid(const struct npu_cold_page_plan *p)
{
    return p->packet_base >= 0x80000000u && p->packet_base < 0xc0000000u &&
           !(p->packet_base & (NPU_COLD_PAGE_BYTES - 1)) &&
           p->packet_bytes >= NPU_COLD_PAGE_IDS * NPU_COLD_PAGE_BYTES &&
           p->packet_bytes <= 0xc0000000u - p->packet_base;
}

static uint32_t population(uint32_t word)
{
    word -= (word >> 1) & 0x55555555u;
    word = (word & 0x33333333u) + ((word >> 2) & 0x33333333u);
    word = (word + (word >> 4)) & 0x0f0f0f0fu;
    return (word * 0x01010101u) >> 24;
}

uint32_t npu_cold_page_init(struct npu_cold_page_state *s,
                           const struct npu_cold_page_plan *p, uint32_t epoch)
{
    uint32_t i;

    if (!s || !p)
        return NPU_COLD_PAGE_ARGUMENT;
    if (s->magic || s->epoch || faulted(s) || s->head || s->count ||
        s->packet_base || s->packet_bytes)
        return NPU_COLD_PAGE_REINITIALIZE;
    for (i = 0; i < NPU_COLD_PAGE_WORDS; i++)
        if (s->claimed[i])
            return NPU_COLD_PAGE_REINITIALIZE;
    if (!epoch || !plan_valid(p)) {
        npu_cold_page_fault(s);
        return NPU_COLD_PAGE_PLAN;
    }
    s->epoch = epoch;
    s->packet_base = p->packet_base;
    s->packet_bytes = p->packet_bytes;
    __atomic_store_n(&s->magic, NPU_COLD_PAGE_MAGIC, __ATOMIC_RELEASE);
    return faulted(s) ? NPU_COLD_PAGE_FAULT : NPU_COLD_PAGE_OK;
}

static struct npu_cold_page_result fail(struct npu_cold_page_state *s, uint32_t status)
{
    struct npu_cold_page_result result = {status, UINT32_MAX, 0, UINT32_MAX, 0};

    npu_cold_page_fault(s);
    return result;
}

struct npu_cold_page_queue_result npu_cold_page_queue_take(
    struct npu_cold_page_state *s, const struct npu_cold_page_plan *p,
    uint32_t epoch, const struct npu_cold_page_queue *q)
{
    struct npu_cold_page_queue_result result;
    uint32_t head, tail, id;

    /* Field initialization avoids a -Os freestanding memcpy dependency. */
    result.page.status = NPU_COLD_PAGE_ARGUMENT;
    result.page.id = UINT32_MAX;
    result.page.address = 0;
    result.page.next_head = UINT32_MAX;
    result.page.committed = 0;
    result.published = 0;
    if (!s || !p || !q)
        return result;
    if (__atomic_load_n(&s->magic, __ATOMIC_ACQUIRE) != NPU_COLD_PAGE_MAGIC || faulted(s)) {
        result.page = fail(s, NPU_COLD_PAGE_FAULT);
        return result;
    }
    if (!s->epoch) {
        result.page = fail(s, NPU_COLD_PAGE_CORRUPT);
        return result;
    }
    if (!epoch || epoch != s->epoch) {
        result.page.status = NPU_COLD_PAGE_STALE;
        return result;
    }
    if (!q->head || !q->tail || !q->ids || q->capacity != NPU_COLD_PAGE_IDS ||
        ((uintptr_t)q->head & 1) || ((uintptr_t)q->tail & 1) || ((uintptr_t)q->ids & 1)) {
        result.page = fail(s, NPU_COLD_PAGE_CORRUPT);
        return result;
    }
    head = *q->head;
    tail = *q->tail;
    if (head >= NPU_COLD_PAGE_IDS || tail >= NPU_COLD_PAGE_IDS) {
        result.page = fail(s, NPU_COLD_PAGE_CORRUPT);
        return result;
    }
    id = q->ids[head];
    result.page = npu_cold_page_take(s, p, epoch, head, tail, id);
    if (!result.page.committed)
        return result;

    /* Retain the private claim even when the native snapshot can no longer be
     * published. Never reset either cursor or give the claimed ID back. */
    if (*q->head != head || *q->tail != tail || q->ids[head] != id) {
        npu_cold_page_fault(s);
        result.page.status = NPU_COLD_PAGE_CORRUPT;
        return result;
    }
    __atomic_thread_fence(__ATOMIC_RELEASE);
    *q->head = (uint16_t)result.page.next_head;
    __atomic_thread_fence(__ATOMIC_SEQ_CST);
    if (*q->head != result.page.next_head) {
        npu_cold_page_fault(s);
        result.page.status = NPU_COLD_PAGE_CORRUPT;
        return result;
    }
    result.published = 1;
    if (faulted(s))
        result.page.status = NPU_COLD_PAGE_FAULT;
    return result;
}

struct npu_cold_page_result npu_cold_page_take(
    struct npu_cold_page_state *s, const struct npu_cold_page_plan *p,
    uint32_t epoch, uint32_t head, uint32_t tail, uint32_t id)
{
    struct npu_cold_page_result result = {NPU_COLD_PAGE_ARGUMENT, UINT32_MAX, 0, UINT32_MAX, 0};
    uint32_t i, owned = 0, next, bit;

    if (!s || !p)
        return result;
    if (__atomic_load_n(&s->magic, __ATOMIC_ACQUIRE) != NPU_COLD_PAGE_MAGIC || faulted(s))
        return fail(s, NPU_COLD_PAGE_FAULT);
    if (!s->epoch)
        return fail(s, NPU_COLD_PAGE_CORRUPT);
    if (!epoch || epoch != s->epoch) {
        result.status = NPU_COLD_PAGE_STALE;
        return result;
    }
    if (!plan_valid(p) || s->packet_base != p->packet_base || s->packet_bytes != p->packet_bytes ||
        head >= NPU_COLD_PAGE_IDS || tail >= NPU_COLD_PAGE_IDS || s->head != head ||
        s->count > NPU_COLD_PAGE_IDS ||
        s->head != (s->count & (NPU_COLD_PAGE_IDS - 1)))
        return fail(s, NPU_COLD_PAGE_CORRUPT);
    for (i = 0; i < NPU_COLD_PAGE_WORDS; i++)
        owned += population(s->claimed[i]);
    if (owned != s->count)
        return fail(s, NPU_COLD_PAGE_CORRUPT);
    next = (head + 1) & (NPU_COLD_PAGE_IDS - 1);
    if (next == tail)
        return fail(s, NPU_COLD_PAGE_EMPTY);
    if (id >= NPU_COLD_PAGE_IDS)
        return fail(s, NPU_COLD_PAGE_ID);
    bit = 1u << (id & 31);
    if (s->claimed[id >> 5] & bit)
        return fail(s, NPU_COLD_PAGE_DUPLICATE);
    if (faulted(s))
        return fail(s, NPU_COLD_PAGE_FAULT);

    /* Claim before native head publication. An interrupted caller retains this
     * record instead of letting another setup retry reuse the same page. */
    s->claimed[id >> 5] |= bit;
    s->head = next;
    s->count++;
    __atomic_thread_fence(__ATOMIC_RELEASE);
    result.id = id;
    result.address = p->packet_base + id * NPU_COLD_PAGE_BYTES;
    result.next_head = next;
    result.committed = 1;
    result.status = faulted(s) ? NPU_COLD_PAGE_FAULT : NPU_COLD_PAGE_OK;
    return result;
}
