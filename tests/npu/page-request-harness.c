/* Actual provider sender; modeled allocation and mailbox transport. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t resource_size_t;
typedef int gfp_t;
struct resource { resource_size_t start, end; };
struct airoha_npu { int unused; };
#define DECLARE_FLEX_ARRAY(t, n) t n[]
#define container_of(p, t, m) ((t *)((char *)(p) - offsetof(t, m)))
#define NPU_OP_SET 1
#define NPU_FUNC_WIFI 0
#define AIROHA_NPU_MBOX_SIZE 256
#include "frame-types.inc"

static struct airoha_npu_priv priv;
static unsigned allocations, frees, sends;
static unsigned char packet[256];
static int packet_bytes;

static void *kzalloc(size_t bytes, gfp_t flags)
{
    assert(flags == 7 && bytes <= 256);
    allocations++;
    return calloc(1, bytes);
}

static void kfree(void *value)
{
    frees++;
    free(value);
}

static int airoha_npu_send_msg(struct airoha_npu *npu, int function,
                              const void *data, int bytes)
{
    assert(npu == &priv.npu && function == 0 && bytes <= 256);
    sends++;
    memcpy(packet, data, bytes);
    packet_bytes = bytes;
    return 0;
}
#include "frame-send.inc"

int main(void)
{
    unsigned cases = 0, rejected = 0;
    const u32 profiles[] = {0, 0xe000, 0x10000};
    const unsigned limits[] = {256, 512, 1024, 1536};
    for (unsigned profile = 0; profile < 3; profile++)
    for (unsigned selector = 0; selector < 16; selector++)
    for (unsigned alias = 0; alias < 2; alias++)
    for (unsigned command = 1; command <= 19; command += 18) {
        unsigned index = selector + alias * 16;
        int selected = selector >= 5 && selector <= 8;
        u32 limit = selected ? limits[selector - 5] : 1024;
        const u32 counts[] = {0, 1, limit - 1, limit, limit + 1, 0x80000000, UINT32_MAX};
        const int lengths[] = {0, 1, 2, 3, 4, 8, 12, 16, 248};
        for (unsigned count = 0; count < 7; count++)
        for (unsigned li = 0; li < sizeof(lengths) / sizeof(lengths[0]); li++) {
            int length = lengths[li];
            unsigned char storage[250];
            memset(storage, 0xa5, sizeof(storage));
            /* Deliberately unaligned caller storage. */
            memcpy(storage + 1, &counts[count], 4);
            priv.txbuf_min_size = profiles[profile];
            allocations = frees = sends = 0;
            memset(packet, 0xa5, sizeof(packet));
            int deny = profile == 1 && command == 1 && selected &&
                       (length < 4 || !counts[count] || counts[count] > limit);
            int result = airoha_npu_wlan_msg_send(&priv.npu, index, command,
                                                 storage + 1, length, 7);
            if (deny) {
                assert(result == -EINVAL && !allocations && !frees && !sends);
                rejected++;
            } else {
                assert(!result && allocations == 1 && frees == 1 && sends == 1);
                assert(packet_bytes == 8 + length);
                u32 header, api;
                memcpy(&header, packet, 4);
                memcpy(&api, packet + 4, 4);
                assert(header == (0x10 | (index & 15)) && api == command);
                assert(!memcmp(packet + 8, storage + 1, length));
            }
            cases++;
        }
    }
    printf("{\"passed\":true,\"cases\":%u,\"rejected\":%u}\n", cases, rejected);
    return 0;
}
