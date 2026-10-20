# Original Guarded Entries

Follow-up: [child frontier](CHILD_FRONTIER.md) rechecks64 selected original
bodies,qualifies62 local bodies and retains two denied contracts.

2026-10-20. The explicit relative safe-edge-set profile now qualifies both
original local bodies, with frames496 and192 bytes under the existing entry,
ordinary-ABI and immutable-snapshot assumptions. The strict default still
denies the formatter. Neither result is a whole-chain/IRQ/per-hart/physical
stack bound, current global graph qualification or complete original execution.

## Additional Proof

The formatter has a second unsigned guard entering the AUIPC prefix and two
entries before the primary guard. The new profile does not waive those edges:

- Conservative whole-body constants start with every entry GPR unknown except
  zero. Calls clobber caller-saved values; conflicting joins become unknown.
  Every included guard must actually have bound90, not merely a nearby `li`.
- All predecessors of the safe prefix entry must be the primary unsigned
  guard or an exact BGEU on the same bound/index, with the same default.
  All later prefix predecessors remain unique. Removing the complete safe-edge
  set must disconnect the protected load/jump from entry.
- Table extent, alignment, exact register relationships, internal instruction
  boundaries, unavailable bytes, unknown flows and traps remain checked.
  Local-SP analysis separately requires all-body reachability, consistent
  relative SP, local stack accesses and balanced returns/tails.

This is opt-in proof in the main source, not a new allowed-target list.
The earlier absolute31 and relative22 fixture sets and strict default behavior
remain unchanged. The ordinary-call profile reviews RA links only; the ISA's
alternate link convention is not treated as an invalid instruction, just an
unreviewed call contract here. Unsigned branch semantics follow the
[RISC-V RV32I specification](https://docs.riscv.org/reference/isa/v20260120/unpriv/rv32.html#_conditional_branches).

## Results And Limits

- Formatter `0x840107ca`:all2707 instructions in the7544-byte body are reached;
  91 table words/28 targets, bound90 at both guards, safe edges
  `0x840108ce -> 0x840108d2` and `0x84010a38 -> 0x840108d2`.
  Conditional local frame496;77 external child sites remain unproved.
- Callee `0x840183b2`:2876-byte body,15 words/five targets, bound14 and safe
  edge `0x840184b2 -> 0x840184b6`. Conditional local frame192; eight external
  child sites remain unproved.
- All268 unique units / 286 executions pass without skips.31 new compiled
  guard-set fixtures cover alternate/pre-guard entries, changed/uninitialized/
  unknown/joined bounds, call clobbers, wrong/signed guards, every later-prefix
  bypass, stack errors, traps and unreviewed links. Three independent mutations
  expose covered false acceptances. Older broader runs overlap, not extra tests.
- 54 synthetic guests pass:48 dispatch-prefix guests exactly retain the prior
  observations; six added loop guests stop before the decoded return. The
  index3 loop increments to4 and rejects the second table access. All GPRs,
  PC, MSTATUS, ordered reads/no writes and full protected bytes are checked.
- Original isolated-prefix guests total203 in this run:110 repeat prior
  primary-prefix coverage;93 additionally execute the alternate guard/prefix
  with synthetic registers, bound90 and synthetic memory permissions. They
  stop before case bodies. No complete original function or child executes.

For the real formatter, the primary edge also dominates from function entry:
the alternate path is reached after an earlier dispatch. That does not prove
each later index is checked. Per-predecessor guards and actual constant bounds
remain required. A synthetic loop with a changed later bound demonstrates the
false acceptance if that bound proof is omitted. The earlier Jev question's
contrary formatter-single-edge premise was wrong; its0.52 result remains,
not approval. Initial unsigned-condition0.28 and missing-whole-path
not-established0.96/confidence0.94 remain. Later constant/predecessor semantic
checks are0.94/0.94, not proofs; whole-stack contradiction0.98/confidence0.97.

Exact original bodies/table bytes equal current CODE658c9c32 and Ghidra's
body exports. This does not requalify the older imported ELF or global graph.
Executable-blob table snapshots do not prove physical read-only permissions,
DMA/cache/asynchronous exclusion, register-save correctness, aliases, child
costs, termination, physical placement or a complete stack bound.

## Receipts

Metadata-only `GUARD_SETS.json` hashes
`cb3633b71bea9a732dfeae50ab0ba4657e903f118b1e6ec181cbe574d6b6ce4a`.
Private scope `a2982b34569ca4d43b397c83d1b6c12350e6ab877c2982df68058a5a1347db22`
verifies5152 paths, including2377 readonly pre-edit files and161 separately
preserved earlier test files. Eleven historical inputs resolve only to exact
recorded hashes. One intermediate source is reconstructed at its earlier
recorded digest, not claimed as an original file/timestamp or rerun.

The initial loop test's missing local-label error occurred before guest start;
its failing source/receipt remain. The correction decodes and verifies the
actual return instruction. An initial post-test tuple/list comparison failure
also remains; JSON normalization fixes that comparison, not guest observations.
The two286-unit passes overlap. No original native limit/checkpoint, firmware,
source-lock, pair, saved image, hardware or subagent change occurred.

Next: external child/original/indirect and whole-chain contracts, current raw
graph qualification, current cold/fault/full setup and latest-image checks,
then the still-open hot/checked IRQ/RRO/lifecycle/physical/client gates.
