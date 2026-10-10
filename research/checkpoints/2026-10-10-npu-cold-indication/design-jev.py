from pathlib import Path
import json
import re
import struct

root = Path('/home/captain/W1700KNPU')
here = root / '.local/npu-cold-indication-20261010'
dump = (root / 'research/checkpoints/2026-09-05-npu-admission/ghidra-mailbox/en7581_MT7996_npu_rv32.bin.txt').read_text()
def body(address):
    text = dump.split(' @ ram:' + address + '\n', 1)[1].split('\nFUNCTION ', 1)[0]
    return text.split('\nASSEMBLY', 1)[0]
code = (root / '.build/merged-openwrt/build_dir/target-aarch64_cortex-a53_musl/linux-firmware-20260910/airoha/en7581_MT7996_npu_rv32.bin').read_bytes()
table = list(struct.iter_unpack('<2I', code[0x1cf18:0x1cf70]))
state = dict(indication_body=body('8400bae6'), dispatcher=body('8400dd82'),
    tx_initializer=body('8400d490'), arena_subregions=table,
    project_contract='The existing epoch1 cold callback checks bound nonce/identity/sequence, parked workers and no deferred IRQ/release/arm/drain. Any committed claim/write and software lease must remain retained after ambiguous late failure. No physical exclusion/coherency/drain is proven, and there is no retirement/reset API.',
    proposed_indication_owner='A one-shot private owner captures the existing allocator type1 WLAN-arena reservation and its type6 indication span. Preflight requires fresh zero records and exact geometry. Hooks reserve/record each original status-word write and deny false outer success after a partial or late failure, without clearing committed words or other packet/BA owners.')
questions = {
    'owner_kind': dict(type='choice', instructions='In indication_body, which resource is being initialized? Classify the shown writes, not the function name.', criteria=dict(indication_records='8-byte indication records have their status word ORed with0xe0000000; no buffer-ID pool is dequeued.', ba_pages='BA page IDs are dequeued and allocated.', packet_pool='Packet IDs are dequeued and allocated.', unknown='The supplied body does not establish a resource class.')),
    'geometry_not_ownership': dict(type='noul', instructions='Does a count bound alone establish the immutable indication span and its retained cold owner, according to project_contract and proposed_indication_owner?'),
    'failure_policy': dict(type='choice', instructions='Under project_contract, what should proposed_indication_owner do after an ambiguous failure following a committed indication write?', criteria=dict(retain_no_reset='Latch fault and retain committed words/reservation/lease; deny outer success without a reset or rollback API.', clear_restart='Clear the initialized prefix and restart.', free='Retire the arena when the CPU callback returns.', unknown='The contract does not establish a policy.')),
    'tx_side_effects': dict(type='choice', instructions='Does tx_initializer only store host-address metadata or also program native hardware base registers?', criteria=dict(base_register_writes='The shown body writes native1fc... base registers as part of TX initialization.', metadata_only='It only stores SRAM address metadata.', unknown='The shown body does not establish side effects.')),
    'separate_physical_claim': dict(type='noul', instructions='Would proposed_indication_owner by itself prove physical prior-user exclusion, DMA/cache coherency or retirement, when project_contract explicitly lacks those witnesses?')}
path = here / 'jev-design.json'
assert not path.exists()
path.write_text(json.dumps(dict(model='jev-1.13.0', state=state, questions=questions), indent=2) + '\n')
print('Prepared five bounded native ownership/side-effect judgments.')
