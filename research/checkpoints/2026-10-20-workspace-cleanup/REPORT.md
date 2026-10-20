# Verified Workspace Cleanup And Storage Recovery

This is a storage-maintenance checkpoint, not new NPU qualification. Source code,
firmware, source lock, raw pair and saved image contents were not changed. The
producing source was clean main `0a3fb7def409ca8678dfce262196efffdeb8d15a`.
Machine-readable outcomes and private receipt hashes are in [CLEANUP.json](CLEANUP.json).

## Removed Copies

- Eleven superseded isolated world/provider/mt76 trees: 17,791,075,032 regular-file
  bytes, 579,422 entries. Preserved archive SHA256
  `9f833224ca11f403672de7d6866db28b75f909394cb50b2e5d6213acc7cead9f`.
- Three failed `world-main-40d-v2/v3/v4` preparations: 1,812,213,719 regular-file
  bytes, 8,182 entries. Preserved archive SHA256
  `7f3834e4a402d27f0fa1e8f0ee3ffe86195f11ae6abd4a689dd2e7663a272c90`.
- 7,548 generated q4/q5 download-cache files: 4,858,149,470 bytes. Every selected
  file matched a retained original under `.build/openwrt/dl`; originals were
  checked again after unlinking. No unmatched files were selected. Symlinks and
  shared-inode copies are excluded by the helper.

Archive checks covered the exact member set, full file-content comparisons, Unix
modes/ownership, literal symlinks, special-node identities, nanosecond modification
times and PAX extended attributes, including overlay origin/opaque/UUID metadata.
Source inventories were rechecked before deletion; archives have SHA256 receipts
and removal journals. Ten archive-guard and five cache-content fixture tests passed.
The retained-tree audit examined 14,776 symlinks and found no dependencies into the
removal list. These are cleanup checks, not native firmware tests.

Current original build/download cache, current late-reader module trees, q4/q5
images/non-cache evidence, full v5/v6/current-d6 image-reference inputs, native-case
capsules, keys, device backups, factory/calibration and recovery data were not
cleanup targets. No unrelated personal/application files were removed.

## Capacity Recovery

Linux guest used space fell from 168,075,083,776 to 142,125,989,888 bytes after
cleanup. Windows D: still had only 32,522,240 bytes free: guest deletion did not
shrink the nonsparse backing disk automatically. `fstrim` reported 19,433,127,936
bytes discarded, which is not a measurement of recovered host capacity.

The first maintenance attempt stopped at the exclusive-open guard after Ubuntu
termination; the WSL VM still held the disk. It never started DiskPart. A normal
VM shutdown, guarded by having only Ubuntu registered, permitted standard
`compact vdisk` on only `D:\WSL\Ubuntu\ext4.vhdx`. DiskPart reported success.
No format, resize, unregister, forced detach or sparse-mode change occurred.

Ubuntu restarted successfully. The post-restart observation measured D: free
26,197,639,168 bytes and VHD length 149,976,776,704 bytes, versus the original
176,141,893,632-byte VHD. Live activity can change these observations. The host
capacity distinction and offline compaction constraints follow
[Microsoft's command documentation](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/compact-vdisk).

All 2,736 distinct saved checkpoint bindings and three protected FITs were rehashed
successfully after cleanup, restart and compaction. This is byte-identity evidence,
not new firmware execution or a whole-filesystem repair certification.

## Permanent Preservation

Private archives and their index are now under `C:\Users\captain\W1700K-Archives`:

- `2026-10-20-cleanup/`: new archives, inventories, comparisons/removal journals,
  helper sources, protected-image copies and source backup.
- `2026-10-20-storage-recovery/`: earlier outage continuity and complete-v1/partial-
  damaged-v2 world-input preservation. The existing tar SHA remains
  `fc68f813c6fb192f318595634334ac34b2056dee9ce5e9a9c36e8f14c4b8648a`.
- `2026-10-20-index.json`: SHA256 file index and same-volume relocation mapping.

These directories are protected local evidence, not disposable temporary files.
Private archives/binaries are not committed. Old paths inside receipts describe
creation-time provenance and were not rewritten. Restore into empty Linux ext4
storage before replay; archive identity does not waive missing inputs, original
tool checks or native limits. Overlay uppers also need their original lower tree.

Three protected images have independently hash-verified C: copies. The source
repository is shallow: the bundle alone failed a standalone clone at the omitted
parent. Installing its original companion shallow-boundary file before fetching
into a new bare repository restored exact main `0a3fb7d` and passed `git fsck --full`.
The verification clone was removed. This is a tested shallow-main backup, not
complete upstream history, ignored device-data backup or a whole-VHD backup.

## Native Status

Existing execution records show both old-pair DESC10 aggregates exited 1. Each
has six passed individual case receipts and reported 10,800-second host timeouts
for `before-ready-bitmap` and `before-ready-plan`. The status observation rehashes
the 12 passed receipts and cites saved live-tool observations for the four timeout
reports. It does not independently revalidate their traces or qualify the optimized
pair. The two optimized callers and two old-pair tail jobs were interrupted during
the host-full outage without completed verdicts. None remain live or were restarted.

Fresh work must inspect/preserve partial outputs, use new run names, and check
both actual Windows backing-volume capacity and Linux guest capacity, including
snapshot/cache/overlay/output budgets and margin. Optimized world-input preparation
still needs explicit identities for all four logical linker aliases. Earlier
complete v1/partial damaged v2 remain failed preparations, not current build proof.

Full current cold/fault qualification, the latest optimized image, full setup,
hot/checked IRQ/RRO/lifecycle/physical/whole-stack and real boot/client acceptance
remain open. No firmware tests, image build, flash, hardware access or subagents
were run for cleanup. Jev supplied bounded scope/claim checks only; raw Noul
probabilities and actual model `jev-1.13.0` are retained in CLEANUP.json, not treated
as byte proof, permission or firmware acceptance.
