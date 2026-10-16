"""Synthetic direct-call and cycle controls, not complete native stack proof."""
import unittest

from test_npu_direct_stack import candidates, decode, internal_transfer, transfer


def edge(target, cfa, address=0):
    return dict(target=target, caller_CFA=cfa, address=address)


class DirectStackContractTests(unittest.TestCase):
    def test_AUIPC_pair_resolves_actual_target_not_link_register(self):
        instructions = decode(bytes.fromhex('97000000e780c0f0'), 0x1000)
        self.assertEqual(transfer(instructions[1], instructions[0]),
                         dict(target=0xf0c, kind='AUIPC-direct-call'))

    def test_unrelated_previous_instruction_does_not_resolve_register_call(self):
        instructions = decode(bytes.fromhex('13000000e780c0f0'), 0x1000)
        self.assertIsNone(transfer(instructions[0], None))
        self.assertIsNone(transfer(instructions[1], instructions[0])['target'])

    def test_compressed_register_call_is_unknown_and_returns_are_not_edges(self):
        self.assertIsNone(transfer(decode(bytes.fromhex('8290'), 0)[0], None)['target'])
        for data in ('8280', '67800000'):
            self.assertIsNone(transfer(decode(bytes.fromhex(data), 0)[0], None))

    def test_jump_immediate_is_relative_to_its_own_address(self):
        self.assertEqual(transfer(decode(bytes.fromhex('6f004000'), 0x1000)[0], None),
                         dict(target=0x1004, kind='direct-tail'))

    def test_partial_decode_is_not_accepted(self):
        with self.assertRaises(AssertionError): decode(bytes.fromhex('13000000ff'), 0)

    def test_self_call_is_not_discarded_as_an_internal_jump(self):
        for target in (0x1000, 0x1004):
            self.assertFalse(internal_transfer(dict(target=target, kind='AUIPC-direct-call'), 0x1000, 16))
        self.assertTrue(internal_transfer(dict(target=0x1004, kind='direct-tail'), 0x1000, 16))
        self.assertFalse(internal_transfer(dict(target=0x1000, kind='direct-tail'), 0x1000, 16))

    def test_conditional_transfer_retains_out_of_function_target(self):
        instruction = decode(bytes.fromhex('63040000'), 0x1000)[0]
        result = transfer(instruction, None)
        self.assertEqual(result, dict(target=0x1008, kind='conditional-direct-transfer'))
        self.assertFalse(internal_transfer(result, 0x1000, 8))
        self.assertTrue(internal_transfer(result, 0x1000, 16))

    def test_callsite_CFA_not_unrelated_local_peak_is_added(self):
        functions = {1: dict(frame=64, transfers=[edge(2, 16, 10)]), 2: dict(frame=80, transfers=[])}
        result, cycles = candidates(functions)
        self.assertEqual(result[1], dict(bytes=96, chain=[1, 2], callsites=[10]))
        self.assertEqual(cycles, [])

    def test_tail_transfer_and_unknown_edges_do_not_invent_child_frames(self):
        functions = {1: dict(frame=64, transfers=[edge(2, 0), edge(None, 64)]),
                     2: dict(frame=80, transfers=[])}
        result, cycles = candidates(functions)
        self.assertEqual(result[1]['bytes'], 80)
        self.assertFalse(cycles)

    def test_cycle_and_callers_are_not_given_finite_candidates(self):
        functions = {1: dict(frame=16, transfers=[edge(2, 16)]),
                     2: dict(frame=16, transfers=[edge(3, 16)]),
                     3: dict(frame=16, transfers=[edge(2, 16)]), 4: dict(frame=32, transfers=[])}
        result, cycles = candidates(functions)
        self.assertEqual([result[i] for i in (1, 2, 3)], [None] * 3)
        self.assertTrue(cycles)
        self.assertEqual(result[4]['bytes'], 32)


if __name__ == '__main__': unittest.main()
