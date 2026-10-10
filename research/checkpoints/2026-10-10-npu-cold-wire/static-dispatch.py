import json
from pathlib import Path
import sys

root = Path('/home/captain/W1700KNPU')
sys.path.insert(0, str(root / 'tests/npu'))
import test_npu_firmware_loader as loader
here = root / '.local/npu-cold-wire-20261010'
after = (root / '.local/merge-nonoc-20260923/kernel-merged/drivers/net/ethernet/airoha/airoha_npu.c').read_text()
before = (here / 'previous-source/drivers/net/ethernet/airoha/airoha_npu.c').read_text()
function = loader.extract.function
names = ('airoha_npu_wlan_msg_get', 'airoha_npu_wlan_msg_send', 'airoha_npu_wlan_init_memory')
same = {name: function(after, name) == function(before, name) for name in names}
assert all(same.values())
launch = function(after, 'airoha_npu_start_firmware')
assert 'airoha_npu_wlan_msg_get(npu, 0, WLAN_FUNC_GET_WAIT_NPU_VERSION' in launch
assert 'airoha_npu_wlan_msg_get_session' not in launch
probe = function(after, 'airoha_npu_probe')
assert probe.index('airoha_npu_start_firmware') < probe.index('platform_set_drvdata')
getter = function(after, 'airoha_npu_wlan_msg_get_session')
assert 'priv->checked_pair && READ_ONCE(priv->wlan_session_attempted)' in getter
assert 'return airoha_npu_wlan_msg_get(npu,' in getter
result = dict(passed=True, exact_raw_functions_unchanged=same,
              early_probe_calls_raw_directly=True, checked_ops_use_cold_after_attempt=True,
              limits=['Source dispatch/boot order plus actual boot regression, not physical version transport or legacy hardware acceptance.'])
(here / 'static-dispatch.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
