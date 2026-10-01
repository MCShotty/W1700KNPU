/* Actual provider C with explicit firmware, OF, I/O and mailbox models. */
#define main loader_regression_main
#include "firmware-loader-harness.c"
#undef main
#include <stddef.h>
#define GFP_KERNEL 0
#define container_of(p, t, m) ((t *)((char *)(p) - offsetof(t, m)))

#include "wlan-enum.inc"
static bool reenter_on_send;
static int airoha_npu_wlan_init_memory(struct airoha_npu *npu);
static void mdelay(unsigned int msec) { CHECK(msec == 10); }
static int airoha_npu_wlan_msg_send(struct airoha_npu *n, int index,
                                   enum airoha_npu_wlan_set_cmd cmd,
                                   const void *value, int len, int flags) {
    CHECK(n == &priv.npu && flags == GFP_KERNEL && len == 4 && send_calls < 8);
    sent[send_calls][0] = index; sent[send_calls][1] = cmd;
    memcpy(&sent[send_calls][2], value, 4); send_calls++;
    if (reenter_on_send) {
        int saved = region_missing;
        reenter_on_send = false; region_missing = 0;
        CHECK(airoha_npu_wlan_init_memory(n) == -ENOENT);
        region_missing = saved;
    }
    return send_calls == send_error ? -ETIMEDOUT : 0;
}
#include "wlan-memory.inc"

static void check_wire(int ba) {
    const u32 expected[][3] = {
        {1, 18, 0}, {0, 32, 0x90c00000}, {0, 8, 0x8a000000},
        {0, 23, 0x8cc00000}, {0, 7, 0x90c0e000}, {0, 12, 0},
    };
    CHECK(send_calls == 5 + ba);
    CHECK(!memcmp(sent, expected, (ba ? 6 : 4) * sizeof(sent[0])));
    if (!ba) CHECK(!memcmp(sent[4], expected[5], sizeof(sent[4])));
}

static void early_reject(int expected, struct resource *binary) {
    verify(expected, binary);
    CHECK(requests == 0 && copies == 0 && send_calls == 0);
    CHECK(airoha_npu_wlan_init_memory(&priv.npu) == -EINVAL);
    CHECK(send_calls == 0);
}

static void control(const char *name) {
    struct resource binary = valid_region();
    current_case = name;
    setup(1, 1, 256, 128);
    if (!strcmp(name, "invalid-before-load")) {
        wlan_regions[0].end--;
        early_reject(-EINVAL, &binary);
    } else if (!strcmp(name, "snapshot-reuse")) {
        verify(0, &binary);
        memset(wlan_regions, 0, sizeof(wlan_regions));
        has_ba = 0; region_missing = 0;
        CHECK(airoha_npu_wlan_init_memory(&priv.npu) == 0);
        check_wire(1); CHECK(region_lookups == 4);
    } else if (!strcmp(name, "failed-load-unbound")) {
        request_errors[1] = -ENOMEM;
        verify(-ENOMEM, &binary);
        CHECK(airoha_npu_wlan_init_memory(&priv.npu) == -EINVAL);
        CHECK(send_calls == 0);
    } else CHECK(!"unknown control");
}

int main(int argc, char **argv) {
    if (argc > 1) {
        control(argv[1]);
        printf("{\"control\":\"%s\",\"passed\":true}\n", argv[1]);
        return 0;
    }
    char *loader_args[] = { "loader", NULL };
    CHECK(loader_regression_main(1, loader_args) == 0);
    unsigned loader_cases = cases;
    struct resource binary = valid_region();
    current_case = "cold-memory-plan";
    for (int profile = 0; profile < 3; profile++)
    for (int dts = 0; dts < 2; dts++)
    for (int ba = 0; ba < 2; ba++) {
        setup(profile, dts, 256, 128); has_ba = ba;
        verify(0, &binary);
        CHECK(region_lookups == (profile == 1 ? 3 + ba : 0));
        CHECK(airoha_npu_wlan_init_memory(&priv.npu) == 0);
        check_wire(ba); CHECK(region_lookups == 3 + ba);
    }
    const struct resource invalid[] = {
        {0, 0xffff}, {0x91000004, 0x91000003}, {0x91000001, 0x9100ffff},
        {0x190c00000, 0x190c0dfff}, {0xfffff000, 0x100000fff},
        {0x70000000, 0x7000ffff}, {0xbffff000, 0xc0000fff},
    };
    for (int dts = 0; dts < 2; dts++) {
        for (int i = 0; i < 4; i++) {
            setup(1, dts, 256, 128); region_missing = i;
            early_reject(-ENOENT, &binary);
            for (unsigned j = 0; j < ARRAY_SIZE(invalid); j++) {
                setup(1, dts, 256, 128); wlan_regions[i] = invalid[j];
                early_reject(j >= 5 ? -ERANGE : -EINVAL, &binary);
            }
            setup(1, dts, 256, 128); wlan_regions[i] = binary;
            early_reject(-EINVAL, &binary);
            for (int j = i + 1; j < 4; j++) {
                setup(1, dts, 256, 128); wlan_regions[j] = wlan_regions[i];
                early_reject(-EINVAL, &binary);
            }
        }
        const u32 sizes[] = {1, 0x6800, 0xdfff};
        for (unsigned i = 0; i < ARRAY_SIZE(sizes); i++) {
            setup(1, dts, 256, 128); wlan_regions[0].end = wlan_regions[0].start + sizes[i] - 1;
            early_reject(-EINVAL, &binary);
        }
        setup(1, dts, 256, 128); wlan_regions[0].end++;
        early_reject(-EINVAL, &binary);
        setup(1, dts, 256, 128); has_ba = 0; region_missing = 3;
        verify(0, &binary); CHECK(airoha_npu_wlan_init_memory(&priv.npu) == 0); check_wire(0);
        for (int failed = 1; failed <= 6; failed++) {
            setup(1, dts, 256, 128); verify(0, &binary); send_error = failed;
            CHECK(airoha_npu_wlan_init_memory(&priv.npu) == -ETIMEDOUT);
            CHECK(send_calls == failed && region_lookups == 4);
        }
        for (int which = 0; which < 2; which++) {
            const int errors[] = {-ENOENT, -ENOMEM, -EIO, -EINVAL, -ETIMEDOUT};
            for (unsigned e = 0; e < ARRAY_SIZE(errors); e++) {
                setup(1, dts, 256, 128); request_errors[which] = errors[e];
                verify(errors[e] == -ENOENT ? -EPROBE_DEFER : errors[e], &binary);
                CHECK(airoha_npu_wlan_init_memory(&priv.npu) == -EINVAL && send_calls == 0);
            }
        }
        for (int which = 0; which < 2; which++)
        for (int empty = 0; empty < 2; empty++) {
            setup(1, dts, 256, 128);
            images[which].size = empty ? 0 : (which ? DATA_LIMIT : CODE_LIMIT) + 1;
            verify(empty ? -EINVAL : -E2BIG, &binary);
            CHECK(airoha_npu_wlan_init_memory(&priv.npu) == -EINVAL && send_calls == 0);
        }
        /* Failed repeat admission must not expose a prior plan. No live reset is modeled. */
        setup(1, dts, 256, 128); verify(0, &binary);
        memset(wlan_regions, 0, sizeof(wlan_regions));
        CHECK(airoha_npu_run_firmware(&priv, data_memory + GUARD, &binary) == -EINVAL);
        CHECK(airoha_npu_wlan_init_memory(&priv.npu) == -EINVAL && send_calls == 0);
        for (int failure = 0; failure < 3; failure++) {
            setup(1, dts, 256, 128); verify(0, &binary);
            if (failure == 0) match_missing = 1;
            if (failure == 1) map_error = -EBUSY;
            struct resource again = failure == 2 ? (struct resource){0, 1} : binary;
            CHECK(airoha_npu_run_firmware(&priv, data_memory + GUARD, &again) < 0);
            CHECK(airoha_npu_wlan_init_memory(&priv.npu) == -EINVAL && send_calls == 0);
        }
    }
    /* Profiles without the exact MT7996 name must not require WLAN resources to boot. */
    for (int p = 0; p < 3; p += 2)
    for (int dts = 0; dts < 2; dts++) {
        setup(p, dts, 256, 128); memset(wlan_regions, 0, sizeof(wlan_regions)); region_missing = 0;
        verify(0, &binary); CHECK(region_lookups == 0);
        CHECK(airoha_npu_wlan_init_memory(&priv.npu) == -ENOENT && send_calls == 0);
    }
    for (int p = 0; p < 3; p += 2)
    for (int dts = 0; dts < 2; dts++) {
        setup(p, dts, 256, 128); verify(0, &binary); reenter_on_send = true;
        CHECK(airoha_npu_wlan_init_memory(&priv.npu) == 0);
        check_wire(1); CHECK(region_lookups == 5);
    }
    control("invalid-before-load"); control("snapshot-reuse"); control("failed-load-unbound");
    printf("{\"loader_cases\":%u,\"additional_load_cases\":%u,\"passed\":true}\n",
           loader_cases, cases - loader_cases);
    return 0;
}
