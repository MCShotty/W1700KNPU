from pathlib import Path
import hashlib
import json
import sys

root = Path('/home/captain/W1700KNPU')
here = root / '.local/npu-cold-tx-20261010'
sys.path.insert(0, str(root / 'tests/npu'))
import test_npu_firmware_loader as loader
dump_path = root / 'research/checkpoints/2026-09-05-npu-admission/ghidra-mailbox/en7581_MT7996_npu_rv32.bin.txt'
dump = dump_path.read_text()
def body(address):
    return dump.split(' @ ram:' + address + '\n', 1)[1].split('\nFUNCTION ', 1)[0].split('\nASSEMBLY', 1)[0]
source_path = root / '.local/merge-nonoc-20260923/mt76-merged/mt7996/npu.c'
source = source_path.read_text()
state = dict(callback=body('84010164'), helper=body('8400d836'),
    rx_caller=loader.extract.function(source, 'mt7996_npu_rxd_init'),
    tx_caller=loader.extract.function(source, 'mt7996_npu_txd_init'),
    scope='Static source classification only. No new GET transport, TX descriptor owner, physical backing, DMA visibility, drains or hardware acceptance is implemented by this review.')
questions = {
    'all_read_only': dict(type='noul', instructions='Does helper only read metadata and never write descriptor memory for every supported selector? Classify actual shown stores, not the GET name.'),
    'rx_effect': dict(type='choice', instructions='For selectors0/2/8/10/11/12 used by rx_caller, what does helper do?', criteria=dict(pointer_lookup='Read stored ring pointers and mask their value; no shown allocation or descriptor write for these selectors.', descriptor_initialize='Write descriptor status fields.', fresh_allocate='Allocate new backing.', unknown='Not established by the shown body.')),
    'tx_effect': dict(type='choice', instructions='For selectors5/7 used by tx_caller, what effect does helper have?', criteria=dict(descriptor_status_initialize='After reading a nonzero ring pointer, write status0x80000000 through its descriptor span before returning.', read_only='Only return an existing pointer.', retire='Reclaim the old ring.', unknown='Not established by the shown body.')),
    'fallback': dict(type='choice', instructions='When helper returns0, how does callback encode that outcome?', criteria=dict(success_sentinel='Store0x457 in the reply value and return1, so transport success alone does not establish a valid ring address.', error_status='Return a failure status without changing the reply value.', zero_pointer='Return success with a zero pointer.', unknown='Not established by the shown body.')),
}
path = here / 'jev-next-setup.json'
assert not path.exists()
path.write_text(json.dumps(dict(model='jev-1.13.0', state=state, questions=questions), indent=2) + '\n')
inputs = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
          for path in (dump_path, source_path, Path(__file__), Path(loader.extract.__file__))}
(here / 'next-setup-inputs.json').write_text(json.dumps(dict(inputs=inputs, static_only=True), indent=2) + '\n')
print('Prepared four selector-specific GET effect/fallback judgments.')
