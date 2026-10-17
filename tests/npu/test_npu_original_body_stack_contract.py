"""Synthetic local-SP controls; no original firmware executes in these units."""
import hashlib
import json
from pathlib import Path
import unittest

from test_npu_original_body_stack import local_body

FIXTURE_PATH = Path(__file__).with_name('original_body_stack_fixtures.json')
FIXTURE_SHA256 = 'd2a79a6d81ef5b79a8534f3e06097698b0256bb0483e6a3a643bac496affd025'
assert hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest() == FIXTURE_SHA256
FIXTURES = json.loads(FIXTURE_PATH.read_bytes())['fixtures']


def inspect(name):
    row = FIXTURES['case_' + name]
    return local_body(bytes.fromhex(row['bytes_hex']), row['address'])


class OriginalBodyStackContractTests(unittest.TestCase):
    def reject(self, name):
        with self.assertRaises(AssertionError):
            inspect(name)

    def test_leaf_is_local_zero_not_a_whole_chain_bound(self):
        row = inspect('leaf')
        self.assertEqual(row['local_max_stack_bytes'], 0)
        self.assertFalse(row['complete_call_chain_bound_proven'])

    def test_balanced_frame_checks_both_stack_accesses(self):
        row = inspect('frame')
        self.assertEqual(row['local_max_stack_bytes'], 16)
        self.assertEqual([r['entry_SP_offset'] for r in row['stack_memory']], [-4, -4])

    def test_tail_keeps_unknown_child_cost_explicit(self):
        row = inspect('tail')
        self.assertEqual(row['local_max_stack_bytes'], 0)
        self.assertEqual(row['external_transfers'][0]['target'], 0x8000)
        self.assertFalse(row['external_transfers'][0]['child_frame_proved'])

    def test_tail_cannot_leave_its_frame_reserved(self): self.reject('tail_leak')
    def test_conflicting_SP_paths_do_not_join_to_a_guess(self): self.reject('merge')
    def test_loop_cannot_accumulate_stack(self): self.reject('growth')
    def test_dynamic_SP_write_is_not_a_constant_depth(self): self.reject('dynamic')
    def test_load_into_SP_is_not_a_known_frame(self): self.reject('load_sp')
    def test_unknown_indirect_tail_is_not_a_return(self): self.reject('indirect')
    def test_trap_is_not_ordinary_fallthrough(self): self.reject('trap')
    def test_stack_access_cannot_reach_caller_storage(self): self.reject('stack_overrun')
    def test_absolute_zero_SP_is_not_entry_relative_zero(self): self.reject('absolute_sp')
    def test_non_RA_link_is_not_an_ordinary_ABI_call(self): self.reject('wrong_link')

    def test_balanced_loop_does_not_claim_termination(self):
        row = inspect('balanced_loop')
        self.assertEqual(row['local_max_stack_bytes'], 16)
        self.assertFalse(row['termination_proved'])

    def test_call_records_current_depth_without_child_frame(self):
        row = inspect('call')
        self.assertEqual(row['local_max_stack_bytes'], 16)
        self.assertEqual([r['caller_CFA'] for r in row['external_transfers']], [16])
        self.assertFalse(row['child_frames_proved'])

    def test_CSR_cannot_replace_SP(self): self.reject('csr_sp')

    def test_incomplete_instruction_bytes_are_not_ignored(self):
        row = FIXTURES['case_leaf']
        with self.assertRaises(AssertionError):
            local_body(bytes.fromhex(row['bytes_hex']) + b'\xff', row['address'])

    def test_entry_must_be_aligned(self):
        with self.assertRaises(AssertionError):
            local_body(bytes.fromhex(FIXTURES['case_leaf']['bytes_hex']), 0x1001)

    def test_privileged_return_is_not_an_ordinary_return(self):
        with self.assertRaises(AssertionError):
            local_body(bytes.fromhex('73002030'), 0x1000)


if __name__ == '__main__':
    unittest.main()
