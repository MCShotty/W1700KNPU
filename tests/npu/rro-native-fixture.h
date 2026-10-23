#ifndef W1700K_RRO_NATIVE_FIXTURE_H
#define W1700K_RRO_NATIVE_FIXTURE_H

#include "rro-native.h"

#define RRO_TEST_ALIAS 0x48000000u
#define RRO_TEST_ALIAS_BYTES 0x804000u
#define RRO_TEST_SRAM 0x3e900000u
#define RRO_TEST_SRAM_BYTES 0x5000u

static void rro_test_zero(void *pointer, uint32_t bytes)
{
    volatile unsigned char *p = pointer;
    for (uint32_t i = 0; i < bytes; i++) p[i] = 0;
}

static void rro_test_plan(struct npu_rro_plan *p, uint32_t profile)
{
    rro_test_zero(p, sizeof(*p));
    p->identity = (struct npu_rro_identity){1, 1, 2, 1, 3, 1, 4, 1, 1};
    p->profile = profile;
    for (uint32_t i = 0; i < 8; i++)
        p->mailbox[i] = (struct npu_rro_span){0x90000000u + i * 0x40000u, 0x1000};
    for (uint32_t i = 0; i < 6; i++) {
        p->tx[i].address = 0x91000000u + i * 0x40000u;
        p->tx[i].bytes = i < 2 ? 0x20000 : 0x40000;
        p->native[i] = (struct npu_rro_span){0x84000000u + i * 0x100000u, 0x100000};
    }
    p->rx_event = (struct npu_rro_span){0x92000000, 8192};
    p->bar = (struct npu_rro_span){0x20000000, 0x100000};
}

static uint32_t rro_test_extent(uint32_t profile, uint32_t ordinal, struct npu_rro_extent *out)
{
    uint32_t result = npu_rro_extent_geometry(profile, ordinal, out);
    if (result) return result;
    out->cpu_lo = 0x10000000 + ordinal * 0x20000;
    out->cpu_hi = 1;
    if (out->role == NPU_RRO_ELEMENT)
        out->dma_lo = 0x88000000 + out->index * 65536;
    else if (out->role == NPU_RRO_SESSION)
        out->dma_lo = 0x88801000;
    else if (out->role == NPU_RRO_BA)
        out->dma_lo = 0x88900000 + out->index * 65536;
    else if (out->role == NPU_RRO_MSDU)
        out->dma_lo = 0x88a00000 + out->index * 65536;
    else
        out->dma_lo = 0x88b00000 + (out->role == NPU_RRO_EMI_DMA ? 0x1000 : 0);
    return NPU_RRO_OK;
}

#endif
