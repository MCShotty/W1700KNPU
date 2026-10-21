# Linux Entry And Native Ext4 Build Scratch

Date: 2026-10-21. Supersedes the prior new-WSL-entry blockage, not any NPU
runtime verdict. Full reverse engineering and implementation remain active.

## Verified Progress

The installed Store WSL executable launches root Linux normally. The documented
WslLaunchInteractive entry also launches UID1000 successfully, although distro
configuration queries return access denied and the System32 CLI timed out.
No VM/service restart, original-job stop, sudo bypass or execution-policy change
was used. The Linux-to-Windows long encoded capacity query still fails; this
transport limitation is not claimed fixed.

All 32 existing Linux world/source tests passed. After adding the explicit
`--output-root` option, all 36 pass with zero skips. The default store is unchanged;
explicit paths require an existing writable ext4 directory under `.local`, with
no aliases or frozen-input subtree. Namespace isolation, critical output cleaning,
world/source/FIT/DTB/package/ABI checks and lower/cache/snapshot comparisons remain.
Unit tests are not image or hardware acceptance.

A new exclusively created 64MiB C-backed regular file was formatted and mounted
as actual ext4. As UID1000 its private cross-filesystem bwrap overlay passed
case sensitivity, symlinks, chmod, FIFO, namespace separation and unchanged lower
checks. The probe was unmounted and its loop detached afterward.

A separate new 24GiB regular file now backs ext4 build scratch at
`.local/npu-build-scratch/native-c1`, UUID
`4a6f22ea-746e-441b-8191-5d726aff1b66`. Its backing file is
`C:\Users\captain\W1700K-BuildScratch\2026-10-21-checked-irq\world-checked-irq-q1.img`.
Only this exclusively created file was formatted, not an existing disk, VHD,
partition, backup or image. No fstab/policy change or extra swap was made.

The Windows-direct capacity sidecar records actual Healthy C/D volumes, registered
Ubuntu VHD identity, a nonce and producer hash. Linux requires matching identity
and freshness within60 seconds, then measures real guest ext4 capacity. D budgets
128MiB new inputs, 32MiB metadata, the unchanged jobs' full1GiB future output and
2GiB margin. C budgets the full24GiB backing-file growth plus2GiB margin; scratch
guest budgets2.5GiB cache,8GiB overlay,512MiB output and2GiB margin. These are
point-in-time estimates, not reservations. A separate C-filesystem advisory lock
does not displace the existing native guard's D lock.

## Current Image Preparation

The precommit plan contains6665 files/3093161390 logical bytes,6291 shared and
374 copied/59130011 new payload bytes. It is a plan, not an actual snapshot or build.
After committing, replan from the clean current head before materialization.

The genuine unchanged combined module receipt90abc8f3 at source-lockcb035741
remains current execution authority, including all364 inputs and four actual
AArch64 artifacts. Prior snapshot94de35ba supplies storage only. Exactly two old
private kernel references changed; both must match the new producer. Every other
reused private file still matches its prior hash. Historical receipts are retained
as evidence, not substituted as current producer success.

The full clean checked-IRQ world/image is **not run yet** at this checkpoint.
The next stages freeze the committed source and run the unchanged full image
gates on C-backed ext4. Protected image01fc0ef0 predates checked IRQ. No flash,
router/radio/client access, source-lock/firmware/UI/WiFi modification or subagent.

## Existing Replays And Scope

Both original native children400224/400225 retain start ticks3965918, the same
systemd cgroup, advancing CPU and guard400207/FLOCK. Both remain in DESC10 after
six TXBUF phases/RX-event; the final controller receipt is absent. They were not
restarted or paused. Frozen73ce969 replay scope does not qualify later IRQ code.
Full sizes,3M instructions,60M-us limits and existing checkpoints are unchanged.

`RECOVERY.json` binds scoped source/test/probe/storage/plan records and actual
Jev results. Jev classified reuse as storage-only/current-authority with1.0
confidence; gate-retention0.91, unit-implies-image0.04 and offline-implies-physical
0.07 are semantic evidence, not execution proof.

Full cold/fault/setup, hot TX/RX/event/token/TXFREE/free-pool/PPE/FastTX, retained
RRO context, DMA/cache/PMA/exclusion, in-flight drain/reset/recovery/retirement,
whole-stack, physical Gemtek boot/radios/MLO/client/performance/stability remain.
