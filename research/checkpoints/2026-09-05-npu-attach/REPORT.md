# NPU Provider Guard and Recovery Checkpoint

## Implemented

Patch `003-mt7996-skip-npu-buffers-without-provider.patch` checks provider
attachment before the six managed coherent allocations in
`mt7996_npu_hw_init()`. Previously an early attachment failure could leave the
driver on normal DMA but still allocate unused buffers, or fail probe with
`-ENOMEM` before the inner initializer noticed that no provider existed.

The eliminated allocations total **1,310,720 bytes (1.25 MiB)** on the current
MT7996-family branch and **2,621,440 bytes (2.5 MiB)** on the MT7992 branch.
Attached-provider behavior, allocation-failure returns and inner-init errors
are unchanged. This is not late-initialization rollback, NPU recovery, a fix for
the historical throughput result, or a measured improvement on the router.

The current image already compiles WLAN NPU out, so this patch does not change
its executable driver code. It prepares a more reliable future NPU-enabled
build. No image was rebuilt/flashed and no live module was replaced.

## Verification

- 20 native compiled-C cases execute the actual initializer body with provider,
  allocation and inner-init stubs. Both chip branches and all six allocation
  failures pass. The unpatched negative control reproduces six allocations
  with no attached provider. These are component tests, not kernel runtime.
- Real OpenWrt mt76 package builds pass with NPU enabled and disabled. The
  enabled ELF defines the three NPU lifecycle symbols. The disabled ELF does
  not. The normal build configuration is byte-identical to the preserved seed.
- Every nonempty executable ELF section of all three normal-DMA modules matches
  the retained pre-change baseline. Debug/path metadata may differ; full-module
  byte identity is not claimed. See `module-verification.json`.
- Full Ghidra auto-analysis ran on the two stock modules and rebuilt enabled
  `mt7996e.ko`: 27 + 21 + 314 initialized executable functions. Exported all 48
  stock functions and five current lifecycle functions, with zero failed
  selected decompilations. Binary SHA256 values bind the exports to their ELFs.
- The rebuilt initializer's AArch64 code branches to the zero-return epilogue
  on a missing provider before the first `dmam_alloc_attrs` call. The assembly
  listing and decompilation corroborate the source-body tests.
- Strict checkpatch: zero errors, warnings and checks. Source reconstruction
  verifies 33 OpenWrt and 3 LuCI changed files, including the new overlay patch.
- Pinned, Ethernet-bound read-only router access verifies the expected W1700K
  board, kernel 6.18.44 and WLAN NPU `compiled-out` state. Latest sample has
  1,659,132 KiB MemAvailable out of 1,868,028 KiB. No configuration or radio/
  transmit-power changes, module loads, reset triggers, or flash occurred.

## Recovery Gates Still Open

### L1 Stop and Restart Errors

Current `mt7996_mac_reset_work()` discards the return values of both
`mt7996_npu_hw_stop()` and `__mt7996_npu_hw_init()`, then resumes processing.
The new binary reproduces that call ordering. The stop helper can return a
mailbox error or timeout. Successful stop currently sends command 4, polls
GET_NPU_INFO index 3 until zero, then sends command 6. That protocol still
requires ownership/drain validation; adding an error log is not a fix.

### Full Reset Releases Tokens Before NPU Quiescence

The full-reset/restart branch calls `mt7996_tx_token_put()` before
`mt7996_dma_reset(..., true)` without a successful NPU-stop step. DMA reset
itself cleans TX/RX queues before its later NPU IRQ disable. Source and the
enabled ELF agree. With an independently active NPU this is an unresolved
buffer-lifetime hazard, not a reproduced use-after-free or device crash.
The full-reset branch also needs a validated provider restart sequence; fixing
only the two L1 return values is insufficient.

### Stock Exit Hooks Are Not a Drain Receipt

Fresh stock decompilation confirms that `hostadpt_tx_handler` indexes 0x400
entries at stride 0xd0, publishes producer positions through 0xa8/0xb8, and
unmaps/frees retained SKBs as observed consumer indices 0xac/0xbc advance.
The current host-adapter port therefore needs ownership accounting tied to
consumer progress, not just interrupt masking.

Stock `hostadpt.ko` cleanup frees IRQ registrations and clears hooks; stock
`npu.ko` cleanup clears `npu_stat` and removes proc entries. Neither selected
exit function establishes a complete hardware-drain/reset contract. Do not
copy their exit sequence and declare current OpenWrt recovery safe.

## Next Implementation Boundary

1. Trace the provider/stock WiFi mailbox reset coordinator and establish what
   successful stop actually guarantees about host-owned buffers and late writes.
2. Add a shared quiescence/failure policy covering L1, full reset and removal
   before token/ring reclamation; retain ownership when the guarantee fails.
3. Port the required Daybreak19 lifecycle accounting onto current mt76, with
   reproducible fault tests for timeout, partial restart and late completion.
4. Only then build an NPU-active image for serial-backed synthetic acceptance.
   Real-client WiFi/MLO throughput remains a separate unfulfilled acceptance gate.

The source base remains mt76
`be5ce7910521492d4a2e4ce7ee3843680a46c047`; live `git ls-remote` confirms it is
also the current upstream HEAD at this checkpoint. Relevant upstream files:
[initializer](https://github.com/openwrt/mt76/blob/be5ce7910521492d4a2e4ce7ee3843680a46c047/mt7996/npu.c)
and [recovery](https://github.com/openwrt/mt76/blob/be5ce7910521492d4a2e4ce7ee3843680a46c047/mt7996/mac.c).

## Tooling Limits

No GUI/MCP Ghidra instance was running; native headless Ghidra 12.1.2 was used.
Ghidra rejects dot-prefixed project-path components, so generated projects live
under ignored `scratch/`, not `.local/`. A first export incorrectly included
synthetic EXTERNAL-block entries; the corrected export excludes them and
retains the original logs as diagnostic history. Existing user tool-template
XML errors and optimized DWARF-location warnings are recorded, not hidden.
They did not prevent program auto-analysis or the selected exports, but the
decompiled types/local variables are not treated as exact original source.
