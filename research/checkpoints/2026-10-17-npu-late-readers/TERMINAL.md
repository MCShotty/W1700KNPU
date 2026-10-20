# Current Cold Caller Failures

2026-10-20 audit of both frozen-v3 producing runs. These runs ended on
2026-10-18 with exit 1; they are no longer running and are not repaired.
The 2,378 producing inputs / 525,043,700 bytes remain unchanged, bound by
capsule receipt `7ddc73cd215b3f99f16d5056a581210fb497a93bdd31ec7e33ec0524522cbf60`.

## Validated Preceding Stages

Both profiles have independently marked validated original-store traces for
the complete 512-entry DESC10 path: 25,606 original stores, 3,072 packet
claims and matching protected memory. All three tail stages also validate,
with 2 + 2 + 5 original stores and three published journal steps. These
are actual original-instruction executions with modeled backing and host
transport, not a whole-caller pass or physical proof.

The 25,606 current stores are not the earlier 25,604-store diagnostic's
count. An initial audit scaffold stopped on that obsolete expectation before
writing a verdict; its source is retained. No producing count or trace changed.

## INODE Stop

Both runs enter the actual callback, but stop during stage-0 preimage capture
at 217 of the required 1,030 entries. Neither executes an original INODE
store or reaches a callback/outer return. There is no stage-1 prefix or
complete `result.json`. Native owner state remains active with no fabricated
completion or reclamation.

The default profile stops at `0x84042f86`; HIF2 stops at `0x84042df6`.
Both failure receipts report `AssertionError`, no unmodeled access and
`wall_budget_exhausted=false`. The failing source assertion requires END or
an existing stop PC after a 3,000,000-instruction engine invocation. This
is a nonterminal-PC stop, not the earlier misplaced entry-ABI assertion.
Instruction-window exhaustion is under investigation; the receipts do not
directly count the executed instructions. The unchanged per-engine wall
budget is 60,000,000 microseconds. Neither limit was increased.

A separate strictly restored-prefix diagnostic is prepared in
`reader-progress-v2` with 2,464 readonly inputs / 536,037,569 bytes,
receipt `0945ca33d0d875aa4ea660d8a2e3c0bbb87ea5592c557d6be8ef7e13fbe2eea8`.
It adds host observations only, with no extra progress checkpoint or skipped
guest instruction. Its result must be checked separately; restoration never
becomes a fresh allocator/loader/caller qualification. The first preservation
copy, v1, remains preservation-only and was not executed.

`COLD_CALLERS.json` has metadata only, SHA256
`54c2e23813ac7ad16cb3cedc5a711573751a28753c80b8b0f7c2802f50cf2ac3`.
The 3,060-path terminal audit hashes
`56932e89fd1aa3bfdfd000ca47e2e3695af6a4c661ee3284502e61daa06dcc6f`.

Current eight-DESC10/all-36-tail fault matrices and actual INODE stage-1 /
all-24-INODE controls remain unqualified. The older all-36 diagnostics stay
older-source-bound. Full setup, hot lifecycle, IRQ, DMA/cache/exclusion,
drains/recovery, original/indirect/stack and hardware/client gates remain.
The separately built FIT `633b4d71` does not change these runtime verdicts.
No hardware, flash, source/hash/budget waiver or subagent was involved.

## Current Fault Runs Started

`reader-controls-v1` separately preserves 2,673 readonly files / 567,317,019
bytes, receipt `90580953a640c1028ec5e071eeff6381e5a0ea1513e52af6bf98ce7091dc30ff`.
Its exact actual prefixes feed the unchanged eight-case DESC10 and 36-case
tail runners, for both profiles, with two workers per runner. Tags are
`desc10-default-q1`, `desc10-hif2-q1`, `tail-default-q1` and `tail-hif2-q1`;
outputs live in that capsule's `root/.local/npu-reader-controls-20261020/`.
These are diagnostic fault matrices, not restarted producing callers. They
are running, not passed, and retain all original counts/inputs/budgets. Check
their execution and aggregate receipts before making a completion claim.

## Restored Stop Reproduced

The separate default-profile probe completed with diagnostic exit 0, while
reproducing the original caller's failure PC `0x84042f86`, active owner and
217 captured preimages. It still has zero original INODE stores and no
callback/outer return. The last original engine invocation uses the unchanged
3,000,000-instruction / 60,000,000-us limits and reports no wall timeout or
explicit harness stop. Instruction-window exhaustion remains an inference,
not a newly measured exact instruction counter or a successful constructor.

Both producing failure PCs bind byte-exactly to the same 930-byte
`npu_cold_txbuf_dma_valid` body, SHA256
`5fd46aecfc3b845c6a3bd1a7fdb5255edae314e21ae32534ca15183ae864f7be`.
Host hooks observe repeated non-inlined validator entries after begin; these
are not all source calls or per-iteration counts. Avoid treating the repeated
geometry validation as a proven root cause until an equivalent bounded
implementation is tested. No extra checkpoint, skipped instruction or
source/hash/budget waiver was used. A sibling HIF2 diagnostic was not run.

`INODE_PROGRESS.json` contains metadata only, SHA256
`84c4212e9fd1171f1bbd087a55a7dab57bfe170ab8d41b3dc27ff5c3260fdbd9`.
The independent 2,497-path audit hashes
`03e67f38894dae21ce9daf7378ca0875fd42f3f59f6815f787341b7e71e97578`.
The diagnostic receipt is `a74e02e2`; original producing runs remain failed.
