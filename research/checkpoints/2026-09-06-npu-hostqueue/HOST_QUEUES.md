# Pinned Host TX Queue Publication

Status: extracted host-C execution with explicit framework boundaries, not a
whole-driver/kernel run or hardware-readiness certificate. No production patch.

## Result

- 12 success traces: HIF2 absent/present x NPU inactive/active x stop after band0/1/2.
- 60 controls: 4 pre-seeded TX1 storage cases, 40 modeled allocation/framework
  failures, and 16 explicitly counterfactual page-pool/WED error-return cases.
- 4 mutants killed: omitted base publication, wrong NPU queue ID, forced
  SINGLE-HIF allocation, and base publication moved before ring size.
- 19 complete pinned functions and 2 unchanged TX-only blocks execute.
  Two consecutive final runs produced identical harness, executable and JSON hashes.
- GCC 15.2.0, GNU C11, `-Wall -Wextra -Werror -Wno-sign-compare`, UBSan with
  recovery disabled. Only generated host test executables ran.
- Parent review of the generated harness boundaries and full independent rerun
  passed with the same harness, binary and evidence hashes listed below.

| HIF2 | NPU | Band0/1/2 queue owners | Allocated descriptor rings | NPU TX1 writes |
| --- | --- | --- | --- | --- |
| absent | inactive | 0 / 0 / 2 | two, each 2048 x 16 bytes | none |
| present | inactive | 0 / 1 / 2 | three, each 2048 x 16 bytes | none |
| absent | active | 0 / 0 / 0 | TX0: 1024 x 208 bytes | none |
| present | active | 0 / 1 / 1 | TX0: 1024 x 208; TX1: 512 x 208 | base and size during band1 |

Every access-category queue through `MT_TXQ_PSD` has its pointer alias checked.
The oracle checks exact ordered register-write addresses/values, allocation byte
counts, physical DMA queue selection, errors, and registration cleanup.

## Publication

For each NPU TX queue, actual reset/sync/write C emits this sequence into storage:
NPU cpu_idx=0, NPU dma_idx=0, NPU ring_size, physical ring_size, physical desc_base,
NPU desc_base, then a modeled register read for dma_idx. Allocation precedes it.
With NPU inactive, all four writes target only the physical register storage.

The provider-address boundary uses the supplied prior mapping
`0x30d000 + 0x80 + ((qid + 2) << 4)`. With the separately supplied physical base
`0x1e900000`, TX1 desc_base/ring_size correspond to `0x1ec0d0b0/b4`.
Neither provider implementation nor physical address mapping was re-executed or
independently revalidated here. All observed addresses are host-test storage keys.

SINGLE-HIF emits no TX1 publication; pre-seeded nonzero TX1 values survive untouched.
DUAL-HIF publishes TX1 before `mt76_register_phy()`; a modeled failure at that later
boundary leaves the published values present while the PHY pointer is removed.
Nonzero registers, queue publication, and successful return are not readiness proof.

## Execution Boundary

Complete, unmodified extracted functions include `mt7996_register_phy` (init.c:708),
`mt7996_init_tx_queues` (mt7996/dma.c:10), `mt76_dma_alloc_queue` (dma.c:828),
`mt76_dma_queue_reset` (221), `mt76_dma_sync_idx` (201), `mt76_dma_read_dma_idx`
(193), `mt76_npu_queue_setup` (npu.c:244), both register handlers (dma.h:51/79),
and ten header predicates. Original queue/register/descriptor declarations and
relevant macros are extracted, with per-fragment hashes in `host-queues.json`.

The original TX configuration block (mt7996/dma.c:130) and primary-TX allocation
block (682) have fixture entrypoints; full `mt7996_dma_config`, `mt7996_dma_init`
and `mt7996_register_device` do not execute. The fixture schedules band0 then
band1 then band2. Its `TXQ_CONFIG` projection sets q_id and asserts WFDMA0; it
does not implement interrupt-mask assignment. Primary HIF offset is fixture-framed.

The connac -> mt76_init_tx_queue -> mt76_init_queue bridge is a model grounded in
the pinned helper bodies, not extracted execution: it allocates a queue, sets
flags/WED pointer, calls the real DMA allocator, propagates errors, then aliases
access-category queues. It replaces the queue_ops dispatch, not allocator logic.
Those bodies and their locations are separately hashed in the evidence.

Other modeled boundaries: MT7996/MMIO identity; inactive WED; radio allocation;
EEPROM/capability/wiphy/registration success or injected errors; coherent memory
with synthetic DMA addresses; serialized RCU/locks; provider lookup; regmap/MMIO
storage. WED-RRO magic setup asserts the excluded flag absent. TX page-pool setup
returns zero normally. Its eight injected failures, and eight WED setup failures,
are counterfactual propagation checks only. They are not reachable TX failures.
No concurrency, cache, DMA visibility, full ABI, RX fill or attachment proof.

## Next Action

The SINGLE-HIF TX1 contract remains unresolved under the independently supplied
boot prerequisite. Before selecting any host change, establish deliberate TX1
queue ownership, physical queue mapping, allocation and publication. SINGLE-HIF
configuration assigns band0 and band2 IDs, not band1: merely removing band1's alias
would select its zero-initialized physical queue ID 0. No dummy publication or
production correction is proposed by this test; no native prerequisite was rerun.

Parent-supplied live context: R1 has no configured wifi-iface/wifi-mld and no
hostapd interfaces, so there is no reproduced client failure. `mt7996e` is bound
to `0000:01:00.0` and `mt7996e_hif` to `0002:01:00.0`; those bindings alone do not
prove internal `dev->hif2` pairing. The matrix is not a live-device root cause.

## Inputs And Reproduction

Repository HEAD was verified at task start as
`834786a0248b23a602c168c268c7852c0cf9b6fc`; mt76 pin is
`be5ce7910521492d4a2e4ce7ee3843680a46c047`.
The test reads only 12 source/header archive members, compares all six available
snapshot copies byte-for-byte before and after execution, and writes scratch only
below `.local/npu-hostqueue`. Missing snapshot members come from the pinned archive.

Dependencies: `mt7996/init.c`, `mt7996/dma.c`, `dma.c`, `dma.h`, `npu.c`, `mt76.h`,
`mt7996/mt7996.h`, `mt7996/regs.h`, `mt7996/eeprom.h`, `airoha_offload.h`;
`mt76_connac_mac.c` and `mac80211.c` are read only for framework-boundary provenance.
Full member hashes, fragment hashes, compiler command and per-case traces are in
`host-queues.json`. No import or run of existing bootstrap/native test helpers.

```sh
cd /home/captain/W1700KNPU
python3 tests/npu/test_host_queue_publication.py
```

SHA256:

```text
archive  d1d0f7588c5b9ceafcac341ce19dd206ed9ec106847e672ab77e48bacb57f81a
test     184706671c0583b4b12d5ea0bfdd5bc3a7a9c2d0409851cc17796eeec1e7aaf0
harness  b7031d6073b38427a80ac6543690b5551ef34961c57203789907f86e4b86a407
binary   746cf9dc9aaf9685baf0e82d2212b8a28450c7371e24c2aaa41000c85e029bf4
evidence d00d35871d15d1689a7ff362930a6d9c60a93e7f82e5f273d6578d0d8f12e8a1
```

Only this report, `host-queues.json`, the new test and ignored task scratch were
written. The canonical ledger and parent-owned live Wi-Fi docs/files were left
untouched by this task. No firmware/native binary execution, Ghidra, excluded
consumer/provider work, hardware/network/configuration action, shared-source build,
image/flash, Git mutation or production patch occurred.
