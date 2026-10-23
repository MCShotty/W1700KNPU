# Current Caller Replay Recovery

## Runtime Launch

`RUNTIME.json` records an actual new default nominal profile, not a preflight:

- Clean source `132949e311d245b3a7f1e724e8e7304c7cf49733` and capsule
  `e75e6f778222d1c6e9c4fb5596e118ec7fa3dadc558da754663eb580541fdf80`.
- 2860 verified immutable inputs/607671333 logical bytes, 2807 shared read-only
  inputs and 53 independent copies/9371788 copied payload bytes. Prior donor
  content/modes/ownership/mtime remain exact; link counts/ctime are not claimed.
- Service `w1700k-npu-checked-default-q1.service`, controller PID2367065/start
  tick13186072, native PID2367072/start tick13186243. Native CPU ticks advance;
  actual mount namespace and project inode match the frozen input root and
  differ from the parent namespace/worktree. Thirteen native-policy files
  match the original frozen caller exactly. No restore-prefix shortcut.
- Fresh RAM/storage budgets pass;4GiB service MemoryMax,MemorySwapMax0,
  OOMPolicy stop,Restart no. No VM/swap/global setting changed. Initial runtime
  observation is118759424 current/119480320 peak cgroup bytes,zero service
  swap;this is a sample,not a whole-run peak-memory or all-OOM-causes-fixed proof.
- Native output emits15 enrollment records and cold-command progress. A closed
  log-prefix copy is hashed;the live log/journal are not asserted immutable.
  Service `Result=success` while active is not its eventual terminal status.

The runtime seal rehashes6090 project paths and one external object,including
all2860 new inputs,the old2473 frozen inputs/624 interrupted outputs,and all
seven protected image copies. Its private manifest is linked in RUNTIME.json.
Only default nominal is running;no terminal execution/caller result exists at
this observation. HIF2 needs a separate fresh budget/launch after default is
terminal. Full faults,retained RRO,whole-stack and physical/client gates remain.
The full NPU objective stays active. Later tracking commits do not redate the
frozen executing source cohort.

## Preflight

The current sender fixture now compiles the actual `mt76_npu_irq_error`
accessor, `mt76_npu_irq` state and HWRRO enum. Four existing sticky errors
(`-EIO`, `-ETIMEDOUT`, `-ESHUTDOWN`, `-ENODEV`) return before provider
acquisition/publication and leave the modeled mutex/spinlock released.
The existing three publication, seven RX-getter and twelve PCIe-tail sender
controls remain. Actual selected sender C passes ASan/UBSan/leak checks;
kernel/framework/DMA and lock scheduling remain modeled.

The native caller runner has an explicit `--compile-only` gate. Its exclusive
`compile-preflight.json` records C linkage and exact input/binary hashes with
`native_executed:false`, `full_native_caller_verdict:false`, and no `passed`
flag. It returns before loading the C libraries or constructing the RV32 peer.
The actual current linkage checks 88 inputs. Hash-drift and existing-receipt
regressions are rejected. Default native execution remains selected without
this flag.

- Sender receipt: `.local/npu-cold-pages-wire-20261010/checked-irq-sender-q1/result.json`,
  SHA256 `562a8113d41b2ad2949fe3961f1fd5e1067eef9a661e2b8e44967c84980f6a4e`.
- Link receipt: `.local/npu-host-tx-lifetime-20261011/checked-irq-preflight-q2/compile-preflight.json`,
  SHA256 `f02dc8c178c79db1b5ddcf95a848911539ec76e930c4f54dfe4b931edf646265`.
- All 50 focused sender/journal/oracle/prefix units and 80 build/storage units
  pass, with zero skips. Expected argparse errors in storage-negative controls
  are not suite failures.

This checkpoint does not contain a new full native caller result. Runtime
status is recorded separately in RUNTIME.json after the clean freeze/actual
launch, not inferred from this preflight. EVIDENCE.json describes the earlier
preflight state before launch. Its first private seal attempt captured its
own open log;that attempt remains private/non-authoritative. The final q2 seal
rehashes closed outputs and passed an independent post-seal verification.

## Frozen Inputs

The new capsule must use a clean committed current source cohort, the genuine
checked-IRQ module receipt `90abc8f3`, and the new sender above. Thirteen native
policy files are required to match the old frozen caller exactly. The original
three-million-instruction limit, 60-million-us per-engine timeout, checkpoint
PCs, full sizes and requested DESC10/RX-PCIe/tail/INODE scopes remain unchanged.

The preliminary dirty-source plan selects 2858 files/607657944 logical bytes,
with 2807 shared read-only files and 51 copies/9358399 payload bytes. This is
only a plan; the final clean-commit plan and capsule receipt are authoritative.
Sharing verified immutable prior inodes is storage reuse, not independent
backup copies. The old interrupted capsule is not a reuse donor because it
contains additional output files; the exact-file-set checked-IRQ world capsule
is the donor instead. Existing source receipts are never rewritten.

The unchanged `4e43de6f` CODE / `a282ca7a` raw DATA pair and prior actual-C
publication bytes are reused literally. Published DATA `a7add2d2` contains the
declared runtime slots. This is not new execution of the loader/publication
qualification and does not redate its historical broad producer metadata.

## Controlled Execution

Run only one nominal profile per managed service. Require fresh nonce/hash-
bound Windows backing-volume plus guest observations, at least 1 GiB output
budget and 2 GiB storage margin, and MemAvailable covering the entire 4 GiB
cgroup cap plus 2 GiB system margin. New service swap allowance is zero; the
existing VM/swap configuration is not changed. Hold the cooperative storage
lock. Preserve service handles, process start ticks, namespace proof, logs,
results, and an ExecStopPost receipt even on resource termination. Do not
restart the old OOM service or automatically start HIF2 on stale capacity data.

The lossless observer journal is explicit. A passing bounded observer A/B
does not establish whole-run memory safety or eliminate every OOM cause.
Resource termination must be reported as such, never firmware correctness.

## Boundaries

The original OOM service remains terminal with all old PIDs absent. Its 2473
declared frozen inputs and 624 interrupted output files are retained and
rehashed. Six project image copies and the separate C image copy remain exact.
No cleanup deletion, firmware/source-lock/raw-pair change, new image, hardware,
flash, VM restart, policy change, or subagent is part of this preflight.

HIF2, full fault matrices, retained RRO ownership/order/handoff/error/late/reset/
drain/retirement, full hot paths and physical/client acceptance remain open.
The overall NPU goal is active. Jev checks source/scope claims as advisory
evidence, not native or physical proof; its controller judgment is only 0.56
confidence and is not launch approval.
