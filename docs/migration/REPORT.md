# Workspace Migration and Cleanup - 2026-09-05

## Canonical Workspace

- GitHub: https://github.com/MCShotty/W1700KNPU (private).
- WSL checkout: `/home/captain/W1700KNPU`.
- Windows access: `\\wsl.localhost\Ubuntu\home\captain\W1700KNPU`.
- Active build: `.build/openwrt`; upstream Git backing: `.local/upstream/openwrt`.
- Previous build paths are compatibility symlinks only. Old Windows workspace
  and firmware folders contain migration pointers and retained archival inputs.

Initial import commit `4a5a3fe0589d34849fc8b8c53559a06db01238e6` preserved the
existing GitHub initial commit and exactly matched the local 175-file Git tree.
Native Git credentials are unavailable. Upload used the authorized GitHub
connector, with Git object/tree SHA verification and hash-verified local commit
import. Local history has a shallow boundary at the first import; remote history
retains the original initial commit. No connector credential was extracted.

## Preserved Work

- Cumulative source export from public OpenWrt and LuCI bases, including both
  committed and uncommitted customization, plus overlays and feed/config pins.
  All 35 changed files reconstruct and match their source hashes.
- Current Daybreak21 R1 and V6.87 rollback bundles; both checksum files pass.
- Original stock firmware, selected vendor/OpenWrt ELF inputs, NPU blob ZIP,
  and the complete separate Daybreak19 legacy source snapshot.
- Historical archive: **49,891 files**, **21,925 unique contents**, original
  source paths and SHA256 manifest. Every archive member was verified against
  the screened original; hardlink deduplication preserves repeated paths.
- Canonical current reference, stock-port ledger and logging session.

Large artifacts use 16 MiB parts because the GitHub blob API rejected the full
44,331,008-byte stock firmware request. The parts include complete-object and
per-part SHA256 values. Reassemble an input with `tools/restore_artifact.py`:

```sh
python3 tools/restore_artifact.py research/stock/WXK001-05.00.30.82.bin.parts.json --output .local/stock/WXK001-05.00.30.82.bin
python3 tools/restore_artifact.py research/history-20260905.tar.gz.parts.json --output .local/history.tar.gz
mkdir -p .local/history
tar -xzf .local/history.tar.gz -C .local/history
```

## Privacy and Boundaries

Gitleaks 8.30.1 plus private-path and configuration filters screened the import.
The only allowlist is the reviewed non-secret phrase `scatter/SKB/bufid`.
The initial history pass withheld 1,224 paths/files. The subsequent scanner
flagged 292 matches in 152 additional files; those files were quarantined, not
uploaded. Archive verification proves every included byte matches screened
input and every flagged file is excluded. This is a conservative privacy filter,
not a claim that all flagged historical source is genuinely secret.

Protected router backups, credentials, signing keys, factory/calibration,
bootloader dumps and the recovery VHD were not uploaded or deleted. Raw retained
archives are local preservation, not an independent off-machine backup.
Historical paths, hashes, and experimental claims remain historical evidence;
they do not make old patches safe to apply to current upstream.

## Cleanup Scope

- Eight superseded Ghidra project directories are preserved in verified archives
  under `C:\Users\captain\Downloads\FW\W1700KNPU-LocalArchives\ghidra`.
  Receipts include every member hash; original directories were removed only
  after archive and fresh source checks. Annotations and raw inputs are retained.
- Two old prepared Linux build directories are archived in
  `.local/archives/build-cache`. This preserves unique manually modified source,
  not just regenerable object files. See removal receipts for completed paths.
- The missing assumed `.v685-build-upper/build_dir` path was not removed;
  the `.v685` tree remains untouched. Current build, retained v689 source,
  signing-key archives, and recovery VHD remain protected.
- 597 pre-September obsolete experimental FIT images (11,744,507,404 bytes)
  were selected for retirement after source/report/hash preservation. Exact
  retirement completion is recorded separately; current, rollback, recovery,
  initramfs and factory/calibration paths/hashes are excluded.
- No firmware source behavior, router configuration, radio, transmit-power,
  NPU setting, flashing or live-router validation was changed by this task.

Cleanup completion, measured drive-space changes and final upload verification
are appended below after the respective operations finish. Firmware runtime
acceptance and unfinished stock-port boundaries remain as recorded in the ledger.
