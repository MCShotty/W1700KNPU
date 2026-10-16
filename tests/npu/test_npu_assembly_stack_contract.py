"""Synthetic assembly audit controls; no native stack acceptance."""
from copy import deepcopy
import unittest

from test_npu_assembly_stack_usage import ASSEMBLY_ONLY, WRAPPERS, check_contract, match_code, scan


def fixture():
    components = {name: {'SP_references': []} for name in ASSEMBLY_ONLY}
    components['order']['SP_references'] = [dict(kind='SP-based-memory', mnemonic='lhu', offset=6, register='a4')]
    components['egress']['SP_references'] = [dict(kind='SP-adjustment', delta=value) for value in (-16, -48)]
    components['egress']['SP_references'] += [dict(kind='SP-based-memory', mnemonic='sw', offset=index * 4,
        register=register) for index, register in enumerate(
            ('a0', 'a1', 'a2', 'a3', 'a4', 'a5', 'a6', 'a7', 'ra', 't1', 't4', 'zero'))]
    wrappers = {name: {'SP_references': []} for names in WRAPPERS.values() for name in names}
    return components, wrappers


class AssemblyStackContractTests(unittest.TestCase):
    def test_decoder_uses_structured_SP_and_memory_operands(self):
        result = scan(bytes.fromhex('130101ff2320a100'), 0x1000)
        self.assertEqual(result['instructions'], 2)
        self.assertEqual([(r['kind'], r.get('delta'), r.get('offset')) for r in result['SP_references']],
                         [('SP-adjustment', -16, None), ('SP-based-memory', None, 0)])

    def test_decoder_rejects_unknown_trailing_and_compressed_bytes(self):
        for data in (b'', bytes.fromhex('13000000ff'), bytes.fromhex('0100')):
            with self.assertRaises(AssertionError): scan(data, 0x1000)

    def test_exact_raw_bounds_and_bytes_are_required(self):
        match_code(b'AB', 0x1001, b'XABY', 0x1000)
        for address, data in ((0xfff, b'AB'), (0x1003, b'AB'), (0x1001, b'AC')):
            with self.assertRaises(AssertionError): match_code(data, address, b'XABY', 0x1000)

    def test_reviewed_layout_passes(self):
        check_contract(*fixture())

    def test_wrapper_SP_and_component_set_cannot_be_silently_ignored(self):
        for mutate in ('wrapper', 'component', 'bridge'):
            components, wrappers = fixture()
            if mutate == 'wrapper': next(iter(wrappers.values()))['SP_references'] = [{'kind': 'other-SP-reference'}]
            elif mutate == 'component': del components['reset']
            else: components['bridge']['SP_references'] = [{'kind': 'SP-adjustment', 'delta': -16}]
            with self.assertRaises(AssertionError): check_contract(components, wrappers)

    def test_exact_ring_read_and_egress_layout_are_required(self):
        for target, field, value in (('order', 'offset', 8), ('order', 'mnemonic', 'sw'),
                                     ('egress', 'delta', -64)):
            components, wrappers = deepcopy(fixture())
            components[target]['SP_references'][0][field] = value
            with self.assertRaises(AssertionError): check_contract(components, wrappers)
        components, wrappers = fixture()
        components['egress']['SP_references'].pop()
        with self.assertRaises(AssertionError): check_contract(components, wrappers)


if __name__ == '__main__': unittest.main()
