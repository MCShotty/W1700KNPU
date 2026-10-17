"""Synthetic graph composition controls;no guest firmware execution."""
from copy import deepcopy
import unittest

from test_npu_resolved_stack_subset import code_identity,integrate,validate_functions


def edge(pc,target=None,cfa=16,kind='unresolved-register-transfer'):
    return dict(address=pc,target=target,caller_CFA=cfa,kind=kind)


def node(address,frame=16,transfers=()):
    return dict(address=address,bytes=16,frame=frame,name='function_'+str(address),transfers=list(transfers))


def site(caller,pc,target,cfa=16,kind='literal-register-call'):
    return dict(caller=caller,address=pc,target=target,caller_CFA=cfa,kind=kind,
                caller_name='function_'+str(caller),control_flow_qualified=True)


class ResolvedSubsetContracts(unittest.TestCase):
    def test_single_CODE_identity_ignores_unrelated_source_hashes(self):
        graph = dict(inputs={'candidate/CODE.bin':'a'*64,'reproduction/CODE.bin':'a'*64,'source.py':'b'*64})
        self.assertEqual(code_identity(graph,dict(paired_CODE_sha256='a'*64),dict(mapped_CODE_sha256='a'*64)), 'a'*64)

    def test_mixed_missing_and_malformed_CODE_identities_fail(self):
        for mode in ('mixed-alias','missing','native','export','malformed'):
            with self.subTest(mode=mode):
                graph = dict(inputs={'candidate/CODE.bin':'a'*64,'reproduction/CODE.bin':'a'*64})
                native,export = dict(paired_CODE_sha256='a'*64),dict(mapped_CODE_sha256='a'*64)
                if mode == 'mixed-alias': graph['inputs']['reproduction/CODE.bin'] = 'b'*64
                elif mode == 'missing': graph['inputs'] = {}
                elif mode == 'native': native['paired_CODE_sha256'] = 'b'*64
                elif mode == 'export': export['mapped_CODE_sha256'] = 'b'*64
                else: graph['inputs'] = {'candidate/CODE.bin':True}
                with self.assertRaises(AssertionError): code_identity(graph,native,export)

    def base(self):
        return {0x100:node(0x100,32,[edge(0x104,cfa=32)])},[site(0x100,0x104,0x200,cfa=32)],{0x200:node(0x200,64)}

    def test_composes_known_target_without_mutating_prior_graph(self):
        old,sites,added = self.base()
        before = deepcopy((old,sites,added))
        result = integrate(old,sites,added)
        self.assertEqual(result['ranked_subset_candidates'][0]['bytes'],96)
        self.assertEqual(result['resolved_transfers'],1)
        self.assertEqual(result['unresolved_transfers'],[])
        self.assertEqual((old,sites,added),before)

    def test_uses_callsite_CFA_not_unrelated_local_peak(self):
        old = {0x100:node(0x100,64,[edge(0x104,cfa=16)])}
        result = integrate(old,[site(0x100,0x104,0x200)],{0x200:node(0x200,80)})
        self.assertEqual(result['ranked_subset_candidates'][0]['bytes'],96)

    def test_tail_with_zero_CFA_does_not_add_released_frame(self):
        old = {0x100:node(0x100,16,[edge(0x104,cfa=0)])}
        result = integrate(old,[site(0x100,0x104,0x200,0,'literal-register-tail')],{0x200:node(0x200,32)})
        self.assertEqual(result['ranked_subset_candidates'][0]['bytes'],32)

    def test_preserves_every_unselected_unknown(self):
        old,sites,added = self.base()
        old[0x100]['transfers'].extend([edge(0x108),edge(0x10c,0x900)])
        result = integrate(old,sites,added)
        self.assertEqual([(row['address'],row['target']) for row in result['unresolved_transfers']],
                         [(0x108,None),(0x10c,0x900)])

    def test_rejects_unqualified_and_duplicate_sites(self):
        for mode in ('unqualified','duplicate'):
            with self.subTest(mode=mode):
                old,sites,added = self.base()
                if mode == 'unqualified': sites[0]['control_flow_qualified'] = False
                else: sites.append(deepcopy(sites[0]))
                with self.assertRaises(AssertionError): integrate(old,sites,added)

    def test_requires_exact_caller_and_unknown_instruction(self):
        for key,value in (('caller',0x300),('caller_name','wrong'),('address',0x108)):
            with self.subTest(key=key):
                old,sites,added = self.base()
                sites[0][key] = value
                with self.assertRaises(AssertionError): integrate(old,sites,added)

    def test_rejects_CFA_drift_and_unproved_target(self):
        for key,value in (('caller_CFA',16),('target',0x900),('kind','direct-call')):
            with self.subTest(key=key):
                old,sites,added = self.base()
                sites[0][key] = value
                with self.assertRaises(AssertionError): integrate(old,sites,added)

    def test_does_not_replace_existing_resolved_edge(self):
        old,sites,added = self.base()
        old[0x100]['transfers'][0]['target'] = 0x200
        with self.assertRaises(AssertionError): integrate(old,sites,added)

    def test_rejects_colliding_or_overlapping_additions(self):
        for address in (0x100,0x108):
            with self.subTest(address=address):
                old,sites,added = self.base()
                added = {address:node(address)}
                sites[0]['target'] = address
                with self.assertRaises(AssertionError): integrate(old,sites,added)

    def test_rejects_invalid_frame_and_transfer_shapes(self):
        for frame in (-16,8,True):
            with self.subTest(frame=frame):
                with self.assertRaises(AssertionError): validate_functions({0x100:node(0x100,frame)})
        for changed in (edge(0x120),edge(0x104,cfa=32),edge(0x104,cfa=True)):
            with self.subTest(edge=changed):
                with self.assertRaises(AssertionError): validate_functions({0x100:node(0x100,16,[changed])})

    def test_rejects_duplicate_transfer_and_function_identity_drift(self):
        value = node(0x100,16,[edge(0x104),edge(0x104)])
        with self.assertRaises(AssertionError): validate_functions({0x100:value})
        value = node(0x100)
        value['address'] = 0x200
        with self.assertRaises(AssertionError): validate_functions({0x100:value})

    def test_added_callee_cannot_hide_unknown_transfer(self):
        old,sites,added = self.base()
        added[0x200]['transfers'] = [edge(0x204)]
        with self.assertRaises(AssertionError): integrate(old,sites,added)

    def test_cycles_have_no_finite_candidate(self):
        old,sites,added = self.base()
        added[0x200]['transfers'] = [edge(0x204,0x100)]
        result = integrate(old,sites,added)
        self.assertTrue(result['cycles'])
        self.assertEqual(result['ranked_subset_candidates'],[])

    def test_added_direct_leaf_and_literal_edge_are_separate_counts(self):
        old,sites,added = self.base()
        added[0x200]['transfers'] = [edge(0x204,0x300,16,'original-body-direct-call')]
        added[0x300] = node(0x300,0)
        result = integrate(old,sites,added)
        self.assertEqual(result['qualified_literal_sites'],1)
        self.assertEqual(result['resolved_transfers'],2)
        self.assertEqual(len(result['functions']),3)


if __name__ == '__main__':
    unittest.main()
