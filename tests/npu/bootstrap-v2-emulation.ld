/* Additional test reservations only; no production placement approval. */
ASSERT(npu_emulation_control_v2_state >= npu_emulation_bootstrap_plan + 48,
       "V2 session overlaps bootstrap plan")
ASSERT(npu_emulation_control_v2_state + 20 <= npu_emulation_control_v2_boot,
       "V2 session overlaps loader identity")
ASSERT(npu_emulation_control_v2_boot + 8 <= 0x3e908000,
       "V2 identity outside local SRAM fixture")
ASSERT((npu_emulation_control_v2_state & 3) == 0 &&
       (npu_emulation_control_v2_boot & 3) == 0,
       "V2 control identity is not word aligned")
