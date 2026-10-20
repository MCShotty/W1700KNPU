"""Independent semantic mutations must expose covered false acceptances."""
import ast
import inspect
import types
import unittest

import test_npu_relative_guardset_contract as contracts
import test_npu_switch_targets as targets


def mutated_function(function, operation):
    tree = ast.parse(inspect.getsource(function))
    count = operation(tree)
    assert count == 1, 'mutation-site-drift'
    namespace = dict(targets.__dict__)
    exec(compile(ast.fix_missing_locations(tree), '<synthetic-analyzer-mutation>', 'exec'), namespace)
    return namespace[function.__name__]


def inspect_with(function, name):
    namespace = dict(targets.__dict__)
    namespace[function.__name__] = function
    changed = types.FunctionType(targets.inspect_function.__code__, namespace)
    fixture = contracts.FIXTURES['programs'][name]
    return changed(bytes.fromhex(fixture['program_hex']), fixture['address'],
        contracts.reader(fixture), relative_guard_sets=True)


def omit_bound_check(tree):
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            for index, item in enumerate(node.body):
                if isinstance(item, ast.Assert) and isinstance(item.msg, ast.Constant) and item.msg.value == 'guard-bound-not-proved-constant':
                    node.body[index] = ast.Pass()
                    count += 1
    return count


def accept_signed_guard(tree):
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == 'bgeu':
            node.value = 'bge'
            count += 1
    return count


def omit_call_clobber(tree):
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            for index, item in enumerate(node.body):
                if (isinstance(item, ast.Assign) and isinstance(item.value, ast.Call)
                        and isinstance(item.value.func, ast.Name) and item.value.func.id == 'local_effect'):
                    addition = ast.parse("if edges[pc] is not None and 'call' in edges[pc]['kind']:\n    after = states[pc]\n").body[0]
                    node.body.insert(index+1, addition)
                    count += 1
                    break
    return count


class RelativeGuardSetMutationContracts(unittest.TestCase):
    def false_acceptance(self, function, operation, name):
        with self.assertRaises(AssertionError):
            contracts.inspect(name)
        changed = mutated_function(function, operation)
        self.assertTrue(inspect_with(changed, name)['tables'][0]['control_flow_qualified'])

    def test_omitting_bound_proof_exposes_a_changed_bound(self):
        self.false_acceptance(targets.relative_guard_set, omit_bound_check, 'bound_changed')
        self.false_acceptance(targets.relative_guard_set, omit_bound_check, 'changed_loop')

    def test_accepting_a_signed_alternate_exposes_the_wrong_guard(self):
        self.false_acceptance(targets.relative_guard_set, accept_signed_guard, 'signed_alternate')

    def test_preserving_caller_saved_values_exposes_the_call_clobber(self):
        self.false_acceptance(targets.reaching_constants, omit_call_clobber, 'call_clobbered')


if __name__ == '__main__':
    unittest.main()
