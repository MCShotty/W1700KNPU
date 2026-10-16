#include "cold-inode.h"

extern struct npu_cold_inode_state npu_test_inode_state;
extern struct npu_cold_pcie_tail_plan npu_test_tail_plan;
extern uint32_t npu_test_tail_cells[9], npu_test_inode_mutation, npu_test_inode_mutated;
extern uint32_t npu_test_tail_prepare(uint32_t), npu_test_tail_begin(uint32_t, uint32_t, uint32_t);
extern uint32_t npu_test_tail_reserve(uint32_t, uint32_t, uint32_t, uint32_t);
extern uint32_t npu_test_tail_effect(uint32_t, uint32_t), npu_test_tail_publish(uint32_t, uint32_t, uint32_t);
extern uint32_t npu_test_tail_finish(void);
extern uint32_t npu_test_inode_prepare(uint32_t), npu_test_inode_begin(uint32_t, uint32_t, uint32_t);
extern uint32_t npu_test_inode_run(uint32_t, uint32_t), npu_test_inode_finish(void), npu_test_inode_live(void);
extern uint32_t npu_test_inode_stage_live(uint32_t);

static int prepare(uint32_t hif2)
{
    if (npu_test_tail_prepare(hif2)) return 1;
    for (uint32_t stage = 0; stage < 3; stage++) {
        uint32_t end = stage < 2 ? stage * 2 + 2 : 9;
        if (npu_test_tail_begin(npu_cold_pcie_tail_selector(stage),
            npu_cold_pcie_tail_value(&npu_test_tail_plan, stage), 1)) return 2;
        for (uint32_t i = stage * 2; i < end; i++) {
            struct npu_cold_pcie_tail_store store;
            if (npu_cold_pcie_tail_recipe(&npu_test_tail_plan, i, &store) ||
                npu_test_tail_reserve(store.address, store.bytes, store.value, npu_test_tail_cells[i]) ||
                npu_test_tail_effect(i, store.value) ||
                npu_test_tail_publish(store.address, store.bytes, store.value)) return 3;
        }
        if (npu_test_tail_finish()) return 4;
    }
    return npu_test_inode_prepare(hif2);
}

int main(void)
{
    for (uint32_t hif2 = 0; hif2 < 2; hif2++) {
        if (prepare(hif2)) return 1;
        for (uint32_t stage = 0; stage < 2; stage++) {
            uint32_t remaining = stage ? 6 : 1030;
            if (npu_test_inode_begin(stage ? 7 : 2, 0, 1)) return 2;
            while (remaining) {
                uint32_t count = remaining > 16 ? 16 : remaining;
                if (npu_test_inode_run(count, 0)) return 3;
                remaining -= count;
            }
            if (npu_test_inode_finish()) return 4;
            if (!npu_test_inode_stage_live(stage) || npu_test_inode_stage_live(stage ^ 1) ||
                npu_test_inode_stage_live(2)) return 8;
        }
        if (!npu_test_inode_live()) return 5;
    }
    for (uint32_t mode = 1; mode <= 8; mode++) {
        if (prepare(0)) return 6;
        npu_test_inode_mutation = mode;
        if (!npu_test_inode_begin(2, 0, 1) || !npu_test_inode_mutated ||
            !npu_test_inode_state.fault || npu_test_inode_state.committed) return 7;
    }
    return 0;
}
