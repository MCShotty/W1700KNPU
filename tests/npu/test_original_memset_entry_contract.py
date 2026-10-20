"""Synthetic solver/layout contracts;actual bytes are qualified separately."""
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

import z3
import original_memset_entry as entry
from test_npu_direct_stack import decode
from test_original_memset_entry import loaded_solver_paths


class OriginalMemsetEntryContracts(unittest.TestCase):
    def test_five_lemmas_include_two_counterexample_controls(self):
        result = entry.bitvector_lemmas(0x840103aa)
        self.assertEqual([row['result'] for row in result['queries']],['unsat']*3+['sat']*2)
        self.assertTrue(all(row['SMT2'] for row in result['queries']))
        self.assertTrue(all(row['counterexample'] for row in result['queries'][3:]))

    def test_bitvectors_remain_valid_at_both_address_boundaries(self):
        for address in (0,(1<<32)-168):
            with self.subTest(address=address):
                self.assertEqual([row['result'] for row in entry.bitvector_lemmas(address)['queries']],
                                 ['unsat']*3+['sat']*2)

    def test_invalid_addresses_never_reach_solver(self):
        with patch.object(z3,'Solver') as solver:
            for address in (-2,1,(1<<32)-166,1<<32,False,2.0):
                with self.subTest(address=address), self.assertRaises(AssertionError):
                    entry.bitvector_lemmas(address)
            solver.assert_not_called()

    def test_solver_timeout_cannot_be_removed_or_raised(self):
        with patch.object(z3,'Solver') as solver:
            for timeout in (0,-1,10001,False,1.0):
                with self.subTest(timeout=timeout), self.assertRaisesRegex(AssertionError,'invalid-solver-timeout'):
                    entry.bitvector_lemmas(0,timeout)
            solver.assert_not_called()

    def test_unknown_result_fails_closed(self):
        solver = Mock()
        solver.check.return_value = z3.unknown
        with patch.object(z3,'Solver',return_value=solver), self.assertRaisesRegex(
                AssertionError,'solver-did-not-establish-required-result'):
            entry.bitvector_lemmas(0)
        solver.set.assert_called_once_with(timeout=10000)
        solver.model.assert_not_called()

    def test_wrong_solver_result_fails_closed_for_each_query(self):
        original = z3.Solver
        for index in range(5):
            number = 0
            def changed_solver():
                nonlocal number
                solver = original()
                selected = number == index
                number += 1
                if selected:
                    solver.check = lambda: z3.sat if index < 3 else z3.unsat
                return solver
            with self.subTest(query=index), patch.object(z3,'Solver',side_effect=changed_solver), self.assertRaisesRegex(
                    AssertionError,'solver-did-not-establish-required-result'):
                entry.bitvector_lemmas(0)

    def test_exact_carrier_extent_is_required_before_decode(self):
        with patch.object(entry,'decode') as decoder:
            for value in (b'',b'\0'*167,b'\0'*169,bytearray(168)):
                with self.subTest(type=type(value),length=len(value)), self.assertRaisesRegex(
                        AssertionError,'carrier-extent-drift'):
                    entry.inspect_entry(value)
            decoder.assert_not_called()

    def test_reviewed_template_keeps_the_two_distinct_link_forms(self):
        program = entry.expected_program()
        self.assertEqual(len(program),55)
        self.assertEqual(program[54],('jalr',(entry.r('zero'),entry.r('a3'),entry.imm(10))))
        self.assertEqual(program[150],('jalr',(entry.r('ra'),entry.r('a3'),entry.imm(-88))))
        self.assertEqual([program[58+4*index] for index in range(15)],
            [('sb',(entry.r('a1'),entry.memory('a4',14-index))) for index in range(15)])
        self.assertEqual(program[118],('c.jr',(entry.r('ra'),)))

    def test_signature_uses_decoded_operands_not_printed_text(self):
        instruction = decode(bytes.fromhex('2320b500'),0)[0]
        self.assertEqual(entry.signature(instruction),('sw',(entry.r('a1'),entry.memory('a0',0))))
        instruction = decode(bytes.fromhex('8280'),0)[0]
        self.assertEqual(entry.signature(instruction),('c.jr',(entry.r('ra'),)))

    def test_solver_binding_is_observed_in_actual_process_maps(self):
        z3.get_full_version()
        paths = loaded_solver_paths()
        self.assertEqual(paths[0],Path(z3.__file__).resolve())
        self.assertEqual(len(paths),2)
        self.assertTrue(paths[1].name.startswith('libz3.so'))
        self.assertTrue(paths[1].is_file())

    def test_missing_or_multiple_native_libraries_fail_closed(self):
        for contents in ('','1000-2000 r-xp 0 0 0 /fake/libz3.so.5.3\n'):
            with self.subTest(contents=contents), patch.object(Path,'read_text',return_value=contents), self.assertRaises(
                    AssertionError):
                loaded_solver_paths()
        contents = '\n'.join('1000-2000 r-xp 0 0 0 /fake/'+name
                             for name in ('libz3.so.5.3','libz3.so.5.4'))
        with patch.object(Path,'read_text',return_value=contents), patch.object(Path,'is_file',return_value=True), self.assertRaisesRegex(
                AssertionError,'missing-or-multiple-mapped-solvers'):
            loaded_solver_paths()

    def test_optimized_python_cannot_disable_the_contract(self):
        path = Path(entry.__file__).parent
        environment = dict(os.environ)
        environment['PYTHONPATH'] = str(path)+os.pathsep+environment.get('PYTHONPATH','')
        run = subprocess.run([sys.executable,'-B','-O','-c','import original_memset_entry'],
            env=environment,capture_output=True,text=True,timeout=30)
        self.assertNotEqual(run.returncode,0)
        self.assertIn('original-entry-proof-requires-assertions',run.stderr)


if __name__ == '__main__':
    unittest.main()
