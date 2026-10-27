# Selected Compiled TX Token And SKB Lifetime

## Qualified Scope

`tests/npu/test_tx_token_native.py` now executes retained AArch64 token teardown,
TXWI return and ordinary connac completion paths. Final replay-q5 passes 62 cases
and nine emulator-byte mutation controls, with 17 input bindings. This is selected
compiled-function evidence with explicit kernel models, not complete Linux
lifetime, physical DMA drain, or board/client acceptance.

The producer is pre-FW-high-DMA-fix module cohort `92c75156`, not a build of the
current source fix. All 417 producer inputs verify using three preserved old
source-lock, patch and mac.c aliases. Current lock `cc128c3b` and its FW-TXP fix
remain target-compile/execution pending. Private evidence:
`.local/npu-tx-token-native-20261027/`.

Final receipt SHA256:
`80f29771647a3a0db91e33c54970f3bebc2b0be3eb6faa2a2f22c7cb02921e18`.
Tested source SHA256:
`25fb60a3f179ba02cc97f111a9ac8ba57bc228dd740ed5f3d19d52b016bddf40`.

## Executed Paths

There are 54 token cases and eight ordinary completion-callback cases. Empty,
single and sparse fixtures include IDs 0, 3, 7, 8191, 8192 and 16383. SKB presence,
FW/MAC layouts and PHY presence vary. Driver flags are the actual MT7996 set,
`0x1b1`, including TXWI_NO_FREE and NAPI_LIFETIME.

Seven compiled bodies actually enter; eight are mapped. The selected
`mt76_put_txwi.part.0` copy does not enter because the exported body contains its
own inlined cache operations. Aggregate entry counts across distinct cases:

- `mt7996_tx_token_put`: 54; `mt7996_txwi_free`: 102.
- `mt76_put_txwi`: 102; `__mt76_tx_complete_skb`: 68.
- `mt76_tx_status_unlock`: six.
- `mt76_connac_tx_complete_skb`: eight; `mt76_connac_txp_skb_unmap`: 54.

The actual loop calls a modeled sparse IDR iterator, executes compiled release,
decrements the token count, unlocks, reaches modeled IDR destruction and resets
management pending counters only for present PHYs. Emulated native stores maintain
both directions of the circular TXWI cache. Each release is checked before the
next IDR query, not only at final token zero.

Release must unmap expected arguments, complete or mark the SKB pending, clear
`t->skb`, then return the TXWI. The ordinary connac callback executes no-TXWI
free, null-SKB and status-completion branches. PHY selection uses the original
selector and checks that native code clears it. FW fixtures use low DMA addresses;
MAC fixtures include high bits. This does not qualify the pending FW decoder fix.

## Tokens Are Not Every SKB

Pending and ready cases each use three nonempty tokens. In the pending case,
compiled code sets DMA_DONE, records jiffies, clears TXWI SKB pointers, returns
the TXWIs and leaves three SKBs awaiting TX status. No modeled mac80211 completion
occurs. In the ready case, preexisting TXS_DONE lets the compiled status-list path
reach three modeled mac80211 completions.

Thus zero tokens/cached TXWIs do not prove every SKB is finished. These fixtures
deliberately do not populate the packet-status IDR and do not establish its
complete ownership, later TXS/flush behavior or absence of leaks. IDR get-next/
destroy, mac80211 status/free, DMA-unmap effects, bottom-half enable and memset
are modeled. Station, non-AQL and power-save branches, concurrency, real kernel
IDR internals and physical drain remain unexecuted. Emulated lock/list instructions
are not a Linux SMP or hardware drain witness.

## Controls And Preserved Attempts

Nine controls omit token release, count decrement, IDR destruction, SKB completion,
cache insertion, DMA unmap, management reset, SKB clearing and ordinary SKB free.
Each must fail its intended assertion. Only emulated instruction bytes change;
retained modules do not.

Replay-q2 failed its fixture's PHY-owner assertion: it read the selector after
native code cleared it. Log and consumed source are preserved. The correction
retains the original selector and asserts clearing. Replay-q3's earlier 50-case
zero-driver-flags fixture is retained, not current acceptance. Replay-q4 uses
actual flags/62 cases. Replay-q5 adds per-token ordering checks and is final.
Repeated 62-case runs are not 124 distinct cases. Every consumed version remains.

The bounded read-only service peaked at 72.7 MiB, with a 192 MiB cap, no swap,
Nice 19, fresh Windows/Linux RAM/backing-storage margins and a 120-second oneshot
activation deadline. A C-backed output write control returned EROFS. There was
no compiler, C-output write, load or target contact. Frozen cohorts verify before
and after execution.

## Original Native Recipe

Original full-q16 invocation `20c8f1ab62d74236bf977c134d09b059` remains live with
the original guard/wrapper/driver identities and advancing CPU. Profile 0 now has
final artifacts. Independent read-only verification checks 6,421 positive RPCs/
journal comparisons, 2,179 extent comparisons, four complete-memory comparisons,
the final transcript hash, and retained broker/journal/prefix/summary hashes.
The summary still has modeled MCU results and no hardware acceptance.

Audit-q6 captures profile 1's prefix at 173 positive RPCs/33 publications, not a
completed profile. Profile 0 alone is not the complete three-profile/19,261-RPC
result. Original limits, cap, reserve and writer lock remain unchanged. No replay
was restarted or assembled from older subsets.

## Continue

Existing Windows queue PID 17788 remains live and waiting. Plan `e67d5198` still
verifies 454 target inputs; all 332 native inputs/read-only retained versions
verify. This new test and tracking prefixes are outside both frozen sets. The
queue was not edited to add this suite. No target phase has started. The current
source fix's target acceptance remains pending.

Follow that queue; do not start a duplicate or change bound inputs. After fresh
module/regression qualification, rerun this suite with the new producer/matching
source, without the old mac.c alias. Continue nonempty packet-status IDR/SKB,
station, consumer/devres/context lifetime, physical containment/drain, reuse/hot
and image/board/client acceptance. Earlier contents of all six tracking documents
are byte-preserved. Ethernet stays disconnected. No module load, image, flash,
Wi-Fi change, shutdown, compaction or subagent occurred. Full NPU goal stays active.
