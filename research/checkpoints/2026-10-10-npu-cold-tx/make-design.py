from pathlib import Path
import json
import struct

root = Path('/home/captain/W1700KNPU')
here = root / '.local/npu-cold-tx-20261010'
dump = (root / 'research/checkpoints/2026-09-05-npu-admission/ghidra-mailbox/en7581_MT7996_npu_rv32.bin.txt').read_text()
def body(address):
    return dump.split(' @ ram:' + address + '\n', 1)[1].split('\nFUNCTION ', 1)[0].split('\nASSEMBLY', 1)[0]
code = (root / '.build/merged-openwrt/build_dir/target-aarch64_cortex-a53_musl/linux-firmware-20260910/airoha/en7581_MT7996_npu_rv32.bin').read_bytes()
state = dict(tx_address=body('8400d5da'), tx_programming=body('8400d490'),
    token_limit=body('8400dfb0'), subregion_getter=body('8400fab2'),
    subregions=list(struct.iter_unpack('<2I', code[0x1cf18:0x1cf70])),
    contract='The existing cold epoch is held and authenticated by boot/nonce/sequence. Software ownership must precede original side effects and persist after ambiguous partial failure. Mutex ownership/readback, table geometry and modeled registers are not physical DMA exclusion/coherency/retirement evidence. No rollback/reset/reclaim API exists.',
    proposed_owner='Capture the unique existing type1 WLAN-arena reservation under original allocator lock18. Retain host metadata, shared-index and native-register write progress for both TX bands, plus the fixed token-limit publication, without clearing claims on failure. Original writes must pass per-write identity/order/value guards and readback. Use authenticated cold commands in the main raw setup regression; its later direct TXDONE lease remains explicitly modeled.')
questions = {
    'tx_effect_class': dict(type='choice', instructions='In tx_address and tx_programming, what kind of operation do selectors0/2 perform?', criteria=dict(metadata_and_native_programming='Store host metadata, reset shared indices and program native base registers.', metadata_only='Only store host metadata.', allocate_buffers='Allocate buffer IDs or new backing.', unknown='The supplied bodies do not establish the effect class.')),
    'token_effect_class': dict(type='choice', instructions='Classify token_limit by its shown side effects.', criteria=dict(metadata_publication='Store the supplied token limit in native shared state.', new_allocation='Allocate new token storage or dequeue tokens.', release='Retire existing token resources.', unknown='The supplied body does not establish the effect class.')),
    'getter_ownership': dict(type='noul', instructions='Does subregion_getter establish exclusive ownership or allocate backing by itself, according to its body and contract?'),
    'partial_failure_policy': dict(type='choice', instructions='Under contract, after an original native-register store becomes visible and a later guard fails, which policy should proposed_owner follow?', criteria=dict(retain_and_deny='Latch fault, retain reservation/progress/outer lease and deny outer success.', rollback='Restore preimages and reset ownership.', release='Release the resource when the CPU callback returns.', unknown='The contract does not establish the policy.')),
    'readback_physical_claim': dict(type='noul', instructions='Would successful modeled register readback alone prove physical DMA exclusion, delivery, coherency or retirement under contract?'),
    'source_value_class': dict(type='choice', instructions='In tx_programming, where do the values written to native base registers come from?', criteria=dict(local_arena_subregions='Original subregion lookups within the existing WLAN arena plus fixed offsets, masked into the native address namespace.', host_bar_argument='Directly from the supplied host BAR address argument.', fresh_dma_allocation='From a new DMA allocation made in this routine.', unknown='The source does not establish the provenance.')),
}
path = here / 'jev-design.json'
assert not path.exists()
path.write_text(json.dumps(dict(model='jev-1.13.0', state=state, questions=questions), indent=2) + '\n')
(here / 'original-token-body.txt').write_text(body('8400dfb0') + '\n')
print('Prepared six bounded effect/provenance/retention judgments.')
