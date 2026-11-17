# Backing storage and Git maintenance follow-up

This supersedes the **capacity and mount status** of the [initial
audit](REPORT.md). It does not change the October replay verdict. The first
audit and its machine-readable receipt remain intact at commit `ba4cdc3`.

## Disk budget correction

The registered Ubuntu VHD is under a **C: directory junction to D:**. The
old storage probe took the first letter of `FileInfo.FullName` and reported
92,140,277,760 free bytes on C: for the Ubuntu build. That was the wrong volume:
D: reported 20,055,011,328 bytes. A writer relying on the old observation could
have exhausted the actual disk while appearing to have ample room.

`tools/npu_storage_budget.py` now opens the existing VHD for metadata only,
gets its normalized DOS path, and independently queries the volume containing
the registered file. An ambiguous volume, unhealthy volume, unsupported path
or disagreement is a refusal, not a fallback to the registry drive. Receipts
distinguish the registered path from the resolved path. Live checks resolved
the active Ubuntu VHD to `D:\WSL\Ubuntu\ext4.vhdx` and the separate scratch
VHD to C:. All 19 storage tests and the expanded 209-test host suite passed
with no skips. No VHD was opened for data writes, compacted or resized.

## Scratch readiness

The existing scratch directory was bind-mounted from the already-running
scratch distribution into the shared WSL mount and the canonical Ubuntu
`.local/npu-build-scratch/native-c2` path. No persistent mount configuration,
new filesystem mount of the raw device, keepalive process or old queue was
installed. Both Ubuntu views were verified `rw,nosuid,nodev` on ext4 UUID
`b0b1bc48-d684-4090-a8cf-1ecb2939c36d`, same device/inode and original marker.
The initial peer bind in Ubuntu did not inherit all mount flags; the private
preflight rejected it until the peer's bind flags were corrected and rechecked.

Point-in-time guest and host budgets passed on both volumes (512 MiB C: output
plus 2 GiB margin; D: 1 GiB + 64 MiB allowance plus 2 GiB margin). Available
guest RAM exceeded the 400 MiB task cap plus 2 GiB margin. The existing writer
lock was acquired for the check and released. No compiler, replay, module or
router was started. Before a new writer, recheck the mounts, host/guest RAM
and both volumes, reacquire the lock and bind a **new** post-boot plan. The old
boot-bound plan and immutable historical scripts are not launch authorization.

## Net cleanup

Windows Git's fetch verified the published tree but its automatic repack over
the WSL UNC path left a new pack and failed to update the multi-pack index.
Native Ubuntu Git verified that pack, selected it as the index's preferred
pack, and expired four older non-cruft packs wholly covered by it. Packs
containing other data and all cruft packs were protected. Another 365 loose
objects then had packed copies. The entire set of **6,431 Git object IDs, types
and sizes** was identical before and after; refs, reflogs, stashes, worktrees
and the exact 25 dangling objects were unchanged. Native multi-pack-index
verification and full Git fsck passed.

Measured from **before the first cleanup** to the end of native maintenance:
Git objects went from 1,263,804,416 to 358,449,152 allocated bytes. Including
972,025,856 compiler-cache bytes and 1,716,224 Python-cache bytes, the net
reduction was **1,879,097,344 bytes (1.75 GiB)** inside Ubuntu. Do not add
the two phase totals: the intervening fetch allocated a temporary duplicate.
No Windows host-space gain is claimed. Use native Git for pack/index
maintenance. For Windows credentialed transport to this UNC checkout, use
per-invocation `-c maintenance.auto=false -c gc.auto=0`.

Selected checks and local receipt hashes: [FOLLOWUP.json](FOLLOWUP.json).
