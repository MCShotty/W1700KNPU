#!/usr/bin/env python3
"""One-time, non-destructive import from the pre-September-2026 workspace."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
OLD = Path('/mnt/c/Users/captain/Documents/Codex/2026-06-12/i-need-help-wiping-the-nand')
FW = Path('/mnt/c/Users/captain/Downloads/FW/MessingWstuff')
if os.name == 'nt':
    OLD = Path('C:/Users/captain/Documents/Codex/2026-06-12/i-need-help-wiping-the-nand')
    FW = Path('C:/Users/captain/Downloads/FW/MessingWstuff')
BUILD = Path('/home/captain/w1700k-openwrt-build')
SOURCE = BUILD / 'openwrt-w1700k-daybreak20-20260904'
BASE = '28ba2708f1f609bfd134975808b2bc6ed9dc9742'
LUCI_BASE = '506ca606d379dd69e9826b2a5e7e2ab90e6b89a5'
MIGRATION = ROOT / '.migration'
TEXT_EXT = {'.md', '.patch', '.diff', '.c', '.h', '.py', '.ps1', '.sh', '.js',
            '.cjs', '.mjs', '.json', '.java', '.uc', '.dts', '.dtsi', '.mk',
            '.config', '.txt', '.log', '.csv', '.tsv', '.yaml', '.yml', '.toml',
            '.ini', '.html', '.css', '.awk', '.s', '.S', '.xml', '.config', '.seed'}
SKIP_DIRS = {'.git', '.codex', '.agents', 'node_modules', '__pycache__',
             'router-backups', 'recovery', 'staging_dir', 'dl', 'tmp'}
PRIVATE_PATH = re.compile(r'(?i)(private|known_hosts|authorized_keys|credentials|'
                          r'router.?backup|factory\.(bin|img)|calibration|'
                          r'(^|/)shadow$|(^|/)id_(rsa|ed25519)|\.pem$|\.key$|\.ppk$)')
SENSITIVE = re.compile(r'-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----|'
                       r'^\s*(?:option\s+(?:key|password|sae_password)|'
                       r'(?:password|passwd|psk|sae_password|vpn_password|api_key)\s*[=:])\s*[\x22\x27]?[^\s$]{4}|'
                       r'uci\s+set\s+[^\s]+\.(?:key|password)\s*=|'
                       r'\$?password\s*=\s*[\x22\x27][^$\x22\x27]{4,}[\x22\x27]', re.I | re.M)


def git(path, *args, **kwargs):
    return subprocess.check_output(['git', '-C', str(path), *args], **kwargs)


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_json(path, data):
    put(path, (json.dumps(data, indent=2) + '\n').encode())


def source():
    lock = {'schema': 1, 'snapshot': 'Daybreak21-WLAN-DMA-R1-20260905',
            'openwrt': {'url': 'https://github.com/openwrt/openwrt.git', 'base': BASE,
                        'local_head': git(SOURCE, 'rev-parse', 'HEAD').decode().strip()},
            'luci': {'url': 'https://github.com/openwrt/luci.git', 'base': LUCI_BASE,
                     'local_head': git(SOURCE / 'feeds/luci', 'rev-parse', 'HEAD').decode().strip()},
            'feeds': {}, 'mt76': 'be5ce7910521492d4a2e4ce7ee3843680a46c047',
            'kernel': '6.18.44', 'board': 'gemtek,w1700k-ubi',
            'wlan_npu': 'compiled out; Ethernet offload is separate'}
    for label, src, base in [('openwrt', SOURCE, BASE), ('luci', SOURCE / 'feeds/luci', LUCI_BASE)]:
        patch = git(src, 'diff', '--binary', '--full-index', base, '--', '.')
        put(ROOT / f'firmware/patches/{label}.patch', patch)
        changed = git(src, 'diff', '--name-only', '-z', base).decode().split('\0')
        extras = git(src, 'ls-files', '--others', '--exclude-standard', '-z').decode().split('\0')
        files = []
        for name in sorted(set(filter(None, changed + extras))):
            path = src / name
            if not path.is_file():
                continue
            if PRIVATE_PATH.search(name):
                raise RuntimeError(f'Protected path in source delta: {name}')
            files.append({'path': name, 'sha256': digest(path), 'mode': oct(path.stat().st_mode & 0o777)})
            if name in extras:
                dest = ROOT / f'firmware/overlay/{label}' / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest)
        lock[label]['changed_files'] = files
    for feed in (SOURCE / 'feeds').iterdir():
        if (feed / '.git').exists():
            lock['feeds'][feed.name] = {
                'commit': git(feed, 'rev-parse', 'HEAD').decode().strip(),
                'url': git(feed, 'remote', 'get-url', 'origin').decode().strip(),
                'dirty': bool(git(feed, 'status', '--porcelain'))}
    put(ROOT / 'firmware/build.config', (SOURCE / '.config').read_bytes())
    put(ROOT / 'firmware/feeds.conf.default', (SOURCE / 'feeds.conf.default').read_bytes())
    write_json(ROOT / 'firmware/source-lock.json', lock)
    for name in ['W1700K_STOCK_PORT_CURRENT_REFERENCE.md', 'W1700K_STOCK_PORT_LEDGER.md',
                 'W1700K_STOCK_PORT_LOGGING_SESSION_20260625.md']:
        if not (ROOT / 'docs' / name).exists():
            put(ROOT / 'docs' / name, (OLD / 'work' / name).read_bytes())
    # Retain the final separate legacy candidate as evidence, not active patches.
    legacy = BUILD / 'mt76-patch85-integration-daybreak19-r2-20260904'
    if legacy.exists():
        put(ROOT / 'research/legacy-npu/git-log.txt', git(legacy, 'log', '-12', '--format=fuller'))
        put(ROOT / 'research/legacy-npu/daybreak15-to-daybreak19.patch',
            git(legacy, 'diff', '--binary', '--full-index', '0f4f1e6'))
        put(ROOT / 'research/legacy-npu/working.patch', git(legacy, 'diff', '--binary', 'HEAD'))
    print('Exported cumulative source deltas, overlays, pins and trackers', flush=True)


def history():
    stage = MIGRATION / 'history'
    rows, skipped = [], []
    for prefix, root in [('workspace', OLD), ('firmware-inputs', FW)]:
        for folder, dirs, names in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.endswith('.rep'))
            for name in sorted(names):
                path = Path(folder) / name
                rel = path.relative_to(root)
                label = str(Path(prefix) / rel)
                if path.is_symlink() or PRIVATE_PATH.search(str(rel)):
                    skipped.append({'path': label, 'reason': 'protected path'})
                    continue
                if path.suffix not in TEXT_EXT and name not in {'Makefile', 'Config.in', '.config', 'series'}:
                    continue
                if path.stat().st_size > 100 * 1024 * 1024:
                    skipped.append({'path': label, 'reason': 'large generated text retained locally'})
                    continue
                data = path.read_bytes()
                try:
                    text = data.decode('utf-8-sig')
                except UnicodeError:
                    skipped.append({'path': label, 'reason': 'non-UTF8 retained locally'})
                    continue
                if '\0' in text:
                    continue
                if SENSITIVE.search(text):
                    skipped.append({'path': label, 'reason': 'credential-pattern quarantine; original retained'})
                    continue
                target = stage / label
                if target.exists():
                    if target.read_bytes() != data:
                        raise RuntimeError(f'Staged history changed: {label}')
                else:
                    put(target, data)
                rows.append({'path': label, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    write_json(MIGRATION / 'history-inventory.json', rows)
    write_json(MIGRATION / 'withheld.json', skipped)
    print(json.dumps({'history_files': len(rows), 'bytes': sum(r['bytes'] for r in rows),
                      'quarantined': len(skipped)}), flush=True)


def pack():
    stage = MIGRATION / 'history'
    findings_path = MIGRATION / 'gitleaks-history.json'
    if not findings_path.exists():
        raise RuntimeError('Run the credential scan before packing history')
    findings = json.loads(findings_path.read_text()) or []
    for finding in findings:
        p = Path(finding['File'])
        if not p.is_absolute():
            p = ROOT / p
        p = p.resolve()
        if not p.is_relative_to(stage.resolve()):
            raise RuntimeError('Scanner path outside stage')
        target = MIGRATION / 'quarantine' / p.relative_to(stage)
        if p.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            p.rename(target)
        elif not target.is_file():
            raise RuntimeError(f'Scanner finding path missing: {p}')
    inventory = []
    dest = ROOT / 'research/history-20260905.tar.gz'
    dest.parent.mkdir(parents=True, exist_ok=True)
    canonical = {}
    with tarfile.open(dest, 'w:gz', compresslevel=6) as archive:
        for p in sorted(stage.rglob('*')):
            if not p.is_file():
                continue
            rel = p.relative_to(stage).as_posix()
            sha = digest(p)
            info = archive.gettarinfo(p, arcname=rel)
            identity = (sha, info.mode)
            if identity in canonical:
                info.type = tarfile.LNKTYPE
                info.linkname = canonical[identity]
                info.size = 0
                archive.addfile(info)
            else:
                canonical[identity] = rel
                with p.open('rb') as f:
                    archive.addfile(info, f)
            inventory.append({'path': rel, 'bytes': p.stat().st_size, 'sha256': sha})
    write_json(ROOT / 'research/history-manifest.json', inventory)
    write_json(ROOT / 'docs/migration/history-privacy-summary.json', {
        'files_archived': len(inventory), 'bytes_archived_uncompressed': sum(r['bytes'] for r in inventory),
        'unique_file_contents_and_modes': len(canonical),
        'archive_bytes': dest.stat().st_size, 'archive_sha256': digest(dest),
        'scanner': 'gitleaks 8.30.1, default rules, redacted reporting',
        'quarantined_scanner_files': len({f['File'] for f in findings}),
        'pre_scan_withheld_files': len(json.loads((MIGRATION / 'withheld.json').read_text())),
        'originals': 'Retained locally; no credential-bearing original uploaded or deleted'})
    print(f'Archived {len(inventory)} files into {dest.stat().st_size} bytes', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['source', 'history', 'pack'])
    args = parser.parse_args()
    MIGRATION.mkdir(parents=True, exist_ok=True)
    globals()[args.phase]()
