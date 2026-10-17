"""Synthetic complete-caller receipt checks; no runtime qualification."""
from copy import deepcopy
import unittest

import raw_pair_retained as retained
import test_pcie_tail_raw_contract as tail
from inode_trace import original_events, END, STACK_TOPS


class InodeRawContractTests(unittest.TestCase):
    def fixture(self, hif2=False):
        caller = tail.TailRawContractTests().fixture(hif2=hif2)
        native = caller['native']
        native['inode_requested'] = True
        native['cold'] = native['cold'][:-2]
        spans = (*retained.SPACES, *((base, 4096) for base in retained.MODEL_BAR_PAGES))
        for stage in (0, 1):
            header = 0x12 if stage == 0 else 0x17
            request = [0x3f, 1, 0x3253434e, 2, 80, 1, 80 + stage, 3, 4, 1, 2, header, 24, *([0] * 7)]
            reply = request.copy()
            reply[2] = 0x3252434e
            saved, interrupt = list(range(14)), [0x800, 0x84004100]
            callback_saved = [value + 100 if index < 12 else value for index, value in enumerate(saved)]
            callback_return = dict(pc=0x84044d2a, saved=callback_saved.copy(),
                sp=STACK_TOPS[0] - 0x1100, mstatus=0, interrupt=interrupt.copy())
            trace = dict(stage=stage, validated=True, actual_stores=1030 if stage == 0 else 6,
                expected_stores=1030 if stage == 0 else 6, stores=[list(event) for event in original_events(stage)],
                ordered_lock_writes=[[0x1ec031c8, 4, 0x40], [0x1ec03248, 4, 0]],
                guest_writes_by_observer=False, abi_observed_before_context_restore=True,
                validation_is_separate=True, exact_owner_bytes=4372, exact_setup_bytes=412, code_private_bytes=0x200000,
                original_entries=['callback', 'wrapper', 'helper', 'release'],
                entry_saved_registers=saved, entry_interrupt_csrs=interrupt,
                callback_entry=dict(callback_return, pc=0x840f112c, return_pc=0x84044d2a,
                    saved=callback_saved.copy(), interrupt=interrupt.copy()),
                callback_returns=[callback_return],
                native_returns=[dict(pc=END, saved=saved.copy(), sp=STACK_TOPS[0] - 0x1000, mstatus=0, interrupt=interrupt.copy())],
                protected_bytes=868352, protected_memory=[dict(base=hex(base), bytes=size, differing_bytes=0) for base, size in spans])
            native['cold'].append(dict(header=header, api=24, value=0, packet_claims=3072, page_claims=1792,
                inode_stage=stage, inode_original_store_trace=trace,
                reply=dict(request=request, reply=dict(flags=7, words=reply, callbacks=['0x8400fc2c'],
                    returned_stack=hex(STACK_TOPS[0] - 0x1000)))))
        native['cold'].append(dict(actual_pcie_tail_sender=True, pcie_tail_stages=3, pcie_tail_original_stores=9,
            actual_inode_sender=True, native_inode_legacy_denial=False, inode_api=24,
            native_inode_stages=2, inode_original_stores=1036, full_setup=False))
        return caller

    def test_both_profiles_require_both_real_constructor_shapes(self):
        for hif2 in (False, True):
            caller = self.fixture(hif2)
            self.assertIs(retained.caller_contract(caller, inode_api=24), caller['native'])

    def test_each_constructor_requires_exact_store_memory_journal_and_ABI_scope(self):
        for stage in (0, 1):
            for fault in range(19):
                caller = self.fixture(True)
                row = caller['native']['cold'][-3 + stage]
                trace = row['inode_original_store_trace']
                if fault == 0: row['inode_stage'] ^= 1
                if fault == 1: trace['validated'] = False
                if fault == 2: trace['stores'][0][0] ^= 4
                if fault == 3: trace['stores'][0][3] ^= 1
                if fault == 4: trace['actual_stores'] -= 1
                if fault == 5: trace['ordered_lock_writes'].reverse()
                if fault == 6: trace['guest_writes_by_observer'] = True
                if fault == 7: trace['protected_memory'][0]['differing_bytes'] = 1
                if fault == 8: trace['protected_memory'][0]['base'] = '0xdead0000'
                if fault == 9: trace['exact_owner_bytes'] -= 4
                if fault == 10: trace['exact_setup_bytes'] = 404
                if fault == 11: trace['code_private_bytes'] = 0x100000
                if fault == 12: trace['abi_observed_before_context_restore'] = False
                if fault == 13: trace['native_returns'][0]['saved'][0] ^= 1
                if fault == 14: trace['native_returns'][0]['mstatus'] = 8
                if fault == 15: trace['original_entries'].pop()
                if fault == 16: row['reply']['reply']['words'][14] = 7
                if fault == 17: row['reply']['request'] = [row['header'], 24, 0, 0, 0, 0]
                if fault == 18: row['reply']['reply']['callbacks'] = []
                with self.subTest(stage=stage, fault=fault):
                    with self.assertRaises(AssertionError): retained.caller_contract(caller, inode_api=24)

    def test_second_constructor_must_advance_same_session_sequence(self):
        for index in (6, 7, 9):
            caller = self.fixture()
            row = caller['native']['cold'][-2]
            row['reply']['request'][index] ^= 1
            row['reply']['reply']['words'][index] ^= 1
            with self.assertRaises(AssertionError): retained.caller_contract(caller, inode_api=24)

    def test_callback_return_proof_is_independent_and_mandatory(self):
        for stage in (0, 1):
            for fault in range(9):
                caller = self.fixture()
                trace = caller['native']['cold'][-3 + stage]['inode_original_store_trace']
                if fault == 0: trace.pop('callback_entry')
                if fault == 1: trace.pop('callback_returns')
                if fault == 2: trace['callback_returns'] = []
                if fault == 3: trace['callback_returns'] *= 2
                if fault == 4: trace['callback_returns'][0]['saved'][0] ^= 1
                if fault == 5: trace['callback_returns'][0]['sp'] += 16
                if fault == 6: trace['callback_returns'][0]['mstatus'] = 8
                if fault == 7: trace['callback_entry']['saved'][-1] ^= 1
                if fault == 8: trace['callback_returns'][0]['pc'] += 2
                with self.subTest(stage=stage, fault=fault):
                    with self.assertRaises(AssertionError): retained.caller_contract(caller, inode_api=24)

    def test_old_denial_or_partial_new_summary_cannot_be_promoted(self):
        for fault in range(8):
            caller = self.fixture()
            native, summary = caller['native'], caller['native']['cold'][-1]
            if fault == 0: native['cold'].pop(-2)
            if fault == 1: summary['actual_inode_sender'] = False
            if fault == 2: summary['native_inode_legacy_denial'] = True
            if fault == 3: summary['native_inode_stages'] = 1
            if fault == 4: summary['inode_original_stores'] = 1030
            if fault == 5: summary['full_setup'] = True
            if fault == 6: native['pcie_tail_requested'] = False
            if fault == 7: native['inode_requested'] = 'true'
            with self.assertRaises(AssertionError): retained.caller_contract(caller, inode_api=24)

    def test_existing_full_prefix_and_all_three_tail_stages_stay_mandatory(self):
        for index in (0, 21, 24, 25, 26):
            caller = self.fixture()
            caller['native']['cold'].pop(index)
            with self.assertRaises(AssertionError): retained.caller_contract(caller, inode_api=24)


if __name__ == '__main__': unittest.main()
