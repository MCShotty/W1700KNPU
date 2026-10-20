# Original Memory Routine: Conditional Computed Entry

## Result

The opt-in exact-artifact profile qualifies `0x840103aa`'s computed code
entries and zero local SP use. It is separate from the unchanged strict
generic checker. Combined with the preceding selected-body profiles, **63 of
64** original routines now have conditional local results. This is not a
whole-NPU, whole-chain, IRQ, per-hart, physical-stack or device result.

The remaining denied routine is `0x84017086`: its ECALL handler/ABI and error
child `0x840170fa` remain unreviewed. No syscall substitution or waiver occurs.
Earlier 62-of-64 and strict generic denials are retained, not rewritten.

## Exact Artifact And Source Identity

Current CODE `658c9c32` and original blob `e743d1b5` match the complete
168-byte carrier, SHA256
`50232f532bf996f5d738050c60480fab6069d6ef4cb842cfc582170e351630c6`.
Ghidra's two recovered ranges remain 58 and 48 bytes. The intervening 62 bytes
are separately decoded and checked as 15 descending SB stores and a return;
they are not relabeled as a contiguous recovered Ghidra function.

Unmodified public [Newlib RISC-V memset source](https://github.com/mirror/newlib-cygwin/blob/1b7c72fdcc4bde7520407d2d3364146f04fb8312/newlib/libc/machine/riscv/memset.S)
compiles to exactly these 168 bytes at this address with the recorded RV32
LLVM command. The source/header is preserved privately without alteration.
This establishes a byte-identical public-source implementation, not the
vendor build date, vendor compiler, entire firmware origin or runtime ABI.
Compiler, linker, source and ELF hashes are in `MEMSET_ENTRY.json`.

## Static Contract

- Check all 55 decoded instruction boundaries, mnemonics and typed operands.
  No generic target allowlist or ordinary opaque indirect call is introduced.
- At `0x840103e0`, the nonlinking JALR enters one of 16 checked SB/return
  positions. Three actual unsigned/masked guards have known bound 15. Every
  prefix predecessor and safe-edge cutset is checked with conservative
  whole-carrier constants and last-definition sets.
- At `0x84010440`, the linking JALR enters one of 15 SB positions. The
  nonzero masked alignment guard dominates its prefix. The exact store-only
  suffix preserves GPRs and returns to `0x84010444`; incoming RA is separately
  checked through its T0 save/restore. It is not modeled as a generic ABI call.
- All carrier instructions are conservatively reached, protected register
  destinations are absent and SP remains entry-relative zero. Z3 5.3.1.0
  establishes three 32-bit target/mask lemmas and produces two expected SAT
  counterexamples for weakened conditions. Unknown/wrong solver results,
  disabled assertions and an absent/ambiguous loaded library fail closed.

Assumptions remain exact entry, an ordinary valid incoming return address,
immutable code, caller-owned accessible nonwrapping destination and no
asynchronous faults or interrupts. General memory-fill semantics and
termination are not established by this static result. Earlier 4,992 finite
entry-to-return guests remain a separate, unchanged execution result.

## Validation And Preservation

All **292 unique tests / 310 executions**, without skips, pass. Direct core
checks reject all **1,344 single-bit mutations**, without an outer hash check
deciding the result. Another **15 controls** corrupt proof intermediates and
reject missing bounds, mask definitions, RA provenance, predecessor checks
and cutsets. These controls are not unmodified-original guest coverage.

The failed first CLI preflight (deleted Z3 module-global library handle) and
initial metadata-schema failure have exact sources retained. The corrected
audit observes the loaded native library in Linux process maps and verifies
the prior frontier's actual characterization schema. No denied receipt is
turned into a passed proof. All 2,451 prechange readonly files and 58 isolated
solver files rehash correctly. The host interpreter/system dependencies are
not a portable replay environment.

Jev's six semantic checks are retained with full distributions, not used as
mathematical proof. Its source-date classification has confidence 0.56;
the report makes no vendor-date/compiler claim. The solver and deterministic
code, not Jev, establish the bounded arithmetic and execution checks.

Private scope SHA256:
`aab7c913bf3d4e2ffceed672beedc7afcbeeb118102efbece6174d979c44e6b1`
binds 2,706 workspace paths and one external compiler identity. Public
metadata SHA256:
`5094d371c68ba67892b8037af69da186c05f029a5c8dd0ce6a7c61d1cd2d5e02`.
The maintained proof receipt is `24687e04`; the broader-unit receipt is
`2e7ce4dd`. Raw blobs, source caches and private receipts are not published.

Both optimized actual cold callers and four old-pair fault matrices are still
live at this checkpoint. Firmware, source-lock, pair, three saved FITs and
native budgets/checkpoints remain unchanged. Current global graph, complete
cold/fault/full setup, latest optimized image, hot paths, checked IRQ/RRO,
physical ownership/drain/recovery and real boot/radio/client gates remain.
No hardware or subagents were used. The full project objective stays open.
