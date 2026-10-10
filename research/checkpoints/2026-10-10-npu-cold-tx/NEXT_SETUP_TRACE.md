# Next Strict Setup Boundary

Static source/Ghidra trace only. This file does not implement or authorize a
new GET transport, descriptor owner, physical write, reset or flash.

## Current Stop

Current actual mt7996 offload C completes version/port/RX/page/indication/ACK/
TX0/TX2/token setup. Native nominal replay then explicitly attempts
GET-selector0/API4 and observes `-EINVAL`, no callback and retained completed
prefix131071. Full `__mt7996_npu_hw_init()` still cannot finish.

The current host source next invokes `mt7996_npu_rxd_init()`: GET selectors
0,2,10,11,12,8, each followed by an endpoint `desc_base` write. Afterwards
`mt7996_npu_txd_init()` uses GET selectors5/7 and three TX-buffer-base commands
per band. TXDONE/event, PCIe-address/INODE and final IRQ setup follow. These
later host register writes and buffer lifetimes need their own checked contract.

## Original GET Is Not Uniformly Read-Only

Original GET table begins at DATA offset0x148. API4 maps to
`npu_table_158` at0x84010164, calling `FUN_ram_8400d836`. The selected RX cases
read stored pointers and mask them with0x1fffffff:

| Selector | Native Pointer Slot |
| --- | --- |
| 0 | 0x3e902ab0 |
| 2 | 0x3e902ce0 |
| 10 | 0x3e902a94 |
| 11 | 0x3e902aa4 |
| 12 | 0x3e904638 |
| 8 | 0x3e902aa0 |

Selectors5/7 are different. The same helper reads pointer slots0x3e9021ec/
0x3e90459c and writes status0x80000000 at offset4 of16-byte descriptors across
0x2000/0x4000-byte spans before returning. Those mutations are not covered by
the TX register owner in this checkpoint. Do not whitelist all API4 selectors
as read-only or treat a stored pointer as exclusive backing authority.

If the helper returns0, the original outer callback stores0x457 in the reply
and returns1. Transport success is therefore not a valid-address certificate.
A new strict getter must reject unsupported/fallback outcomes and validate its
exact original pointer provenance, alignment/span, existing ownership and
session/history before publication; host consumption must propagate failure
before its endpoint register write. Cache/DMA visibility and physical engine
coverage remain independent, unproved prerequisites.

## Host TX Buffer Lifetime

Current `mt7996_npu_hw_init()` allocates six TX buffers with
`dmam_alloc_coherent()` before `__mt7996_npu_hw_init()`. The currently denied
later API21 commands would publish these DMA addresses. Current6.18.52
`kernel/dma/mapping.c` registers a managed release callback calling
`dma_free_attrs()` and explicitly documents release on driver detach. Before
admitting those commands, establish retained host-buffer ownership after first
exposure and ambiguous partial setup/detach; a coherent allocation or returned
CPU call is not device retirement. This is a future integration requirement,
not a claim that this checkpoint exposes these still-denied addresses.

## Evidence

- Current source: `.local/merge-nonoc-20260923/mt76-merged/mt7996/npu.c`,
  functions `__mt7996_npu_hw_init`, `mt7996_npu_rxd_init`,
  `mt7996_npu_txd_init`, `mt7996_npu_rx_event_init` and later setup helpers.
- Original hash-pinned Ghidra export:
  `research/checkpoints/2026-09-05-npu-admission/ghidra-mailbox/en7581_MT7996_npu_rv32.bin.txt`,
  lines27230 and33783 begin the helper and callback. SHA256:
  `1536a9972838ca7c02da77629e784b392af919c5d25368478aff4d0c2422e2ca`.
- Existing table reconstruction:
  `tests/npu/test_mt7996_bootstrap_sequence.py`, GET table map/API4 callback.
  Its synthetic host GET values are not current native pointer proof.
- Fresh bounded `jev-1.13.0` review classifies RX as pointer lookup, TX5/7 as
  descriptor-status initialization and fallback as success-with-sentinel,
  each at probability/confidence1.0; all-selectors-read-only Noul0.06.
  Actual payload/results and source hashes are preserved beside this trace.
  These judgments support source triage, not runtime or physical acceptance.
