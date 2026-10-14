#include "cold-pcie-tail.h"

extern struct npu_cold_pcie_tail_state npu_test_tail_state;
extern struct npu_cold_pcie_tail_plan npu_test_tail_plan;
extern uint32_t npu_test_tail_cells[9], npu_test_tail_mutation, npu_test_tail_mutated;
extern uint32_t npu_test_tail_prepare(uint32_t);
extern uint32_t npu_test_tail_begin(uint32_t, uint32_t, uint32_t);
extern uint32_t npu_test_tail_reserve(uint32_t, uint32_t, uint32_t, uint32_t);
extern uint32_t npu_test_tail_effect(uint32_t, uint32_t);
extern uint32_t npu_test_tail_publish(uint32_t, uint32_t, uint32_t);
extern uint32_t npu_test_tail_finish(void), npu_test_tail_live(void);

int main(void)
{
    for (uint32_t hif2 = 0; hif2 < 2; hif2++) {
        if (npu_test_tail_prepare(hif2)) return 1;
        for (uint32_t stage = 0; stage < 3; stage++) {
            uint32_t first = stage * 2, end = stage < 2 ? first + 2 : 9;
            if (npu_test_tail_begin(npu_cold_pcie_tail_selector(stage),
                npu_cold_pcie_tail_value(&npu_test_tail_plan, stage), 1)) return 2;
            for (uint32_t i = first; i < end; i++) {
                struct npu_cold_pcie_tail_store store;
                if (npu_cold_pcie_tail_recipe(&npu_test_tail_plan, i, &store) ||
                    npu_test_tail_reserve(store.address, store.bytes, store.value, npu_test_tail_cells[i]) ||
                    npu_test_tail_effect(i, store.value) ||
                    npu_test_tail_publish(store.address, store.bytes, store.value)) return 3;
            }
            if (npu_test_tail_finish()) return 4;
        }
        if (!npu_test_tail_live()) return 5;
    }
    for (uint32_t mode = 1; mode <= 4; mode++) {
        if (npu_test_tail_prepare(0)) return 6;
        npu_test_tail_mutation = mode;
        if (!npu_test_tail_begin(0, 0x200d4580, 1) || !npu_test_tail_mutated ||
            !npu_test_tail_state.fault || npu_test_tail_state.committed) return 7;
    }
    return 0;
}
