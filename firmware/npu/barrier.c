#include "barrier.h"

static uint32_t load(const uint32_t *word)
{
    return __atomic_load_n(word, __ATOMIC_ACQUIRE);
}

static void store(uint32_t *word, uint32_t value)
{
    __atomic_store_n(word, value, __ATOMIC_RELEASE);
}

static void ownership_fence(void)
{
#ifdef __riscv
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
#else
    __atomic_thread_fence(__ATOMIC_SEQ_CST);
#endif
}

static int stopped(const struct npu_barrier *s, uint32_t epoch)
{
    return epoch && !load(&s->fault) && load(&s->request) == epoch &&
           load(&s->released) != epoch;
}

void npu_barrier_init(struct npu_barrier *s)
{
    uint32_t i;

    s->request = 1;
    s->released = s->armed = s->prepared = s->fault = 0;
    for (i = 0; i < NPU_BARRIER_WORKERS; i++)
        s->parked[i] = s->ready[i] = 0;
    for (i = 0; i < NPU_BARRIER_DOMAINS; i++)
        s->drained[i] = 0;
    ownership_fence();
}

uint32_t npu_barrier_stop(struct npu_barrier *s)
{
    uint32_t epoch = load(&s->request);

    if (load(&s->fault) || !epoch)
        return 0;
    if (load(&s->released) != epoch)
        return epoch;
    /* Never wrap into an old acknowledgement, even after a partial restart. */
    if (epoch == UINT32_MAX) {
        store(&s->fault, 1);
        return 0;
    }
    store(&s->request, epoch + 1);
    return epoch + 1;
}

enum npu_barrier_action npu_barrier_poll(struct npu_barrier *s,
                                       uint32_t hart, uint32_t *epoch)
{
    uint32_t current = load(&s->request);

    *epoch = current;
    if (hart >= NPU_BARRIER_WORKERS || !current || load(&s->fault))
        return NPU_BARRIER_FAULT;
    if (load(&s->released) != current) {
        /* Caller must be outside ownership work with datapath IRQs gated.
         * A fence orders writes; it is NOT a hardware DMA-drain witness. */
        ownership_fence();
        store(&s->parked[hart], current);
        return NPU_BARRIER_PARK;
    }
    if (load(&s->ready[hart]) != current)
        return NPU_BARRIER_REFRESH;
    if (load(&s->armed) != current)
        return NPU_BARRIER_PARK;
    return NPU_BARRIER_RUN;
}

int npu_barrier_workers_parked(const struct npu_barrier *s, uint32_t epoch)
{
    uint32_t i;

    if (!stopped(s, epoch))
        return 0;
    for (i = 0; i < NPU_BARRIER_WORKERS; i++)
        if (load(&s->parked[i]) != epoch)
            return 0;
    return stopped(s, epoch);
}

int npu_barrier_record_drain(struct npu_barrier *s, uint32_t domain, uint32_t epoch)
{
    if (domain >= NPU_BARRIER_DOMAINS || !npu_barrier_workers_parked(s, epoch))
        return 0;
    /* Only a platform-specific, generation-matched drain completion may call
     * this. Timeouts, old mailbox DONEs and an IRQ mask alone are not witnesses. */
    ownership_fence();
    store(&s->drained[domain], epoch);
    return 1;
}

int npu_barrier_reclaimable(const struct npu_barrier *s, uint32_t epoch)
{
    uint32_t i;

    if (!npu_barrier_workers_parked(s, epoch))
        return 0;
    for (i = 0; i < NPU_BARRIER_DOMAINS; i++)
        if (load(&s->drained[i]) != epoch)
            return 0;
    return stopped(s, epoch);
}

int npu_barrier_prepare(struct npu_barrier *s, uint32_t epoch)
{
    if (!npu_barrier_reclaimable(s, epoch))
        return 0;
    /* New ring storage and globals are published while all owners are parked. */
    ownership_fence();
    store(&s->prepared, epoch);
    return 1;
}

int npu_barrier_release(struct npu_barrier *s, uint32_t epoch)
{
    if (!npu_barrier_reclaimable(s, epoch) || load(&s->prepared) != epoch)
        return 0;
    store(&s->released, epoch);
    return 1;
}

int npu_barrier_refreshed(struct npu_barrier *s, uint32_t hart, uint32_t epoch)
{
    if (hart >= NPU_BARRIER_WORKERS || !epoch || load(&s->fault) ||
        load(&s->request) != epoch || load(&s->released) != epoch)
        return 0;
    /* Caller has reloaded cached pointers/indices, without consuming work. */
    ownership_fence();
    store(&s->ready[hart], epoch);
    return 1;
}

int npu_barrier_arm(struct npu_barrier *s, uint32_t epoch)
{
    uint32_t i;

    if (!epoch || load(&s->fault) || load(&s->request) != epoch ||
        load(&s->released) != epoch || load(&s->prepared) != epoch)
        return 0;
    for (i = 0; i < NPU_BARRIER_WORKERS; i++)
        if (load(&s->ready[i]) != epoch)
            return 0;
    /* Platform restart must have succeeded, with external ingress still gated.
     * Only after this succeeds may the coordinator reopen that ingress. */
    ownership_fence();
    store(&s->armed, epoch);
    return 1;
}
