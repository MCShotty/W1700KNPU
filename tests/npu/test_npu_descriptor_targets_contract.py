"""Synthetic controls for joint descriptor table and literal target qualification."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import unittest

from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import UC_PROT_READ, UC_PROT_EXEC
from unicorn import riscv_const as registers

import test_npu_descriptor_targets as targets
from test_npu_switch_targets import inspect_function as table_only

FIXTURE_PATH = Path(__file__).with_name('descriptor_target_fixtures.json')
FIXTURE_SHA256 = '7898064f2d38b7f995c5a6f97c377fc744125a23680d16ee6d1e6c0d4a9bc70a'
assert hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest() == FIXTURE_SHA256
FIXTURES = json.loads(FIXTURE_PATH.read_bytes())
assert FIXTURES['format'] == 'synthetic-rv32-descriptor-target-fixtures-v1'
assert FIXTURES['synthetic_only'] is FIXTURES['no_router_firmware_bytes'] is True
assert len(FIXTURES['programs']) == 15
GUEST_EVIDENCE = []


def inspect(name,known=(0x30040,0x40040),table_data=None):
    fixture = FIXTURES['programs'][name]
    raw = bytes.fromhex(fixture['table_hex']) if table_data is None else table_data
    def read(address,count):
        offset = address-fixture['table_address']
        assert offset >= 0 and offset+4*count <= len(raw), 'unavailable-table'
        return raw[offset:offset+4*count]
    return targets.inspect_function(bytes.fromhex(fixture['program_hex']),FIXTURES['address'],read,set(known))


def graph_state():
    def edge(pc,target=None):
        return dict(address=pc,target=target,caller_CFA=48,kind='unresolved-register-transfer' if target is None else 'direct-call')
    functions = {0x1000:dict(address=0x1000,bytes=64,frame=48,name='descriptor',component='unit',
        transfers=[edge(0x1004),edge(0x1008),edge(0x100c),edge(0x1010),edge(0x1014,0x9000),edge(0x1018,0x2000)])}
    for address in (0x2000,0x3000):
        functions[address] = dict(address=address,bytes=16,frame=16,name='callee'+str(address),
            component='original-reviewed-body',transfers=[])
    table = dict(caller=0x1000,address=0x1004,caller_name='descriptor',component='unit',caller_CFA=48,
        control_flow_qualified=True,same_function_only=True,guard_safe_edge_dominates_load_and_jump=True,
        target_CFA_matches_dispatch=True,interfunction_edge=False,entry_count=2,
        table_targets=[0x101c,0x101e],default_target=0x1020)
    literals = [dict(caller=0x1000,address=pc,caller_name='descriptor',component='unit',caller_CFA=48,
        control_flow_qualified=True,qualified_with_internal_tables=True,kind='literal-register-call',
        target=target,target_frame=16) for pc,target in ((0x1008,0x2000),(0x100c,0x3000))]
    return functions,[table],literals


class DescriptorTargetsContracts(unittest.TestCase):
    def test_independent_setup_and_base_destination_add_are_recognized(self):
        result = inspect('setup')
        self.assertEqual(result['literals'],[])
        row = result['tables'][0]
        self.assertTrue(row['control_flow_qualified'])
        self.assertEqual((row['table_address'],row['entry_count'],row['target_register']),(0x20040,4,'s1'))
        self.assertEqual(row['pattern'],'bounded-table-with-independent-setup-and-base-destination-add')

    def test_table_and_literal_calls_are_qualified_together(self):
        result = inspect('callback')
        self.assertEqual(len(result['tables']),1)
        self.assertEqual([row['target'] for row in result['literals']],[0x30040,0x40040])
        self.assertTrue(all(row['control_flow_qualified'] and row['qualified_with_internal_tables'] for row in result['literals']))
        fixture = FIXTURES['programs']['callback']
        with self.assertRaisesRegex(AssertionError,'other-unresolved-register-flow'):
            table_only(bytes.fromhex(fixture['program_hex']),0x10000,
                lambda address,count:bytes.fromhex(fixture['table_hex']))

    def test_no_unproved_literal_entry_is_admitted(self):
        for known in ((),(0x30040,),(0x40040,)):
            with self.subTest(known=known),self.assertRaisesRegex(AssertionError,'unproved-literal-target'):
                inspect('callback',known)

    def test_setup_dependencies_target_and_stack_cannot_be_clobbered(self):
        for name in ('setup_clobber_bound','setup_clobber_index','setup_clobber_target','setup_sp_clobber',
                     'setup_wrong_add','setup_wrong_load','setup_signed_guard'):
            with self.subTest(name=name),self.assertRaisesRegex(AssertionError,'no-recognized-table'):
                inspect(name)

    def test_guard_and_post_guard_setup_cannot_be_bypassed(self):
        for name in ('setup_bypass_guard','setup_bypass_zero'):
            with self.subTest(name=name),self.assertRaisesRegex(AssertionError,'prefix-can-bypass-definition'):
                inspect(name)

    def test_literal_addition_and_call_cannot_be_bypassed(self):
        for name,reason in (('callback_bypass_add','literal-addition-can-bypass-definition'),
                            ('callback_bypass_call','literal-call-can-bypass-addition')):
            with self.subTest(name=name),self.assertRaisesRegex(AssertionError,reason):
                inspect(name)

    def test_other_unknown_flow_or_wrong_literal_base_stays_rejected(self):
        for name in ('callback_other_unknown','callback_wrong_literal_base'):
            with self.subTest(name=name),self.assertRaisesRegex(AssertionError,'other-unresolved-register-flow'):
                inspect(name)

    def test_table_cannot_enter_a_literal_sequence_interior(self):
        fixture = FIXTURES['programs']['callback']
        raw = bytes.fromhex(fixture['table_hex'])
        changed = struct.pack('<I',fixture['labels']['literal_add'])+raw[4:]
        with self.assertRaisesRegex(AssertionError,'literal-addition-can-bypass-definition'):
            inspect('callback',table_data=changed)

    def test_noninternal_table_targets_and_short_data_fail_closed(self):
        fixture = FIXTURES['programs']['setup']
        raw = bytes.fromhex(fixture['table_hex'])
        for target in (0x10000,0x10001,0x30000):
            with self.subTest(target=target),self.assertRaisesRegex(AssertionError,'noninternal-table-target'):
                inspect('setup',table_data=struct.pack('<I',target)+raw[4:])
        with self.assertRaisesRegex(AssertionError,'unavailable-table'):
            inspect('setup',table_data=raw[:-4])

    def test_composes_calls_only_to_existing_proved_nodes_without_mutation(self):
        functions,tables,literals = graph_state()
        before = deepcopy((functions,tables,literals))
        result = targets.integrate(functions,tables,literals)
        self.assertEqual((functions,tables,literals),before)
        self.assertEqual(set(result['functions']),set(functions))
        self.assertEqual((result['resolved_transfers'],result['qualified_literal_calls']),(3,2))
        self.assertEqual([(row['address'],row['target']) for row in result['unresolved_transfers']],
                         [(0x1010,None),(0x1014,0x9000)])
        self.assertEqual(result['ranked_subset_candidates'][0]['bytes'],64)

    def test_original_frame_component_and_size_must_match(self):
        for field,value in (('component','unproved'),('frame',32)):
            with self.subTest(field=field):
                functions,tables,literals = graph_state()
                functions[0x2000][field] = value
                with self.assertRaises(AssertionError): targets.integrate(functions,tables,literals)

    def test_missing_target_cannot_invent_a_callee(self):
        functions,tables,literals = graph_state()
        literals[0]['target'] = 0x4000
        with self.assertRaises(AssertionError): targets.integrate(functions,tables,literals)

    def test_literal_flags_kind_and_CFA_are_required(self):
        for key,value in (('control_flow_qualified',False),('qualified_with_internal_tables',False),
            ('kind','literal-register-tail'),('caller_CFA',16),('caller_CFA',True),('target_frame',32)):
            with self.subTest(key=key):
                functions,tables,literals = graph_state()
                literals[0][key] = value
                with self.assertRaises(AssertionError): targets.integrate(functions,tables,literals)

    def test_duplicate_or_already_known_literal_sites_are_rejected(self):
        for mode in ('duplicate','known'):
            with self.subTest(mode=mode):
                functions,tables,literals = graph_state()
                if mode == 'duplicate': literals.append(deepcopy(literals[0]))
                else: functions[0x1000]['transfers'][1]['target'] = 0x2000
                with self.assertRaises(AssertionError): targets.integrate(functions,tables,literals)

    def test_callsite_identity_cannot_drift(self):
        for key,value in (('caller_name','wrong'),('component','wrong'),('address',0x1024)):
            with self.subTest(key=key):
                functions,tables,literals = graph_state()
                literals[0][key] = value
                with self.assertRaises(AssertionError): targets.integrate(functions,tables,literals)

    def test_existing_cycle_is_not_given_a_finite_candidate(self):
        functions,tables,literals = graph_state()
        functions[0x2000]['transfers'] = [dict(address=0x2004,target=0x1000,caller_CFA=16,kind='direct-call')]
        result = targets.integrate(functions,tables,literals)
        self.assertTrue(result['cycles'])
        self.assertEqual([row['root'] for row in result['ranked_subset_candidates']],[0x3000])

    def test_synthetic_guests_observe_reordered_tables_and_literal_links(self):
        ids = [getattr(registers,'UC_RISCV_REG_X'+str(index)) for index in range(32)]
        for name in ('setup','callback'):
            fixture = FIXTURES['programs'][name]
            result = inspect(name)
            table_row = result['tables'][0]
            specs = [('table',index) for index in (0,3,4,0xffffffff)]
            specs += [('literal',index) for index in range(len(result['literals']))]
            for kind,index in specs:
                with self.subTest(name=name,kind=kind,index=index):
                    code,raw = bytes.fromhex(fixture['program_hex']),bytes.fromhex(fixture['table_hex'])
                    cpu = Uc(UC_ARCH_RISCV,UC_MODE_RISCV32)
                    for address in (0x10000,0x20000,0x30000,0x40000):
                        cpu.mem_map(address,4096)
                    cpu.mem_write(0x10000,code)
                    cpu.mem_write(0x20040,raw)
                    cpu.mem_protect(0x10000,4096,UC_PROT_READ|UC_PROT_EXEC)
                    cpu.mem_protect(0x20000,4096,UC_PROT_READ)
                    for number,register in enumerate(ids[1:],1):
                        cpu.reg_write(register,0xa0000000+number)
                    cpu.reg_write(registers.UC_RISCV_REG_SP,0x50000)
                    source = 13 if name == 'setup' else 10
                    cpu.reg_write(ids[source],index)
                    expected = [cpu.reg_read(register) for register in ids]
                    reads,writes = [],[]
                    if kind == 'table':
                        allowed = index < table_row['entry_count']
                        start = table_row['definition_start']
                        target = table_row['table_targets'][index] if allowed else table_row['default_target']
                        if name == 'setup':
                            expected[15],expected[18] = 3,0x600
                            if allowed:
                                for register,value in {16:0,20:0,9:target,8:0x20040+4*index,21:1,19:index}.items():
                                    expected[register] = value
                        else:
                            expected[11] = target if allowed else 3
                            if allowed: expected[12] = 0x20040
                        wanted_reads = [(0x20040+4*index,4)] if allowed else []
                    else:
                        row = result['literals'][index]
                        start,target = row['definition_start'],row['target']
                        expected[11],expected[1] = target,row['address']+2
                        wanted_reads = []
                    def read(engine,access,address,width,value,unused):
                        reads.append((address,width))
                    def written(engine,access,address,width,value,unused):
                        writes.append((address,width,value))
                    cpu.hook_add(UC_HOOK_MEM_READ,read)
                    cpu.hook_add(UC_HOOK_MEM_WRITE,written)
                    cpu.emu_start(start,target,count=50)
                    actual = [cpu.reg_read(register) for register in ids]
                    self.assertEqual(cpu.reg_read(registers.UC_RISCV_REG_PC),target)
                    self.assertEqual(actual,expected)
                    self.assertEqual((reads,writes),(wanted_reads,[]))
                    self.assertEqual(bytes(cpu.mem_read(0x10000,len(code))),code)
                    self.assertEqual(bytes(cpu.mem_read(0x20040,len(raw))),raw)
                    GUEST_EVIDENCE.append(dict(fixture=name,kind=kind,index=index,start=start,PC=target,
                        RA=actual[1],SP=actual[2],reads=reads,writes=writes,
                        registers_sha256=hashlib.sha256(struct.pack('<32I',*actual)).hexdigest(),
                        program_sha256=hashlib.sha256(code).hexdigest(),observed_before_restoration=True,
                        synthetic_program_only=True,router_firmware_executed=False))


if __name__ == '__main__':
    unittest.main()
