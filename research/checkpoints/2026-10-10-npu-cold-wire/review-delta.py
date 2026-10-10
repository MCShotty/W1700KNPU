from pathlib import Path
import difflib
import hashlib
import os
import shutil
import subprocess

root = Path('/home/captain/W1700KNPU')
here = root / '.local/npu-cold-wire-20261010'
work = root / '.local/merge-nonoc-20260923'
before = here / 'previous-source'
names = ('drivers/net/ethernet/airoha/airoha_npu.c', 'drivers/net/ethernet/airoha/Makefile')
for name in names:
    path = before / name
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(work / 'kernel-upstream' / name, path)
patch = here / 'previous-kernel.patch'
patch.write_bytes(subprocess.check_output(['git', '-C', root, 'show', 'HEAD:firmware/overlay/openwrt/target/linux/airoha/patches-6.18/999-w1700k-integrated-npu.patch']))
subprocess.run(['git', 'apply', *['--include=' + name for name in names], str(patch)], cwd=before,
               env=dict(os.environ, GIT_CEILING_DIRECTORIES=str(before.parent)), check=True)
delta = ['Subject: [PATCH] net: airoha: route checked initial cold commands\n\n',
         'Reuse the provider session and serialize the dedicated cold envelope.\n',
         'No DMA retirement, physical containment or full offload is implied.\n\n---\n']
for name in names:
    delta.extend(difflib.unified_diff((before / name).read_text().splitlines(True),
        (work / 'kernel-merged' / name).read_text().splitlines(True), fromfile='a/' + name, tofile='b/' + name))
for name in ('linux-control.c', 'linux-control.h'):
    old = subprocess.check_output(['git', '-C', root, 'show', 'HEAD:firmware/npu/' + name]).decode()
    delta.extend(difflib.unified_diff(old.splitlines(True), (root / 'firmware/npu' / name).read_text().splitlines(True),
                 fromfile='a/drivers/net/ethernet/airoha/w1700k/' + name,
                 tofile='b/drivers/net/ethernet/airoha/w1700k/' + name))
(here / 'provider-cold-wire.patch').write_text(''.join(delta))
kernel = root / '.local/npu-provider-kernel-link/verified/linux-6.18.44'
done = subprocess.run(['perl', kernel / 'scripts/checkpatch.pl', '--strict', '--no-signoff', '--no-tree',
                       here / 'provider-cold-wire.patch'], capture_output=True, text=True)
(here / 'checkpatch.log').write_text(done.stdout + done.stderr)
print(done.stdout + done.stderr)
assert done.returncode == 0
backup = here / 'pre-world-image'
backup.mkdir()
for path in sorted((root / '.build/merged-openwrt/bin/targets/airoha/an7581').iterdir()):
    if path.is_file():
        if path.name.endswith('-sysupgrade.itb'):
            assert hashlib.sha256(path.read_bytes()).hexdigest() == '6a7dc41ebcec3070231764e8ba226cef29b7b5383ba1ed5e5b7c9cf0e639461a'
        shutil.copy2(path, backup / path.name)
        assert path.read_bytes() == (backup / path.name).read_bytes()
print('Previous verified complete image preserved.')
