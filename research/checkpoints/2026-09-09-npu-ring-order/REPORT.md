# Native Command Ring Ordering

Started 2026-09-09; finalized 2026-09-10 (Asia/Riyadh).
Status: compiled, instruction-tested and formally modeled;
**unpromoted**. No image or router change.

Three native detours now place four ordering fences around command-ring
publication, consumption and slot return. Selected bad outcomes are excluded
under the tested ordinary coherent-memory assumptions. Cache/PMA/alias and
complete initialization/lifecycle contracts are not established by this work.

## Implementation

`tests/npu/command-ring-order-emulation.S` compiles to 44 text bytes at
`0x84054000`, with no data/BSS, inside its independent test reservation.

| Native Site | Adapter Work | Resume |
| --- | --- | --- |
| `0x8400c96c` | Producer acquire fence; original token/command stores; release fence | `0x8400c970` |
| `0x8400cc1e` | Consumer acquire fence; original stack halfword load | `0x8400cc22` |
| `0x8400cc4e` | Consumer release fence; original read-index store | `0x8400cc52` |

Each fence is `fence iorw, iorw`. The original ready/empty status stores remain
in place. Queue geometry, payload fields, indices and caller register effects
are preserved. No new allocation, lock, cache maintenance or drain witness is
introduced. RISC-V defines fence ordering using predecessor/successor access
classes; the execution environment determines which accesses are I/O. That
does not identify this target's memory attributes. [RISC-V memory ordering](https://docs.riscv.org/reference/isa/v20260120/unpriv/rv32.html)

The pinned decompiler has one direct call per step in these paths:

- Producer: core6_main `0x84000aca`, wrapper `0x8400e800`, worker
  `0x8400cd1a`, helper `0x8400c284` at call site `0x8400cd8e`.
- Consumer: core5_main `0x84000aa6`, wrapper `0x8400e7f8`, worker
  `0x8400cb0e` at call site `0x8400e7fc`.

The producer slice's scratch frame now uses hart6's stack region instead of
hart1's. These are explicit instruction slices, not complete worker-entry
executions. Direct-call evidence is not indirect-alias or reentry closure.

## Formal Checks

The runner executes sixteen actual native fence-mask variants and captures
their ring loads, stores and fence instructions. It retains the original
status-dependent branch and duplicate consumer status load when generating
litmus programs. Index/statistic/stack operations are projected out. The
native IORW fences are projected to their R/W ordering for these ordinary
memory accesses, not modeled as device I/O or cache operations.

Herd7 evaluates 96 cases: 64 bad-outcome queries and 32 successful-handoff
witnesses. A separate handwritten unfenced publication example calibrates
the generator. This uses the upstream RISC-V axiomatic model; the ISA's formal
appendix explains the models and their relationship to normative RVWMO.
[RISC-V formal models](https://docs.riscv.org/reference/isa/v20260120/unpriv/mm-formal.html),
[herdtools7](https://github.com/herd/herdtools7/tree/7.58)

| Property | Model Result |
| --- | --- |
| Ready observed with stale token or command | Allowed without producer release or consumer acquire; excluded with both |
| Old consumer reads next publication's payload | Allowed without consumer release; excluded with it |
| All four fences present | All four selected bad outcomes excluded |
| Successful publication and reuse | Admitted for every fence-mask combination |

Across the complete matrix, 24 bad-outcome queries are `Never`, 40 deliberately
insufficient-mask controls are `Sometimes`, and all 32 success queries are
`Sometimes`. These are permitted model behaviors, not observed physical faults.

Removing producer acquire alone does **not** reintroduce these bad outcomes:
the native status-dependent branch already orders its later stores in this
coherent-memory model. That fence is retained conservatively; its necessity
outside this projection is not claimed. Successful-handoff witnesses prevent
mistaking a model that disallows all work for a valid correction.

## Native Checks

- 384 isolated original/corrected pairs compare all 31 writable integer
  registers, MSTATUS/MIE, complete heap/SRAM/ring/stack regions and exact data
  reads/writes. Original effects match, including the consumer's register
  load. The three adapters execute two, one and one fences respectively.
- 8,194 producer/consumer pairs pass across original heap and relocated DRAM
  addresses. Full 2,048-slot capacity, wrap, blocked producer/resume, empty
  consumer, canaries and complete memory/write checks remain intact. The
  original write oracle translates three moved store PCs; the new receipt
  separately captures actual adapter PCs and fence counts.
- All 40 detours installed before reset retain all eight initial gates with
  the larger bridge definition and relocated ring present. None of the new
  adapters executes through those gates; bridge allocation and TXDONE ready
  remain absent there.
- The updated default, unfenced layout fixture also passes its full 8,194-pair
  regression, four original mutation controls, header/allocation checks and
  37-detour control. Old receipts are preserved, not overwritten.

Both new receipts replay byte-for-byte. Unicorn supplies instruction/register/
memory checks; herd7 supplies weak-memory analysis. Neither is physical cache,
interrupt, DMA or NPU-boot validation. The allocator implementation and host
source/overlays were not changed in this checkpoint.

## Provenance

| Artifact | SHA256 |
| --- | --- |
| `ring-order.json` | `65c3c21054e177c204a5a8063f9e6b311f33ea62fac1c2af1e701438e598df8e` |
| `layout-regression.json` | `260dad66b04e5a81ce3f5b4eeb5b5e8e02753230b6642b325172348f1322d4f3` |
| Ignored ordering ELF | `99515c31abf83b30e4b7d171f717a5536d6a5e4011e3c6107364ddc53c3e46b7` |
| Installed herd7 binary | `f398c4ba11ee87226e104efc77e64873cf775292e16b90e1e71015962969060b` |

Ubuntu package `herdtools7 7.58-1` was installed without upgrades or removals.
Its compiled library path did not supply the model files. The runner therefore
uses the matching sparse upstream checkout at commit
`1ca343e16a2038e406d1ac674e7e3a1b722b36c7`, explicitly selects `riscv.cat`, checks
the clean source tree and binds all 87 CAT files. The ordering receipt also
binds 86 current project inputs and every generated litmus input.

Reproduce from the canonical WSL checkout:

```sh
export PYTHONPATH=.local/npu-reset/python-lib:tests/npu
python3 tests/npu/test_command_ring_order.py --check
python3 tests/npu/test_command_ring_layout.py --check --output research/checkpoints/2026-09-09-npu-ring-order/layout-regression.json
```

## Remaining Work

- Establish the target's cache/PMA and address-alias contract before promoting
  the DRAM placement. No cache-flush operation was inferred from scalar addresses.
- Prove fresh initialization visibility, complete loader/backing reservations,
  index ownership, non-reentry and every pointer alias/consumer bound.
- Complete allocation profiles, downstream helpers, full worker/IRQ paths,
  physical containment/drains, recovery and Linux lifecycle integration.
  Performance and full NPU/host-adapter parity remain unverified.

The 44-byte adapter does not authorize admission or reclamation. All four
trackers and the NPU README are updated; physical, Wi-Fi and subagent work
remain deferred.
