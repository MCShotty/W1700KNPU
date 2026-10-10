/* Actual Linux boot sequencer; regmap, timing and version transport are modeled. */
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint32_t u32;
typedef uint64_t u64;
typedef uint64_t dma_addr_t;
struct device { int unused; };
struct regmap { int unused; };
struct list_head { struct list_head *next, *prev; };
struct resource { u64 start, end; };
struct airoha_npu { struct device *dev; struct regmap *regmap; };
#define NPU_NUM_CORES 8
#define GFP_KERNEL 0
#define dev_info(...) ((void)0)
#define CHECK(p) do { if (!(p)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #p); exit(11); } } while (0)
#include "constants.inc"
#include "types.inc"

struct event { unsigned kind; u32 a, b; };
static struct event events[32];
static unsigned writes, gets, count, effects, cases, write_faults;
static unsigned fault_at, after_effect;
static int write_error, get_error;
static u32 version;
static struct regmap map;
static struct device device;
static struct airoha_npu_dma_lifetime lease;

static void event(unsigned kind, u32 a, u32 b)
{
    CHECK(count < 32);
    events[count++] = (struct event){kind, a, b};
}

static int regmap_write(struct regmap *regmap, u32 reg, u32 value)
{
    CHECK(regmap == &map);
    writes++;
    event(1, reg, value);
    if (writes == fault_at) {
        effects += after_effect;
        return write_error;
    }
    effects++;
    return 0;
}

static void msleep(unsigned delay) { event(2, delay, 0); }
static void usleep_range(unsigned low, unsigned high) { event(3, low, high); }
static int airoha_npu_wlan_msg_get(struct airoha_npu *npu, int index,
                                  enum airoha_npu_wlan_get_cmd command,
                                  void *reply, int bytes, unsigned flags)
{
    CHECK(npu->regmap == &map && index == 0 && command == WLAN_FUNC_GET_WAIT_NPU_VERSION);
    CHECK(reply && bytes == 4 && flags == GFP_KERNEL);
    gets++;
    event(4, index, command);
    *(u32 *)reply = get_error ? 0xdeadc0deu : version;
    return get_error;
}
#include "boot.inc"

static const struct event expected[] = {
    {1, 0x30c168, 0x84200000}, {1, 0x30c16c, 0x40000},
    {1, 0x30c170, 0}, {1, 0x30c194, 1}, {2, 100, 0},
    {1, 0x306020, 0x84000000}, {1, 0x306024, 0x84000000},
    {1, 0x306028, 0x84000000}, {1, 0x30602c, 0x84000000},
    {1, 0x306030, 0x84000000}, {1, 0x306034, 0x84000000},
    {1, 0x306038, 0x84000000}, {1, 0x30603c, 0x84000000},
    {3, 1000, 2000}, {1, 0x306004, 0xff}, {1, 0x306000, 1},
    {2, 100, 0}, {4, 0, 10}
};

static void setup(struct airoha_npu_priv *priv, bool checked)
{
    memset(priv, 0, sizeof(*priv));
    memset(&lease, 0, sizeof(lease));
    memset(events, 0, sizeof(events));
    priv->npu.dev = &device;
    priv->npu.regmap = &map;
    priv->dma_lifetime = &lease;
    lease.exposed = true;
    priv->firmware_loaded = true;
    priv->checked_pair = checked;
    priv->native_published = checked;
    priv->boot_identity = checked ? 0x9abcdef012345678ULL : 0;
    writes = gets = count = effects = fault_at = after_effect = 0;
    write_error = get_error = 0;
    version = 0x457;
}

static void run(struct airoha_npu_priv *priv, int wanted)
{
    struct resource res = {0x84000000, 0x849fffff};
    struct airoha_npu_priv before = *priv;
    int ret = airoha_npu_start_firmware(priv, &res);
    CHECK(ret == wanted);
    if (writes) {
        CHECK(priv->boot_attempted && lease.exposed);
        CHECK(priv->firmware_loaded == before.firmware_loaded);
        CHECK(priv->native_published == before.native_published);
        CHECK(priv->boot_identity == before.boot_identity);
        if (fault_at) {
            CHECK(writes == fault_at && !gets && effects == fault_at - 1 + after_effect);
            unsigned prefix = 0, seen = 0;
            do { seen += expected[prefix++].kind == 1; } while (seen < fault_at);
            CHECK(count == prefix);
        } else {
            CHECK(writes == 14 && gets == 1 && effects == 14 && count == 18);
        }
        CHECK(!memcmp(events, expected, count * sizeof(*events)));
        unsigned old_writes = writes, old_gets = gets, old_count = count, old_effects = effects;
        struct airoha_npu_priv attempted = *priv;
        CHECK(airoha_npu_start_firmware(priv, &res) == -EBUSY);
        CHECK(writes == old_writes && gets == old_gets && count == old_count && effects == old_effects);
        CHECK(!memcmp(priv, &attempted, sizeof(*priv)));
    } else {
        CHECK(!gets && !count && !effects && !memcmp(priv, &before, sizeof(*priv)));
    }
    cases++;
}

int main(void)
{
    struct airoha_npu_priv priv;
    const int errors[] = {-EIO, -ENOMEM, -EINTR, -ETIMEDOUT};
    for (unsigned checked = 0; checked < 2; checked++) {
        setup(&priv, checked); run(&priv, 0);
        for (unsigned at = 1; at <= 14; at++)
        for (unsigned effect = 0; effect < 2; effect++)
        for (unsigned error = 0; error < sizeof(errors) / sizeof(*errors); error++) {
            setup(&priv, checked);
            fault_at = at; after_effect = effect; write_error = errors[error];
            run(&priv, write_error); write_faults++;
        }
        for (unsigned error = 0; error < sizeof(errors) / sizeof(*errors); error++) {
            setup(&priv, checked); get_error = errors[error]; run(&priv, checked ? get_error : 0);
        }
        const u32 wrong_versions[] = {0, 0x458, 0x40039, 0xffffffff};
        for (unsigned i = 0; i < sizeof(wrong_versions) / sizeof(*wrong_versions); i++) {
            setup(&priv, checked); version = wrong_versions[i]; run(&priv, checked ? -EPROTO : 0);
        }
    }
    setup(&priv, true); priv.boot_attempted = true; run(&priv, -EBUSY);
    setup(&priv, true); priv.firmware_loaded = false; run(&priv, -EINVAL);
    setup(&priv, true); priv.dma_lifetime = NULL; run(&priv, -EINVAL);
    setup(&priv, true); lease.exposed = false; run(&priv, -EINVAL);
    setup(&priv, true); priv.native_published = false; run(&priv, -EINVAL);
    setup(&priv, true); priv.boot_identity = 0; run(&priv, -EINVAL);
    printf("{\"passed\":true,\"cases\":%u,\"write_faults\":%u,\"nominal_writes\":14,\"nominal_events\":18}\n",
           cases, write_faults);
    return 0;
}
