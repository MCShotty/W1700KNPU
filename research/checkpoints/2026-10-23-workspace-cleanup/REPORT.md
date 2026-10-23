# Verified Build-Cache Cleanup

This is storage maintenance, not new NPU qualification. The starting committed
source is main `4b8ea14efbba1ca921a74ef17e2c07a183c0ff52`. Three pre-existing
unfinished RRO test edits were hash-preserved, not validated by this cleanup.
Firmware, source lock, UI/WiFi, compiled outputs and image contents were unchanged.
Machine-readable results are in [CLEANUP.json](CLEANUP.json).

## Removed Duplicates

Only independent regular files in these three completed build download caches
were selected. Each build already had a passed terminal result.

| Cache Below The Project Root | Files | Logical Bytes Removed |
| --- | ---: | ---: |
| `.local/npu-isolated-world/world-inode-q1/build-upper/dl` | 3,774 | 2,429,074,735 |
| `.local/npu-isolated-world/world-bytewise-q1/build-upper/dl` | 3,774 | 2,429,074,735 |
| `.local/npu-build-scratch/native-c2/world-checked-irq-q6/build-upper/dl` | 3,774 | 2,429,074,735 |
| Total | 11,322 | 7,287,224,205 |

Every removed file matched the declared SHA256 and exact bytes of its retained
read-only keeper under
`.local/npu-validation-capsules/world-checked-irq-v5/root/.build/openwrt/dl`.
That capsule receipt remains
`da9cc62461bd15b9d9d5fd24950405d02036e04d83ea8296016ff2e8c864f29f`.
The original `.build/openwrt/dl` cache was not a removal target.

The plan retained each removed file's owner, mode, modification time, extended
attributes and keeper mapping. Paths, inode identities, content hashes and
read-only keeper status were checked before selection and immediately before
each unlink. Shared inodes, aliases and unmatched files were ineligible; none
remained among these selected caches. Directories were not removed.

The exact restoration map is `.local/workspace-cleanup-20261023/plan.json`,
SHA256 `3cdd8f66f914608069b5e643c5e80e958494242e91aed1e729bb48640b9f4ee2`.
The completed removal journal is `removed.jsonl` in that directory, SHA256
`69004b2e5e9fed8bc9b02ef3bc3905babf12bc17405ef09c6f94bfb20ec12957`.
These old cache paths are now logically consolidated, not present independent
copies. Restore from their mapped keepers into empty cache paths before any
exact old-tree replay. Original receipts were not rewritten; a historical
receipt does not waive the now-missing cache paths. Full-tree restoration was
not executed as part of this cleanup.

## Preservation Checks

- All 2,357 previously tracked file contents matched immediately before and
  after removal, including the three unfinished RRO files. The six resume and
  ledger documents were updated only after this preservation check.
- All 2,865 declared inputs in the executing compact caller capsule rehashed
  correctly. All matching keepers retained their contents and checked stat
  metadata. Access times and directory modification times are not claimed equal.
- Fourteen bound project image paths and one external protected object rehashed
  correctly. These are path bindings, not fifteen distinct image identities or
  independently backed-up disks.
- Eight focused cleanup byte/scope guard tests passed with zero skips. These
  are not firmware or RRO behavior tests. Jev supplied bounded classification
  and report-scope judgments, not deletion authority or byte-identity proof.

The candidate trees were disjoint from the saved protected path set, and no
process file descriptor, working directory, root, mapping or mount record
referenced a candidate cache when checked. The native-C world lock was held;
the running replay's existing storage lock was not replaced or displaced.
The mounted native-c2 ext4 UUID was verified. The damaged read-only native-c1
disk, unique error samples, compiled trees, logs, results, failed capsules,
keys, calibration, device backups, recovery material and archives were not
removal targets.

## Capacity And Live Work

Observed guest free space increased by 4,875,206,656 bytes on the original
Ubuntu filesystem and 2,440,126,464 bytes on native-c2. These point-in-time
guest measurements include filesystem allocation and concurrent activity;
they are not a measurement of recovered Windows host capacity. Fresh Windows
backing-volume observations and budgets included the live replay's future
output allowance and margin. No VHD compaction, disk resize, new swap, VM
shutdown or service restart was performed.

At the post-cleanup observation, `w1700k-npu-compact-default-q1.service` remained
active with controller PID 2396851 and native PID 2396859 at their original
start ticks. Native CPU time advanced; no new terminal native verdict is
claimed here. Memory peaked at 378,957,824 bytes and current service swap was
zero at that observation. The existing full nominal replay continues with its
original frozen source, limits and guards. No hardware, flash, boot, module
load, physical drain or client acceptance was performed. Full retained RRO,
cold/fault/hot/lifecycle/whole-stack and physical NPU work remains open.
