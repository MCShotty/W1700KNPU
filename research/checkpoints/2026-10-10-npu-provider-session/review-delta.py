from pathlib import Path
import difflib
import hashlib
import os
import shutil
import subprocess

root = Path('/home/captain/W1700KNPU')
dest = root / '.local/npu-provider-session-20261010'
work = root / '.local/merge-nonoc-20260923'
relative = 'drivers/net/ethernet/airoha/airoha_npu.c'
before = dest / 'previous-source'
(before / relative).parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(work / 'kernel-upstream' / relative, before / relative)
patch = dest / 'previous-kernel.patch'
patch.write_bytes(subprocess.check_output(['git', '-C', root, 'show', 'HEAD:firmware/overlay/openwrt/target/linux/airoha/patches-6.18/999-w1700k-integrated-npu.patch']))
subprocess.run(['git', 'apply', '--include=' + relative, str(patch)], cwd=before,
               env=dict(os.environ, GIT_CEILING_DIRECTORIES=str(before.parent)), check=True)
delta = ['Subject: [PATCH] net: airoha: own the initial held WLAN control session\n\n',
         'Bind the Linux client to the loader identity and existing bootstrap prefix.\n',
         'Consume one attempt without authorizing physical drain, release or rearm.\n\n---\n']
for name in (relative, 'drivers/net/ethernet/airoha/Makefile'):
    old = before / name if name == relative else work / 'kernel-upstream' / name
    new = work / 'kernel-merged' / name
    delta.extend(difflib.unified_diff(old.read_text().splitlines(True), new.read_text().splitlines(True),
                                    fromfile='a/' + name, tofile='b/' + name))
(dest / 'provider-session.patch').write_text(''.join(delta))
backup = dest / 'pre-world-image'
backup.mkdir()
images = root / '.build/merged-openwrt/bin/targets/airoha/an7581'
for path in sorted(images.iterdir()):
    if path.is_file():
        if path.name.endswith('-sysupgrade.itb'):
            assert hashlib.sha256(path.read_bytes()).hexdigest() == 'b0400eaa873beeb309fc10e7376255f89cefb7c1f986096863916f5a4ee222b6'
        shutil.copy2(path, backup / path.name)
        assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256((backup / path.name).read_bytes()).digest()
print('Preserved previous complete image files.')
kernel = root / '.local/npu-provider-kernel-link/verified/linux-6.18.44'
done = subprocess.run(['perl', kernel / 'scripts/checkpatch.pl', '--strict', '--no-signoff', '--no-tree',
                       dest / 'provider-session.patch'], capture_output=True, text=True)
(dest / 'checkpatch.log').write_text(done.stdout + done.stderr)
print(done.stdout + done.stderr)
assert done.returncode == 0
