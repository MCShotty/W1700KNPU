#include "cold-tx-buffer.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned checks;

static void check(int condition, const char *name)
{
    checks++;
    if (!condition) {
        fprintf(stderr, "FAIL[txbuf] %s\n", name);
        exit(11);
    }
}

static struct npu_cold_txbuf_plan plan(void)
{
    struct npu_cold_txbuf_plan p = {
        .arena = 0x3e810000, .endpoint_base = 0x20000000, .endpoint_bytes = 0x100000,
        .host = {0x96000000, 0x96100000, 0x96200000, 0x96300000, 0x96400000, 0x96500000},
        .mailbox = {0x83000000, 0x83100000, 0x83200000, 0x83300000,
                    0x83400000, 0x83500000, 0x83600000, 0x83700000},
        .boot.region = {{0x84000000, 0xa00000}, {0x90c00000, 0xe000},
                        {0x8a000000, 0x2c00000}, {0x8cc00000, 0x4000000},
                        {0x90c0e000, 0x200000}, {0x83000000, 256}}
    };

    return p;
}

static unsigned meta_count(unsigned step)
{
    return step == 2 || step == 5 ? 4 : 1;
}

static unsigned count(unsigned step)
{
    static const unsigned counts[] = {1, 16385, 2052, 1, 32769, 2052};

    return counts[step];
}

/* This oracle comes from the original ef36/a5fa store traces, not the core recipe. */
static struct npu_cold_txbuf_store original(const struct npu_cold_txbuf_plan *p,
                                           unsigned step, unsigned index)
{
    static const unsigned slots[] = {0x3e902cf8, 0x3e901f38, 0x3e903960,
                                    0x3e902ab4, 0x3e902abc, 0x3e902a88};
    static const unsigned metadata[2][3] = {{0x3e90462c, 0x3e90395a, 0x3e902acc},
                                           {0x3e902a8c, 0x3e90390c, 0x3e9021e8}};
    struct npu_cold_txbuf_store result = {.bytes = 4};
    unsigned band = step >= 3, internal = step == 1 || step == 4;
    unsigned base = internal ? p->arena + (band ? 0x2a040 : 0x8020) :
                              band ? 0x3e8a4020 : 0x3e8a2000;

    if (!index) {
        result.address = slots[step];
        result.value = internal ? base : (p->host[step] & 0x3fffffff) | 0x40000000;
    } else if (index < meta_count(step)) {
        result.address = metadata[band][index - 1];
        result.bytes = index < 3 ? 2 : 4;
        result.value = index < 3 ? 0 : base;
    } else {
        unsigned word = index - meta_count(step);

        result.address = base + word * 4;
        if (internal)
            result.value = word % 32 == 0 ? 0x100000 : word % 32 == 31 ? 0x10000 : 0;
        else {
            result.bytes = word % 4 == 3 ? 1 : 4;
            result.value = word % 4 ? 0 : ((p->host[step] + word / 4 * 256) & 0x3fffffff) | 0x80000000;
        }
    }
    return result;
}

unsigned npu_test_txbuf_sequence(unsigned salt)
{
    struct npu_cold_txbuf_state *s = calloc(1, sizeof(*s));
    struct npu_cold_txbuf_plan p = plan();
    unsigned selectors[] = {0, 5, 10, 2, 7, 12};
    unsigned step, i, total = 0;

    check(s != NULL, "state backing");
    check(npu_cold_txbuf_plan_valid(&p), "valid complete plan");
    for (step = 0; step < 6; step++) {
        unsigned meta[4] = {0xdeadbeef ^ salt, 0x1234, 0xabcd, 0xcafef00d ^ salt};
        unsigned n = count(step) - meta_count(step);
        unsigned *records = n ? malloc(n * sizeof(*records)) : NULL;

        check(!n || records != NULL, "record backing");
        for (i = 0; i < n; i++)
            records[i] = (i * 0x9e3779b1u + salt) ^ 0xa5c3e7f9u;
        check(!npu_cold_txbuf_begin(s, &p, 1, selectors[step], p.host[step], meta, records), "begin exact selector");
        for (i = 0; i < count(step); i++) {
            struct npu_cold_txbuf_store wanted = original(&p, step, i), actual;
            unsigned *cell = i < meta_count(step) ? &meta[i] : &records[i - meta_count(step)];
            unsigned before = *cell, readback = wanted.bytes == 1 ? (before & 0xffffff00u) | wanted.value : wanted.value;

            check(!npu_cold_txbuf_recipe(&p, step, i, &actual) &&
                  actual.address == wanted.address && actual.bytes == wanted.bytes && actual.value == wanted.value,
                  "independent original store recipe");
            check(!npu_cold_txbuf_reserve(s, &p, 1, wanted.address, wanted.bytes, wanted.value, before), "reserve before store");
            check(s->committed == total + 1 && s->published == total && s->preimages[total] == before,
                  "retained arbitrary preimage and pending claim");
            *cell = readback;
            check(!npu_cold_txbuf_publish(s, &p, 1, wanted.address, wanted.bytes, *cell), "publish exact readback");
            total++;
        }
        check(!npu_cold_txbuf_finish(s, &p, 1, meta, records), "finish whole owned span");
        check(s->next == step + 1 && !s->active && s->completed == (1u << (step + 1)) - 1,
              "one-shot progress, not retirement");
        free(records);
    }
    check(total == 53260 && s->reserved == 63 && s->committed == s->published, "all six selectors complete");
    check(npu_cold_txbuf_begin(s, &p, 1, 0, p.host[0], NULL, NULL) != 0 && s->fault,
          "completed owner cannot restart");
    free(s);
    return total;
}

unsigned npu_test_txbuf_controls(void)
{
    struct npu_cold_txbuf_state *s = calloc(1, sizeof(*s));
    struct npu_cold_txbuf_plan p = plan(), changed;
    unsigned meta[4] = {0x89abcdef, 0, 0, 0}, i;
    unsigned controls = 0;

    check(s != NULL, "control state");
    for (i = 0; i < 6; i++) {
        changed = p;
        changed.host[i] = 0;
        check(!npu_cold_txbuf_plan_valid(&changed), "missing host extent"); controls++;
        changed = p;
        changed.host[i] = p.mailbox[0];
        check(!npu_cold_txbuf_plan_valid(&changed), "mailbox overlap"); controls++;
        changed = p;
        changed.host[i] = p.endpoint_base | 0x80000000;
        check(!npu_cold_txbuf_plan_valid(&changed), "cached BAR overlap"); controls++;
        changed = p;
        changed.host[i] = 0xbfffff00;
        check(!npu_cold_txbuf_plan_valid(&changed), "whole host span"); controls++;
    }
    for (i = 0; i < 8; i++) {
        changed = p; changed.mailbox[i] = p.mailbox[(i + 1) % 8];
        check(!npu_cold_txbuf_plan_valid(&changed), "mailbox identity or duplicate"); controls++;
    }
    s->preimages[53259] = 1;
    check(npu_cold_txbuf_begin(s, &p, 1, 0, p.host[0], meta, NULL) == NPU_COLD_TXBUF_REINITIALIZE && !s->magic,
          "dirty tail cannot become fresh state"); controls++;
    memset(s, 0, sizeof(*s));
    check(!npu_cold_txbuf_begin(s, &p, 1, 0, p.host[0], meta, NULL), "control begin");
    check(npu_cold_txbuf_reserve(s, &p, 2, 0x3e902cf8, 4, 0x56000000, meta[0]) == NPU_COLD_TXBUF_STALE && !s->fault,
          "stale epoch does not mutate progress"); controls++;
    check(npu_cold_txbuf_reserve(s, &p, 1, 0x3e902cf8, 4, 0x56000000, meta[0] ^ 1) == NPU_COLD_TXBUF_ORDER && s->fault,
          "changed preimage fails before store"); controls++;
    memset(s, 0, sizeof(*s));
    check(!npu_cold_txbuf_begin(s, &p, 1, 0, p.host[0], meta, NULL), "partial begin");
    check(!npu_cold_txbuf_reserve(s, &p, 1, 0x3e902cf8, 4, 0x56000000, meta[0]), "partial claim");
    check(npu_cold_txbuf_publish(s, &p, 1, 0x3e902cf8, 4, 0x56000001) == NPU_COLD_TXBUF_PUBLISH &&
          s->fault && s->active && s->committed == 1 && !s->published, "bad readback retains pending claim"); controls++;
    for (i = 0; i < 5; i++) {
        unsigned address = 0x3e902cf8, width = 4, value = 0x56000000, before = meta[0];

        memset(s, 0, sizeof(*s)); changed = p;
        check(!npu_cold_txbuf_begin(s, &p, 1, 0, p.host[0], meta, NULL), "negative begin");
        if (i == 0) address += 4;
        if (i == 1) width = 1;
        if (i == 2) value ^= 1;
        if (i == 3) before ^= 1;
        if (i == 4) changed.host[5] += 256;
        check(npu_cold_txbuf_reserve(s, &changed, 1, address, width, value, before) != 0 &&
              s->fault && s->active && !s->committed && !s->published,
              "address/width/value/preimage/whole-plan pin before store"); controls++;
    }
    memset(s, 0, sizeof(*s));
    check(!npu_cold_txbuf_begin(s, &p, 1, 0, p.host[0], meta, NULL), "whole readback begin");
    check(!npu_cold_txbuf_reserve(s, &p, 1, 0x3e902cf8, 4, 0x56000000, meta[0]), "whole readback reserve");
    check(!npu_cold_txbuf_publish(s, &p, 1, 0x3e902cf8, 4, 0x56000000), "whole readback publication");
    check(npu_cold_txbuf_finish(s, &p, 1, meta, NULL) == NPU_COLD_TXBUF_PUBLISH &&
          s->active && s->committed == 1 && s->published == 1,
          "finish rechecks actual full metadata span"); controls++;
    free(s);
    return controls;
}

#ifndef TXBUF_LIBRARY
int main(void)
{
    unsigned stores = npu_test_txbuf_sequence(0x13579bdf);
    unsigned controls = npu_test_txbuf_controls();

    printf("{\"passed\":true,\"stores\":%u,\"controls\":%u,\"checks\":%u}\n", stores, controls, checks);
    return 0;
}
#endif
