"""Check compiler-phase replay, immutable commands and unchanged outer inspections."""
import ast
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_rro_reset_modules as original
import test_rro_reset_phased_modules as phase


class PhaseControlTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.command = ['make', '-j1', 'fixture.o']
        self.environment = {key: 'fixture-'+key for key in phase.ENV_KEYS}
        self.environment['UNRELATED_CREDENTIAL'] = 'synthetic-do-not-persist'

    def request(self):
        with self.assertRaises(phase.PhaseYield):
            phase.phase_make(self.directory, self.command, 'provider', self.environment)

    def complete(self):
        (self.directory / 'provider.log').write_text('fixture compiler success\n')
        phase.complete_phase(self.directory, 0)

    def test_outer_inspections_unchanged(self):
        source = inspect.getsource(original.inner)
        before, after = ast.parse(source), phase.transform_inner(source)

        class Normalize(ast.NodeTransformer):
            def visit_FunctionDef(self, node):
                if node.name == 'make':
                    node.body = [ast.Pass()]
                    return node
                return self.generic_visit(node)

            def visit_With(self, node):
                value = node.items[0].context_expr
                if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and \
                        isinstance(value.func.value, ast.Name) and value.func.value.id == 'extra_path':
                    return ast.Pass()
                return self.generic_visit(node)

            def visit_Expr(self, node):
                if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and \
                        node.value.func.id == '_symvers_once':
                    return ast.Pass()
                return self.generic_visit(node)

        self.assertEqual(ast.dump(Normalize().visit(before)), ast.dump(Normalize().visit(after)))

    def test_request_yields_and_excludes_unrelated_environment(self):
        self.request()
        path = self.directory / 'phase-control/provider-command.json'
        record = json.loads(path.read_bytes())
        self.assertEqual(record['command'], self.command)
        self.assertEqual(set(record['environment']), set(phase.ENV_KEYS))
        self.assertNotIn('synthetic-do-not-persist', path.read_text())

    def test_changed_command_rejected(self):
        self.request()
        with self.assertRaises(AssertionError):
            phase.phase_make(self.directory, ['make', 'different.o'], 'provider', self.environment)

    def test_failed_phase_cannot_be_completed(self):
        self.request()
        with self.assertRaises(AssertionError):
            phase.complete_phase(self.directory, 1)
        self.assertFalse((self.directory / 'phase-control/provider-result.json').exists())

    def test_only_completed_exact_phase_is_replayed(self):
        self.request()
        self.complete()
        self.assertIsNone(phase.phase_make(self.directory, self.command, 'provider', self.environment))

    def test_pending_command_bytes_are_bound(self):
        self.request()
        (self.directory / 'phase-control/provider-command.json').write_text('{}\n')
        with self.assertRaises(AssertionError):
            phase.complete_phase(self.directory, 0)

    def test_completed_log_bytes_are_bound(self):
        self.request()
        self.complete()
        (self.directory / 'provider.log').write_text('changed\n')
        with self.assertRaises(AssertionError):
            phase.phase_make(self.directory, self.command, 'provider', self.environment)

    def test_dependency_table_idempotent(self):
        path = self.directory / 'dependencies.symvers'
        phase.symvers_once(path, 'fixture\n')
        before = phase.digest(path)
        phase.symvers_once(path, 'fixture\n')
        self.assertEqual(phase.digest(path), before)

    def test_dependency_table_drift_rejected(self):
        path = self.directory / 'dependencies.symvers'
        phase.symvers_once(path, 'fixture\n')
        with self.assertRaises(AssertionError):
            phase.symvers_once(path, 'different\n')
        self.assertEqual(path.read_text(), 'fixture\n')

    def test_total_compile_deadline_not_extended(self):
        self.request()
        clock = json.loads((self.directory / 'phase-control/clock.json').read_bytes())
        now = clock['start_monotonic_ns'] + clock['limit_ns'] + 1
        with patch.object(phase.time, 'monotonic_ns', return_value=now), \
             patch.object(phase.os, 'execvpe') as execute:
            with self.assertRaises(SystemExit) as stopped:
                phase.execute_phase(self.directory)
            self.assertEqual(stopped.exception.code, 124)
            execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
