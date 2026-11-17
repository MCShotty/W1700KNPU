# Current MT7996 target: FW-TXP DMA arguments

The FW-TXP correction is no longer compile-pending. On Linux 6.18.52 the
current AArch64 MT7996 module passes the default correct-argument contract:
90 cases, four negative controls, zero incorrect DMA arguments. In a concrete
one-buffer case the unmap call received address `0x123400000`, length 64,
direction `DMA_TO_DEVICE`, attributes 0. No module was loaded and kernel DMA
effects are modeled; this is not a physical drain or firmware boot result.

## What was built

Source parent `231914d`, source-lock SHA256 `cc128c3b2dc196c41c3b7db858dd22c3a1c7eb76ed9ca01efe11f060122c9d2d`.
A new boot-bound plan used the verified C-backed scratch, 400 MiB/no swap,
fresh host/guest budgets and the existing writer lock. The old queue and
interrupted replay were not restarted. A private build namespace reconstructed
18 patch outputs with zero fuzz and checked 330 mt76 source paths.

The compile log shows `CC mt7996/mac.o` and the link log shows
`LD mt7996/mt7996e.ko`. All four resulting module artifacts were checked.
Only the radio module changed (SHA256
`cb1d9f0f4e0f1187f17b5a722c007e1d5b14c0ec6e2e4669e200e8f52d98429b`);
the provider, mt76 core and connac library remained byte-identical. This was an
incremental target build, not a clean world build. The missing-description
modpost warnings matched the previous build. Before/after manifests for
102,685 kernel entries, 516 mt76 entries and 1,036 prior-cache entries matched.

Current producer: `b5af9591d0f6116547a08749fe733a98ac4d89b6088f8d1465950b052e4f69bd`
(420 inputs). The pre-fix producer remains `92c75156`, verified with its 417
inputs and three preserved source aliases. It is not used as fixed acceptance.

## Compiled checks

| Independent contract on the same producer | Cases | Negative controls |
| --- | ---: | ---: |
| FW and MAC TXP unmap arguments | 90 | 4 |
| RXWI retirement | 10 | 3 |
| Cold MCU shutdown | 31 | 3 |
| Consumer cleanup | 35 | 6 |
| RX/TX cleanup | 64 | 7 |
| Token and SKB lifetime | 62 | 9 |
| Kernel IDR traversal and destruction | 56 | 7 |
| MT7996 TX status and kernel IDR | 64 | 9 |

The first five final receipts are from helpers-b; the last three are from
helpers-d. Helpers-b as a whole **failed**: two token harnesses refused the new
binary before running their cases. The compiler had moved the cache pointer
from `x19` to `x22`. Both builds still load and clear `cache->skb` at offset
24 and then pass that cache back to mt76. The revised checker follows the
second argument across direct branches, requires the loaded SKB at **both**
completion calls, and binds the negative control to the actual null store.
Discarded loads, wrong bases/widths, partial overwrites and paths that skip
the clear are not accepted. The original and intermediate sources are retained
for their historical receipts; neither a repeated suite nor a classifier
judgment is counted as extra executed cases.

All 15 wider regression suites passed, including the 167-method tooling group,
1,090 caller cases and selected reset/ownership checks. The final independent
host test run passed 214 methods without skips (overlaps the tooling group).
The final status replay used 23 linked kernel IDR/radix functions. Slab/RCU
scheduling, kernel DMA effects, actual interrupts and clients were not exercised.

## Resume

Proceed to an independent raw RV32 replay from reset. The 330 runtime input
hashes still match the qualified raw pair/observer cohort; the two additional
October full-run inputs are its old launcher and publication receipt. That is
input-equivalence evidence, **not** a full verdict. Require all three profiles,
19,261 comparisons and the terminal result in one new invocation; never import
October's partial profile. Full consumer/devres/context/RRO lifetime, physical
containment/drain, BA reuse/hot lifecycle and current-image/board/client
acceptance remain open. Ethernet stayed disconnected.

See [EVIDENCE.json](EVIDENCE.json) for exact artifact/phase hashes. Detailed
results remain under the canonical ignored `.local/npu-txp-fresh-20261118/`
and on the registered scratch volume in `fw-txp-20261118-*`.
