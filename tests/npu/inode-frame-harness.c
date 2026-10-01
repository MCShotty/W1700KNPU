/* Extracted provider code; allocation and mailbox transport are host models. */
#include <assert.h>
#include <errno.h>
#include <limits.h>
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
static unsigned allocations, frees, sends, captured_length;
static bool deny_allocation;
static int transport_error;
static u8 captured[AIROHA_NPU_MBOX_SIZE];

static void *kzalloc(size_t bytes, gfp_t flags)
{
    assert(flags == 7 && bytes <= AIROHA_NPU_MBOX_SIZE);
    allocations++;
    return deny_allocation ? NULL : calloc(1, bytes);
}

static void kfree(void *memory)
{
    frees++;
    free(memory);
}

static int airoha_npu_send_msg(struct airoha_npu *npu, int function,
                              const void *data, int length)
{
    assert(npu == &priv.npu && function == NPU_FUNC_WIFI);
    assert(length >= 8 && length <= AIROHA_NPU_MBOX_SIZE);
    sends++;
    captured_length = length;
    memcpy(captured, data, length);
    return transport_error;
}

#include "frame-send.inc"

static void setup(unsigned profile)
{
    memset(&priv, 0, sizeof(priv));
    priv.txbuf_min_size = profile == 1 ? NPU_EN7581_7996_TX_CHECK_SIZE :
                          profile == 2 ? 0x10000 : 0;
    memset(captured, 0xa5, sizeof(captured));
    allocations = frees = sends = captured_length = 0;
    deny_allocation = false;
    transport_error = 0;
}

static void packet(unsigned profile, unsigned command, unsigned index,
                    unsigned length, bool original)
{
    setup(profile);
    u8 *input = malloc(length ? length : 1);
    assert(input);
    for (unsigned i = 0; i < length; i++)
        input[i] = 0x71 + i;
    unsigned expected = 8 + length;
    if (!original && profile == 1 && command == 24 && length < 16)
        expected = 24;
    assert(airoha_npu_wlan_msg_send(&priv.npu, index, command, input, length, 7) == 0);
    assert(allocations == 1 && frees == 1 && sends == 1 && captured_length == expected);
    u32 header, api;
    memcpy(&header, captured, 4);
    memcpy(&api, captured + 4, 4);
    assert(header == (0x10 | index) && api == command);
    assert(!memcmp(captured + 8, input, length));
    for (unsigned i = 8 + length; i < expected; i++)
        assert(captured[i] == 0);
    printf("{\"profile\":%u,\"api\":%u,\"selector\":%u,\"input_bytes\":%u,\"bytes\":%u,\"hex\":\"",
           profile, command, index, length, captured_length);
    for (unsigned i = 0; i < captured_length; i++)
        printf("%02x", captured[i]);
    puts("\"}");
    free(input);
}

static unsigned failures(void)
{
    unsigned cases = 0;
    u32 input = 0x12345678;
    const int invalid[] = {-1, INT_MIN, 249, INT_MAX};
    const int errors[] = {-ETIMEDOUT, -EBUSY, -EIO};
    for (unsigned profile = 0; profile < 3; profile++) {
        for (unsigned i = 0; i < sizeof(invalid) / sizeof(invalid[0]); i++) {
            setup(profile);
            assert(airoha_npu_wlan_msg_send(&priv.npu, 2, 24, &input, invalid[i], 7) == -EINVAL);
            assert(!allocations && !frees && !sends);
            cases++;
        }
        setup(profile);
        assert(airoha_npu_wlan_msg_send(&priv.npu, 2, 24, NULL, 4, 7) == -EINVAL);
        assert(!allocations && !frees && !sends);
        cases++;
        setup(profile);
        assert(airoha_npu_wlan_msg_send(&priv.npu, 2, 24, NULL, 0, 7) == 0);
        assert(captured_length == (profile == 1 ? 24 : 8));
        cases++;
        setup(profile);
        deny_allocation = true;
        assert(airoha_npu_wlan_msg_send(&priv.npu, 2, 24, &input, 4, 7) == -ENOMEM);
        assert(allocations == 1 && !frees && !sends);
        cases++;
        for (unsigned i = 0; i < sizeof(errors) / sizeof(errors[0]); i++) {
            setup(profile);
            transport_error = errors[i];
            assert(airoha_npu_wlan_msg_send(&priv.npu, 2, 24, &input, 4, 7) == errors[i]);
            assert(allocations == 1 && frees == 1 && sends == 1);
            cases++;
        }
    }
    return cases;
}

int main(int argc, char **argv)
{
    bool original = argc == 2 && !strcmp(argv[1], "--original");
    const unsigned lengths[] = {0, 1, 3, 4, 8, 12, 15, 16, 17, 32, 248};
    unsigned cases = 0;
    _Static_assert(sizeof(struct wlan_mbox_data) == 8, "wire header");
    for (unsigned profile = 0; profile < 3; profile++)
    for (unsigned command = 19; command <= 24; command += 5)
    for (unsigned index = 0; index < 16; index++)
    for (unsigned i = 0; i < sizeof(lengths) / sizeof(lengths[0]); i++) {
        packet(profile, command, index, lengths[i], original);
        cases++;
    }
    unsigned auxiliary = original ? 0 : failures();
    fprintf(stderr, "PASS frames=%u auxiliary=%u original=%u\n", cases, auxiliary, original);
    return 0;
}
