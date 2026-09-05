# Second Storage Cleanup - 2026-09-05

## Result

| Drive | Before free | After free | Net increase |
| --- | ---: | ---: | ---: |
| C: | 28.69 GiB | 59.96 GiB | 31.27 GiB |
| D: | 29.93 GiB | 38.34 GiB | 8.41 GiB |

Approximately **39.68 GiB additional free space** across both drives in this
pass. These are host-drive measurements; background activity may change them.
See `summary.json`, `drive-space-after.json` and `vhd-compaction.json`.

## Completed Actions

- Preserved and losslessly compressed 221 inactive task-history files, with
  222 hash-verified operations including the pilot/recheck. Content SHA256 values
  are unchanged. Actual allocation decreased by 21,549,123,499 bytes, about
  20.07 GiB. The active task file was excluded; no history was deleted.
- Removed 4,110 regenerable shader/browser cache files totaling 3,233,957,587
  logical bytes, about 3.01 GiB. One in-use item was skipped. Accounts, cookies,
  browser settings/bookmarks and installed applications were not removed.
- Removed 19 redundant installer downloads, 8,681,127,677 bytes, about 8.09 GiB.
  Every file matched its member in the existing backup ZIP by SHA256; the backup
  archive was reverified and preserved. Personal documents/media were excluded.
- Removed 818 WSL cache files, 2,425,573,376 allocated bytes, about 2.26 GiB:
  133 duplicate source downloads with verified surviving copies, 683 cached
  package downloads, and two apt index-cache files. Unique source downloads,
  package-manager locks/partial downloads and installed packages remain.
- Replaced the inactive v689 expanded build directory with a complete verified
  archive: 11,720,147,920 logical source bytes preserved in 3,695,476,891 bytes.
  The archive includes its unique source changes and historical binaries, not
  merely rebuild instructions. All members and fresh source hashes were checked
  before removal. Exact location/hash: `linux-archive-removal.json`.
- Completed normal offline WSL VHD compaction: 77,866,205,184 -> 67,204,284,416
  bytes, reclaiming 10,661,920,768 physical bytes. WSL restarted successfully.
  This is not additive to the drive totals or the guest-cache savings.

The Kbuild-only audit also identified 5,057 generated objects, about 427 MiB.
They were not discarded individually: v689's full contents were archived, and
the separate v685 tree remains unchanged.

## Preserved and Verified

- Current build/source/toolchain, current NPU test artifacts and runtime tools.
- Current Daybreak21 R1 and V6.87 rollback bundles; checksum files still pass.
- All task histories, account credentials, private router backups, factory/
  calibration and bootloader/recovery data. Recovery VHD remains read-only.
- Existing source/Ghidra archives and personal documents, media and archives.
- Current source reconstruction still verifies all 33 OpenWrt and 3 LuCI files;
  build config is unchanged, Git integrity passes and systemd reports running.

No router connection, configuration change, firmware build, flash, radio/power
change, application uninstall, or unsafe sparse-VHD mode was part of this pass.
Shader/browser caches will regenerate and may cause a slower first load.

Detailed user-folder and personal-archive inventories remain local under the
Git-ignored cleanup receipt directory. Only aggregate results are published.

## Resume Work

The requested [remaining-work checklist](../../REMAINING_WORK.md) records the
NPU recovery/ownership implementation, stock-port work, WiFi/MLO client and
throughput acceptance, CPU-frequency readback, monitoring and service checks.
Firmware work remains at checkpoint `b385f6f`; this cleanup does not close those
implementation or runtime-validation gates. The ledger and current reference
were updated, with bounded standalone subagent prompts recommended to avoid
replicating the accumulated task history unnecessarily.

Filesystem procedures follow Microsoft's documented [compact command](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/compact),
[allocated-size query](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getcompressedfilesizew),
and [virtual-disk compaction API](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/nf-virtdisk-compactvirtualdisk).
