import json
from pathlib import Path
import sys

root = Path('/home/captain/W1700KNPU')
sys.path.insert(0, str(root / 'tests/npu'))
import test_npu_firmware_loader as loader
here = root / '.local/npu-provider-session-20261010'
before = (here / 'previous-source/drivers/net/ethernet/airoha/airoha_npu.c').read_text()
after = (root / '.local/merge-nonoc-20260923/kernel-merged/drivers/net/ethernet/airoha/airoha_npu.c').read_text()
names = ('airoha_npu_wlan_init_memory', 'airoha_npu_wlan_cmd_with_retry', 'airoha_npu_wlan_msg_send')
same = {name: loader.extract.function(before, name) == loader.extract.function(after, name) for name in names}
assert all(same.values())
wrapper = loader.extract.function(after, 'airoha_npu_wlan_init_session')
guard = 'if (!priv->checked_pair)\n\t\treturn airoha_npu_wlan_init_memory(npu);'
assert wrapper.count(guard) == 1 and wrapper.index(guard) < wrapper.index('mutex_lock(')
(here / 'legacy-static.json').write_text(json.dumps(dict(passed=True, exact_unchanged_functions=same,
    scope='Exact source comparison and checked dispatch branch; not physical legacy runtime acceptance.'), indent=2) + '\n')
request = dict(model='jev-1.13.0', state=dict(wrapper_prefix=wrapper.split('mutex_lock(', 1)[0],
    exact_comparison=same, previous_scope='Preservation of the source call path for unmarked providers, not hardware acceptance.'),
    questions=dict(legacy_dispatch=dict(type='choice',
        instructions='Does the evidence support the narrow claim that an unmarked provider delegates directly to the unchanged legacy reserved-memory initializer without creating a V2 executor?',
        criteria=dict(supported='The first branch directly returns the unchanged legacy initializer.',
                      contradicted='It instead runs V2 initialization or changes the legacy initializer.',
                      not_established='The dispatch branch or function comparison does not establish the call path.'))))
(here / 'jev-legacy.json').write_text(json.dumps(request, indent=2) + '\n')
print(json.dumps(dict(passed=True, exact_unchanged_functions=same)))
