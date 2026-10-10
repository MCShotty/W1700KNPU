from pathlib import Path
import difflib
import os
import shutil
import subprocess

root = Path('/home/captain/W1700KNPU')
here = root / '.local/npu-cold-tx-20261010'
work = root / '.local/merge-nonoc-20260923'
name = 'drivers/net/ethernet/airoha/airoha_npu.c'
before = here / 'previous-source'
assert not before.exists()
path = before / name
path.parent.mkdir(parents=True)
shutil.copy2(work / 'kernel-upstream' / name, path)
patch = here / 'previous-kernel.patch'
patch.write_bytes(subprocess.check_output(['git', '-C', root, 'show',
    '38bc79d:firmware/overlay/openwrt/target/linux/airoha/patches-6.18/999-w1700k-integrated-npu.patch']))
subprocess.run(['git', 'apply', '--include=' + name, patch], cwd=before,
               env=dict(os.environ, GIT_CEILING_DIRECTORIES=str(before.parent)), check=True)
delta = ['Subject: [PATCH] net: airoha: route retained cold TX and token setup\n\n',
         'Extend the existing checked session without physical retirement claims.\n\n---\n']
delta.extend(difflib.unified_diff(path.read_text().splitlines(True),
    (work / 'kernel-merged' / name).read_text().splitlines(True), fromfile='a/' + name, tofile='b/' + name))
out = here / 'provider-tx.patch'
out.write_text(''.join(delta))
kernel = root / '.build/merged-openwrt/build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/linux-6.18.52'
done = subprocess.run(['perl', kernel / 'scripts/checkpatch.pl', '--strict', '--no-signoff', '--no-tree', out],
                      capture_output=True, text=True)
(here / 'checkpatch.log').write_text(done.stdout + done.stderr)
print(done.stdout + done.stderr)
assert done.returncode == 0 and 'total: 0 errors, 0 warnings, 0 checks' in done.stdout
