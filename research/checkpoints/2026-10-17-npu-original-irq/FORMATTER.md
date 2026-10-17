# Formatter Frontier And Local Arithmetic

2026-10-18. This is static original-body analysis plus synthetic guest tests,
not original logger execution, a whole stack bound or physical acceptance.

Read-only/noanalysis Ghidra exports pin the complete 7544-byte body at
`0x840107ca`, 2707 decoded instructions, 78 external transfer sites to 21 known
targets and one computed jump at`0x840108e2`. Original CODE and both old/current
paired images have identical bytes throughout the body and its table. The
observed entry instruction reserves 496 bytes. This is not a qualified all-path
local or whole-chain bound. Ghidra reports unsettled type propagation; its
pseudocode supports a formatting-role inference,not an exact library symbol.

The relative table at `0x8401d4b4` has 91 entries reaching 28 instruction starts
inside the body. Ghidra's returned labels are signed target-like values,not
verified index labels,and it supplies no load-table records. Decoding the bytes
does not establish the guard/bypass paths. The unchanged checker rejects this
computed flow. FORMATTER_FRONTIER.json preserves that earlier19-source scope;
its metadata SHA256 is
`a79ca3cc88addb43351fdc0d582ca73526cbebc8220c4e925c17d68214047a73`.

The 21 directly named callees were exported separately. Before the helper
extension, 12 passed local-SP analysis and nine were rejected. That 38-file
producing cohort/receipts remain readonly-preserved. The checker now handles
`SEQZ` and RV32`MUL/MULH/MULHSU/MULHU/DIV/DIVU/REM/REMU` only as conservative
unknown clobbers of non-SP GPR destinations. Existing self-relative-SP, control,
return, memory and merge guards remain. It does not calculate arithmetic results
or widen the constant-target engine. The integer instruction definition is in
the [RISC-V M specification](https://github.com/riscv/riscv-isa-manual/blob/main/src/unpriv/m-st-ext.adoc).

Fresh current analysis qualifies 20 individual callee local-SP depths, largest 496,
under the existing ordinary-ABI/no-asynchronous-mutation assumptions. Callee
`0x840183b2` still fails for unknown computed flow;the formatter itself remains
rejected too. Child calls, aliases/escaped stack pointers, register-save behavior,
termination and physical placement remain separate unproved contracts. The
global300/718/six-internal/56-unknown/9696 partial graph is not extended or
requalified for current CODE858d1408.

All 25 earlier local-control methods remain. New LLVM fixtures contain 28 variants:
nine non-SP,nine SP-writing,nine zero-register and one balanced-frame case.
The maintained tests execute 84 tiny synthetic RV32 guests over ordinary,
divide-by-zero and signed-overflow input contexts. All32 GPRs,PC and protected
code/stack bytes compare before any host restore. SP-writing cases stop after
their first instruction and remain rejected by the static checker. These are
not original firmware runs. The first private probe failed fetching its unmapped
return-stop page,after returning correctly to0x2000;its exact source and failed
diagnostic remain. Separate corrected q2 passes84;the maintained q3 reproduces
exactly those same84 observations,not additional unique coverage.

Current broader 234 unique/252 unit executions pass, no skips. They include the
local-control methods and overlap the narrower scopes. Private scope6cd11a12
verifies252 paths and the compiled ELF/fixture bytes. Maintained guest receipt
hashes37b0e8c5;broader receipt18a78539. FORMATTER_ARITHMETIC.json hashes
e21b547717543a3270c0f5df030360281cd26defd36c9e04ebf2b65973a73439.

Actual Jev q3/q4 probabilities remain in both metadata files. Formatting role
is0.73/confidence0.64;the new SP-guard claim remains not-established0.45/
confidence0.18. Non-SP-clobber wording is supported0.94/confidence0.91.
Whole-cost wording is not approved. Direct code inspection, nine SP-destination
counterexamples and the84 executions provide the covered evidence;no resampling
or model approval replaces them.

Source-lockd6b6e2da,firmware,paired CODE/DATA and protected images are unchanged.
Fresh v3 actual cold callers remain active with their frozen inputs/budgets.
Full512/eight-DESC10/all36-tail/actual INODE stage1/new24 faults,full setup,hot
TX/RX,checked IRQ/RRO/lifecycle/DMA/cache/drain/recovery/remaining original and
indirect/per-hart/physical/boot/client gates remain. No hardware or subagents.
