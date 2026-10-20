"""Synthetic route/solver contracts,not hardware exception delivery."""
import unittest
from unittest.mock import Mock, patch

import z3
from test_original_trap_routing import IRQ, UNKNOWN, PrefixFixture, prefix_contract, route, routing_lemmas


class OriginalTrapRoutingContracts(unittest.TestCase):
    def test_only_exact_machine_external_interrupt_takes_IRQ_route(self):
        for cause in (*range(32),*(0x80000000+value for value in range(32)),0xffffffff):
            with self.subTest(cause=cause):
                self.assertEqual(route(cause),IRQ if cause == 0x8000000b else UNKNOWN)

    def test_environment_calls_are_not_machine_external_interrupts(self):
        for cause in (8,9,11):
            self.assertEqual(route(cause),UNKNOWN)
            self.assertEqual(route(cause|0x80000000),IRQ if cause == 11 else UNKNOWN)

    def test_non_RV32_inputs_are_not_silently_normalized(self):
        for cause in (-1,1<<32,False,11.0):
            with self.subTest(cause=cause), self.assertRaises(AssertionError):
                route(cause)

    def test_quantified_branch_predicate_and_missing_sign_bit_control(self):
        records = routing_lemmas()
        self.assertEqual([row['result'] for row in records],['unsat','unsat','sat'])
        self.assertTrue(records[-1]['counterexample'])
        self.assertTrue(all(row['SMT2'] for row in records))

    def test_unknown_solver_result_does_not_qualify_the_route(self):
        solver = Mock()
        solver.check.return_value = z3.unknown
        with patch.object(z3,'Solver',return_value=solver), self.assertRaisesRegex(
                AssertionError,'routing-solver-did-not-establish-result'):
            routing_lemmas()
        solver.set.assert_called_once_with(timeout=10000)

    def test_invalid_prefix_inputs_reject_before_engine_access(self):
        fixture = object.__new__(PrefixFixture)
        for cause,syscall_id,vector in ((-1,0,False),(1<<32,0,False),(8,-1,True),
                (8,1<<32,True),(False,214,True),(11,0,1)):
            with self.subTest(cause=cause,syscall_id=syscall_id,vector=vector), self.assertRaises(AssertionError):
                fixture.run(cause,syscall_id,vector=vector)

    def test_an_arbitrary_decodable_prefix_is_not_accepted(self):
        with self.assertRaisesRegex(AssertionError,'trap-routing-prefix-drift'):
            prefix_contract(bytes.fromhex('0100')*20)


if __name__ == '__main__':
    unittest.main()
