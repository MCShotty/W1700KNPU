# Per-Queue Shared IRQ Status

## Implemented Scope

The current provider getter rejects queue IDs outside0/1 before register access
and intersects successful shared-status reads with `NPU_IRQ_RX_MASK(q)`. Both
per-queue callers acknowledge that returned value. Previously either queue could
acknowledge the whole shared word,including other/unrelated pending bits. Read
errors still return0. IRQ ABI,scheduling,mask/enable and owner paths are unchanged.
The canonical kernel patch/source-lock include this change.

This is not a checked IRQ contract. Zero status cannot distinguish a read error.
Acknowledgement/mask/enable errors are still lost:148 modeled handler schedules
after errors,5624 silent bulk errors,12 lost initial/eight lost hot enables.
Completed setup/session/lifetime gates,partial effects/readback,atomic rearm,
quarantine,concurrency,drain/removal/reset and physical routing remain open.
No sleeping session mutex belongs in hard IRQ/RCU contexts;possibly active
resources cannot be freed without retirement evidence.

## Fresh Checks

| Receipt | SHA256 | Scope |
| --- | --- | --- |
| `.local/npu-irq-queue-status/queue-filter-q1/result.json` | `5cf48d46185848d736abbff88ecd94bed05326cfbfedeafe72eb357d1a53dd69` | 110 valid/10 invalid queue cases;five compiled mutants and preserved old getter rejected |
| `.local/npu-irq-ack-mask-contract/queue-filter-q1/result.json` | `22f9a0555df00c22503a7ec80d1bea7b3023ebc2726e9512e7e033b521cf8548` | 150 handler/5625 bulk/three null cases;other pending bits preserved under modeled effects |
| `.local/npu-irq-status-msan/queue-filter-q1/result.json` | `10674b7dc29ee763f9b50021acef454a9412aeec9e776b2cbd7322398e0d5ba2` | Actual getter success/no-output error clean under host MSan |
| `.local/npu-final-irq-contract/queue-filter-q1/result.json` | `98f7748c3acf30895fe9444cb20670f0dcc303baf175d5b23b4c13cfb6e817fb` | 21 initialization/31 poll cases,five rejected RCU mutants;error gaps retained |
| `.local/npu-provider-session-20261010/irq-queue-filter-host-q1/result.json` | `3ed8acf8d2ed78c6cf055bf4c8b3dcb241b8d4b996c96bf05b9125cb892b9baf` | 609 modeled provider cases/nine mutants;no native run |
| `.local/npu-irq-channel-20261017/provider-object-q1/result.json` | `fe62d3b151072bd049e925912985f4434929bafb6b3352238b0d956513d0a7cc` | Isolated AArch64 object;getter48/cold-command544-byte static frames |
| `.local/npu-irq-channel-20261017/export-q1/result.json` | `969bb44be2d85482be30ac102923c6d58b045d15c653468463607a536b597f28` | Zero-fuzz/five exact kernel files;70 OpenWrt/five LuCI files and22 component sources checked |
| `.local/npu-irq-channel-20261017/host-scope-q1/result.json` | `b89fdc7efeb09d138e883063b2833bfeac92e219a78e8a8d5dd53fadce8bec84` | Fresh174 units/no skips/41 tiny synthetic RV32 guests,not original firmware |
| `.local/npu-irq-channel-20261017/scope-q2.json` | `523c8a2ee0175a4624cbae8201ba19104eb6430205d640ee1dc0a544a2b87e82` | 359 current hashes/separate214 unique broader units in232 executions/no skips |

The two unit groups overlap;do not add them as distinct tests. The getter fixture
independently expects bit16/17,tests simultaneous/unrelated pending bits,read
errors with/without output and invalid signed IDs without register access.
Address/undefined/leak sanitizers are enabled. This is modeled register behavior,
not physical lost-interrupt evidence. MSan does not repeat the older uninitialized
legacy reproduction here. The isolated getter frame increased32->48 bytes;
individual frames are not whole IRQ/call-chain/physical stack bounds.

Pre-edit2313 files/520126273 bytes are readonly-preserved in
`irq-queue-filter-before-v1`,receipt
`f7d55aa725251c69fda480de2f27a5ce9129b0bbd41ef27840447dff2b0dce1d`.
That is preservation,not private replay qualification. Scopeq1 stopped before
execution because a copied manifest expected210/228. Four already-added mt76
export tests explain214/232;none were removed. Failed source/count receipt
20752c2f is retained. Freshq2 verifies the recorded identifiers and runs all232.

## Stock Artifact Cross-Check

REA imported immutable `stock_mtk_pci.ko`,SHA256
`c71b2073eeb2498c05c5e42bb5ceaf3df664cff42bf0b0740eb6152458e0857b`,
with Ghidra12.1.2. The bridge is verified against12.1.4;retain that limitation.
Twenty complete local Evidence records are exported in bundle
`d141baec902d16fe1c767007e23cb8c9617455069f5c42351535f3d983b9b318`
and snapshot`c541add7fae8a0da49c1d4eb76b02b3187c8144665818a08cf289a101da74fe0`.
The temporary target is closed. Only metadata is committed,not the module/full
decompilation/device data. Full Evidence IDs are in `IRQ_QUEUE_STATUS.json`.

- `FUN_00101630` reads shared status,intersects it with descriptor+0x34 at
  imported0x10168c,and supplies that result to the second MMIO callback.
  Selected original unrelocated AND/callback-setup instruction bytes match.
- `FUN_00101334` updates descriptor masks/HIF shadows under irqsave/spinlock;
  `FUN_00101040` merges disabled masks back into enabled shadows. These are
  static paths,not completed initialization,concurrency or hardware proof.
- DATA reference0x10e248 maps to file57992 in `.eh_frame`,not an ops member.
  A separate `.rela.data` relocation at0x170 lies in `pci_dma_ops`,offset0xb8,
  and points at text+0x1610. Imported slot0x10f8b8 contains0x101630. A DATA
  reference alone must not be promoted to callback registration.
- The MMIO read wrapper's inferred void pseudocode omits the result,but assembly
  contains `LDR W0,[X0]`/`DMB OSHLD`;the write has `DMB OSHST`/`STR W2,[X1]`.
  Original bytes corroborate them. Imperfect prototype/volatile inference is
  not evidence that no read occurs.

This is related filtering evidence,not independent physical bit16/17 mapping
proof. No stock module executed;ET_REL import addresses are not runtime addresses.

## Remaining Gates

Jev1.13 q1 selects not-established for queue wording0.57/confidence0.35 and stock
wording0.68/0.52. Scope is supported0.73/0.59,decompiler0.96/0.94,callback0.56/0.34;
remaining checked-error/lifetime category1.00/1.00. Raw probabilities remain
without resampling or model-approval claims. Direct checks govern their scope.

Current source-lock is
`d6b6e2daf745414e82579bc89308821c5ba392d805fe3a220cd184dacbef7f47`;
kernel patch`55e97086f843466c1ea674ba00b13a923e56babf3735597b2072e8e5ef559c0e`.
Both FITs978f9ddd/a22300ea/prepared kernel/modules are unchanged;neither image
contains this new change. No world/module relink,load,flash,IRQ/radio operation,
reset,reclaim or physical/client acceptance occurred.

Both callers/full36 tail matrices/HIF2 bitmap continue on frozen600055c sources
with original budgets/guards. They cannot qualify newer main. Full512/eight-
DESC10/all36-tail/new24-INODE/broader/current-source/full setup,hot TX/RX/RRO/
worker/lifecycle/DMA/cache,remaining original/indirect/per-hart stack,boot and
actual-client gates remain. Older stack metadata keeps its original40d29368
source-lock/receipt scope;do not promote it from passing current synthetic units.
