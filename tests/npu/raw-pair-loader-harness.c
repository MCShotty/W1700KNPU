/* Actual provider copies of the raw pair with modeled firmware/resource I/O. */
#define main original_loader_matrix
#include "firmware-loader-harness.c"
#undef main

static size_t read_image(const char *path, unsigned char *payload, size_t capacity)
{
    FILE *file = fopen(path, "rb");
    CHECK(file && !fseek(file, 0, SEEK_END));
    long size = ftell(file);
    CHECK(size > 0 && (size_t)size <= capacity && !fseek(file, 0, SEEK_SET));
    CHECK(fread(payload, 1, size, file) == (size_t)size && !fclose(file));
    return size;
}

static void dump(const char *directory, const char *name,
                 const unsigned char *memory, size_t bytes)
{
    char path[1200];
    int size = snprintf(path, sizeof(path), "%s/%s", directory, name);
    CHECK(size > 0 && (size_t)size < sizeof(path));
    FILE *file = fopen(path, "wb");
    CHECK(file && fwrite(memory, 1, bytes, file) == bytes && !fclose(file));
}

int main(int argc, char **argv)
{
    if (argc == 1)
        return original_loader_matrix(argc, argv);
    CHECK(argc == 5);
    current_case = argv[4];
    setup(1, 1, 1, 1);
    images[0].size = read_image(argv[1], code_payload, CODE_LIMIT);
    images[1].size = read_image(argv[2], data_payload, DATA_LIMIT);
    size_t code_bytes = images[0].size, data_bytes = images[1].size;
    int expected = 0;
    if (!strcmp(current_case, "missing-data")) {
        request_errors[1] = -ENOENT;
        expected = -EPROBE_DEFER;
    } else if (!strcmp(current_case, "empty-code")) {
        images[0].size = 0;
        expected = -EINVAL;
    } else if (!strcmp(current_case, "empty-data")) {
        images[1].size = 0;
        expected = -EINVAL;
    } else if (!strcmp(current_case, "oversize-code")) {
        images[0].size = CODE_LIMIT + 1;
        expected = -E2BIG;
    } else if (!strcmp(current_case, "oversize-data")) {
        images[1].size = DATA_LIMIT + 1;
        expected = -E2BIG;
    } else if (!strcmp(current_case, "invalid-plan")) {
        wlan_regions[0].end = wlan_regions[0].start + 0x6800 - 1;
        expected = -EINVAL;
    } else {
        CHECK(!strcmp(current_case, "nominal"));
    }
    struct resource resource = valid_region();
    int result = airoha_npu_run_firmware(&priv, data_memory + GUARD, &resource);
    CHECK(result == expected && send_calls == 0);
    CHECK(acquired[0] == released[0] && acquired[1] == released[1]);
    if (expected) {
        CHECK(copies == 0 && !priv.firmware_loaded);
        memory_matches(code_memory, CODE_LIMIT, 0, 0);
        memory_matches(data_memory, DATA_LIMIT, 0, 0);
    } else {
        const int order[] = {10, 11, 20, 21, 31, 30};
        CHECK(requests == 2 && copies == 2 && event_count == 6);
        CHECK(!memcmp(events, order, sizeof(order)) && priv.firmware_loaded);
        CHECK(!memcmp(code_memory + GUARD, code_payload, code_bytes));
        CHECK(priv.checked_pair && priv.native_published && fake_lifetime.exposed);
        CHECK(io_writes == 14 && io_reads == 19 && module_pins == 1 && random_calls == 1);
        CHECK(!memcmp(data_memory + GUARD + NPU_EN7581_NATIVE_PLAN, priv.native_plan, 48));
        CHECK(!memcmp(data_memory + GUARD + NPU_EN7581_NATIVE_IDENTITY, &random_identity, 8));
        for (size_t i = 0; i < data_bytes; i++)
            if (!(i >= NPU_EN7581_NATIVE_PLAN && i < NPU_EN7581_NATIVE_PLAN + 48) &&
                !(i >= NPU_EN7581_NATIVE_IDENTITY && i < NPU_EN7581_NATIVE_IDENTITY + 8))
                CHECK(data_memory[GUARD + i] == data_payload[i]);
        for (size_t i = 0; i < sizeof(code_memory); i++)
            if (i < GUARD || i >= GUARD + code_bytes)
                CHECK(code_memory[i] == 0xa5);
        for (size_t i = 0; i < sizeof(data_memory); i++)
            if (i < GUARD || i >= GUARD + data_bytes)
                CHECK(data_memory[i] == 0xa5);
    }
    dump(argv[3], "code-memory.bin", code_memory, sizeof(code_memory));
    dump(argv[3], "data-memory.bin", data_memory, sizeof(data_memory));
    printf("{\"result\":%d,\"requests\":%d,\"copies\":%d,\"code_bytes\":%zu,"
           "\"data_bytes\":%zu,\"released\":[%d,%d],\"events\":[",
           result, requests, copies, code_bytes, data_bytes, released[0], released[1]);
    for (int i = 0; i < event_count; i++)
        printf("%s%d", i ? "," : "", events[i]);
    printf("]}\n");
    return 0;
}
