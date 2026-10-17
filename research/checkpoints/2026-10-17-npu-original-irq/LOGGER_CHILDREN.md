# Logger Child Local-SP Extension

Later follow-up: [FORMATTER.md](FORMATTER.md) inventories the formatter and
qualifies20 individual callee local-SP depths after conservative arithmetic
clobber support. The formatter and one callee still have unqualified computed
flow;no whole logger bound follows. The earlier checkpoint below is retained
with its original receipts/source cohort.

The current checker admits `C.LUI`, `NEG` and `SNEZ` only as checked non-SP
destination clobbers to unknown. Self-relative SP/control/byte/merge guards stay
unchanged. Six new LLVM controls accept the three non-SP forms and reject
LUI/NEG/SNEZ writes to SP;all19 previous controls remain. The standard distinguishes
C.LUI from the SP-adjusting encoding;the checker does not merge their roles.
[RISC-V C specification](https://docs.riscv.org/reference/isa/v20260120/unpriv/c-st-ext.html).

Fresh25 local controls and199 focused units/no skips pass,including41 tiny
synthetic guests. Both assembly fixtures/hashes are checked. Scope3f22a3bd
verifies570 combined paths. The previous193-unit/394-run cohort is readonly-
preserved in140 files/3039180 bytes,30604441;this is not private replay
qualification. Initial C.LUI triage and a later explicit SNEZ denial retain
their original source/results. No unsupported instruction is treated as zero cost.

Read-only/noanalysis Ghidra exports preserve the exact original/paired bytes.
The four logger children now have local-SP analyses under ordinary-ABI restored-SP
assumptions:

| Entry | Body Bytes | Local SP | Remaining Transfer |
| --- | --- | --- | --- |
| 0x840067b8 | 156 | 16 | Calls0x84004212 |
| 0x840106b2 | 14 | 0 | Tails0x84010684 |
| 0x84004218 | 24 | 0 | None in this body |
| 0x84006854 | 64 | 16 | Calls0x84004212 |
| 0x84010684 | 46 | 128 | Calls0x840107ca,unreviewed |

A fresh current-helper audit also checks the earlier three original bodies at
local0/16/16,including the6-byte hart getter0x84004212. The original PLIC/logger
bodies still analyze at0/0/64. These are individual local analyses,not completed
callee behavior or a full logger/IRQ bound. In particular,80 bytes is not an
established full logger cost:the formatting path has a128-byte wrapper and a
further unreviewed child. No global graph is extended or reranked.

The fresh394 original-code diagnostics have records exactly equal to the
preserved earlier394:384 normal returns,eight explicitly disabled-logger returns,
two prefixes stopped before the first logger child. All32 GPR/PC/MSTATUS/trace/
protected-memory comparisons still occur before restoration. No newly inspected
logger child,other hart,UART loop or full logger path executes. These are not
fresh cold callers or physical IRQ/client acceptance.

| Current Receipt | SHA256 |
| --- | --- |
| `.local/npu-original-body-stack/logger-local-q2/result.json` | `f4ed16ca0cc699e4e08949bda5ccd2e965ee05658e9794c9a076b1fa7bb0c948` |
| `.local/npu-original-body-stack/formatter-local-q1/result.json` | `07af7f697c5e23082734d330cb13992bb0f41cd2a0033b90eb077398e3d55866` |
| `.local/npu-original-body-stack/earlier-originals-q1/result.json` | `ad0f83346bf23830f980e55139662c8d6e6632f1272ebc15523e8294929d9bf6` |
| `.local/npu-original-body-stack/irq-local-q3/result.json` | `dc1b5c257684c0ef94951fb3e66bfd184cfaf833382f3a6b364e3e9deb8cb7a5` |
| `.local/npu-original-irq-20261017/original-probes-q2/result.json` | `100f029a2456c229656b1d94181941a87070b47203ad70a9ed61c98b919d714f` |
| `.local/npu-original-irq-20261017/host-scope-q2/result.json` | `094dd85513de6b34fba13120501992181971552533b3f97502ae604f24f27bb8` |
| `.local/npu-original-irq-20261017/local-contracts-q3/result.json` | `8d35c542ac5841cb164e5f22240e0a0888fc1f076d71bd2d0a8eb0799206317c` |
| `.local/npu-original-irq-20261017/children-scope-q1.json` | `3f22a3bde1fd59e43af1602b56ab5a8584943f229670e77c37aab4679d532366` |

Metadata-only LOGGER_CHILDREN.json hashes33477f2b. Earlier ORIGINAL_IRQ.json
stays unchanged. Jev1.13 q2 primitive/diagnostic/scope support is0.72/0.77/0.55,
confidence0.58/0.66/0.33. Cost wording is not-established0.85/confidence0.77;
retain that uncertainty,not a model approval. Direct analyses have explicit ABI,
alias/escape/register-save/termination/physical limitations;no resampling occurred.

Current source-lockd6b6e2da,both978f9ddd/a22300ea images and the older300/718/
six-internal/56-unknown/9696 graph are unchanged. Native producing inputs/budgets
stay frozen;both callers/full36 matrices/HIF2 bitmap/new24-INODE/broader/current-
source/full setup/hot/RRO/IRQ/lifecycle/physical/boot/client gates stay distinct.
No firmware implementation,module/image build,hardware,restart or subagents.
