/* Execute extracted provider C; firmware requests and I/O are modeled. */
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>

typedef uint32_t u32;
typedef uint16_t u16;
#define __iomem
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define upper_32_bits(a) ((uint64_t)(a) >> 32)
#define IS_ALIGNED(a, b) (!((a) & ((b) - 1)))
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define EPROBE_DEFER 517
#define CODE_LIMIT 0x200000u
#define DATA_LIMIT 0x10000u
#define GUARD 16u

static const char *current_case;
#define CHECK(p) do { if (!(p)) { \
    fprintf(stderr, "FAIL[%s] line %d: %s\n", current_case, __LINE__, #p); \
    exit(11); \
} } while (0)

struct resource { uint64_t start, end; };
struct device_node { int unused; };
struct device { struct device_node *of_node; };
struct airoha_npu { struct device *dev; };
struct firmware { size_t size; const unsigned char *data; };
struct airoha_npu_soc_data;
static const struct airoha_npu_soc_data *of_device_get_match_data(struct device *);

static unsigned char code_payload[CODE_LIMIT + 1], data_payload[DATA_LIMIT + 1];
static unsigned char code_memory[CODE_LIMIT + 2 * GUARD];
static unsigned char data_memory[DATA_LIMIT + 2 * GUARD];
static struct firmware images[2];
static struct device_node node;
static struct device dev = { &node };
static const char *expected_names[2];
static int request_errors[2], acquired[2], released[2];
static int requests, copies, events[8], event_count, property, property_count;
static int map_error, match_missing;
static unsigned cases;
static struct resource wlan_regions[4];
static int has_ba, region_missing, region_lookups, send_calls, send_error;
static u32 sent[8][3];
static const char * const region_names[] = { "tx-bufid", "pkt", "tx-pkt", "ba" };

static bool resource_overlaps(const struct resource *a, const struct resource *b) {
    return a->start <= b->end && a->end >= b->start;
}
static int of_property_match_string(struct device_node *n, const char *p, const char *s) {
    (void)n; (void)p; (void)s; return has_ba ? 3 : -EINVAL;
}
static int of_reserved_mem_region_to_resource_byname(struct device_node *n,
                                                     const char *name, struct resource *r) {
    (void)n; region_lookups++;
    for (int i = 0; i < 4; i++) if (!strcmp(name, region_names[i])) {
        if (region_missing == i) return -ENOENT;
        *r = wlan_regions[i]; return 0;
    }
    return -EINVAL;
}

static void event(int value) { CHECK(event_count < 8); events[event_count++] = value; }
static uint64_t resource_size(const struct resource *r) { return r->end - r->start + 1; }
static int dev_err_probe(struct device *d, int err, const char *fmt, ...) {
    (void)d; (void)fmt; return err;
}
static void dev_err(struct device *d, const char *fmt, ...) { (void)d; (void)fmt; }
static void *devm_ioremap_resource(struct device *d, struct resource *r) {
    (void)d; (void)r;
    return map_error ? (void *)(intptr_t)map_error : code_memory + GUARD;
}
static void *of_find_property(struct device_node *n, const char *p, void *len) {
    (void)n; (void)p; (void)len; return property ? &node : NULL;
}
static int of_property_read_string_array(struct device_node *n, const char *p,
                                         const char **names, size_t count) {
    (void)n; (void)p; CHECK(count == 2);
    if (property_count == 2) {
        names[0] = expected_names[0]; names[1] = expected_names[1];
    }
    return property_count;
}
static int request_firmware_direct(const struct firmware **out, const char *name,
                                    struct device *d) {
    CHECK(d == &dev && requests < 2);
    int which = requests++;
    CHECK(!strcmp(name, expected_names[which]));
    event(10 + which);
    if (request_errors[which]) return request_errors[which];
    acquired[which] = 1; *out = &images[which]; return 0;
}
static void release_firmware(const struct firmware *fw) {
    int which = fw == &images[0] ? 0 : fw == &images[1] ? 1 : -1;
    CHECK(which >= 0 && acquired[which] && !released[which]);
    released[which]++; event(30 + which);
}
static void memcpy_toio(void *dest, const void *src, size_t bytes) {
    int which = dest == code_memory + GUARD ? 0 : dest == data_memory + GUARD ? 1 : -1;
    CHECK(which >= 0 && acquired[which] && !released[which]);
    CHECK(src == images[which].data && bytes == images[which].size);
    CHECK(bytes > 0 && bytes <= (which ? DATA_LIMIT : CODE_LIMIT));
    copies++; event(20 + which); memcpy(dest, src, bytes);
}

#include "firmware-loader.inc"

static struct airoha_npu_soc_data soc;
static struct airoha_npu_priv priv;
static const struct airoha_npu_soc_data *of_device_get_match_data(struct device *d) {
    CHECK(d == &dev); return match_missing ? NULL : &soc;
}

static void setup(int profile, int dts, size_t code_size, size_t data_size) {
    memset(&priv, 0, sizeof(priv)); priv.npu.dev = &dev;
    memset(code_memory, 0xa5, sizeof(code_memory));
    memset(data_memory, 0xa5, sizeof(data_memory));
    memset(code_payload, 0x3c, sizeof(code_payload));
    memset(data_payload, 0x6d, sizeof(data_payload));
    memset(request_errors, 0, sizeof(request_errors));
    memset(acquired, 0, sizeof(acquired)); memset(released, 0, sizeof(released));
    memset(events, 0, sizeof(events)); requests = copies = event_count = 0;
    wlan_regions[0] = (struct resource){0x90c00000, 0x90c0dfff};
    wlan_regions[1] = (struct resource){0x8a000000, 0x8cbfffff};
    wlan_regions[2] = (struct resource){0x8cc00000, 0x90bfffff};
    wlan_regions[3] = (struct resource){0x90c0e000, 0x90e0dfff};
    has_ba = 1; region_missing = -1; region_lookups = send_calls = send_error = 0;
    memset(sent, 0, sizeof(sent));
    property = dts; property_count = 2; map_error = match_missing = 0;
    expected_names[0] = profile == 1 ? NPU_EN7581_7996_FIRMWARE_RV32 :
                         profile == 2 ? NPU_AN7583_FIRMWARE_RV32 : NPU_EN7581_FIRMWARE_RV32;
    expected_names[1] = profile == 1 ? NPU_EN7581_7996_FIRMWARE_DATA :
                         profile == 2 ? NPU_AN7583_FIRMWARE_DATA : NPU_EN7581_FIRMWARE_DATA;
    soc.fw_rv32.name = expected_names[0]; soc.fw_rv32.max_size = CODE_LIMIT;
    soc.fw_data.name = expected_names[1]; soc.fw_data.max_size = DATA_LIMIT;
    images[0].size = code_size; images[0].data = code_payload;
    images[1].size = data_size; images[1].data = data_payload;
}

static void memory_matches(const unsigned char *memory, size_t capacity,
                           size_t copied, unsigned char value) {
    for (size_t i = 0; i < capacity + 2 * GUARD; i++)
        CHECK(memory[i] == (i >= GUARD && i < GUARD + copied ? value : 0xa5));
}

static void verify(int expected, struct resource *res) {
    int result = airoha_npu_run_firmware(&priv, data_memory + GUARD, res);
    CHECK(result == expected);
    CHECK(released[0] == acquired[0] && released[1] == acquired[1]);
    if (expected) {
        CHECK(copies == 0);
        memory_matches(code_memory, CODE_LIMIT, 0, 0);
        memory_matches(data_memory, DATA_LIMIT, 0, 0);
    } else {
        const int order[] = { 10, 11, 20, 21, 31, 30 };
        CHECK(requests == 2 && copies == 2 && event_count == 6);
        CHECK(!memcmp(events, order, sizeof(order)));
        memory_matches(code_memory, CODE_LIMIT, images[0].size, 0x3c);
        memory_matches(data_memory, DATA_LIMIT, images[1].size, 0x6d);
        CHECK(priv.txbuf_min_size == (property &&
              !strcmp(expected_names[0], NPU_EN7581_7996_FIRMWARE_RV32) ? 0xe000 :
              !property && !strcmp(soc.fw_rv32.name, NPU_EN7581_7996_FIRMWARE_RV32) ? 0xe000 : 0));
    }
    cases++;
}

static struct resource valid_region(void) {
    struct resource res = { 0x84000000, 0x849fffff }; return res;
}

int main(int argc, char **argv) {
    struct resource res = valid_region();
    current_case = argc > 1 ? argv[1] : "matrix";
    if (argc > 1) {
        setup(1, 1, 256, 128);
        int expected = -EINVAL;
        if (!strcmp(argv[1], "data-missing")) { request_errors[1] = -ENOENT; expected = -EPROBE_DEFER; }
        else if (!strcmp(argv[1], "data-overlimit")) { images[1].size = DATA_LIMIT + 1; expected = -E2BIG; }
        else if (!strcmp(argv[1], "code-empty")) images[0].size = 0;
        else if (!strcmp(argv[1], "data-empty")) images[1].size = 0;
        else CHECK(!"unknown case");
        verify(expected, &res);
    } else {
        const size_t code_sizes[] = { 0, 1, 256, CODE_LIMIT, CODE_LIMIT + 1 };
        const size_t data_sizes[] = { 0, 1, 128, DATA_LIMIT, DATA_LIMIT + 1 };
        const int errors[] = { -ENOENT, -ENOMEM, -EIO, -EINVAL, -EPROBE_DEFER, -ETIMEDOUT };
        for (int profile = 0; profile < 3; profile++)
        for (int dts = 0; dts < 2; dts++) {
            for (size_t c = 0; c < ARRAY_SIZE(code_sizes); c++)
            for (size_t d = 0; d < ARRAY_SIZE(data_sizes); d++) {
                setup(profile, dts, code_sizes[c], data_sizes[d]);
                int expected = !code_sizes[c] ? -EINVAL : code_sizes[c] > CODE_LIMIT ? -E2BIG :
                               !data_sizes[d] ? -EINVAL : data_sizes[d] > DATA_LIMIT ? -E2BIG : 0;
                verify(expected, &res);
            }
            for (int which = 0; which < 2; which++)
            for (size_t e = 0; e < ARRAY_SIZE(errors); e++) {
                setup(profile, dts, 256, 128); request_errors[which] = errors[e];
                verify(errors[e] == -ENOENT ? -EPROBE_DEFER : errors[e], &res);
            }
            setup(profile, dts, 256, 128); map_error = -EBUSY; verify(-EBUSY, &res);
            CHECK(requests == 0);
            setup(profile, dts, 256, 128); match_missing = 1; verify(-EINVAL, &res);
            CHECK(requests == 0);
            if (dts) {
                const int counts[] = { -EINVAL, -ENODATA, 0, 1, 3 };
                for (size_t c = 0; c < ARRAY_SIZE(counts); c++) {
                    setup(profile, dts, 256, 128); property_count = counts[c];
                    verify(-EINVAL, &res); CHECK(requests == 0);
                }
            }
            struct resource bad[] = { {0, 0x9fffff}, {0x84000000, 0x8423fffe},
                                       {0x84000001, 0x849fffff}, {0x184000000, 0x1849fffff} };
            for (size_t b = 0; b < ARRAY_SIZE(bad); b++) {
                setup(profile, dts, 256, 128); verify(-EINVAL, &bad[b]); CHECK(requests == 0);
            }
        }
    }
    printf("{\"cases\":%u,\"requests\":%d,\"copies\":%d}\n", cases, requests, copies);
    return 0;
}
