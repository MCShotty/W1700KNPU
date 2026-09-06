# Current MT7996 Host Attachment Sequence

2026-09-06. Bounded host-sequence lane; full NPU goal remains **OPEN**.
Only this report, `host-sequence.json`, and
`tests/npu/test_mt7996_bootstrap_sequence.py` were written. Generated C/executables
are under `.local/npu-nativewifi/host`. No production, policy/platform, protocol,
binding, source-lock, overlay, config, build-tree, staging, router, flash, commit,
or ledger changes. Parent owns full native Wi-Fi boot and scheduling evidence.

## Evidence Levels

- **Executed host C:** ten actual function bodies from pinned MT7996 `npu.c`,
  actual mt76 scalar wrappers, actual current provider SET/GET framing functions
  and wire structure, current kernel enums, and pinned register macros. Compiled
  and executed with modeled host structs, allocation, MMIO, replies and errors.
  MT7996 only; MT7992 alternate helpers compile but are not exercised.
- **Original RV32 instructions:** DATA-table-bound mailbox callbacks run through
  the existing Mailbox harness. PLIC/mailbox W1C, hart ID and printf retain its
  documented substitutions. Complex DESC/TX-init paths stop at helper entry,
  without inventing a successful return. Two TXBUFSPACE record tests substitute
  only allocator returns. No full kernel build or full boot is claimed.
- **Static only:** downstream initializer requirements, consumer waits, and the
  six host-adapter register writers. No additional core0/L2/helper/scheduling
  emulation was added for the parent's follow-up request.

Inputs: `.local/npu-startup/snapshot-audit/mt76/mt7996/npu.c`, revision
`be5ce7910521492d4a2e4ce7ee3843680a46c047`; seven audited snapshot members are
byte-compared to the retained download archive. Missing `mt7996/regs.h`,
`mt7996/pci.c`, `dma.h`, and the TX queue allocation chain are read directly
from that archive, without preparing a build tree. Enums/provider are from
the current Linux `6.18.44` build source. Complete input/member/function hashes
and exact traces are in `host-sequence.json`.

## Exact Wire Order

`P = dev->mt76.mmio.phy_addr`; `H = hif2 ? 0x4000 : 0`.
`T[0..5] = dev->npu_txd_addr[]`; `F = q_rx[TXFREE_BAND0].desc_dma`.
`port = dev->mt76.mmio.npu_type`, initialized by PCI probe to domain-nonzero
`? 3 : 2`, independently of HIF2. All selected queue bases use WFDMA0.

Every row advertises **12 bytes**: 8-byte header plus one 32-bit payload/result.
SET word0 is `0x10 | ifindex`; GET word0 is `0x30 | ifindex`; word1 is the
numeric API. GET request payload is zero-initialized by the provider; response
is four bytes. Wait-enabled completion is used by the current provider.

| # | Operation / API | Ifindex | Value or destination |
|---|---|---|---|
| 1 | GET VERSION / 10 | 0 | Logged only; no readiness check |
| 2 | SET PORT / 14 | 0 | `port` |
| 3 | SET DESC / 1 | 0 | 1536 |
| 4 | SET DESC / 1 | 2 | 1024 |
| 5 | SET PCIe / 0 | 5 | `P + 0xd45a0` |
| 6 | SET DESC / 1 | 5 | 256 |
| 7 | SET PCIe / 0 | 6 | `P + 0xd45b0` |
| 8 | SET DESC / 1 | 6 | 512 |
| 9 | SET PCIe / 0 | 7 | `P + 0xd45c0` |
| 10 | SET DESC / 1 | 7 | 1024 |
| 11 | SET PCIe / 0 | 8 | `P + 0xa040` |
| 12 | SET DESC / 1 | 8 | 1536 |
| 13 | SET TX_RING_PCIE / 19 | 3 | `P + 0xa050`, ACK-SN register |
| 14 | SET TX_RING_PCIE / 19 | 0 | `P + 0xd4420` |
| 15 | SET TX_RING_PCIE / 19 | 2 | `P + 0xd4450 + H` |
| 16 | SET TOKEN / 33 | 0 | 8192; then host `token_start=8192` |
| 17 | GET RXDESC / 4 | 0 | Write RRO_BAND0 descriptor base |
| 18 | GET RXDESC / 4 | 2 | Write RRO_BAND2 descriptor base |
| 19 | GET RXDESC / 4 | 10 | Write MSDU_PAGE_BAND0 descriptor base |
| 20 | GET RXDESC / 4 | 11 | Write MSDU_PAGE_BAND1 descriptor base |
| 21 | GET RXDESC / 4 | 12 | Write MSDU_PAGE_BAND2 descriptor base |
| 22 | GET RXDESC / 4 | 8 | Write RRO_IND descriptor base |
| 23 | GET RXDESC / 4 | 5 | Write `phys[1]->q_tx[0]` descriptor base |
| 24 | SET TXBUFSPACE / 21 | 0 | `T[0]` |
| 25 | SET TXBUFSPACE / 21 | 5 | `T[1]` |
| 26 | SET TXBUFSPACE / 21 | 10 | `T[2]` |
| 27 | GET RXDESC / 4 | 7 | Write `phys[0]->q_tx[0]` descriptor base |
| 28 | SET TXBUFSPACE / 21 | 2 | `T[3]` |
| 29 | SET TXBUFSPACE / 21 | 7 | `T[4]` |
| 30 | SET TXBUFSPACE / 21 | 12 | `T[5]` |
| 31 | SET TXDONE_RING / 22 | 0 | `F` |
| 32 | SET DESC / 1 | 10 | 512 |
| 33 | SET PCIe / 0 | 10 | `P + 0xd4590` |
| 34 | SET PCIe / 0 | 0 | `P + 0xd4580` |
| 35 | SET PCIe / 0 | 2 | `P + 0xd4560 + H` |
| 36 | SET PCIe / 0 | 15 | **0: publish five ring CPU indices** |
| 37 | SET INODE / 24 | 2 | **0: run gates and ICV clear** |
| 38 | SET INODE / 24 | 7 | **0: further run gates** |

Only rows 15/35 acquire `H`. With HIF2 absent, band1 shares band0's TX queue,
so rows 23/27 write the **same register target**. The fixture models this alias.
Both HIF choices and both port values are tested. Addresses are synthetic in
the executable, not recovered live BAR/DMA allocations.

Each error returns immediately from the current host path, with no subsequent
command or IRQ enable. Earlier successful side effects are not rolled back.
All 38 error positions are tested for all four profiles. Provider timeout
ownership is outside this test; an error does not certify no firmware action.

## Callback Contract

Offsets below use SRAM base `0x3e900000`. `U(v)=(v & 0x3fffffff)|0x40000000`.
DATA SET table starts at `+0x178`; GET table at `+0x148`. Every listed callback
is asserted against original DATA bytes and the pinned Ghidra export.

| API | Callback -> implementation | Selectors and requirements |
|---|---|---|
| SET14 | `8400ff34 -> 8400da92` | Ignores selector; consumes low byte of value, stores `+390e`. No port-range rejection. Host uses 2/3. |
| SET0 | `8400fdc4 -> dfac -> b94e` | 0/2 store PCIe bases `+2cf0/+3904` **and write base+8 = 1535/1023**. 5/6/7/8/10 store `+395c/+2a80/+4630/+2a9c/+2a90`. 15 dereferences those five saved bases and writes CPU indices 255/511/1023/1535/`u16(+2a7c)-1`. Others warn/no action. |
| SET1 | `8400fe34 -> 8400dd82` | 0/2 call RX initialization `d2d4`, then `b6ba/b7e8`; 5/6/7 fetch table IDs 7/8/9, then `bc02`; 8 fetches table ID6 then `bae6`; 10 calls TXDONE initializer `b432`. 12 is explicitly ignored; other selectors warn/no action. |
| SET19 | `8400fc16 -> e28e -> d5da` | 0/2 store PCIe TX bases `+4700/+46fc`, then **call TX initialization `d490`**, which selects port-specific `1fc08030/34`, `1fc28030/34`, or `1fc48030/34` register writes from firmware table IDs 1/2. 3 only stores ACK-SN base `+4610`. Others warn/no action. |
| SET33 | `8400fdda -> 8400dfb0` | Accepts **2047..28672 inclusive**, stores token size at `gp-0x7e8 = SRAM+0xbc0`. Outside that interval callback returns failure (mailbox flags 3, not 7). Host sends 8192. |
| SET21 | `8400fbca -> f0c2 -> ef36` | 0/2 store `U(value)` at `+2cf8/+2ab4`. 5/7 get table IDs 10/11 into `+1f38/+2abc` and initialize 512/1024 **128-byte** records; the supplied address is diagnostic-only in these two branches. 10/12 store `U(value)` at `+3960/+2a88` and call `a5fa(0/1)`, which **waits for nonzero TX-packet base `+2ab8`**. Others warn/no action. |
| SET22 | `8400fbb4 -> e2b8 -> b5c6` | 0 stores `U(value)` at `+3964`, required before DESC10. 5/6/7 can replace page descriptor bases `+2a94/+2aa4/+4638`; unused by this host sequence. Others warn/no action. |
| SET24 | `8400fc2c -> 8400e084` | Selector 2 writes `+46ec=1`, `+46f0=1`, `+46f8=3` **before clearing 0x1008 bytes through `+2ac0`**, then `+46f7=0`. Selector 7 writes `+46f5=0`, `+46f0=1`, `+46f9=3`, `+46f8=3`, `+46e1=1`, `+46e0=1`. Neither needs a nonzero scalar. |
| GET4 | `84010164 -> 8400d836` | Supported 0/2/5/7/8/10/11/12 return saved base masked `&0x1fffffff`. **5/7 first write `0x80000000` at base+4 every 16 bytes for 512/1024 descriptors** (8/16 KiB span). Missing/unsupported/zero return becomes successful **`0x457` fallback**. Host does not reject it. |

SET0/19/21/22 diagnose input addresses `>=0xc0000000` but their implementations
continue; the message must not be treated as a validated address capability.
SET24's other implemented selectors are 0/1 (address-dependent table clearing),
3 (table marking), 4 (legacy stop), 5 (diagnostic), 6 (buffer-ID reset); 8..15
are unsupported. Those non-attach operations were not executed in this lane.

**Read footprint:** dispatcher reads the two header words. SET14 reads one byte
at offset8 (9 readable bytes); SET0/1/19/33/21/22 read a word at offset8
(12 readable bytes). SET24 unconditionally loads words at offsets
8/12/16/20: **24 readable bytes although rows 37/38 advertise 12**. Native
length 0/8/12/24 controls all take the same release path with 256 readable
backing bytes. This is a logical-payload overread, not proof of a mapping escape;
selectors 2/7 ignore the extra argument values. GET4/GET10 read 8 header bytes
and write a four-byte response at offset8, requiring 12 writable bytes.

## Consumer Dependencies

These downstream facts are **static Ghidra evidence**, not duplicated full
helper/worker execution. Function addresses and export-line hashes are in JSON.

- DESC0/2 require earlier Wi-Fi/table initialization and packet-buffer/bufid
  allocation. They populate 16-byte RX descriptors, then set `+2a84/+4588=1`.
  Their nominal descriptor-size diagnostic range is 1..1536, but diagnostics
  are not a fail-closed size gate; callback return also does not propagate
  inner initialization failure.
- DESC5/6/7 use the earlier BA/page allocator, initialize 16-byte page
  descriptors, then set `+1f44/+3954/+2ce8=1`. DESC8 initializes 8-byte
  indication descriptors. The host requests 256/512/1024 pages and 1536
  indication entries.
- DESC10 needs the TXFREE base, packet memory, and buffer-ID allocator. It
  fills 512 16-byte descriptors and a buffer-ID table, then sets `+46fa=1`.
  Its nominal size diagnostic range is 1..512; the diagnostic alone does not
  stop invalid-size work. An allocation failure returns before the final flag.
- `worker_8400cdc6` waits on `+2a84`, `+4588`, all three page flags, and `+46ec`.
  `worker_8400c9b0` waits on the three page flags and `+46ec`.
  `worker_8400d0ae` initially waits on `+46fa`, `+4708`, and `+46f9==3`.
  Thus DESC commands plus INODE2/7 can release consumer waits; they are not
  passive address setters. This does not assert complete/repeated quiescence.
- SET21 if10/12 enters a TX-packet-base wait. Once released, `a5fa` obtains
  allocator IDs `0x100/0x101` and constructs 512 16-byte entries pointing into
  the supplied host buffer space at 256-byte increments. Here only wait versus
  post-wait entry is executed; no full helper completion is claimed.
- SET0 if15 needs all five saved MMIO bases valid and the TXDONE count set;
  it does not validate any of them before publication. INODE2 needs a valid
  writable 4104-byte ICV table and exposes its run flags before the clear ends.
  These operations require a complete, contained attachment precondition, not
  permission derived merely from the six provider reservations.

## Host-Adapter Register Writers

**Source-only follow-up for the parent's `f832` wait.** No firmware emulation
was added for these registers. Current AN7581 DTS maps the NPU at `0x1e900000`;
provider `NPU_WLAN_BASE_ADDR=0x30d000`, yielding physical `0x1ec0d000`.
`airoha_npu_wlan_queue_addr_get(qid,xmit)` returns `REG_TX_BASE(qid+2)` for TX
and `REG_RX_BASE(qid)` for RX. `mt76_queue_regs` fields are base/size/CPU/DMA
at offsets 0/4/8/12.

| Register | Established by current host source | Value |
|---|---|---|
| `1ec0d0a0` | Primary PHY band0 NPU TX queue allocation/reset | Coherent descriptor base; 1024 x 208 bytes |
| `1ec0d0a4` | Same | 1024 descriptors |
| `1ec0d0b0` | Band1 registration, **HIF2 present** | Coherent descriptor base; 512 x 208 bytes |
| `1ec0d0b4` | Same | 512 descriptors |
| `1ec0d180` | `MT_RXQ_NPU0` allocation/reset inside `mt7996_dma_init` | Coherent descriptor base; 512 x 24 bytes |
| `1ec0d190` | `MT_RXQ_NPU1` allocation/reset inside `mt7996_dma_init` | Coherent descriptor base; 512 x 24 bytes |

TX writer chain: `mt7996_init_tx_queues` -> `mt76_connac_init_tx_queues` ->
`mt76_init_tx_queue` -> `mt76_init_queue` -> `queue_ops->alloc`.
RX writer chain: `mt7996_npu_rx_queues_init` -> `mt76_npu_rx_queue_init` ->
`queue_ops->alloc`. Both reach `mt76_dma_alloc_queue`, which allocates memory,
calls `mt76_npu_queue_setup` to select `q->wed_regs`, then calls
`mt76_dma_queue_reset` -> `mt76_dma_sync_idx` -> `Q_WRITE` ->
`mt76_dma_handle_write` -> `regmap_write(npu->regmap,q->wed_regs+offset,val)`.
Reset zeros CPU/DMA indices; sync writes ring size, then descriptor base.

These are ordinary register writes, **not mailbox SET APIs**. Their phase is
earlier than `__mt7996_npu_hw_init`: `mt7996_register_device` calls
`mt7996_init_hardware` (including `mt7996_dma_init`), registers bands1/2, then
calls `mt7996_npu_hw_init` with the 38-message tail.

With HIF2 absent, the band1 registration branch aliases band0's TX queue;
NPU-active band2 aliases band1. That path does **not** allocate TX1 or establish
nonzero `1ec0d0b0`. This is the precise source dependency corresponding to the
parent's observed wait, not a reproduced hardware hang or a repair proposal.
Base publication also precedes RX fill/NAPI completion. Nonzero bases alone
do not certify initialized descriptors, correct sizes, or complete attach.
Exact source members/lines/hashes are under `host_adapter_source` in JSON.

## IRQ And Init-Done

After command38 succeeds, `__mt7996_npu_hw_init` calls
`airoha_npu_wlan_enable_irq(npu,0)` then `(npu,1)`. Provider implementation
sets bit16 in `1ec0d034` and bit17 in `1ec0d038`. The host test observes calls,
not physical delivery. IRQ request, NAPI setup and RX allocation occur earlier.

SET API2 `WLAN_FUNC_SET_WAIT_NPU_INIT_DONE` has no call site in the pinned mt76
C files; its enum exists in the compatibility header. Original DATA slot
`+0x180` points to `8400fb18`, a native `return 1` no-op. It is **not** the
effective host-init release. INODE selector2 is the active release that logs
"NPU got init done in host". Separately, the Linux recovery boolean
`dev->recovery.hw_init_done=true` is set later in `mt7996_register_device`,
after RRO start, device registration, and init-work queueing; it is not a wire
message or a firmware readiness attestation.

## Verification

From canonical WSL checkout:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.local/npu-reset/python-lib \
  python3 tests/npu/test_mt7996_bootstrap_sequence.py
```

- 164 compiled-host cases: four successes, 152 error cutoffs, four absent-provider
  cases and four successful `0x457` descriptor-fallback cases.
- 149 bounded original-RV32 cases: 48 port/PCIe/TXDONE selector cases, four
  API2/version controls, seven token bounds, nine complex-entry stops, 32
  unsupported/ignored selectors, three stores, two record-initialization cases,
  four TX-packet wait boundaries, 32 GET4 base cases and eight INODE length cases.
- Three mutation controls rejected: lost HIF offset, wrong final INODE selector,
  ignored version-query error. Original host C SHA is hard-pinned; Ghidra, CODE
  and DATA identities are checked, not inferred from filenames.

| Artifact | SHA256 |
|---|---|
| Pinned host `mt7996/npu.c` | `d70dc1953576c134c8732edb92efd2a8d18e5dbba35435cb230f98ce448b6b5e` |
| Current offload header | `9359009a4161de572e7f44b41b172860bb6414b56332f16ed6ff8df972126364` |
| Original RV32 CODE | `e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643` |
| Original DATA | `61a75afb052feed2ceb2f3023e16f50317c05c78f9c8e564bf01924ce39c7ec1` |
| Pinned Ghidra export | `1536a9972838ca7c02da77629e784b392af919c5d25368478aff4d0c2422e2ca` |
| New test | `93a8faaab3de05599bd262fafd32564216cdb3ee438abf19ab006c8c057a94dd` |
| Evidence JSON | `7135e05b76218e8f0cd815e9bd3cc13434129ddedb1afe15279f250c038e3739` |

No prepared mt76 build, kernel execution, native full attachment, all-helper
completion, allocator exhaustion closure, concurrent consumer schedule, physical
DMA/cache containment, Linux recovery/removal, or actual-client parity is claimed.
The parent-owned ledger was intentionally left unchanged.
