#include "cold-page.h"

uint32_t probe_init(struct npu_cold_page_state *s, const struct npu_cold_page_plan *p,
                    uint32_t epoch)
{
    return npu_cold_page_init(s, p, epoch);
}

uint32_t probe_take(struct npu_cold_page_state *s, const struct npu_cold_page_plan *p,
                    uint32_t epoch, uint32_t head, uint32_t tail, uint32_t id,
                    struct npu_cold_page_result *result)
{
    *result = npu_cold_page_take(s, p, epoch, head, tail, id);
    return result->status;
}

uint32_t probe_fault(struct npu_cold_page_state *s)
{
    npu_cold_page_fault(s);
    return s ? __atomic_load_n(&s->fault, __ATOMIC_ACQUIRE) : 0;
}
