# Full Replay Outcome And Approved Ubuntu VHD Maintenance

Base source: `11d4abaf93f393bb775742e799c3a7b1db9c733d`. Continued solo.
This is a terminal replay/storage checkpoint, not new firmware implementation,
an image build, physical DMA retirement or actual-client acceptance.

## Native Replay

`w1700k-npu-observer-vectorcall-full-q25.service` is failed, exit1/MainPID0,
invocation `e89d9b04ed0843d6a1f7527d52fa3f62`. Its wrapper and controller fail;
there is no profile summary or complete native result. The prepared293 input
bindings match before and after maintenance. The unit status and journal were
saved before shutdown erased transient systemd state.

The JSONL contains149 checked positive RPCs: OPEN1/ENROLL139/PUBLISH9. The
positive writer emits a row after mailbox/reply/broker and applicable complete
extent/counter checks. Profile0's tenth publication (ordinal9/slot11) times out
at `0x84104d02`, not at a modeled injection. It records7062678 blocks,722891
metadata writes,24576 extent writes and22812 extent reads; wall60001780830ns.
The table has one write/one read, not the required completed two reads.

Original boot3M/10s and RPC100M/60s remain. A timeout does not establish its
root cause or a firmware logic defect. Earlier first-publication probes remain
their independent successes. Do not combine runs, restart unchanged inputs or
extend budgets. Further faithful native block-hook dispatch is only a candidate
for investigation; no profile6 implementation is claimed here.

## Approved Maintenance

The user approved compaction after a job audit. No build/replay/analysis child
was live; the two REA Node processes were idle with no children and no build
lock was held. D: had recovered above its existing reserve before maintenance.
No deletion was needed or performed.

Attemptq1 trimmed only the Ubuntu root, synced and terminated Ubuntu. Windows
still held the VHD. The exclusive-open guard refused before calling native
compaction. That failure and its zero-reclaim receipt remain intact.

Attemptq2 reaudited jobs and required Ubuntu to be the only running distro
before global WSL shutdown. Exclusive offline open then succeeded. The same
Microsoft native compaction API used by earlier project maintenance returned0.
Only `D:\WSL\Ubuntu\ext4.vhdx` was compacted:

| Measurement | Bytes |
| --- | ---: |
| VHD before | 173275086848 |
| VHD immediately after offline compaction | 173193297920 |
| Reclaimed | 81788928 (78MiB) |
| D: free before | 20476542976 |
| D: free immediately after | 20558331904 |
| VHD after normal startup, later snapshot | 173226852352 |
| D: free at that later snapshot | 20524777472 |

The small result is not gigabytes of cleanup. Startup growth is separate from
offline reclaim. Sparse mode stays false. No permanent execution policy or WSL
configuration changed. The C scratch/recovery VHDs were not compacted.

Microsoft documents the [native compaction operation](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/nf-virtdisk-compactvirtualdisk)
and the [detached/read-only compaction requirement](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/compact-vdisk).

## Restoration And Verification

The C scratch registration, UUID `b0b1bc48-d684-4090-a8cf-1ecb2939c36d`, marker
SHA `88204019cf6b25344f75c97fdca80954018427519f8d023c46edb7490a9e2ebf`
and directory identity2112:65538 are checked before restoring the shared and
canonical bind mounts. The original rw/discard/errors=remount-ro/data=ordered
and canonical nosuid/nodev flags are restored.

All2536 saved file hashes match, including2498 tracked files, the complete293
prepared replay binding set and selected private inputs/receipts. Git's
connectivity-only fsck exits0. These checks occurred before the tracking-doc
prefixes below; they are not a fresh full hash inventory of every private
archive or the five earlier complete source/cache inventories.

The first restoration passed, but Ubuntu subsequently idled out and discarded
temporary mounts while the kernel boot ID stayed unchanged. A later remount
correctly failed because its mount was absent. A documented hidden Windows
`wsl ... /bin/sleep infinity` process now keeps the working distro alive without
restarting the large REA servers. Fresh q3 restoration repeats all2536 hashes
and exact mount flags; q4 passes the unchanged registered C native-storage gate.
The keepalive is a temporary process, not a new persistent service/configuration.
Microsoft notes that [systemd services do not keep WSL alive](https://learn.microsoft.com/en-us/windows/wsl/systemd/).

Private evidence is under `.local/npu-vhd-maintenance-20261027/`, with a Windows
offline receipt copy under
`C:\Users\captain\W1700K-BuildScratch\maintenance\20261027-ubuntu-compaction-q1`.
The public EVIDENCE.json binds these scoped receipts without uploading raw
device backups, keys, calibration or private memory contents.

Jev's four claim checks retain all probabilities. Partial support0.66 with
confidence0.49 was not promoted to proof: the positive writer and retained
records were inspected directly. Full-pass contradicted0.99, firmware-cause
not-established1.00 and physical not-established0.95 agree with the scoped
observations; model judgments do not replace executed assertions or hardware.

## Remaining Work

Firmware source lock88502ab3, mt76 patchbb457928 and four-module producer
a840d3cc remain unchanged. No production source edit, module load, image,
router contact or flash occurred. No replay or REA server was restarted.

Next reduce faithful host hook overhead, preserving callback order, exceptions,
lifetime, every count/fresh read and existing guest checks, then requalify before
another full native recipe. Complete native, physical MCU/queue/page-pool
retention/drain, current firmware BA reuse, hot admission/retirement/rearm,
current image/router/actual-client/performance/stability remain open. The full
NPU objective is still active.
