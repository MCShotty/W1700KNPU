#!/usr/bin/env python3
"""Stage the pinned non-OC source upgrade without overwriting the old build."""
import argparse
import difflib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

from prepare_build import checkout

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.local/merge-nonoc-20260923'
OLD = ROOT / '.build/openwrt'
DEST = ROOT / '.build/merged-openwrt'
RELEASE = 'ubi2_2026.09.23_r36536-288d79449f'
UPSTREAM = '288d79449f622a37c727cb12e81e85dba822aecb'
URL = 'https://github.com/OpenWRT-fanboy/OpenW1700k.git'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def original(tree, revision, name):
    done = subprocess.run(['git', '-C', str(tree), 'show', revision + ':' + name],
                          capture_output=True)
    if done.returncode:
        exists = subprocess.run(['git', '-C', str(tree), 'cat-file', '-e', revision + ':' + name],
                                capture_output=True)
        assert exists.returncode
        return None
    return done.stdout


def merge(label, tree, source, lock, ancestor):
    rows = []
    for entry in lock[label]['changed_files']:
        name = entry['path']
        ours_path = source / name
        assert sha(ours_path) == entry['sha256'], name
        ours = ours_path.read_bytes()
        base = original(source, ancestor, name)
        path = tree / name
        theirs = path.read_bytes() if path.exists() else None
        evidence = WORK / 'merge-inputs' / label / name
        evidence.parent.mkdir(parents=True, exist_ok=True)
        for suffix, contents in (('ours', ours), ('base', base), ('theirs', theirs)):
            if contents is not None:
                evidence.with_name(evidence.name + '.' + suffix).write_bytes(contents)
        status = 'merged'
        if theirs == ours:
            result, status = ours, 'already_present'
        elif theirs == base or theirs is None and base is None:
            result = ours
        elif ours == base:
            result, status = theirs, 'upstream_only'
        elif base is None:
            result, status = theirs, 'add_add_review'
        elif theirs is None:
            result, status = None, 'delete_modify_review'
        else:
            args = ['git', 'merge-file', '-p', '--diff3', '-L', 'nonoc', '-L', 'old-base', '-L', 'ours',
                    str(evidence) + '.theirs', str(evidence) + '.base', str(evidence) + '.ours']
            done = subprocess.run(args, capture_output=True)
            assert done.returncode in range(128), done.stderr.decode(errors='replace')
            result = done.stdout
            if done.returncode:
                status = 'conflict'
        # Colliding patches must be reconciled/renumbered, never overwritten.
        if result is not None and status not in ('add_add_review', 'delete_modify_review'):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(result)
            path.chmod(int(entry['mode'], 8))
        rows.append(dict(path=name, status=status, ours_sha256=entry['sha256'],
                         result_sha256=sha(path) if path.exists() else None))
    (WORK / (label + '-merge.json')).write_text(json.dumps(rows, indent=2) + '\n')
    print(json.dumps(dict(label=label, files=len(rows), reviews=[r for r in rows
                     if r['status'] in ('conflict', 'add_add_review', 'delete_modify_review')])), flush=True)


def main():
    options = argparse.ArgumentParser()
    options.add_argument('phase', choices=['openwrt', 'luci', 'feeds', 'builder', 'configure', 'config',
                                         'mt76', 'kernel', 'export-mt76', 'export-kernel', 'builder-files'])
    options.add_argument('--resume-fetch', action='store_true')
    options.add_argument('--luci-commit')
    args = options.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    snapshot = WORK / 'before'
    if args.phase == 'openwrt':
        if not args.resume_fetch:
            assert not snapshot.exists() and not DEST.exists()
            snapshot.mkdir()
            for name in ('source-lock.json', 'build.config'):
                shutil.copy2(ROOT / 'firmware' / name, snapshot / name)
            shutil.copytree(ROOT / 'firmware/patches', snapshot / 'patches')
            shutil.copytree(ROOT / 'firmware/overlay', snapshot / 'overlay')
        lock = json.loads((snapshot / 'source-lock.json').read_text())
        if not DEST.exists():
            checkout(URL, UPSTREAM, DEST)
        else:
            assert args.resume_fetch and not (WORK / 'openwrt-merge.json').exists()
            assert subprocess.check_output(['git', '-C', str(DEST), 'rev-parse', 'HEAD'], text=True).strip() == UPSTREAM
        merge('openwrt', DEST, OLD, lock, lock['openwrt']['base'])
        metadata = dict(release=RELEASE, url=URL, commit=UPSTREAM, destination=str(DEST),
                        old_lock_sha256=sha(snapshot / 'source-lock.json'))
        (WORK / 'source.json').write_text(json.dumps(metadata, indent=2) + '\n')
    elif args.phase == 'luci':
        assert args.luci_commit and len(args.luci_commit) == 40
        lock = json.loads((snapshot / 'source-lock.json').read_text())
        path = DEST / 'feeds/luci'
        if not path.exists():
            checkout('https://github.com/openwrt/luci.git', args.luci_commit, path)
        else:
            assert args.resume_fetch and not (WORK / 'luci-merge.json').exists()
            assert subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip() == args.luci_commit
        merge('luci', path, OLD / 'feeds/luci', lock, lock['luci']['base'])
    elif args.phase == 'builder':
        checkout('https://github.com/w1700k/builds.git',
                 '9449e4ca242ab30278df20940d6654ddc1c102e8', WORK / 'builder')
    elif args.phase == 'builder-files':
        source = WORK / 'builder/user/default/files'
        for name in ('etc', 'www'):
            shutil.copytree(source / name, DEST / 'files' / name, dirs_exist_ok=True)
        overview = DEST / 'feeds/luci/applications/luci-app-attendedsysupgrade/htdocs/luci-static/resources/view/attendedsysupgrade/overview.js'
        shutil.copy2(source / 'overview.js', overview)
        patch = source / '998-single-wiphy.patch'
        done = subprocess.run(['patch', '--batch', '--forward', '-p1', '-i', str(patch)],
                              cwd=DEST / 'feeds/luci/modules/luci-mod-status', capture_output=True, text=True)
        (WORK / 'builder-single-wiphy.log').write_text(done.stdout + done.stderr)
        assert done.returncode == 0, done.stdout + done.stderr
    elif args.phase in ('configure', 'config'):
        values = {}
        for path in (snapshot / 'build.config', WORK / 'builder/user/ubi2/config.diff'):
            for line in path.read_text().splitlines():
                match = re.fullmatch(r'(CONFIG_[^\s=]+)=(.*)', line)
                disabled = re.fullmatch(r'# (CONFIG_[^\s=]+) is not set', line)
                if match:
                    values[match[1]] = match[2]
                elif disabled:
                    values[disabled[1]] = 'n'
        values.update({
            'CONFIG_IMAGEOPT': 'y',
            'CONFIG_VERSIONOPT': 'y',
            'CONFIG_VERSION_CODE': '"r36536-merged-288d79449f"',
            'CONFIG_VERSION_FILENAMES': 'n',
            'CONFIG_VERSION_CODE_FILENAMES': 'n',
            'CONFIG_MT76_AIROHA_NPU': 'y',
            'CONFIG_ALL_KMODS': 'n',
            'CONFIG_PACKAGE_wpad-basic-mbedtls': 'n',
            'CONFIG_PACKAGE_wpad-mbedtls': 'n',
            'CONFIG_PACKAGE_wpad-openssl': 'y',
            'CONFIG_PACKAGE_apk-mbedtls': 'n',
            'CONFIG_PACKAGE_apk-openssl': 'y',
            'CONFIG_PACKAGE_luci-ssl': 'n',
            'CONFIG_PACKAGE_luci-ssl-openssl': 'y',
            'CONFIG_PACKAGE_libustream-mbedtls': 'n',
            'CONFIG_PACKAGE_libustream-openssl': 'y',
            'CONFIG_PACKAGE_px5g-mbedtls': 'n',
            'CONFIG_GOLANG_EXTERNAL_BOOTSTRAP_ROOT': '""',
            'CONFIG_GOLANG_BUILD_BOOTSTRAP': 'y',
        })
        config = '\n'.join('# ' + key + ' is not set' if value == 'n' else key + '=' + value
                           for key, value in sorted(values.items())) + '\n'
        (DEST / '.config').write_text(config)
        if not (DEST / 'dl').exists():
            (DEST / 'dl').symlink_to(OLD / 'dl', target_is_directory=True)
        # Prepare the complete upstream kernel before rebasing the provider delta.
        for name in ('926-net-airoha-npu-protect-inflight-mailbox-buffer.patch',
                     '927-net-airoha-npu-validate-memory-before-wlan.patch'):
            path = DEST / 'target/linux/airoha/patches-6.18' / name
            if path.exists():
                saved = WORK / 'pending-provider' / name
                saved.parent.mkdir(exist_ok=True)
                shutil.move(path, saved)
        env = dict(os.environ, PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin')
        commands = [['make', 'defconfig']]
        if args.phase == 'configure':
            commands = [['./scripts/feeds', 'update', '-i'], ['./scripts/feeds', 'install', '-a']] + commands
        for command in commands:
            log = WORK / ('configure-' + command[0].split('/')[-1] + '-' + command[1] + '.log')
            with log.open('w') as output:
                done = subprocess.run(command, cwd=DEST, env=env, stdout=output, stderr=subprocess.STDOUT)
            assert done.returncode == 0, log.read_text()[-4000:]
        actual = (DEST / '.config').read_text()
        for key in ('TARGET_airoha_an7581_DEVICE_gemtek_w1700k-ubi', 'MT76_AIROHA_NPU',
                    'PACKAGE_kmod-mt7996e', 'PACKAGE_luci-app-sqm', 'PACKAGE_softethervpn5-server',
                    'PACKAGE_adblock', 'PACKAGE_luci-app-airoha-flowsense', 'PACKAGE_luci-app-airoha-npu'):
            assert 'CONFIG_' + key + '=y\n' in actual, key
        assert 'CONFIG_VERSION_CODE="r36536-merged-288d79449f"\n' in actual
        print(json.dumps(dict(configured=str(DEST), kernel='6.18.52', npu_selected=True)), flush=True)
    elif args.phase == 'mt76':
        upstream = WORK / 'mt76-upstream'
        if not upstream.exists():
            checkout('https://github.com/OpenWRT-fanboy/mt76-firmware.git',
                     '01367e60db433534ad0aa3d3b6c886de8cb7d44c', upstream)
        else:
            assert args.resume_fetch
            assert subprocess.check_output(['git', '-C', str(upstream), 'rev-parse', 'HEAD'], text=True).strip() == '01367e60db433534ad0aa3d3b6c886de8cb7d44c'
        package = DEST / 'package/kernel/mt76/patches'
        ours = sorted(package.glob('00[123]-*.patch'))
        assert len(ours) == 3
        ours += sorted((ROOT / 'research/checkpoints').glob('*/00[4-9]-*.patch'))
        assert len(ours) == 9
        for patch in sorted(package.glob('*.patch')):
            if patch in ours:
                continue
            log = WORK / ('mt76-' + patch.name + '.log')
            if args.resume_fetch:
                assert log.exists() and 'FAILED' not in log.read_text() and 'patching file' in log.read_text()
                continue
            done = subprocess.run(['patch', '--batch', '--forward', '-p1', '-i', str(patch)],
                                  cwd=upstream, capture_output=True, text=True)
            log.write_text(done.stdout + done.stderr)
            assert done.returncode == 0, done.stdout + done.stderr
        archive = OLD / 'dl/mt76-2026.09.01~be5ce791.tar.zst'
        old_make = (OLD / 'package/kernel/mt76/Makefile').read_text()
        expected = re.search(r'^PKG_MIRROR_HASH:=(\w+)$', old_make, re.M)[1]
        assert sha(archive) == expected
        zstd = shutil.which('zstd') or str(OLD / 'staging_dir/host/bin/zstd')
        raw = subprocess.check_output([zstd, '-dc', str(archive)])
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as tar:
            tar.extractall(WORK / 'mt76-original', filter='data')
        base = WORK / 'mt76-original/mt76-2026.09.01~be5ce791'
        current = ROOT / '.local/npu-linked-modules/verified/mt76-2026.09.01~be5ce791'
        merged = WORK / 'mt76-merged'
        shutil.copytree(upstream, merged, ignore=shutil.ignore_patterns('.git', '*.orig', '*.rej'))
        names = sorted({match for patch in ours for match in
                        re.findall(r'^\+\+\+ b/([^\n]+)$', patch.read_text(), re.M)})
        rows = []
        for name in names:
            a, b, c = merged / name, base / name, current / name
            assert a.is_file() and b.is_file() and c.is_file(), name
            done = subprocess.run(['git', 'merge-file', '-p', '--diff3', '-L', 'nonoc', '-L', 'old-mt76', '-L', 'ours',
                                   str(a), str(b), str(c)], capture_output=True)
            assert 0 <= done.returncode < 128, done.stderr.decode(errors='replace')
            a.write_bytes(done.stdout)
            rows.append(dict(path=name, status='conflict' if done.returncode else 'merged',
                             base_sha256=sha(b), ours_sha256=sha(c), result_sha256=sha(a)))
        (WORK / 'mt76-merge.json').write_text(json.dumps(rows, indent=2) + '\n')
        print(json.dumps(dict(mt76_files=len(rows), reviews=[r for r in rows if r['status'] == 'conflict'])), flush=True)
    elif args.phase == 'kernel':
        old = ROOT / '.local/npu-provider-kernel-link/verified/linux-6.18.44'
        new = DEST / 'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/linux-6.18.52'
        names = ('drivers/net/ethernet/airoha/airoha_npu.c',
                 'include/linux/soc/airoha/airoha_offload.h', 'drivers/clk/clk-en7523.c')
        for label, source in (('kernel-old-base', old), ('kernel-ours', old), ('kernel-upstream', new),
                              ('kernel-merged', new)):
            for name in names:
                dest = WORK / label / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                assert not dest.exists()
                shutil.copy2(source / name, dest)
        reverse = [ROOT / 'research/checkpoints/2026-09-16-npu-host-lifetime/929-net-airoha-npu-irq-work-lifetime.patch',
                   ROOT / 'research/checkpoints/2026-09-14-npu-control-v2/928-net-airoha-npu-bidirectional-control.patch',
                   WORK / 'pending-provider/927-net-airoha-npu-validate-memory-before-wlan.patch',
                   WORK / 'pending-provider/926-net-airoha-npu-protect-inflight-mailbox-buffer.patch']
        for patch in reverse:
            done = subprocess.run(['patch', '--batch', '--fuzz=0', '-R', '-p1', '-i', str(patch)],
                                  cwd=WORK / 'kernel-old-base', capture_output=True, text=True)
            (WORK / ('reverse-' + patch.name + '.log')).write_text(done.stdout + done.stderr)
            assert done.returncode == 0, done.stdout + done.stderr
        reset = ROOT / 'research/checkpoints/2026-09-23-npu-reset-control/930-clk-en7523-preserve-reset-errors.patch'
        subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(reset)],
                       cwd=WORK / 'kernel-ours', check=True)
        rows = []
        for name in names:
            a, b, c = (WORK / label / name for label in ('kernel-merged', 'kernel-old-base', 'kernel-ours'))
            done = subprocess.run(['git', 'merge-file', '-p', '--diff3', '-L', 'nonoc', '-L', 'old-base', '-L', 'ours',
                                   str(a), str(b), str(c)], capture_output=True)
            assert 0 <= done.returncode < 128, done.stderr.decode(errors='replace')
            a.write_bytes(done.stdout)
            rows.append(dict(path=name, status='conflict' if done.returncode else 'merged',
                             base_sha256=sha(b), ours_sha256=sha(c), result_sha256=sha(a)))
        (WORK / 'kernel-merge.json').write_text(json.dumps(rows, indent=2) + '\n')
        print(json.dumps(dict(kernel_files=len(rows), reviews=[r for r in rows if r['status'] == 'conflict'])), flush=True)
    elif args.phase.startswith('export-'):
        kind = args.phase.removeprefix('export-')
        base, merged = WORK / (kind + '-upstream'), WORK / (kind + '-merged')
        if kind == 'mt76':
            control = ('control-client.c', 'control-v2-client.c', 'linux-control.c',
                       'control-client.h', 'control-v2.h', 'linux-control.h',
                       'admission.h', 'barrier.h', 'kernel-include/stdint.h')
            component_sources = []
            for name in control:
                path = merged / 'w1700k' / name
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / 'firmware/npu' / name, path)
                packaged = DEST / 'package/kernel/mt76/w1700k' / name
                packaged.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, packaged)
                component_sources.append(dict(tree='openwrt', source='firmware/npu/' + name,
                    destination='package/kernel/mt76/w1700k/' + name, sha256=sha(path), mode='0o644'))
            (WORK / 'component-sources.json').write_text(json.dumps(component_sources, indent=2) + '\n')
            names = {r['path'] for r in json.loads((WORK / 'mt76-merge.json').read_text())}
            names.add('Makefile')
            patch = DEST / 'package/kernel/mt76/patches/900-w1700k-integrated-npu.patch'
            for old in sorted(patch.parent.glob('00[123]-*.patch')):
                saved = WORK / 'merged-original-patches' / old.name
                saved.parent.mkdir(exist_ok=True)
                shutil.move(old, saved)
        else:
            names = {r['path'] for r in json.loads((WORK / 'kernel-merge.json').read_text())}
            patch = DEST / 'target/linux/airoha/patches-6.18/999-w1700k-integrated-npu.patch'
        result = ['Subject: [PATCH] W1700K: merge NPU ownership, recovery and control changes\n\n',
                  'Rebased onto the pinned non-OC source. This is the experimental\n',
                  'build input; compilation is not a physical drain or recovery proof.\n\n---\n']
        for name in sorted(names):
            target = merged / name
            if not target.exists():
                continue
            text = target.read_text()
            assert not re.search(r'^(<<<<<<<|=======|>>>>>>>|\|\|\|\|\|\|\|)', text, re.M), name
            original = (base / name).read_text() if (base / name).exists() else ''
            result += difflib.unified_diff(original.splitlines(True), text.splitlines(True),
                                           fromfile='a/' + name if original else '/dev/null', tofile='b/' + name)
        patch.write_text(''.join(result))
        print(json.dumps(dict(patch=str(patch), sha256=sha(patch))), flush=True)
    else:
        pins_path = WORK / 'feed-pins.json'
        pins = json.loads(pins_path.read_text()) if pins_path.exists() else {}
        for name in ('packages', 'routing', 'video', 'telephony'):
            url = 'https://github.com/openwrt/' + name + '.git'
            if name not in pins:
                commit = subprocess.check_output(['git', 'ls-remote', url, 'HEAD'], text=True).split()[0]
                assert len(commit) == 40
                pins[name] = dict(url=url, commit=commit, dirty=False)
                pins_path.write_text(json.dumps(pins, indent=2) + '\n')
            dest = DEST / 'feeds' / name
            if not dest.exists():
                checkout(url, pins[name]['commit'], dest)
            else:
                assert subprocess.check_output(['git', '-C', str(dest), 'rev-parse', 'HEAD'], text=True).strip() == pins[name]['commit']
        pins['luci'] = dict(url='https://github.com/openwrt/luci.git',
                            commit=subprocess.check_output(['git', '-C', str(DEST / 'feeds/luci'),
                                                            'rev-parse', 'HEAD'], text=True).strip(), dirty=True)
        pins_path.write_text(json.dumps(pins, indent=2) + '\n')


if __name__ == '__main__':
    main()
