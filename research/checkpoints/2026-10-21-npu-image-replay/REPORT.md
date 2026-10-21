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

## Execution Status

No new world image or original caller execution follows from these controls.
The next image must embed CODE `4e43de6f` and DATA `a282ca7a`, not the old pair
in image `70b3112e`. Both old original q3 runs remain failed INODE0 results.
Fresh current-pair original runs must retain all full sizes, progress
checkpoints and the original per-engine 3M-instruction / 60M-us limits.

Use the storage guard for snapshot, cache, overlay, output and margin on both
guest ext4 and the actual Windows backing drive. Its cooperative lock and
point-in-time measurement are not a reservation against unrelated writes.
No hardware, flash, radio changes or subagents occurred. Full fault, setup,
hot-path, IRQ, RRO, lifecycle, physical, whole-stack, boot and real-client
acceptance remain open; the full NPU goal is not complete.
