/* Actual loader/parser/publisher C; OF, RNG, I/O and DMA lifetime are modeled. */
#define main original_loader_matrix
#include "firmware-loader-harness.c"
#undef main

static size_t load(const char *path, unsigned char *payload, size_t capacity)
{
    FILE *file = fopen(path, "rb");
    CHECK(file && !fseek(file, 0, SEEK_END));
    long bytes = ftell(file);
    CHECK(bytes > 0 && (size_t)bytes <= capacity && !fseek(file, 0, SEEK_SET));
    CHECK(fread(payload, 1, bytes, file) == (size_t)bytes && !fclose(file));
    return bytes;
}

static void save(const char *directory, const char *name, const void *payload, size_t bytes)
{
    char path[1200];
    int size = snprintf(path, sizeof(path), "%s/%s", directory, name);
    CHECK(size > 0 && (size_t)size < sizeof(path));
    FILE *file = fopen(path, "wb");
    CHECK(file && fwrite(payload, 1, bytes, file) == bytes && !fclose(file));
}

int main(int argc, char **argv)
{
    CHECK(argc == 6);
    current_case = argv[4];
    setup(1, 1, 1, 1);
    images[0].size = load(argv[1], code_payload, CODE_LIMIT);
    images[1].size = load(argv[2], data_payload, DATA_LIMIT);
    size_t code_bytes = images[0].size, data_bytes = images[1].size;
    int expected = atoi(argv[5]);
    if (!strcmp(current_case, "rng-error")) random_error = -EINTR;
    else if (!strcmp(current_case, "rng-zero")) random_identity = 0;
    else if (!strcmp(current_case, "missing-ba")) has_ba = 0;
    else if (!strcmp(current_case, "missing-lease")) priv.dma_lifetime = NULL;
    else if (!strcmp(current_case, "missing-buffer7")) fake_lifetime.buffers[7].buf = NULL;
    else if (!strncmp(current_case, "readback-", 9)) io_fault = atoi(current_case + 9);
    struct resource binary = valid_region();
    int result = airoha_npu_run_firmware(&priv, data_memory + GUARD, &binary);
    CHECK(result == expected);
    CHECK(acquired[0] == released[0] && acquired[1] == released[1]);
    int after_copy = !strncmp(current_case, "readback-", 9);
    if (!expected || after_copy) {
        const int order[] = {10, 11, 20, 21, 31, 30};
        CHECK(requests == 2 && copies == 2 && event_count == 6);
        CHECK(!memcmp(events, order, sizeof(order)));
        CHECK(fake_lifetime.exposed && module_pins == 1 && io_writes == 14);
        CHECK(!memcmp(code_memory + GUARD, code_payload, code_bytes));
        CHECK(priv.native_published == !expected && priv.firmware_loaded == !expected);
        if (!expected) {
            CHECK(io_reads == 19 && random_calls == 1 && priv.boot_identity == random_identity);
            CHECK(!memcmp(data_memory + GUARD + NPU_EN7581_NATIVE_PLAN, priv.native_plan, 48));
            CHECK(!memcmp(data_memory + GUARD + NPU_EN7581_NATIVE_IDENTITY, &priv.boot_identity, 8));
            CHECK(!memchr_inv(data_memory + GUARD + NPU_EN7581_NATIVE_SESSION, 0, 20));
            unsigned old_requests = requests, old_copies = copies, old_rng = random_calls;
            CHECK(airoha_npu_run_firmware(&priv, data_memory + GUARD, &binary) == -EBUSY);
            CHECK(requests == old_requests && copies == old_copies && random_calls == old_rng);
            CHECK(priv.firmware_loaded && priv.native_published);
        }
    } else {
        CHECK(!copies && !fake_lifetime.exposed && !module_pins && !io_writes);
        CHECK(!priv.firmware_loaded && !priv.native_published);
        memory_matches(code_memory, CODE_LIMIT, 0, 0);
        memory_matches(data_memory, DATA_LIMIT, 0, 0);
    }
    save(argv[3], "CODE-copied.bin", code_memory + GUARD, code_bytes);
    save(argv[3], "DATA-published.bin", data_memory + GUARD, data_bytes);
    printf("{\"result\":%d,\"requests\":%d,\"copies\":%d,\"random_calls\":%u,"
           "\"io_writes\":%u,\"io_reads\":%u,\"exposed\":%s,\"module_pins\":%u,"
           "\"published\":%s,\"checked_pair\":%s}\n", result, requests, copies, random_calls,
           io_writes, io_reads, fake_lifetime.exposed ? "true" : "false", module_pins,
           priv.native_published ? "true" : "false", priv.checked_pair ? "true" : "false");
    return 0;
}
