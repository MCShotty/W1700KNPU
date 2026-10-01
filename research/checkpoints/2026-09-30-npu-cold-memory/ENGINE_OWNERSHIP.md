# NPU Engine Ownership And Reset Evidence

Reviewed 2026-09-30. This is a source-bound inventory and a checklist for a
future physical investigation, **not a reset procedure or authorization to run
one**. Complete stock-NPU ownership, containment, teardown and rearm remain open.
The selected next correction is pre-copy reserved-memory planning; it adds no
reset, drain, reclaim or restart authority.

## Provenance And Scope

The two archived source files below were read directly into memory. The complete
history archive and both extracted byte streams matched their retained SHA256
values. No archived source was applied to the current tree.

| Evidence | SHA256 |
| --- | --- |
| Reassembled `research/history-20260905.tar.gz` byte stream | `c4726e4acdde800a4d6a167870e4a03af67c25e130220008a819e271459ac0b7` |
| Archived `clk-en7523.c`, 32,413 bytes | `a4fc60fd9cbde304bf4e925c7de8c08becae8aa37837f76abfeed5d6d07e98ca` |
| Archived `airoha,en7581-reset.h`, 2,102 bytes | `1ca2aec7c4fd3cd05466c8a38bab96ddd5c930abb41988386a58536d60cd3f2a` |
| `../2026-09-23-npu-reset-control/reset-control.json` | `c627c45569b2e142b635f68a6ced59460749232f184bc99fe5215bf672a60c7d` |
| `../2026-09-23-npu-reset-control/reset-native.json` | `d0fe65272e356c397324ddd763416e5c5c80166f3ec13676503acc03e23779d9` |
| `../2026-09-30-npu-loader/stock-reset-gdma.txt` | `c084e1d9438dfea0018c066f854e6adb32d36322b6494c4e66885973633c0b0b` |
| Stock kernel input identified by that export | `a51e6d0a6deee620a5f715c9469f193906cdf3fcea28b97ce01cf88383aa704e` |
| `../2026-09-06-npu-copy/known-gdma-owners.json` | `8a40631429b228d9e2d6137b5cb121fdc73ddcd6419540f295d84022f71651a3` |
| RV32 code input identified by that owner inventory | `e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643` |

Exact archive members, indexed by `research/history-manifest.json`:

- `workspace/work/analysis/patch85-current-cpufreq-audit-20260905/current/drivers/clk/clk-en7523.c`
- `workspace/work/analysis/w1700k-npu-hard-reset-authority-daybreak-20260904/evidence/current-linux/airoha,en7581-reset.h`

Their hashes match the **Linux 6.18.44 reset-control prerequisite** receipt.
This review does **not** independently reverify the complete Linux 6.18.52 reset
map. The integrated kernel patch corrects reset callback value/error handling;
that correction and its modeled tests do not establish physical domain coverage.

## Named Reset Boundaries

The archived driver defines bank offsets at lines 47-48 and 451-455, and the
EN7581 translation table at lines 504-565. Binding IDs below come from the
hash-matched header, not from assuming that a logical ID equals a register bit.

| Named line | Logical ID | Register offset / bit | Evidence limit |
| --- | ---: | --- | --- |
| NPU | 8 | `0x830 / 9` | Does not establish containment of any independent DMA engine |
| WDMA | 18 | `0x830 / 19` | Physical ownership and relation to active Wi-Fi paths unresolved |
| WOE0 / WOE1 | 19 / 20 | `0x830 / 20,21` | Shared consumers and reset dependencies unresolved |
| HSDMA / TDMA | 21 / 22 | `0x830 / 22,24` | Do not identify an engine from a similar address or name alone |
| FE_PDMA / FE_QDMA | 30 / 31 | `0x834 / 1,2` | FE/PPE and network ownership must be reviewed separately |
| GDMA | 38 | `0x834 / 14` | Mapping alone does not prove copy-engine reset/drain semantics |
| GDMP / FE | 43 / 44 | `0x834 / 20,21` | Do not substitute either for a complete shared-owner contract |

This is a relevant-line inventory, not a proposed set of lines to assert.

## Engine And Owner Matrix

All stock line references in this section refer to the retained
`../2026-09-30-npu-loader/stock-reset-gdma.txt`.

| Owner or engine | Source-bound observation | Missing witness |
| --- | --- | --- |
| NPU harts 0-7 | `boot_npu_all_cores`, lines 10200-10293, writes eight boot addresses, mask `+0x306004`, trigger `+0x306000`, then delays. `host_set_npu_core_on_off`, lines 10809-10889, changes mask/trigger with delays | Halt/reset coverage, outstanding bus-work disposition, reset/SRAM access semantics and release ordering |
| Standalone copy GDMA | `SET_GDMA_CONFIG`, lines 9415-9465, uses channel stride 16; CT0 is `+8`. `WAIT_GDMA_DONE`, lines 9594-9624, polls CT0 bit 1 clear. `IS_GDMA_DONE`, lines 9728-9756, reads channel bits at `+0x204`; `CLEAR_GDMA_DONE`, lines 9391-9414, writes them | Actual start/clear behavior, completion visibility, all channels/owners, address aliases and cache semantics |
| Known RV32 copy callers | `known-gdma-owners.json` and its companion report identify hart 2/channel 1 and hart 3/channels 0,3; canonical `firmware/npu/gdma.c` guards those pairs and requires DONE plus ENABLE clear | Inventory covers known direct/tail calls in 427 discovered functions only; other functions, indirect callers, host access and independent masters are not excluded |
| GDMA provider lifetime | `ecnt_gdma_drv_probe`, lines 9504-9593, allocates/maps; `ecnt_gdma_drv_remove`, lines 9490-9503, returns zero | No shutdown or physical drain is supplied by these functions |
| FE/PPE network paths | `get_gdma_special_fp` / `set_gdma_special_fp`, lines 9880-10011, use a different base/global from the copy GDMA mapping, at offsets `+0x55c`, `+0x155c`, `+0x255c` | Do not collapse these network GDMA names into the copy-engine domain; ingress, queues, PPE and other consumers need separate ownership proof |
| Wi-Fi endpoint DMA, rings and tokens | `../2026-09-05-npu-reset/REPORT.md`, "Later Reset Steps", distinguishes PCI BAR PDMA/reset operations from SoC NPU boot/reset; later L1 return checks retain this scope limit | Whole-path admission closure and device drain before token/ring reclamation, including full reset and removal |
| Control mailbox, IRQ and watchdog work | Stock watchdog ISR, lines 10724-10808, acknowledges/inspects status and dumps state. Integrated provider work/IRQ ordering handles selected CPU lifetime. `firmware/npu/LINUX_CONTROL_CONTRACT.md` states that close joins only this executor's CPU calls | Pending coherent mailbox retirement, other provider callers, IRQ/NAPI/work closure and lifetime after ambiguous publication failures |
| Tunnel/bridge and shared pools | `../2026-09-05-npu-workers/REPORT.md` and `../2026-09-06-npu-copy/REPORT.md` retain hart-7 and shared-engine limits | Complete tunnel producer/consumer graph, queue/pool ownership and independent engine completion |

STOP/GET, software PARKED, IRQ masking, reset-bit readback and fixed delays are
not physical drain witnesses. The standalone-copy DONE and CT0 observations are
different signals; even their conjunction needs validated hardware semantics.
The selected stock export contains 40 functions, not complete owner coverage.

## Future Physical Handoff Checklist

These are required deliverables and observations, not instructions to execute a
reset now. An evidence-backed ownership/reset design must precede reset stress.

1. **Bind the target and software.** Record the actual board/layout and device
   identity, running FIT/kernel/provider/mt76/firmware hashes, DT resources and
   boot instance. Independently reconstruct the active reset map and consumer
   bindings; explicitly resolve the older 6.18.44 map versus the active source.
2. **Close the owner graph.** For every device-visible region, record its exact
   extent/aliases, alloc/free owner, all CPU/hart/IRQ and DMA producers/consumers,
   channel/queue, reset domain and shared users. Unknown owners remain blockers.
   Account separately for firmware/SRAM, mailbox buffers, rings, tokens, packet
   pools, FE/PPE, tunnel and Wi-Fi endpoint DMA.
3. **Specify containment before testing it.** Supply authoritative or otherwise
   corroborated evidence for each proposed domain's coverage, outstanding bus
   transaction behavior, shared effects, SRAM accessibility, and ordering/cache
   requirements. Define completion and failure predicates without inferring
   them from names, software acknowledgements or elapsed delays.
4. **Define observable physical witnesses.** Identify the actual registers,
   completion records or bus/device traces that can establish closed admission,
   retired transactions and destination visibility for each owner. State their
   documented semantics and acquisition limits. A status bit is sufficient only
   if its guarantee covers the outstanding work and memory visibility at issue.
5. **Design retention and failure handling.** Specify which allocations stay
   pinned after timeout, failed writes with possible side effects, partial boot,
   probe unwind, provider removal and late completion. Define boot/generation
   correlation and the conditions for reclaim/rearm; unresolved status must not
   silently authorize cleanup or a fresh session.
6. **Prepare an authorized, recoverable validation plan.** Verify current
   protected backup/rollback availability, serial observation and recovery
   access; preserve bootloader, factory/calibration and user configuration.
   Obtain approval for the specific physical actions only after their effects,
   safety boundaries and evidence capture are understood. Do not use reset
   stress or trial-and-error shared-domain toggling to discover ownership.
7. **Capture the designed lifecycle evidence.** Once separately authorized,
   observe the designed cold-start and teardown boundaries, every relevant
   engine's retirement and memory visibility, identity/publication ordering,
   and late-completion rejection. Exercise designed failure/partial-start cases
   without releasing potentially owned memory. Keep modeled, instruction-level,
   physical and actual-client acceptance results distinct.

The software correction can advance independently: validate and retain a
reserved-memory plan before either firmware copy, then consume that snapshot
during setup. It must preserve applicable non-MT7996 profiles. It does not fill
any missing physical witness above. Likewise, propagating a post-publication
register error by returning from probe is not a safe fix until ownership-aware
retention prevents devres from reclaiming still-device-owned resources.

Only this document was created by the ownership review. No reset, router access,
restricted INODE/provider-framing or DESC5-8 operation, firmware execution,
stress test, or publication was performed. The prior software test receipts were
read as evidence, not rerun. The checkpoint report records the pre-copy correction and its
new tests separately.
