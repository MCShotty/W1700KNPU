#!/usr/bin/env python3
"""Publish aggregate cleanup results without personal file inventories."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / '.local/cleanup-20260905'
PUBLIC = ROOT / 'docs/maintenance/cleanup-20260905'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


history = read(PRIVATE / 'history-compression-results.json')
if not all(r.get('contents_unchanged') for r in history):
    raise RuntimeError('History verification incomplete')
cache = read(PRIVATE / 'windows-cache-removals.json')
installers = read(PRIVATE / 'installer-removals.json')
wsl = read(PRIVATE / 'wsl-cache-removals.json')
archive = read(PUBLIC / 'linux-archive-removal.json')
if not archive or not all(r.get('verified') and r.get('original_deleted') for r in archive):
    raise RuntimeError('Inactive build preservation/removal incomplete')
compaction = read(PUBLIC / 'vhd-compaction.json')
if compaction.get('Win32Status') != 0 or compaction.get('RestartExitCode') != 0:
    raise RuntimeError('VHD compaction or restart incomplete')
after = read(PUBLIC / 'drive-space-after.json')
report = {
    'before_free_gib_approx': {'C': 28.69, 'D': 29.93},
    'after': after,
    'inactive_history': {
        'unique_files_processed': len({r['path'] for r in history}),
        'verified_operations': len(history),
        'allocated_bytes_saved': sum(r['allocated_before'] - r['allocated_after'] for r in history),
        'failed_compression_operations': sum(r['exit_code'] != 0 for r in history),
        'all_content_hashes_unchanged': True,
        'active_task_file_excluded': True,
        'method': 'Windows compact LZX; no transcript deletion or content rewriting'},
    'regenerable_windows_caches': {
        'removed_files': sum(r['RemovedFiles'] for r in cache),
        'removed_logical_bytes': sum(r['RemovedLogicalBytes'] for r in cache),
        'locked_or_skipped': sum(r['LockedOrSkipped'] for r in cache)},
    'duplicate_installers': {
        'removed_files': len(installers['Removed']),
        'removed_bytes': sum(r['bytes'] for r in installers['Removed']),
        'existing_backup_zip_preserved': True,
        'zip_members_and_sources_sha256_verified': True},
    'wsl_caches': {'removed_files': wsl['removed_files'], 'allocated_bytes': wsl['allocated_bytes']},
    'inactive_build_archives': archive,
    'vhd_compaction': compaction,
    'privacy': 'Personal filenames, archive contents and complete inventory remain local and Git-ignored.',
    'preserved': ['current source/build/runtime', 'all task histories', 'personal documents/media/archives',
                  'credentials and account/browser state', 'current and rollback firmware',
                  'factory/calibration/router backups', 'recovery VHD', 'only archived-source copies'],
    'router_contacted': False,
}
PUBLIC.mkdir(parents=True, exist_ok=True)
(PUBLIC / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k: report[k] for k in ['before_free_gib_approx', 'after', 'inactive_history']}, indent=2))
