"""Synthetic controls for classifying internal jumps without invented callees."""
from copy import deepcopy
import unittest

from test_npu_internal_dispatch_subset import integrate


def edge(address,target=None):
    return dict(address=address,target=target,caller_CFA=16,kind='unresolved-register-transfer' if target is None else 'direct-call')


def state():
    functions = {0x100:dict(address=0x100,bytes=32,frame=16,name='synthetic',component='unit',
                            transfers=[edge(0x104),edge(0x108,0x200),edge(0x10c),edge(0x110,0x900)]),
                 0x200:dict(address=0x200,bytes=16,frame=32,name='callee',component='unit',transfers=[])}
    site = dict(caller=0x100,address=0x104,caller_name='synthetic',component='unit',caller_CFA=16,
        control_flow_qualified=True,same_function_only=True,guard_safe_edge_dominates_load_and_jump=True,
        target_CFA_matches_dispatch=True,interfunction_edge=False,entry_count=3,
        table_targets=[0x114,0x116,0x114],default_target=0x118)
    return functions,[site]


class InternalDispatchContracts(unittest.TestCase):
    def test_removes_only_internal_unknown_without_mutating_inputs(self):
        functions,sites = state()
        before = deepcopy((functions,sites))
        result = integrate(functions,sites)
        self.assertEqual((functions,sites),before)
        self.assertEqual(result['resolved_transfers'],1)
        self.assertEqual(result['qualified_internal_dispatches'],1)
        self.assertEqual([(row['address'],row['target']) for row in result['unresolved_transfers']],
                         [(0x10c,None),(0x110,0x900)])
        self.assertEqual(result['functions'][0x100]['internal_dispatches'],sites)
        self.assertEqual(result['ranked_subset_candidates'][0]['bytes'],48)

    def test_requires_each_independent_proof_flag(self):
        for key in ('control_flow_qualified','same_function_only','guard_safe_edge_dominates_load_and_jump','target_CFA_matches_dispatch'):
            with self.subTest(key=key):
                functions,sites = state()
                sites[0][key] = False
                with self.assertRaises(AssertionError): integrate(functions,sites)

    def test_does_not_accept_a_call_as_internal(self):
        functions,sites = state()
        sites[0]['interfunction_edge'] = True
        with self.assertRaises(AssertionError): integrate(functions,sites)

    def test_rejects_external_odd_entry_and_boolean_targets(self):
        for value in (0x100,0x101,0x120,0x200,True):
            with self.subTest(value=value):
                functions,sites = state()
                sites[0]['table_targets'][0] = value
                with self.assertRaises(AssertionError): integrate(functions,sites)

    def test_default_must_be_internal_too(self):
        functions,sites = state()
        sites[0]['default_target'] = 0x900
        with self.assertRaises(AssertionError): integrate(functions,sites)

    def test_rejects_missing_or_duplicate_site(self):
        for mode in ('missing','duplicate'):
            with self.subTest(mode=mode):
                functions,sites = state()
                if mode == 'missing': sites[0]['address'] = 0x11c
                else: sites.append(deepcopy(sites[0]))
                with self.assertRaises(AssertionError): integrate(functions,sites)

    def test_requires_exact_function_identity_and_CFA(self):
        for key,value in (('caller',0x200),('caller_name','wrong'),('component','wrong'),('caller_CFA',0),('caller_CFA',True)):
            with self.subTest(key=key):
                functions,sites = state()
                sites[0][key] = value
                with self.assertRaises(AssertionError): integrate(functions,sites)

    def test_cannot_replace_a_known_target(self):
        functions,sites = state()
        functions[0x100]['transfers'][0]['target'] = 0x200
        with self.assertRaises(AssertionError): integrate(functions,sites)

    def test_requires_original_register_transfer_kind(self):
        functions,sites = state()
        functions[0x100]['transfers'][0]['kind'] = 'other-unknown'
        with self.assertRaises(AssertionError): integrate(functions,sites)

    def test_entry_count_and_array_must_match(self):
        for value in (0,True,2,4):
            with self.subTest(value=value):
                functions,sites = state()
                sites[0]['entry_count'] = value
                with self.assertRaises(AssertionError): integrate(functions,sites)

    def test_multiple_sites_are_metadata_not_extra_graph_nodes(self):
        functions,sites = state()
        second = deepcopy(sites[0])
        second['address'] = 0x10c
        result = integrate(functions,[*sites,second])
        self.assertEqual(set(result['functions']),set(functions))
        self.assertEqual(result['resolved_transfers'],1)
        self.assertEqual(result['qualified_internal_dispatches'],2)

    def test_existing_interfunction_cycle_still_has_no_finite_candidate(self):
        functions,sites = state()
        functions[0x200]['transfers'] = [dict(address=0x204,target=0x100,caller_CFA=32,kind='direct-call')]
        result = integrate(functions,sites)
        self.assertTrue(result['cycles'])
        self.assertEqual(result['ranked_subset_candidates'],[])


if __name__ == '__main__':
    unittest.main()
