import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

root = Path('/home/captain/W1700KNPU')
sys.path.insert(0, str(root / 'tests/npu'))
import test_npu_firmware_loader as loader
here = root / '.local/npu-cold-indication-20261010'
work = root / '.local/merge-nonoc-20260923'
build = root / '.build/merged-openwrt/build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581'
kernel = build / 'linux-6.18.52'
mt76 = build / 'mt76-2026.09.01~01367e60'
after_path = work / 'kernel-merged/drivers/net/ethernet/airoha/airoha_npu.c'
after = after_path.read_text()
before = (here / 'previous-source/drivers/net/ethernet/airoha/airoha_npu.c').read_text()
function = loader.extract.function
names = ('airoha_npu_wlan_msg_get', 'airoha_npu_wlan_msg_send', 'airoha_npu_wlan_init_memory')
same = {name: function(after, name) == function(before, name) for name in names}
assert all(same.values())
assert 'airoha_npu_wlan_msg_get(npu, 0, WLAN_FUNC_GET_WAIT_NPU_VERSION' in function(after, 'airoha_npu_start_firmware')
inputs = {}
def tracked(path):
    inputs[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
tracked(after_path)
tracked(Path(__file__))
rows = []
for kind, current, patch in (
    ('kernel', kernel, root / 'firmware/overlay/openwrt/target/linux/airoha/patches-6.18/999-w1700k-integrated-npu.patch'),
    ('mt76', mt76, root / 'firmware/overlay/openwrt/package/kernel/mt76/patches/900-w1700k-integrated-npu.patch')):
    names = (('drivers/net/ethernet/airoha/airoha_npu.c', 'drivers/net/ethernet/airoha/Makefile',
              'include/linux/soc/airoha/airoha_offload.h') if kind == 'kernel' else
             sorted(set(re.findall(r'^\+\+\+ b/(.+)$', patch.read_text(), re.M))))
    destination = here / ('replayed-' + kind)
    assert not destination.exists()
    destination.mkdir()
    for name in names:
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        original = work / (kind + '-upstream') / name
        tracked(original)
        shutil.copy2(original, path)
    tracked(patch)
    subprocess.run(['git', 'apply', *['--include=' + name for name in names], patch], cwd=destination,
                   env=dict(os.environ, GIT_CEILING_DIRECTORIES=str(destination.parent)), check=True)
    for name in names:
        assert (destination / name).read_bytes() == (current / name).read_bytes(), (kind, name)
        assert (destination / name).read_bytes() == (work / (kind + '-merged') / name).read_bytes(), (kind, name)
        tracked(current / name)
        tracked(work / (kind + '-merged') / name)
        rows.append(dict(kind=kind, path=name, sha256=loader.sha(current / name)))
lock_path = root / 'firmware/source-lock.json'
tracked(lock_path)
lock = json.loads(lock_path.read_text())
for entry in lock['component_sources']:
    source = root / entry['source']
    prepared = kernel / entry['destination'].removeprefix('target/linux/airoha/files-6.18/')
    assert source.read_bytes() == prepared.read_bytes() and loader.sha(source) == entry['sha256']
    tracked(source)
    tracked(prepared)
result = dict(passed=True, exact_raw_functions_unchanged=same, early_probe_raw=True,
              nested_source_replay=rows, canonical_components=len(lock['component_sources']), inputs=inputs,
              limits=['Exact cumulative patch reconstruction and prepared compiled-source correspondence, not physical transport/PCI ownership or clients.'])
(here / 'static-dispatch.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(dict(passed=True, nested_files=len(rows), components=len(lock['component_sources']))))
