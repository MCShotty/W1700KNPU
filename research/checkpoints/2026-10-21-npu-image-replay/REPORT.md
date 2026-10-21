# Current-Pair Image And Original Replay

## Read-Only Input Reuse

The new `create --reuse-snapshot` option in
`tools/npu_validation_capsule.py` can share matching read-only files from a
verified prior capsule. Default copying remains independent. Reuse validates
the prior receipt, exact file set, content hashes, modes, ownership and paths;
new or changed inputs are independently copied. A failed hardlink stops the
operation instead of silently expanding its disk budget. Shared inodes are
not independent copies or tamper-proof immutable storage. Their link counts,
ctime and atime are not claimed preserved.

All 35 focused tests pass without skips: five retained capsule controls,
twelve reuse controls and eighteen storage/linker controls. The runtime
functions `digest`, `source_file`, `receipt_inputs`, `inner` and `run` have
unchanged AST against `de5aa83`. The whole bootstrap file necessarily differs;
its exact old bytes remain in Git and the prior read-only snapshot. Historical
receipts are not rewritten or treated as matching the new bootstrap.

`MATERIALIZATION.json` binds the synthetic test log, reviewed source hashes
and private precommit input plan through private scope
`8b055dd3b9fd1b7c5ec7fc2fe2e1408f1f2efee229aa9cf4e59f77f36bce018c`.
The plan predicts 6,308 files / 3,060,947,967 logical bytes, including 6,247
shared files and 61 copied files / 6,573,235 copied payload bytes. It deliberately
stops before creating a snapshot. Counts will be recalculated after this clean
source commit before freezing actual build inputs.

The fresh Jev scope check selects supported (0.93, confidence 0.89); native
waiver probability is 0.04 and shared-storage disclosure probability is 0.97.
These are semantic checks, not permission or runtime qualification. The raw
request and response remain in the private checkpoint directory.

## Offline Image Passed

The actual clean tracked-source freeze at `73ce969` contains 6,310 files /
3,060,956,830 logical bytes: 6,247 shared files and 63 independent copies /
6,582,098 copied payload bytes. Receipt `94de35ba` is the actual materialization,
not the earlier precommit plan. The guarded offline `world-bytewise-q1` run is
terminal zero and passed, including its post-build preservation comparisons.

FIT SHA256:
`01fc0ef04b0b3e9a61933aa8faf47794d2003d162db4f27725e7048f3cfaf405`.
It is 27,009,866 bytes and its actual DTB identifies Gemtek W1700K with
`gemtek,w1700k-ubi`. Linux 6.18.52, 218 packages, 78 module ABI checks, 22 normal
RV32 objects, 168 hooks and exact CODE `4e43de6f` / DATA `a282ca7a` pass.
All 891,138 original build entries, 4,617 cache entries and frozen inputs remain
unchanged. `WORLD.json` (`9f5109fb`) binds the private derivative audit
`3d11b02e`, 56 paths, after the full world runner's own preservation checks.

A separate byte-identical image and new exclusive index are preserved under
`C:\Users\captain\W1700K-Archives\2026-10-21-npu-image-replay`.
All four prior protected images still match. No earlier archive/index/image
was overwritten. One new WSL client timed out with `0x8007274c`; the existing
build continued and a direct `--exec` root shell worked. No VM restart, extra
swap, persistent policy change or native-input modification was used.

## Publication Mismatch And Correction

The first new default/HIF2 launches in `bytewise-caller-v1` both exited one
before raw RV32 construction. They selected the new pair but an old publication
readback, whose copied CODE was `658c9c32`. The unchanged equality assertion in
`raw.load` stopped at line 31, before the factory at line 45. Host libraries had
compiled; no native-failure or complete-caller receipt exists. `PREFLIGHT.json`
preserves both failures. They are not firmware runtime or instruction-budget
failures and were not promoted or overwritten.

Fresh actual current provider C generated publication readbacks for the new
pair. All 60 checked-loader cases and eight rejected mutants pass with address,
undefined and leak sanitizers. Raw startup from those exact readbacks passes
for all eight harts, including parked-state checks. There are no synthetic
plan/identity writes or post-load ELF injection. Copied CODE equals `4e43de6f`;
published DATA `a7add2d2` differs from raw `a282ca7a` only in the two declared
runtime plan/identity slots. `PUBLICATION.json` binds producer `28230867` and
startup `3b8f91c3`; combined private scope `b86f9034` binds 3,083 paths.
This is publication/startup evidence, not full original-caller acceptance.

## Fresh Original Replays Live

Corrected `bytewise-caller-v2` receipt `941716f0` freezes 2,473 files /
526,399,900 logical bytes at the same tracked source revision `73ce969`.
It shares 2,452 verified read-only files and copies 21 files / 2,740,833 payload
bytes. The new planner checks exact publication equality and allowed DATA slots
before freezing. Sixteen replay/publication policy sources remain byte-identical
to the earlier original-caller snapshot.

Both new jobs are live under transient service
`w1700k-npu-bytewise-callers-q2.service`:
`bytewise-default-q2` / `bytewise-hif2-q2`, capsule runners 400219 / 400220,
start ticks 3965760. The guard PID is 400207. `CALLERS.json` (`fdf21da7`) binds
private launch/input audit `3f13c188`, 2,488 paths. This verifies live process
identity and every frozen input, not completed guest execution. Initial log
prefixes were empty; zero complete original-caller results are claimed.

Later `PROGRESS.json` (`72ee0321`) / private `997ee533` preserves two 290-byte
live prefixes: both enroll 15 records with the exact plan/RX-event record, then
show the first three native command frames. Six bound paths support this console
observation, not a complete/atomic trace regrade or completed cold constructor.

Inspect the exact service, PIDs/start ticks, logs and
`.local/npu-image-replay-20261021/caller-controller-q2.result.json` before any
relaunch. No automatic restart is configured; WSL shutdown/reboot can interrupt
the service and does not produce a native verdict. New output names are
`bytewise-caller-q2` / `bytewise-caller-hif2-q2` inside the corrected capsule.
Both old original q3 runs remain failed INODE0 results. All new full sizes,
progress checkpoints and original per-engine 3M-instruction / 60M-us limits stay.

Use the storage guard for snapshot, cache, overlay, output and margin on both
guest ext4 and the actual Windows backing drive. Its cooperative lock and
point-in-time measurement are not a reservation against unrelated writes.
The transient service holds the cooperative guard lock through both replays.
`END.json` records the later derivative rehash and live-handle check, not a new
native execution result. Fresh Jev selects publication-identity mismatch for
the first failures (1.0/confidence1.0), supports the report scope (0.95/confidence
0.92), and retains pending-coverage probability0.97. Startup-to-full-caller
probability0.12 is not completion evidence; raw request/probabilities remain
private. Tests and terminal receipts, not these judgments, determine acceptance.
No hardware, flash, radio changes or subagents occurred. Full fault, setup,
hot-path, IRQ, RRO, lifecycle, physical, whole-stack, boot and real-client
acceptance remain open; the full NPU goal is not complete.
