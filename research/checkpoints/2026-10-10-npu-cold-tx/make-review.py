from pathlib import Path
import json
import re
import sys

root = Path('/home/captain/W1700KNPU')
here = root / '.local/npu-cold-tx-20261010'
sys.path.insert(0, str(root / 'tests/npu'))
import test_npu_firmware_loader as loader

core = (root / 'firmware/npu/cold-tx.c').read_text()
native = (root / 'tests/npu/cold-tx-native-emulation.c').read_text()
assembly = (root / 'tests/npu/cold-tx-native-emulation.S').read_text()
def function(source, name):
    adapted = re.sub(r'\buint32_t\b', 'u32     ', source)
    body = loader.extract.function(adapted, name)
    start = adapted.index(body)
    return source[start:start + len(body)]
state = dict(
    reserve=dict(native=function(native, 'npu_emulation_tx_reserve'),
                 core=function(core, 'npu_cold_tx_reserve'),
                 assembly=assembly[assembly.index('    .macro field'):assembly.index('    field npu_emulation_tx_meta0')]),
    publish=dict(native=function(native, 'npu_emulation_tx_publish'),
                 core=function(core, 'npu_cold_tx_publish')),
    retained=dict(core_fault=function(core, 'npu_cold_tx_fault'),
                  native_fault=function(native, 'fail'),
                  callback=function(native, 'callback'),
                  api=(root / 'firmware/npu/cold-tx.h').read_text()),
    requirements='Reserve before original stores, publish only after readback under pinned ownership, retain all partial progress and outer lease after failure; no reset or retirement. Register preimages are captured values, not assumed zero. Only modeled execution is tested; physical ownership/coherency/drains remain open.',
)
questions = {
    'reserve_before_store': dict(type='noul', instructions='Does reserve.assembly call reserve.native/core successfully before its original field store? Do not infer physical exclusivity from software ownership.'),
    'readback_before_publish': dict(type='noul', instructions='Does publish.native read the allowed target and require pinned ownership, while publish.core checks the expected address/width/value before advancing published?'),
    'retained_failure': dict(type='choice', instructions='According to retained.callback and retained.native_fault/core_fault, what happens to partial progress on failure?', criteria=dict(retain_and_deny='Latch faults, keep partial TX counters/claims and deny callback success.', rollback='Restore original values and reset TX counters.', retire='Free/reclaim committed resources.', not_established='The supplied source does not establish the policy.')),
    'preimage_policy': dict(type='choice', instructions='In retained.callback, what precondition is used for native register preimages?', criteria=dict(captured='Capture the four existing native register values into the pinned plan.', forced_zero='Require those four registers to start at zero.', unvalidated='Do not capture or validate preimages.', unknown='Not established.')),
    'retirement_api': dict(type='noul', instructions='Does retained.api expose a function to reset/reinitialize a used owner or retire/reclaim its committed resources? Initial begin on fresh zero storage is not such a reset API.'),
    'physical_claim': dict(type='noul', instructions='Do requirements claim modeled readback or software pinned ownership establishes physical DMA exclusion, coherency or drain proof?'),
}
path = here / 'jev-review.json'
assert not path.exists()
path.write_text(json.dumps(dict(model='jev-1.13.0', state=state, questions=questions), indent=2) + '\n')
print('Prepared six source-grounded TX publication/retention judgments.')
