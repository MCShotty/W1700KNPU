#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "cold-descriptor.h"

int main(void)
{
    struct npu_cold_descriptor_state s = {0};
    uint32_t words[4096], arena = 0x3e810000;

    for (uint32_t step = 0; step < 8; step++) {
        uint32_t count = step < 6 ? 0 : step == 6 ? 512 : 1024;
        uint32_t base = arena + npu_cold_descriptor_offset(step);

        for (uint32_t i = 0; i < 4096; i++) words[i] = i ^ 0x11223344u;
        assert(!npu_cold_descriptor_begin(&s, arena, 1,
               npu_cold_descriptor_selector(step), count ? words : NULL));
        for (uint32_t i = 0; i < count; i++) {
            assert(!npu_cold_descriptor_reserve(&s, arena, 1, base + i * 16 + 4,
                                               0x80000000, words[i * 4 + 1]));
            words[i * 4 + 1] = 0x80000000;
            assert(!npu_cold_descriptor_publish(&s, arena, 1, base + i * 16 + 4, words[i * 4 + 1]));
        }
        assert(!npu_cold_descriptor_finish(&s, arena, 1, base & 0x1fffffff, count ? words : NULL));
        for (uint32_t i = 0; i < 4096; i++)
            if (i >= count * 4 || i % 4 != 1) assert(words[i] == (i ^ 0x11223344u));
    }
    assert(s.next == 8 && s.completed == 255 && s.reserved_tx == 3 && s.completed_tx == 3);
    assert(s.committed == 1536 && s.published == 1536 && !s.active && !s.fault);
    assert(npu_cold_descriptor_begin(&s, arena, 1, 0, NULL) != 0);
    assert(s.fault && s.committed == 1536 && s.published == 1536);
    memset(&s, 0, sizeof(s));
    s.preimages[1535] = 1;
    assert(npu_cold_descriptor_begin(&s, arena, 1, 0, NULL) == NPU_COLD_DESCRIPTOR_REINITIALIZE);
    assert(s.preimages[1535] == 1);
    printf("{\"passed\":true,\"steps\":8,\"status_writes\":1536,\"retirement\":false}\n");
    return 0;
}
