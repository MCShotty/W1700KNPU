/* Byte-pattern plans test the exact read-boundary predicate, not geometry. */
#include "cold-inode.c"

static struct npu_cold_inode_plan current, held;
static uint32_t calls, changed, callback_result;
uint32_t npu_test_snapshot_cases;
volatile uint32_t npu_test_capture_count;
uint32_t npu_test_capture_before[NPU_COLD_INODE_FIRST_STORES];
static unsigned char compare_left[sizeof(struct npu_cold_inode_state) + 4];
static unsigned char compare_right[sizeof(compare_left)];
volatile uint32_t npu_test_compare_running;

#define REQUIRE(condition) do { if (!(condition)) return __LINE__; } while (0)

static int reader(void *opaque, uint32_t address, uint32_t bytes, uint32_t *value)
{
    calls++;
    if (opaque != &calls || address != 0x3e8bc470 || bytes != 4 || !value)
        return 0;
    *value = 0x12345678;
    if (changed < sizeof(current))
        ((unsigned char *)&current)[changed] ^= 0x80;
    return callback_result;
}

static void prepare(void)
{
    for (uint32_t i = 0; i < sizeof(current); i++) {
        ((unsigned char *)&current)[i] = (i * 37 + 19) & 255;
        ((unsigned char *)&held)[i] = ((unsigned char *)&current)[i];
    }
    calls = 0;
    changed = sizeof(current);
    callback_result = 1;
}

uint32_t npu_test_snapshot_all(void)
{
    const struct npu_cold_inode_context c = {.read = reader, .opaque = &calls};
    uint32_t value;

    npu_test_snapshot_cases = 0;
    prepare();
    REQUIRE(read_plan(&c, &current, &held, 0x3e8bc470, 4, &value));
    REQUIRE(calls == 1 && value == 0x12345678);
    npu_test_snapshot_cases++;
    for (uint32_t i = 0; i < sizeof(current); i++) {
        prepare();
        ((unsigned char *)&current)[i] ^= 0x80;
        value = 0xdeadbeef;
        REQUIRE(!read_plan(&c, &current, &held, 0x3e8bc470, 4, &value));
        REQUIRE(calls == 0 && value == 0xdeadbeef);
        npu_test_snapshot_cases++;
    }
    for (uint32_t i = 0; i < sizeof(current); i++) {
        prepare();
        changed = i;
        REQUIRE(!read_plan(&c, &current, &held, 0x3e8bc470, 4, &value));
        REQUIRE(calls == 1 && value == 0x12345678);
        for (uint32_t j = 0; j < sizeof(current); j++)
            REQUIRE(((unsigned char *)&current)[j] ==
                (((unsigned char *)&held)[j] ^ (i == j ? 0x80 : 0)));
        npu_test_snapshot_cases++;
    }
    prepare();
    callback_result = 0;
    REQUIRE(!read_plan(&c, &current, &held, 0x3e8bc470, 4, &value));
    REQUIRE(calls == 1);
    npu_test_snapshot_cases++;
    REQUIRE(npu_test_snapshot_cases == 2 * sizeof(current) + 2);
    return 0;
}

uint32_t npu_test_capture_all(void)
{
    const struct npu_cold_inode_context c = {.read = reader, .opaque = &calls};

    prepare();
    npu_test_capture_count = 0;
    for (uint32_t i = 0; i < NPU_COLD_INODE_FIRST_STORES; i++) {
        REQUIRE(read_plan(&c, &current, &held, 0x3e8bc470, 4,
                          &npu_test_capture_before[i]));
        npu_test_capture_count++;
    }
    REQUIRE(calls == NPU_COLD_INODE_FIRST_STORES);
    for (uint32_t i = 0; i < NPU_COLD_INODE_FIRST_STORES; i++)
        REQUIRE(npu_test_capture_before[i] == 0x12345678);
    return 0;
}

uint32_t npu_test_equal_boundary(uint32_t offset, uint32_t bytes, uint32_t changed)
{
    REQUIRE(offset < 4 && bytes <= sizeof(struct npu_cold_inode_state));
    for (uint32_t i = 0; i < sizeof(compare_left); i++)
        compare_left[i] = compare_right[i] = (i * 37 + 19) & 255;
    REQUIRE(changed < sizeof(compare_left) - offset);
    compare_right[offset + changed] ^= 0x80;
    npu_test_compare_running = 1;
    int result = equal(compare_left + offset, compare_right + offset, bytes);
    npu_test_compare_running = 0;
    REQUIRE(result == (changed >= bytes));
    compare_right[offset + changed] ^= 0x80;
    REQUIRE(equal((const void *)0, (const void *)0, 0));
    for (uint32_t i = 0; i < sizeof(compare_left); i++)
        REQUIRE(compare_left[i] == ((i * 37 + 19) & 255) &&
                compare_right[i] == compare_left[i]);
    return 0;
}

#ifndef __riscv
int main(void)
{
    uint32_t result = npu_test_snapshot_all();

    if (result) return result;
    result = npu_test_capture_all();
    if (result) return result;
    for (uint32_t offset = 0; offset < 4; offset++)
        for (uint32_t bytes = 0; bytes <= 9; bytes++) {
            result = npu_test_equal_boundary(offset, bytes, bytes);
            if (result) return result;
            if (bytes) {
                result = npu_test_equal_boundary(offset, bytes, bytes - 1);
                if (result) return result;
            }
        }
    return 0;
}
#endif
