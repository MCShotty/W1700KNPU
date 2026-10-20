# Original Memory Routine Execution

2026-10-20. The maintained harness executes original `0x840103aa` from entry
through its actual return for4992 finite cases, on synthetic caller-owned,
nonwrapping buffers. This is new whole-routine emulation evidence, not static
computed-entry permission, a whole-stack proof, a cold constructor or hardware.
The strict static memory/ECALL contracts remain denied.

## Scope And Checks

The168-byte original/current carrier contains Ghidra's106 recovered bytes
plus the62-byte intervening region. Capstone decodes55 instructions, including
15 descending byte stores and their return in that region. Each recovered
Ghidra range/instruction, the full original/current carrier and selected pair
manifest identity/base are checked. The ranges are not silently concatenated
into a purported Ghidra function or approved static CFG.

All16 destination alignment residues, lengths0..65 plus79/80/95/96/127/128/
255/256/511/512/1023/1024, and values0/0x5a/0x100/0x123456ff are covered.
The independent scalar model checks exact write sites, order, address, width
and value, including alignment bytes, bulk words and tails. The guest must
return the original destination, match all32 GPRs/PC/MSTATUS and perform no
data reads. Whole protected CODE, sentinel and data bytes match; only the
owned destination may change. Observations precede any host reset/restoration.

Four separately modified, synthetic guest images must be rejected: omitted
byte store, shifted store outside the owned interval, callee-saved S0 clobber
and wrong return register. They are not original-case coverage and do not
modify the paired/original CODE files.144-case smoke and4992-case maintained
runs both reject all four. The1M-us/50000-instruction guest bounds are distinct
from and do not change original cold-caller3M/60M-us limits.

Earlier private144/4928 runs remain. Their union is4940 unique cases, all
with exactly retained observations in the maintained4992 set;52 cases are
additional. Do not add overlapping executions or negative controls to the
original unique-case count. All280 unique units / 298 executions pass without
skips, retaining the prior selection plus five harness/model contracts.

## Boundaries

This finite set does not prove all32-bit inputs or every computed target,
link-register contract, return path or physical-memory behavior. Caller-owned
accessible buffers, no pointer wrap and no asynchronous exception are explicit
fixture assumptions, not validated device ownership. No callback, fake return
or branch checkpoint replaces the routine's actual instructions.

The selected static corpus remains62 conditional local passes/two denied
contracts. The computed sites103e0/10440, general code-entry proof, ECALL
handler/ABI and error child170fa remain open. Global graph, whole-chain/IRQ/
per-hart/physical bounds, current cold/fault/full setup/latest image/hot/checked
IRQ/RRO/lifecycle/physical/radio/client gates are unchanged. No router contact,
flash, firmware/source-lock/pair/image modification or subagent occurred.

## Evidence

Metadata-only `MEMSET_EXECUTION.json` hashes
`7158e576d0b3c7dd42c7b0ccbfdf4f7d7850de079bab3e161da919cd8fb4c319`.
Private scope `80dc568f6779e47cca77820142719a017d54f802c4bca0c962fe2473f459fb8c`
verifies169 paths and the exact preserved earlier harness source. The full
maintained receipt hashes
`f6561f4ab45f49a9e90603f651bca367a23785db55be3a7b6b08308af94bf546`;
the280-unit receipt is `bf2c14ac`. Raw original code and guest records remain
private. The maintained tool is `tests/npu/test_original_memset_native.py`.

Jev's observation-boundary/mutant-scope judgments are0.93/0.97; evidence kind
is finite-emulation1.0/confidence1.0. They do not replace the execution checks.
Existing ECALL uncertainty is not erased.

Next: an instruction-bound computed-entry proof. Isolated local Z3-solver
5.3.1.0 is installed in `.local/npu-smt-runtime-20261020`, with58 files bound
by preparatory receipt80ae16f6. Its bitvector sanity check is not an NPU proof
and the existing native runtime was not modified. Normal INODE2522/326 still
passes; both actual v2 cold callers/four frozen old-pair fault jobs remain live.
