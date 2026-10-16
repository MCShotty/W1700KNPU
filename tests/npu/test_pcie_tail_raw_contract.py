"""Synthetic caller receipt contracts, never native execution evidence."""
import copy
import unittest

import raw_pair_retained as retained


class TailRawContractTests(unittest.TestCase):
    def fixture(self, tail=True, hif2=False):
        tx2 = 0x200d8450 if hif2 else 0x200d4450
        shape = [(0x10, 1, 1536), (0x12, 1, 1024), (0x15, 1, 256),
                 (0x16, 1, 512), (0x17, 1, 1024), (0x10, 19, 0x200d4420), (0x12, 19, tx2)]
        shape += [(0x30 | selector, 4, 0) for selector in (0, 2, 10, 11, 12, 8, 5, 7)]
        shape += [(0x10 | selector, 21, 0) for selector in (0, 5, 10, 2, 7, 12)]
        shape += [(0x1a, 1, 512), (0x1a, 0, 0x200d4590)]
        cold = [dict(header=header, api=api, value=value,
                     packet_claims=3072 if header == 0x1a and api in (0, 1) else 2560,
                     page_claims=1792) for header, api, value in shape]
        cold.append(dict(actual_rx_event_sender=True, desc10_executed=True,
                         rx_pcie_executed=True, full_setup=False))
        if tail:
            events = [(0x8400ba0c, 0x3e902cf0, 4, 0x200d4580), (0x8400ba18, 0x200d4588, 4, 1535),
                (0x8400ba24, 0x3e903904, 4, tx2 + 0x110), (0x8400ba30, tx2 + 0x118, 4, 1023),
                (0x8400b9ae, 0x200d45a8, 4, 255), (0x8400b9c0, 0x200d45b8, 4, 511),
                (0x8400b9d2, 0x200d45c8, 4, 1023), (0x8400b9ea, 0x2000a048, 4, 1535),
                (0x8400ba00, 0x200d4598, 4, 511)]
            for stage, (header, value) in enumerate(((0x10, 0x200d4580), (0x12, tx2 + 0x110), (0x1f, 0))):
                count = 5 if stage == 2 else 2
                spans = (*retained.SPACES, *((base, 4096) for base in retained.MODEL_BAR_PAGES))
                trace = dict(validated=True, actual_stores=count, expected_stores=count,
                    stores=[list(event) for event in events[stage * 2:stage * 2 + count]],
                    ordered_lock_writes=[[0x1ec031c8, 4, 0x40], [0x1ec03248, 4, 0]],
                    guest_writes_by_observer=False, protected_bytes=868352,
                    protected_memory=[dict(base=hex(base), bytes=size, differing_bytes=0) for base, size in spans])
                cold.append(dict(header=header, api=0, value=value, packet_claims=3072, page_claims=1792,
                    pcie_tail_stage=stage, pcie_tail_original_store_trace=trace,
                    reply=dict(reply=dict(flags=7, words=[0] * 20))))
            cold.append(dict(header=0x12, api=2, value=0, error=-22, actual_legacy_provider_framing=True,
                native_legacy_denial=True, protected_memory_unchanged=True, full_setup=False,
                reply=dict(request=[0x12, 2, 0, 0, 0, 0], reply=dict(flags=3, callbacks=[]))))
            cold.append(dict(actual_pcie_tail_sender=True, pcie_tail_stages=3, pcie_tail_original_stores=9,
                             native_inode_legacy_denial=True, inode_api=2, full_setup=False))
        native = dict(passed=True, actual_c_linux_setup=True, actual_c_txrx_sender=True,
            synthetic_plan_identity_writes=False, post_load_elf_injection=False, cold=cold,
            pcie_tail_requested=tail, workers=[{} for _ in range(7)],
            strict_denials=[dict(flags=3, callbacks=[]) for _ in range(3)])
        return dict(passed=True, native=native, native_enrollment_records=15, rx_event_bytes=8192)

    def test_legacy_prefix_still_requires_RX_PCIE_as_its_final_command(self):
        caller = self.fixture(tail=False)
        self.assertIs(retained.caller_contract(caller), caller['native'])
        caller['native']['cold'].append(dict(header=0x10, api=0, value=0, packet_claims=3072, page_claims=1792))
        with self.assertRaisesRegex(AssertionError, 'unexpected-command-after-RX-PCIE'):
            retained.caller_contract(caller)

    def test_tail_both_profiles_accept_real_boundary_without_fabricated_claim_fields(self):
        for hif2 in (False, True):
            caller = self.fixture(hif2=hif2)
            self.assertNotIn('packet_claims', caller['native']['cold'][-2])
            self.assertIs(retained.caller_contract(caller, inode_api=2), caller['native'])

    def test_missing_or_wrong_independently_bound_INODE_enum_is_rejected(self):
        for api in (None, 3):
            with self.assertRaises(AssertionError):
                retained.caller_contract(self.fixture(), inode_api=api)

    def test_tail_does_not_waive_old_full_prefix_requirements(self):
        for change in range(5):
            caller = self.fixture()
            if change == 0: caller['native_enrollment_records'] = 14
            if change == 1: caller['rx_event_bytes'] = 0
            if change == 2: caller['native']['cold'][0]['value'] = 32
            if change == 3: caller['native']['cold'][22]['packet_claims'] = 2560
            if change == 4: caller['native']['cold'][23]['rx_pcie_executed'] = False
            with self.assertRaises(AssertionError):
                retained.caller_contract(caller, inode_api=2)

    def test_each_tail_stage_requires_exact_native_store_and_memory_proof(self):
        for stage in range(3):
            for change in range(11):
                caller = self.fixture(hif2=True)
                row = caller['native']['cold'][24 + stage]
                trace = row['pcie_tail_original_store_trace']
                if change == 0: row['value'] ^= 4
                if change == 1: row['pcie_tail_stage'] = (stage + 1) % 3
                if change == 2: trace['validated'] = False
                if change == 3: trace['stores'][0][0] ^= 4
                if change == 4: trace['stores'][0][3] ^= 1
                if change == 5: trace['actual_stores'] -= 1
                if change == 6: trace['ordered_lock_writes'].reverse()
                if change == 7: trace['guest_writes_by_observer'] = True
                if change == 8: trace['protected_memory'][0]['differing_bytes'] = 1
                if change == 9: trace['protected_memory'][0]['base'] = '0xdead0000'
                if change == 10: row['reply']['reply']['words'][14] = 7
                with self.assertRaises(AssertionError, msg=f'stage {stage} change {change}'):
                    retained.caller_contract(caller, inode_api=2)

    def test_boundary_must_be_actual_padded_rejection_without_callback_or_memory_effect(self):
        for change in range(8):
            caller = self.fixture()
            row = caller['native']['cold'][-2]
            if change == 0: row['error'] = 0
            if change == 1: row['actual_legacy_provider_framing'] = False
            if change == 2: row['native_legacy_denial'] = False
            if change == 3: row['protected_memory_unchanged'] = False
            if change == 4: row['full_setup'] = True
            if change == 5: row['reply']['request'] = [0x12, 2, 0]
            if change == 6: row['reply']['reply']['flags'] = 7
            if change == 7: row['reply']['reply']['callbacks'] = ['0x84000000']
            with self.assertRaises(AssertionError):
                retained.caller_contract(caller, inode_api=2)

    def test_missing_duplicate_or_success_relabelled_tail_summary_is_rejected(self):
        for change in range(4):
            caller = self.fixture()
            if change == 0: caller['native']['cold'].pop()
            if change == 1: caller['native']['cold'].append(copy.deepcopy(caller['native']['cold'][-1]))
            if change == 2: caller['native']['cold'][-1]['pcie_tail_original_stores'] = 8
            if change == 3: caller['native']['cold'][-1]['full_setup'] = True
            with self.assertRaises(AssertionError):
                retained.caller_contract(caller, inode_api=2)


if __name__ == '__main__': unittest.main()
