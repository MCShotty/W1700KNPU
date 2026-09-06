#include "bootstrap.h"

_Static_assert(sizeof(struct npu_bootstrap) == 80, "bootstrap layout changed");
_Static_assert(sizeof(struct npu_bootstrap_plan) == 48, "bootstrap plan changed");
_Static_assert(sizeof(struct npu_bootstrap_packet) == NPU_BOOTSTRAP_PACKET_BYTES,
               "bootstrap packet changed");

static uint32_t load(const uint32_t *word)
{
    return __atomic_load_n(word, __ATOMIC_ACQUIRE);
}

static int fresh(const struct npu_admission *a, const struct npu_barrier *b)
{
    return a->closed == 1 && !a->fault && !a->nonce_lo && !a->nonce_hi &&
           load(&b->request) == 1 && !load(&b->fault) && !load(&b->prepared) &&
           !load(&b->released) && !load(&b->armed);
}

static int fail(struct npu_bootstrap *s, struct npu_admission *a, struct npu_barrier *b)
{
    s->failed = 1;
    npu_admission_fail(a, b);
    return 0;
}

int npu_bootstrap_init(struct npu_bootstrap *s, const struct npu_bootstrap_plan *plan)
{
    uint32_t i, j;

    /* Reinitialization must not erase already-published resource ownership. */
    if (s->magic || s->failed || s->step || s->inflight || s->retained_mask)
        goto invalid;
    for (i = 0; i < NPU_BOOT_REGIONS; i++) {
        const struct npu_bootstrap_range *r = &plan->region[i];

        if (s->plan.region[i].base || s->plan.region[i].bytes ||
            r->base < 0x80000000u || r->base >= 0xc0000000u ||
            (r->base & 3) || !r->bytes || r->bytes > 0xc0000000u - r->base)
            goto invalid;
        for (j = 0; j < i; j++) {
            const struct npu_bootstrap_range *other = &plan->region[j];

            if (r->base < other->base + other->bytes &&
                other->base < r->base + r->bytes)
                goto invalid;
        }
    }
    if (s->packet.header || s->packet.api || s->packet.value ||
        plan->region[NPU_BOOT_BINARY].bytes < 0x240000u ||
        plan->region[NPU_BOOT_TXCHECK].bytes < 0xe000u ||
        plan->region[NPU_BOOT_REQUEST].bytes != 256u)
        goto invalid;
    for (i = 0; i < NPU_BOOT_REGIONS; i++) {
        s->plan.region[i].base = plan->region[i].base;
        s->plan.region[i].bytes = plan->region[i].bytes;
    }
    s->magic = NPU_BOOTSTRAP_MAGIC;
    return 1;
invalid:
    s->failed = 1;
    return 0;
}

int npu_bootstrap_transport(const struct npu_bootstrap *s, uint32_t address,
                            uint32_t bytes, uint32_t flags)
{
    /* Validate before any request dereference. The coherent buffer is retained
     * by the host across timeout; aliased or offset addresses are not accepted. */
    return s->magic == NPU_BOOTSTRAP_MAGIC && flags == 1 &&
           address == s->plan.region[NPU_BOOT_REQUEST].base &&
           (bytes == NPU_BOOTSTRAP_PACKET_BYTES || bytes == NPU_CONTROL_SIZE);
}

int npu_bootstrap_begin(struct npu_bootstrap *s, struct npu_admission *a,
                        struct npu_barrier *b, const struct npu_bootstrap_packet *p,
                        uint32_t bytes)
{
    static const uint32_t api[NPU_BOOTSTRAP_STEPS] = {18, 32, 8, 23, 7, 12};
    struct npu_bootstrap_packet snapshot;
    uint32_t expected, region = 0;

    if (s->magic != NPU_BOOTSTRAP_MAGIC || s->failed || s->inflight || a->active ||
        !fresh(a, b) || bytes != sizeof(*p))
        return 0;
    snapshot = *p;
    p = &snapshot;
    if (p->header == 0x30 && p->api == 10 && !p->value) {
        /* Version remains available before the first reserved-address command. */
    } else {
        if (s->step >= NPU_BOOTSTRAP_STEPS || p->api != api[s->step] ||
            p->header != (s->step ? 0x10u : 0x11u))
            return 0;
        if (s->step >= 1 && s->step <= 4)
            region = s->step;
        expected = region ? s->plan.region[region].base : 0;
        if (p->value != expected)
            return 0;
    }
    /* Native wrappers use this private snapshot, never reread the host packet. */
    s->packet = *p;
    s->inflight = a->active = 1;
    if (region)
        s->retained_mask |= 1u << region;
    return 1;
}

int npu_bootstrap_finish(struct npu_bootstrap *s, struct npu_admission *a,
                         struct npu_barrier *b, uint32_t result)
{
    if (s->magic != NPU_BOOTSTRAP_MAGIC || s->failed || s->inflight != 1 ||
        a->active != 1 || !fresh(a, b) || result != 1)
        return fail(s, a, b);
    if (s->packet.header != 0x30)
        s->step++;
    s->inflight = a->active = 0;
    return 1;
}
