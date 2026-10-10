/* Actual provider request-plan geometry; no physical containment is modeled. */
static void before_copy(void);
#define NPU_TEST_BEFORE_COPY before_copy
#define main loader_matrix
#include "firmware-loader-harness.c"
#undef main

static unsigned request_cases, copy_checks;
static int selected_profile;

static void check_plan(void)
{
#ifdef NPU_EN7581_7996_PLAN_REGIONS
    CHECK(priv.wlan_request_valid == (selected_profile == 1));
    if (selected_profile != 1) {
        CHECK(!priv.native_plan_ready);
        return;
    }
    CHECK(priv.wlan_request.start == priv.npu.cores[0].addr);
    CHECK(resource_size(&priv.wlan_request) == 256);
    int ready = has_ba == 1 && priv.firmware_region.start == 0x84000000 &&
                priv.firmware_region.end < 0xc0000000;
    CHECK(priv.native_plan_ready == ready);
    if (ready) {
        const u32 expected[][2] = {
            {priv.firmware_region.start, resource_size(&priv.firmware_region)},
            {wlan_regions[0].start, resource_size(&wlan_regions[0])},
            {wlan_regions[1].start, resource_size(&wlan_regions[1])},
            {wlan_regions[2].start, resource_size(&wlan_regions[2])},
            {wlan_regions[3].start, resource_size(&wlan_regions[3])},
            {priv.npu.cores[0].addr, 256},
        };
        CHECK(sizeof(priv.native_plan) == 48);
        CHECK(!memcmp(priv.native_plan, expected, sizeof(expected)));
    } else {
        const u32 zero[12] = {};
        CHECK(!memcmp(priv.native_plan, zero, sizeof(zero)));
    }
#else
    if (selected_profile == 1)
        CHECK(!"native request plan absent");
#endif
}

static void before_copy(void)
{
    check_plan();
    copy_checks++;
}

static void invalidated(void)
{
#ifdef NPU_EN7581_7996_PLAN_REGIONS
    const u32 zero[12] = {};
    CHECK(!priv.wlan_request_valid && !priv.native_plan_ready);
    CHECK(!priv.wlan_request.start && !priv.wlan_request.end);
    CHECK(!memcmp(priv.native_plan, zero, sizeof(zero)));
#endif
}

static void run_case(int profile, int dts, int ba, uint64_t address, int defect)
{
    struct resource binary = valid_region();
    selected_profile = profile;
    setup(profile, dts, 256, 128);
    has_ba = ba;
    priv.npu.cores[0].addr = address;
    if (defect == 1) priv.npu.cores[0].buf = NULL;
    if (defect == 2) priv.npu.cores[0].mbox_pending = true;
    int expected = 0;
    if (profile == 1) {
        if (defect == 1) expected = -EINVAL;
        else if (defect == 2) expected = -EBUSY;
        else if (address & 3) expected = -EINVAL;
        else if (address < 0x80000000 || address > 0xbfffff00) expected = -ERANGE;
        else {
            struct resource request = {address, address + 255};
            if (resource_overlaps(&request, &binary)) expected = -EINVAL;
            for (unsigned i = 0; i < 3 + (unsigned)ba; i++)
                if (resource_overlaps(&request, &wlan_regions[i])) expected = -EINVAL;
        }
    }
    verify(expected, &binary);
    if (expected) {
        CHECK(requests == 0 && copies == 0);
        invalidated();
    } else {
        check_plan();
    }
    request_cases++;
}

int main(int argc, char **argv)
{
    current_case = "provider-request-plan";
    const uint64_t addresses[] = {
        0, 0x80000000, 0x83ffff00, 0x84000000, 0x849fff04, 0x84a00000,
        0x89ffff00, 0x8a000000, 0x8cbfff04, 0x8cc00000, 0x90c00000,
        0x90c0dffc, 0x90c0e000, 0x90e0e000, 0x83000004, 0xbfffff00,
        0xbfffff04, 0xc0000000, 0x183000000, 0xfffffffffffffffc,
        0x7ffffffc, 0x83000001, 0x830000ff,
    };
    for (int profile = 0; profile < 3; profile++)
    for (int dts = 0; dts < 2; dts++)
    for (int ba = 0; ba < 2; ba++) {
        for (unsigned i = 0; i < ARRAY_SIZE(addresses); i++)
            run_case(profile, dts, ba, addresses[i], 0);
        run_case(profile, dts, ba, 0x83000000, 1);
        run_case(profile, dts, ba, 0x83000000, 2);
    }
#ifdef NPU_EN7581_7996_PLAN_REGIONS
    const struct resource relocated[] = {
        {0x70000000, 0x709fffff}, {0x85000000, 0x859fffff}, {0x84000000, 0xc0000000},
    };
    for (unsigned i = 0; i < ARRAY_SIZE(relocated); i++) {
        selected_profile = 1;
        setup(1, 1, 256, 128);
        if (i == 2) {
            /* A huge binary span overlaps the reserved WLAN regions first. */
            verify(-EINVAL, (struct resource *)&relocated[i]);
            invalidated();
        } else {
            verify(0, (struct resource *)&relocated[i]);
            check_plan();
        }
        request_cases++;
    }
    for (int defect = 0; defect < 5; defect++) {
        struct resource binary = valid_region();
        selected_profile = 1;
        setup(1, 1, 256, 128);
        verify(0, &binary);
        requests = copies = event_count = 0;
        memset(acquired, 0, sizeof(acquired));
        memset(released, 0, sizeof(released));
        if (defect == 0) match_missing = 1;
        if (defect == 1) map_error = -EBUSY;
        if (defect == 2) priv.npu.cores[0].addr = 0;
        if (defect == 3) request_errors[0] = -ENOMEM;
        if (defect == 4) request_errors[1] = -ENOMEM;
        CHECK(airoha_npu_run_firmware(&priv, data_memory + GUARD, &binary) < 0);
        invalidated();
        request_cases++;
    }
    selected_profile = 1;
    setup(1, 1, 256, 128);
    struct resource binary = valid_region();
    verify(0, &binary);
    CHECK(argc == 2);
    FILE *file = fopen(argv[1], "wb");
    CHECK(file && fwrite(priv.native_plan, 1, 48, file) == 48 && !fclose(file));
    u32 retained[12];
    memcpy(retained, priv.native_plan, sizeof(retained));
    memset(wlan_regions, 0, sizeof(wlan_regions));
    priv.npu.cores[0].addr = 0x83100000;
    CHECK(!memcmp(retained, priv.native_plan, sizeof(retained)));
#endif
    printf("{\"request_cases\":%u,\"before_copy_checks\":%u,\"passed\":true}\n",
           request_cases, copy_checks);
    return 0;
}
