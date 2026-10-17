# Late-Reader Transitive Owner Checks

Publication: 2026-10-18. Execution receipts retain their original UTC dates.
This implements two logical-owner fixes. It does not qualify a fresh original
cold constructor, complete NPU setup, a new router image, or physical behavior.

## Defects And Fixes

`firmware/npu/cold-pcie-tail.c` checked the complete earlier owner chain before
external metadata/prefix reads, but only compared immediate TX/PCIe snapshots
afterward. A successful reader could fault packet/TXDONE/RX-event ownership
and still receive a positive current-stage query. The fix calls the complete,
pure `npu_cold_txdone_live` after both read boundaries. The paired tail linker
imports the actual DESC10 component symbol; the existing image group checks
that exact symbol binding.

`firmware/npu/cold-inode.c` had a separate analogous gap after its own published
prefix reads. It now calls complete `npu_cold_pcie_tail_live` afterward, before
comparing the final INODE/tail snapshots. The ordering matters because the
nested tail validation itself invokes readers. A dedicated fault-during-recheck
control detects moving that validation after the last local comparisons.

No owner/header sizes, public ABI, store counts, retirement or reset behavior
change. These checks do not establish physical exclusion against concurrent
DMA or writes after return.

## Covered Behavior

| Scope | Result |
| --- | --- |
| Old tail host-C probe | 36 false acceptances / 72 cases |
| Corrected tail host-C probe | 0 / 72 |
| Old INODE host-C probe | 20 false acceptances / 56 cases |
| Corrected source-bound INODE host-C probe | 0 / 56 |
| Normal compiled RV32 tail fixture | 647 calls, 559 controls |
| Current host-C INODE fixture | 592 calls, 326 controls |
| Normal compiled RV32 INODE fixture | 2522 calls, 326 controls |
| Compiled host mutants | 13 tail, 10 INODE, all detected |
| Current unit suite | 219 unique tests, 237 executions, no skips |

The added 180 tail and 172 INODE controls cover both HIF profiles, final metadata
and published-prefix reads, fault and non-fault owner corruption, and retained
progress on begin/reserve/publish/finish failure. Exact modeled owner/plan/memory/
effect snapshots are compared before fixture recreation, excluding diagnostics.
Both full 1030+6 INODE store projections and the complete 4104-byte clear remain.
Fixture snapshots between tests are not authenticated original-firmware captures.
The host and normal RV32 runs share controls and must not be summed as unique
coverage. The strengthened INODE q3 probe repeats exactly q2's same 56 cases.

Omitting the new rechecks produces byte-identical copies of the respective old
C source and reproduces the covered failures. A separate mutant demonstrates
that checking fault bits alone misses structural corruption. All nine original
tail mutation pairs are retained exactly, plus four new cases. Review found
an intermediate runner changed the old HIF2 wrong-register value from 0x10 to
0x100; its q2 receipt and exact source remain preserved. The fresh q3 suite
restores 0x10. It is not a relabeling of q2.

The INODE mutant runner retains its default 120-second host sanitizer limit
and exposes an explicit 120..600-second host-only override. Four parser tests
cover default, bounds and invalid input. The original 120-second timeout still
has no result receipt and remains a timeout. A separate full ASan/UBSan/leak run
passes with an explicit 600-second host limit. Native instruction/wall limits,
full fixture sizes and original failure history are unchanged. Earlier old/new
tail host timing comparisons are not current-candidate native qualification.

## Current Artifacts

Two complete raw builds are byte-identical: 20 components, 168 hooks,
CODE 998664 bytes and DATA 25728 bytes.

```text
CODE 858d14086955983764721acb26400446751cdcbc5708b31c6d4295c968711d3c
DATA 40483c19c5fff003f73918ee6d2829371598e25b5d782888eeea65e70c120389
```

Twenty image groups, 60 actual-C loader cases/eight mutants, six negative raw
boots before IRQ setup/no clears, and 12 unchanged actual-C sender cases pass.
These are separate scopes, not a successful cold INODE constructor. All 22
normal RV32 objects/archive match their stack-instrumented counterparts byte
for byte. The 171 compiler frame records have maximum individual depth 4688;
tail prior/context are 464/560. They are not whole-chain/IRQ/per-hart/physical
bounds. The older 300-node/718-transfer/six-internal/56-unknown/9696 partial
graph remains bound to older CODE and is not requalified for this candidate.

`firmware/source-lock.json` remains
`d6b6e2daf745414e82579bc89308821c5ba392d805fe3a220cd184dacbef7f47`:
kernel/provider and the 22 exported component sources are unchanged. This Linux
export set contains five C files and17 headers;neither native reader implementation
is included. Their C changes are bound by Git and raw-pair manifests. Both protected
FITs remain unchanged, at `978f9ddd...` and `a22300ea...`; neither contains these
latest changes. No new full world/kernel/module/image build or flash occurred.

## Evidence And Run Inventory

Private execution artifacts remain in `.local/npu-tail-liveness-20261017/`,
`.local/npu-pcie-tail-owner/`, and `.local/npu-inode-owner/`. The public JSON
files contain metadata only, no firmware payloads or device-specific data.

- `LATE_READERS.json` records the earlier q3 preparation snapshot, when the
  normal RV32 INODE result was pending. It is not a live status file.
- `LATE_READERS_NATIVE.json` records the later source-bound preflight, the
  completed normal RV32 INODE result and exact original tail mutation pairs.
  Its private preflight binds3478 inputs and hashes
  `c267c21522a0cd4d8400c97d9f9f84593f20e03c6a5a3711e425e6ccb984b0b1`.
  The normal INODE receipt hashes
  `50bb11c087b8b69bca01cd96307e446d5a89ac28eda3d264af114f7ee0ac17d5`;
  the fresh exact-legacy13-mutant receipt hashes
  `cc87fb26680c380ce122eb4fbdcbe305a272f7f03b96377a2e6d1fc49fa8cd80`.
- Original probe receipts, original 120-second timeout, both old cold-caller
  failures and interrupted matrix artifacts remain unchanged.
- Pre-edit preservation cohorts contain 2521 and 2731 files. The later
  pre-review cohort contains 5393 files/773414982 bytes; its receipt hashes
  `99987ea075c5b67d1642298b7bf11232132608cd1802da447d6543491652a891`.
  All are preservation only, not privately replay-qualified environments.
- An initial recursive pre-review preservation refused source drift when
  traversing historical negative-probe receipts; no success receipt was made.
  The separate declared-input preservation verifies every explicit current
  preflight input and retains historical receipts without treating their older
  source maps as current. No old receipt or source hash is waived or rewritten.

Both original all-36 tail runs were interrupted with 34 passed individual
cases/profile and no terminal/aggregate verdict. Separate frozen-source q2
completion diagnostics reuse byte-exact checked caches and execute the two
missing stage2 release-fault/unlock-neighbor cases per profile. They are still
running at this checkpoint. They qualify only their older diagnostic scope,
not the new reader fixes, and do not repair the interrupted executions.
Both original actual cold callers remain terminal exit1 at the earlier misplaced
entry-ABI observer; real INODE stage0 prefixes exist, stage1 does not. The
corrected callback-return/outer-return observer is retained for fresh runs.

Actual Jev q1/q2 batches and raw probabilities remain in the metadata. Tail
logic and INODE layer/ordering judgments have material uncertainty; INODE
layer/ordering choices are `not_established` at 0.59/0.56. The claim that the
600-second run repairs the earlier timeout is contradicted at 0.88. These
judgments are not model approvals; compiled counterexamples/tests establish
only their explicitly covered behavior.

A separate documentation-scope batch evaluates the current report/README,
not the firmware design again. It supports modeled/frozen/overall scope at1.0
and timeout wording at0.80,confidence0.70. Exact request/result hashes and raw
probabilities are retained in `DOCUMENTATION_SCOPE.json`. This does not replace
the earlier uncertain design judgments or authorize hardware actions.

## Runtime Input Follow-Up

The first new capsule omitted the test DTB. Both v1 launches ended exit1 before
the cold constructor. A later v2 captured that DTB and reached15 native
enrollment records on each profile, then ended exit1 because the selected
host-sender library was absent. All four failures and their immutable producing
input sets remain. No failed execution is relabeled or repaired.

The replay now adds the hash-pinned, parsed test DTB to its input manifest.
The actual TX caller also checks its selected sender against the independent
passed compiler receipt, rejects missing/changed/outside-storage libraries, and
includes that exact binary in producer inputs before emulation. The general
peer records the selected sender too. No firmware guard, native size or budget
changes. Four DTB/five sender synthetic tests pass. The complete earlier test
selection plus these nine gives228 unique/246 executions,no skips,receipt
`5978771cfdb32d5a798a787f51d4a02b6bd706776e242b870f41a8e240742675`.

A94-input preflight constructs the exact raw harness and loads six sender
symbols without calling the guest engine or sender functions. Its receipt is
`7279390bf7ceef07bd8fae5468fcac44aed9b88aa1baa7cb21cf6e9e62f02b20`.
New `late-readers-caller-v3` preserves2378 readonly files/525043700 bytes,receipt
`7ddc73cd215b3f99f16d5056a581210fb497a93bdd31ec7e33ec0524522cbf60`.
All nine dependency controls pass inside its isolated mounts. This is input/
construction qualification,not cold-constructor success.

Both fresh original cold callers are live with tags `default-hif-q3`/`hif2-q3`
and output names `reader-caller-q3`/`reader-caller-hif2-q3`. Paired CODE/DATA
remain858d1408/40483c19. `RUNTIME_INPUTS.json` hashes
`529e124e5bd1190be004e027ba3c733a53e8608cdaf1e743018dcc5973351beb`.
It preserves all four failed attempts, new preparation evidence and explicit
pending status. The older frozen tail diagnostics remain independent. No new
stage1 INODE capture, current full matrix or overall NPU acceptance is claimed.

The separate Jev runtime-scope batch supports sender-identity wording at0.90,
confidence0.85,and failure-history/limited-acceptance wording at1.0. Its raw
request/result remain under `.local/npu-tail-liveness-20261017/jev-runtime-q4.*`;
the result hashes
`f2112e2a1a326c6ff0192fe515911780f7888ddbd5964035be5d9c8a5e77accf`.
These are semantic checks,not constructor or hardware proof.

## Terminal Older Tail Diagnostics

Both separate older-source completion collections are now terminal0 and pass36
cases each. Each contains34 byte-exact retained cases and two new stage2
release-fault/unlock-neighbor executions. Both aggregates were then regraded
successfully in the original canonical-path private namespace,using every
cached case and the unchanged strict grader;no native case was rerun or
aggregate rewritten during that regrade.

Audit`d544d4bcf692c32555f00df29122b71e2e4e39676cb1363138fa7563cd7a8f92`
verifies8120 paths/2338 original+supplemental sources,case inputs/artifacts,
preserved earlier34-case inventories and all868352-byte protected projections.
Aggregate hashes are`9799750e929e9617b1c9daf57c60c6e15555d33950ecf96a349f7f2bd69f19aa`
and`7c1f4730e2d4ff8616534c0e2957fbf9b34a0bb8ef83fe378d2b96be166b43ce`.
FROZEN_TAIL_DIAGNOSTICS.json hashes
`df5959635c9afe3a71668617bfad61d27d721515fe1e27a584b4047ce5d0c55f`.
Native60M-us and original10800-second host case limits remain. The original
interrupted executions still have34 individual passes and no final verdict.
Neither was repaired. These collections qualify only restored diagnostics on
older CODE/source,not the reader fixes/current cold constructor/full setup.
This supersedes the earlier running-completion descriptions in this report.
Current v3 cold callers remain live and separately unqualified.

## Next Gates

Fresh current-source both-HIF actual cold callers, full512 DESC10/eight DESC10
cases/all36 tail cases, actual INODE stage1/new24 faults and broader full setup
remain. Then continue hot TX/RX ownership and workers, checked IRQ/quarantine/
atomic rearm, RRO, DMA/cache/PMA/exclusion/drain/remove/recovery, remaining
original/indirect/whole-stack/IRQ/per-hart contracts, complete image qualification
and actual Gemtek W1700K boot/client/performance/stability evidence. No hardware,
resource reclamation, source-hash/native-budget waiver or subagents occurred.
