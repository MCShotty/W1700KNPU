#include "startup.h"

_Static_assert(sizeof(struct npu_startup) == NPU_STARTUP_BYTES, "startup layout changed");

static uint32_t load(const uint32_t *word)
{
    return __atomic_load_n(word, __ATOMIC_ACQUIRE);
}

static int header(const struct npu_startup *s)
{
    uint32_t i;

    if (load(&s->magic) != NPU_STARTUP_MAGIC ||
        load(&s->version) != NPU_STARTUP_VERSION || load(&s->bytes) != sizeof(*s))
        return 0;
    for (i = 0; i < 3; i++)
        if (load(&s->reserved[i]))
            return 0;
    return 1;
}

static enum npu_startup_action fail(struct npu_startup *s)
{
    /* FAILED arbitrates with the publisher's CAS before the fault latch. */
    __atomic_store_n(&s->phase, NPU_STARTUP_FAILED, __ATOMIC_RELEASE);
    __atomic_store_n(&s->fault, 1, __ATOMIC_RELEASE);
    return NPU_STARTUP_FAULT;
}

enum npu_startup_action npu_startup_poll(struct npu_startup *s, uint32_t hart)
{
    uint32_t phase;

    if (!header(s) || hart >= NPU_BARRIER_WORKERS || load(&s->fault) ||
        load(&s->arrived[hart]) != 1)
        return fail(s);
    phase = load(&s->phase);
    if (phase == NPU_STARTUP_READY) {
        if (load(&s->fault))
            return fail(s);
        return NPU_STARTUP_CONTINUE;
    }
    if (phase == NPU_STARTUP_FRESH || phase == NPU_STARTUP_INITIALIZING)
        return NPU_STARTUP_WAIT;
    return fail(s);
}

enum npu_startup_action npu_startup_arrive(struct npu_startup *s,
                                          uint32_t hart, uint32_t warm)
{
    uint32_t expected = 0;

    if (!header(s) || hart >= NPU_BARRIER_WORKERS || warm || load(&s->fault))
        return fail(s);
    /* A repeated reset entry cannot reuse this boot's already-published state. */
    if (!__atomic_compare_exchange_n(&s->arrived[hart], &expected, 1, 0,
                                      __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE))
        return fail(s);
    if (hart)
        return npu_startup_poll(s, hart);
    expected = NPU_STARTUP_FRESH;
    if (!__atomic_compare_exchange_n(&s->phase, &expected, NPU_STARTUP_INITIALIZING,
                                      0, __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE))
        return fail(s);
    return NPU_STARTUP_INITIALIZE;
}

int npu_startup_publish(struct npu_startup *s, const struct npu_barrier *b,
                        const struct npu_admission *a, const uint32_t *masked,
                        uint32_t hart)
{
    uint32_t i, expected = NPU_STARTUP_INITIALIZING;

    if (!header(s) || hart || load(&s->fault) || load(&s->arrived[0]) != 1 ||
        load(&b->request) != 1 || load(&b->released) || load(&b->armed) ||
        load(&b->prepared) || load(&b->fault) || a->closed != 1 ||
        a->active || a->fault || a->nonce_lo || a->nonce_hi)
        goto fault;
    for (i = 0; i < NPU_BARRIER_WORKERS; i++)
        if (load(&b->parked[i]) || load(&b->ready[i]))
            goto fault;
    for (i = 0; i < NPU_BARRIER_DOMAINS; i++)
        if (load(&b->drained[i]))
            goto fault;
    for (i = 0; i < NPU_ADMISSION_IRQ_WORDS; i++)
        if (a->deferred[i] || masked[i])
            goto fault;
    if (__atomic_compare_exchange_n(&s->phase, &expected, NPU_STARTUP_READY,
                                    0, __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE))
        return 1;
fault:
    fail(s);
    return 0;
}
