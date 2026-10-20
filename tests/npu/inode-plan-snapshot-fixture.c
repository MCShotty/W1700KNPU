/* Byte-pattern plans test the exact read-boundary predicate, not geometry. */
#include "cold-inode.c"

static struct npu_cold_inode_plan current, held;
static uint32_t calls, changed, callback_result;
uint32_t npu_test_snapshot_cases;

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

#ifndef __riscv
int main(void)
{
    return npu_test_snapshot_all();
}
#endif
