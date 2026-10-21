# Linux Entry And Native Ext4 Build Scratch

Date: 2026-10-21. Supersedes the prior new-WSL-entry blockage, not any NPU
runtime verdict. Full reverse engineering and implementation remain active.

## Native Storage And Per-Mount Inode Identity

The actual v4 freeze is3b303442e70fef480db7a4fb8a3419c51881e1a0af1862820508cc6ea29d8e82,
6680 files at cleane1a58ae. q4 stages both current recipes and passes cache
identity,but make exits2 while extracting Linux6.18.52. Outer fails1;all891138
original build entries,4617 cache entries,snapshot and parent namespaces match.
No image is qualified for checked IRQ. These are preserved terminal failures.

### Two Distinct Problems

Actual kernel logs contain loop0 read/write resource errors,ext4 writeback I/O
errors and failed unwritten-extent conversion/potential-data-loss warnings.
The zero filesystem error counter does not certify health. The exact idle loop
and image identity were checked and only native-c1 was remounted read-only.
Its raw24GiB file remains untouched. No repair,forced teardown or VM restart.
All62 selected evidence paths,including prior-bound logs,receipts,three bad
samples and the unqualified q3 image,were independently rescued to Windows C:
content-addressed objects with matching hashes and a restoration journal.

Official Ubuntu Base26.04.1 amd64 checksum
a496a960472ce474a59590b8987d3a1135d3cbef1991f3b1abe8cacfea8bf85a was verified
before a documented own-user WSL2 import on C. Signature verification is not
claimed. The additive W1700K-BuildScratch-20261021 native VHDX gives ext4 UUID
b0b1bc48-d684-4090-a8cf-1ecb2939c36d,shared via /mnt/wsl and bound at native-c2.
Original Ubuntu's registration/default and live replay identities are unchanged.
Two fresh nonce/hash-bound Windows sidecars check the actual D/C backings and
Healthy host capacity;guest free space alone is insufficient. Budgets retain
the full native future-output allowance/margin and count planned C VHD growth,
not the entire logical maximum. No fstab/global-policy/system-bwrap replacement.

Native direct extraction verifies91151 regular files/6048 directories/85 symlinks,
1538072591 regular bytes. The regular-file manifest is
a4e5ee95d0104b5c3018745e5c49b7ed87a17c9fef0b9fb5534b7a1832a2c16d.
The original cross-filesystem bubblewrap overlay still fails tar directory
identity checks on this native disk,with no new I/O errors. Thus replacing the
loop alone is insufficient. A private mount-namespace xino=on extraction passes,
while global xino_auto staysN. This follows the documented OverlayFS inode
identity distinction,but does not establish the loop I/O/zero-fill root cause.

### Private Launcher And Validation Scope

Upstream bubblewrap0.11.1 commit124c4cdf4321f63ef17a1cb0ce8f9dd45bd7adbe is
built privately with the single userxattr -> userxattr,xino=on edit. Source patch
reverse-checks against the actual tree. Binary SHA256
12f8d2268caed87b5325ac1cfe5800e3914018c12549b055e9778e94a70a6f7f is0555,
non-setuid and capability-free. The system binary and global module parameter
are unchanged. Only meson/libcap-dev were installed,not upgrades/autoremove.

An actual UID1000 private-overlay extraction using this binary passes and
verifies the complete same native/archive content manifest,with actual xino=on
mount evidence and zero new I/O errors. An earlier q2 probe stopped before
launch because the binary had not yet copied after a Git-ownership guard;
that partial directory is retained. q3 is the successful private-binary probe.

The world tool's optional --bubblewrap requires an ordinary,declared,read-only,
nonprivileged frozen executable under .local,checks source/frozen hashes,executes
the frozen path and records/rechecks the actual hash. Default execution is the
absolute system binary. All mount/network/PID/root/snapshot,clean,source/module,
image/FIT/package/ABI and protected-input gates remain. Inner proof also records
the actual overlay mount lines. All56 project units/five cleanup guards pass,
zero skips. This is not yet a full world with the new launcher.

Broader upstream tests are explicitly not all green:three suites pass,seccomp
skips,and test-run.sh aborts134 at --file0. The same abort reproduces in an
unmodified build and identical isolated controls. World uses no --file. This
limits general launcher qualification;the common failure's cause is unproven.
Original source LICENSE -> COPYING is recorded as a literal upstream alias;
its frozen representation must be an explicit read-only ordinary file.

STORAGE.json binds these results,source/test/provenance data and independently
rescued objects,and rehashes all five protected images. Both unchanged original
replays now pass DESC10,RX-PCIe and tail stages0/1,no final verdict. Next clean
commit,v5 freeze with launcher/provenance/alias,fresh budget,full image and
protected copy only on success. Firmware/lockcb035741/UI/WiFi/raw pair unchanged.
No hardware,flash,job signals,restarts,native-limit/checkpoint changes or
subagents. Full cold/fault/setup/hot/RRO/lifecycle/drain/physical/client goal open.

Primary context: [WSL import](https://learn.microsoft.com/en-us/windows/wsl/use-custom-distro),
[Ubuntu checksums](https://cdimage.ubuntu.com/ubuntu-base/releases/26.04/release/SHA256SUMS),
[OverlayFS inode properties](https://www.kernel.org/doc/html/latest/filesystems/overlayfs.html),
[bubblewrap source](https://github.com/containers/bubblewrap/tree/124c4cdf4321f63ef17a1cb0ce8f9dd45bd7adbe).

## Private Source Staging And Cache Consolidation

The q3 `make world` command returned0, but the enclosing locked-source audit
rejected the result before image verification. The protected seed still has
the older mt76/kernel integration recipes; neither current recipe had been
installed into the private upper. This is a missing source-staging step, not
another zero-filled cache copy. The q3 image is **unqualified for checked IRQ**.
All891138 original build entries,4617 cache entries and frozen inputs remain
unchanged. Its build output and failed audit are preserved.

The runner now installs authoritative overlay-backed locked files, components
and config into its private build overlay **before** download staging, cleaning
or compilation. Canonical source hashes and destination paths are checked;
copies use the verified userspace helper. All70 OpenWrt/five LuCI locked files,
22 components and config are then checked. Cumulative-only files without an
overlay body must already match; missing/stale ones fail, not get invented.
Every existing postbuild prepared-source/FIT/package/ABI gate remains.

Actual source-stage-q1 passes on the older lower:55 authority files checked,
exactly two recipe files copied,75 locked files/22 components verified,second
call copies zero. The original locked-source subset remains byte/mode unchanged.
All52 Linux world/source/cache units and five cleanup guards pass,zero skips.
This is staging and test evidence, not a new image or hardware result.

To fit a complete retry without resizing or deleting build evidence,7545
ordinary independent cache duplicates were verified and removed from two closed
C-scratch cache trees. Every selected file matches its declared retained
read-only frozen keeper; identities/hashes were rechecked before removal and
keepers rehashed afterward. The three unmatched zero-filled samples remain.
Modes/ownership/mtime/xattrs and mappings are in the manifest/removal journal.
No directories,images,unique data,source or native-job inputs were removed.
Keeper identity checks cover mode,uid/gid,size,mtime,inode,nlink,blocks and device;
atime/ctime equality is not claimed. Copy xattrs are retained as restoration data.

Removed duplicate payload:4856372501 bytes. Actual scratch availability rose
from10225426432 to15103901696 bytes. This reclaims space **inside** the existing
24GiB C-file filesystem, not Windows host-volume capacity. Cache output copies
are logically consolidated, not independent backups; restore them from the
recorded frozen keepers before trying to replay those old private outputs.
No disk growth,compaction,VM restart,extra swap or original-job intervention.

STAGING.json binds the rejected q3 world,actual stage,52+5 tests,cleanup and
current sources. Next:clean commit/v4 plan/freeze/fresh C/D+guest budgets/full
world retry. Source-lockcb035741,firmware/UI/WiFi and the4e43de6f/a282ca7a pair
are unchanged. Full NPU,cold/fault/hot/RRO/lifecycle/drain/physical/client scope
remains open. Do not promote q3 merely because make returned0.

## Cache Staging Follow-Up

The first freeze wrote preservation receiptb53fa1c6 but its wrapper exited1:
four logical linker aliases had collapsed during ordinary resolved-path includes.
That attempt is retained. Supplying the genuine alias receipt fixed the graph;
alias-complete freeze6d2c971f has6673 files/3117708513 bytes,6667 shared/six copied/
24531762 new payload bytes, clean tracked57b08cd source and current90abc8f3 authority.

The actual world-checked-irq-q2 run entered its private namespaces but exited1
at the private download-cache manifest check, before cleaning or compilation.
All891138 original build entries,4617 original cache entries, frozen inputs and
parent namespaces compared unchanged. No new image or native verdict resulted.
All3774 copied filenames and lengths match; exactly three archives are entirely
zero-filled, while their frozen sources still match their expected hashes.

A separate actual overlay comparison ran36 cases:27 default-copy/buffered/sendfile
copies matched, and nine direct copy_file_range calls returnedEXDEV. Inner and
physical-upper hashes agree. The small default-copy probe did not reproduce the
earlier corruption. A specific kernel/Python defect is **not established**.

The cache copier now uses exclusive targets, explicit1MiB userspace copying,
flush/fsync, preserved metadata and per-file SHA256 equality. Existing complete
source/target manifests and all later world/image gates remain. All47 Linux
world/source/cache units pass,zero skips. Four new methods check fast-copy
avoidance, refusal to overwrite, same-length zero-fill rejection and writeback
failure propagation.

The complete3774-file actual staging probe passes with this production helper,
including physical-upper manifest comparison after the namespace exits. This is
cache staging, not a world/image or hardware pass. CACHE.json binds that scope,
the failed run, retained copy comparisons, unit logs and current source501a5e07.
RECOVERY.json remains evidence for the earlier57b08cd source, not the changed
copier. WSL new entries remain intermittent; the recovered root session is kept.

Next:commit this source, plan/freeze world-checked-irq-v3 from that clean head,
refresh both-volume budgets including the retained failed/probe outputs, and
run the full image again with a unique output name. Original replays remain
untouched; full NPU/physical/client scope remains open.

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
