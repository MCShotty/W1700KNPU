# Original Trap Routing: ECALL Service Still Denied

## Finding

The original boot fragment at `0x84004388` defines `0x84006894` and writes
it to MTVEC. The current pair and original blob retain these exact bytes.
The vector's 164-byte body calls `0x84004230`, whose 268-byte dispatcher
recognizes only `mcause == 0x8000000b` as its machine-external-interrupt path.
It does not inspect A7 to implement a heap-growth syscall.

Standard synchronous ECALL causes 8, 9 and 11 therefore enter the diagnostic
prefix when delivered to this original machine-level path. These cause values
and the distinct interrupt bit are defined by the
[RISC-V machine-level specification](https://docs.riscv.org/reference/isa/v20260120/priv/machine.html).
This does not establish the actual NPU privilege/delegation/debug environment
or prove that every hart installs and retains this vector.

The diagnostic body contains logger calls and a self-loop at `0x84004318`.
Its in-body CFG has no edge to the normal return or IRQ branch, under the
stated ordinary-return treatment of external calls. Logger completion,
pointer safety, asynchronous behavior and an actual fatal-trap execution
are not proved. The ECALL parent `0x84017086` remains denied; neither a Linux
syscall-number match nor source-level familiarity establishes an NPU service
ABI or replacement equivalence.

## Exact Evidence

Read-only/no-analysis Ghidra 12.1.2 exports bind the vector, dispatcher and
eight-byte error child to original and current `658c9c32` CODE. The imported
ELF and full mapped older `a6813d39` CODE identities are retained. This does
not requalify that older global graph as the current graph.

The error child `0x840170fa` computes a GP-relative address, loads a value
into A0 and returns. It now passes the existing conditional zero-local-SP
checker. The loaded pointer's validity, errno identity and parent ECALL ABI
remain unproved. The earlier selected 64-body / 63 conditional-local result
is not inflated by adding this separately reviewed helper.

Two 32-bit SMT lemmas establish the exact branch predicate, and a weakened
sign-bit check produces the expected counterexample. Unknown solver results
fail closed. The vector still rejects as an ordinary-return local body;
MRET is not relabeled as RET or an opaque ordinary call.

## Isolated Execution

**66 dispatcher-prefix guests** cover 22 cause values with three A7 values.
They stop at the diagnostic or IRQ entry before child calls. **Four vector-
prefix guests** execute the actual register-save/CSR-read instructions and
stop before the dispatcher call. Exact all-32 GPR/PC/MSTATUS, ordered stack
writes, no data reads and full protected code/stack bytes match before reset.
The vector prologue reserves 128 bytes; this is not a complete IRQ-stack bound.

Two separate modified guests reject an inverted sign test and the wrong IRQ
number. They are not original guest coverage. No callback return, ECALL
delivery or device event is injected. The earlier 70 prefix observations
match exactly; they are repeats, not 140 unique cases. Their exact earlier
source is reconstructed to its preexisting digest and retained read-only,
not claimed to have its original file timestamp or replay qualification.

All **299 unique tests / 317 executions**, without skips, pass. Isolated
guests retain 500 instructions / 1,000,000 microseconds; constructor limits
and checkpoints are unchanged. Firmware, source-lock, pair and saved images
rehash unchanged through the preceding sealed inputs.

## Separate Native Failures

Both old-pair DESC10 matrices reported `TimeoutExpired` and `passed:false`
for `before-ready-bitmap` at the unchanged 10,800-second host limit. The
observed parent reports and exact case logs are preserved separately from
passed proofs. Their aggregate matrix verdicts are still pending at this
checkpoint. This is the old `858d1408` pair, not the optimized `658c9c32`
pair. The two optimized actual cold callers and two old-pair tail matrices
remain live. No timeout is waived or increased.

## Receipts And Limits

Private scope SHA256
`35393cef13c267de23f20dad8921fd86a33e0eca17129924a55fff31a35714e5`
binds 2,735 workspace paths and one external compiler identity. Public metadata
SHA256
`6f372992e3f9a72e3349faf7611948e18b79b1acc21f2864be8bd4a877351cdf`.
Prefix receipt `6fef0034`, unit receipt `f45ddb8a`, timeout-observation receipt
`36b3ae0b`. Jev's scope/role checks are retained as judgments, not proof;
its error-ABI claim is not established with confidence 0.43. No approval or
ABI claim is inferred from that uncertainty.

Actual trap delivery, complete handlers, ECALL service/return equivalence,
current global graph, whole-chain/IRQ/per-hart/physical bounds, complete
cold/fault/full setup, latest optimized image, hot paths, checked IRQ/RRO,
DMA/cache/drain/recovery and real boot/radio/client gates remain. No hardware
or subagents were used. The full project objective remains active.
